"""HTTP surface for the live project change stream and ephemeral presence.

Both are information only. They never change a snapshot, revision, review,
thread, or authority field, and nothing is gated on presence.
"""

from __future__ import annotations

import inspect
import json
import os
import threading
import time
import weakref
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Mapping

import anyio
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from .operator_identity import (
    OperatorRegistryError,
    OperatorTokenInvalid,
    resolve_operator,
)
from .project_events import diff_states, project_state
from .project_presence import (
    PresenceError,
    PresenceLimitError,
    PresenceValidationError,
    delete_presence,
    list_presence,
    put_presence,
)
from .project_store import InvalidProjectId, ProjectNotFound, ProjectStore, validate_project_id

_POLL_ENV = "HARDWARE_SPLICER_EVENT_POLL_SECONDS"
_KEEPALIVE_ENV = "HARDWARE_SPLICER_EVENT_KEEPALIVE_SECONDS"
_MAX_SECONDS_ENV = "HARDWARE_SPLICER_EVENT_MAX_SECONDS"
_MAX_STREAMS_ENV = "HARDWARE_SPLICER_EVENT_MAX_STREAMS"
_POLL_DEFAULT = 1.0
_KEEPALIVE_DEFAULT = 15.0
_MAX_SECONDS_DEFAULT = 1800.0
_MAX_SECONDS_MIN = 0.2
_MAX_STREAMS_DEFAULT = 50

_stream_lock = threading.Lock()
_stream_counts: dict[str, int] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_float(name: str, default: float, lo: float, hi: float) -> float:
    raw = os.environ.get(name)
    try:
        value = default if raw is None or str(raw).strip() == "" else float(raw)
    except (TypeError, ValueError):
        value = default
    return min(hi, max(lo, value))


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = os.environ.get(name)
    try:
        value = default if raw is None or str(raw).strip() == "" else int(raw)
    except (TypeError, ValueError):
        value = default
    return min(hi, max(lo, value))


def poll_seconds() -> float:
    return _env_float(_POLL_ENV, _POLL_DEFAULT, 0.05, 10.0)


def keepalive_seconds() -> float:
    return _env_float(_KEEPALIVE_ENV, _KEEPALIVE_DEFAULT, 0.05, 300.0)


def max_stream_seconds() -> float:
    return _env_float(_MAX_SECONDS_ENV, _MAX_SECONDS_DEFAULT, _MAX_SECONDS_MIN, 1800.0)


class TooManyProjectStreams(RuntimeError):
    """Raised when a project already has its live stream cap."""


def max_streams() -> int:
    return _env_int(_MAX_STREAMS_ENV, _MAX_STREAMS_DEFAULT, 1, 10_000)


def _sse(event: str, data: Mapping[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _keepalive_comment() -> str:
    return ": keepalive\n\n"


def _acquire_stream(key: str, limit: int) -> bool:
    with _stream_lock:
        current = _stream_counts.get(key, 0)
        if current >= limit:
            return False
        _stream_counts[key] = current + 1
        return True


def _release_stream(key: str) -> None:
    with _stream_lock:
        current = _stream_counts.get(key, 0)
        if current <= 1:
            _stream_counts.pop(key, None)
        else:
            _stream_counts[key] = current - 1


class SlotLease:
    """Idempotent per-project stream slot. Safe to release more than once."""

    def __init__(self, key: str, started_at: float) -> None:
        self.key = key
        self.started_at = started_at
        self._lock = threading.Lock()
        self._released = False

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._released = True
        _release_stream(self.key)


def acquire_slot_lease(
    store: ProjectStore,
    project_id: str,
    *,
    clock: Callable[[], float] | None = None,
) -> SlotLease:
    stream_key = stream_slot_key(store, project_id)
    if not _acquire_stream(stream_key, max_streams()):
        raise TooManyProjectStreams("too many live streams for this project")
    now = clock or time.monotonic
    return SlotLease(stream_key, float(now()))


def _operator_token(x_hs_operator_token: str | None) -> str | None:
    if x_hs_operator_token is not None and x_hs_operator_token != "":
        return x_hs_operator_token
    return None


def _events_error(exc: Exception) -> HTTPException:
    if isinstance(exc, OperatorTokenInvalid):
        return HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"type": "operator_token_invalid", "message": str(exc)},
        )
    if isinstance(exc, OperatorRegistryError):
        return HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "operator_registry_error", "message": str(exc)},
        )
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_identifier", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"type": "not_found", "message": str(exc)},
        )
    if isinstance(exc, PresenceLimitError):
        return HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"type": "too_many_presence", "message": str(exc)},
        )
    if isinstance(exc, PresenceValidationError):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, (ValueError, TypeError)):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, PresenceError):
        return HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "presence_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "project_events_error", "message": str(exc)},
    )


def _project_dir(store: ProjectStore, project_id: str) -> Path:
    safe_id = validate_project_id(project_id)
    path = store._project_dir(safe_id)
    if not path.is_dir():
        raise ProjectNotFound(safe_id)
    return path


def stream_slot_key(store: ProjectStore, project_id: str) -> str:
    return str(_project_dir(store, project_id))


def active_stream_count(store: ProjectStore, project_id: str) -> int:
    key = stream_slot_key(store, project_id)
    with _stream_lock:
        return int(_stream_counts.get(key, 0))


def reset_stream_counts() -> None:
    with _stream_lock:
        _stream_counts.clear()


async def _is_disconnected(is_disconnected: Callable[[], Any] | None) -> bool:
    if is_disconnected is None:
        return False
    result = is_disconnected()
    if inspect.isawaitable(result):
        return bool(await result)
    return bool(result)


async def event_frames(
    store: ProjectStore,
    project_id: str,
    is_disconnected: Callable[[], Any] | None = None,
    poll: float | None = None,
    keepalive: float | None = None,
    max_seconds: float | None = None,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    started_at: float | None = None,
) -> AsyncIterator[str]:
    """Yield SSE frames for a project. Ends on disconnect or ``max_seconds``."""

    project_dir = _project_dir(store, project_id)
    interval = poll_seconds() if poll is None else float(poll)
    keepalive_every = keepalive_seconds() if keepalive is None else float(keepalive)
    lifetime = max_stream_seconds() if max_seconds is None else float(max_seconds)
    now = clock or time.monotonic
    nap = sleep or anyio.sleep
    started = now() if started_at is None else float(started_at)
    deadline = started + lifetime

    state = await anyio.to_thread.run_sync(project_state, project_dir)
    yield _sse(
        "hello",
        {
            "project_id": project_id,
            "revision": int(state.get("revision") or 0),
            "thread_count": len(state.get("threads") or {}),
            "review_count": len(state.get("reviews") or {}),
            "server_time": _utc_now(),
            "poll_seconds": interval,
        },
    )
    last_emit = now()
    last_poll = started
    last_state = state
    while True:
        if await _is_disconnected(is_disconnected):
            return
        stamp = now()
        remaining = deadline - stamp
        if remaining <= 0:
            return
        next_poll = last_poll + interval
        next_keepalive = last_emit + keepalive_every
        wake_at = min(next_poll, next_keepalive, deadline)
        delay = min(wake_at - stamp, remaining)
        if delay > 0:
            await nap(delay)
        if await _is_disconnected(is_disconnected):
            return
        stamp = now()
        if stamp >= deadline:
            return
        if stamp >= next_poll:
            current = await anyio.to_thread.run_sync(project_state, project_dir)
            last_poll = stamp
            changes = diff_states(last_state, current)
            if changes:
                if now() >= deadline:
                    return
                yield _sse(
                    "change",
                    {"changes": changes, "server_time": _utc_now()},
                )
                last_state = current
                last_emit = now()
        if now() >= deadline:
            return
        if now() - last_emit >= keepalive_every:
            yield _keepalive_comment()
            last_emit = now()


class LeasedEventStream:
    """Async iterator that always releases ``lease``, even if never started."""

    def __init__(self, frames: AsyncIterator[str], lease: SlotLease) -> None:
        self.lease = lease
        self._frames = frames
        self._finalizer = weakref.finalize(self, SlotLease.release, lease)

    def __aiter__(self) -> LeasedEventStream:
        return self

    async def __anext__(self) -> str:
        return await self._frames.__anext__()

    async def aclose(self) -> None:
        try:
            closer = getattr(self._frames, "aclose", None)
            if closer is not None:
                await closer()
        finally:
            self.lease.release()


def start_project_event_stream(
    store: ProjectStore,
    project_id: str,
    *,
    is_disconnected: Callable[[], Any] | None = None,
    poll: float | None = None,
    keepalive: float | None = None,
    max_seconds: float | None = None,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> LeasedEventStream:
    """Acquire the per-project stream slot, then yield ``event_frames``.

    The slot is released by ``SlotLease.release`` from the generator
    ``finally``, ``aclose()``, a StreamingResponse ``BackgroundTask``, and a
    ``weakref.finalize`` fallback. Release is idempotent.
    """

    lease = acquire_slot_lease(store, project_id, clock=clock)

    async def generate() -> AsyncIterator[str]:
        try:
            async for frame in event_frames(
                store,
                project_id,
                is_disconnected=is_disconnected,
                poll=poll,
                keepalive=keepalive,
                max_seconds=max_seconds,
                clock=clock,
                sleep=sleep,
                started_at=lease.started_at,
            ):
                yield frame
        finally:
            lease.release()

    return LeasedEventStream(generate(), lease)


def build_event_stream_response(
    store: ProjectStore,
    project_id: str,
    *,
    is_disconnected: Callable[[], Any] | None = None,
    poll: float | None = None,
    keepalive: float | None = None,
    max_seconds: float | None = None,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> StreamingResponse:
    body = start_project_event_stream(
        store,
        project_id,
        is_disconnected=is_disconnected,
        poll=poll,
        keepalive=keepalive,
        max_seconds=max_seconds,
        clock=clock,
        sleep=sleep,
    )
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
        background=BackgroundTask(body.lease.release),
    )


def create_project_events_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects", tags=["project-events"])

    @router.get("/{project_id}/events")
    async def stream_project_events(project_id: str, request: Request) -> StreamingResponse:
        try:
            return build_event_stream_response(
                store,
                project_id,
                is_disconnected=request.is_disconnected,
            )
        except TooManyProjectStreams as exc:
            raise HTTPException(
                status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"type": "too_many_streams", "message": str(exc)},
            ) from exc
        except Exception as exc:
            raise _events_error(exc) from exc

    @router.post("/{project_id}/presence")
    def post_project_presence(
        project_id: str,
        request: Dict[str, Any],
        x_hs_operator_token: str | None = Header(default=None, alias="X-HS-Operator-Token"),
    ) -> Dict[str, Any]:
        try:
            project_dir = _project_dir(store, project_id)
            identity = resolve_operator(_operator_token(x_hs_operator_token))
            if not isinstance(request, Mapping):
                raise PresenceValidationError("request must be an object")
            return put_presence(project_dir, request, operator=identity)
        except Exception as exc:
            raise _events_error(exc) from exc

    @router.get("/{project_id}/presence")
    def get_project_presence(project_id: str) -> Dict[str, Any]:
        try:
            project_dir = _project_dir(store, project_id)
            return list_presence(project_dir)
        except Exception as exc:
            raise _events_error(exc) from exc

    @router.delete("/{project_id}/presence/{client_id}")
    def delete_project_presence(project_id: str, client_id: str) -> Dict[str, Any]:
        try:
            project_dir = _project_dir(store, project_id)
            return delete_presence(project_dir, client_id)
        except Exception as exc:
            raise _events_error(exc) from exc

    return router

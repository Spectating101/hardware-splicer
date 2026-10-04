"""HTTP surface for append-only review threads.

Author identity is self-declared. This API does not authenticate, so stored
events always set ``author_verified`` to false in v1.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status

from .project_store import InvalidProjectId, ProjectNotFound
from .project_thread_store import (
    ProjectThreadStore,
    ThreadConflict,
    ThreadNotFound,
    ThreadStateError,
    ThreadValidationError,
    reject_authority_keys,
)


def _thread_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_identifier", "message": str(exc)},
        )
    if isinstance(exc, (ProjectNotFound, ThreadNotFound)):
        return HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"type": "not_found", "message": str(exc)},
        )
    if isinstance(exc, ThreadConflict):
        return HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"type": "thread_conflict", "message": str(exc)},
        )
    if isinstance(exc, ThreadStateError):
        return HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"type": "thread_state", "message": str(exc)},
        )
    if isinstance(exc, ThreadValidationError):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, (ValueError, TypeError)):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    return HTTPException(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "project_thread_error", "message": str(exc)},
    )


def _as_request_object(payload: Any, *, label: str) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ThreadValidationError(f"{label} must be an object")
    request = dict(payload)
    reject_authority_keys(request, label=label)
    return request


def create_project_thread_router(thread_store: ProjectThreadStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects/{project_id}/threads", tags=["project-threads"])

    @router.get("")
    def list_project_threads(
        project_id: str,
        object_id: str | None = Query(default=None),
        status: str | None = Query(default=None),
    ) -> Dict[str, Any]:
        try:
            threads = thread_store.list_threads(project_id, object_id=object_id, status=status)
        except Exception as exc:
            raise _thread_error(exc) from exc
        return {"ok": True, "threads": threads}

    @router.post("", status_code=http_status.HTTP_201_CREATED)
    def create_project_thread(project_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            payload = _as_request_object(request, label="request")
            thread = thread_store.create_thread(
                project_id,
                payload.get("anchor"),
                payload.get("author"),
                payload.get("body"),
            )
        except Exception as exc:
            raise _thread_error(exc) from exc
        return {"ok": True, "thread": thread}

    @router.get("/{thread_id}")
    def load_project_thread(project_id: str, thread_id: str) -> Dict[str, Any]:
        try:
            thread = thread_store.get_thread(project_id, thread_id)
        except Exception as exc:
            raise _thread_error(exc) from exc
        return {"ok": True, "thread": thread}

    @router.post("/{thread_id}/events", status_code=http_status.HTTP_201_CREATED)
    def append_project_thread_event(
        project_id: str,
        thread_id: str,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            payload = _as_request_object(request, label="request")
            event = thread_store.append_event(
                project_id,
                thread_id,
                payload.get("type"),
                payload.get("author"),
                body=payload.get("body", ""),
                expected_event_seq=payload.get("expected_event_seq"),
            )
        except Exception as exc:
            raise _thread_error(exc) from exc
        return {"ok": True, "event": event}

    return router

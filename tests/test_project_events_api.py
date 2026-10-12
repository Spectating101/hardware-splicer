from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_events_api import (
    _acquire_stream,
    _release_stream,
    active_stream_count,
    build_event_stream_response,
    create_project_events_router,
    event_frames,
    reset_stream_counts,
    start_project_event_stream,
    stream_slot_key,
)
from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.project_thread_store import ProjectThreadStore

try:
    import pytest_timeout  # noqa: F401

    pytestmark = pytest.mark.timeout(10)
except ImportError:
    pytestmark = []


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += float(dt)


def snapshot(purpose: str = "Build an inspection robot") -> dict:
    return {
        "projectId": "robot",
        "projectName": "Inspection robot",
        "currentStage": "design",
        "machineProject": {
            "project_id": "robot",
            "name": "Inspection robot",
            "purpose": purpose,
        },
    }


@pytest.fixture(autouse=True)
def _reset_stream_slots() -> Any:
    reset_stream_counts()
    yield
    reset_stream_counts()


def _app(tmp_path: Path) -> tuple[TestClient, ProjectStore]:
    store = ProjectStore(tmp_path)
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_events_router(store))
    return TestClient(app), store


def _seed(api: TestClient) -> None:
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": snapshot(), "expected_revision": 0},
    )
    assert saved.status_code == 200


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == "presence":
            continue
        digest.update(str(relative).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _parse_sse(buffer: str) -> list[tuple[str, Any]]:
    frames: list[tuple[str, Any]] = []
    for chunk in buffer.split("\n\n"):
        event = None
        data_lines: list[str] = []
        comment = False
        for line in chunk.splitlines():
            if line.startswith(":"):
                comment = True
                frames.append(("comment", line[1:].strip()))
            elif line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if event is not None:
            payload = json.loads("\n".join(data_lines) or "{}")
            frames.append((event, payload))
        elif comment:
            continue
    return frames


def _get_with_timeout(api: TestClient, path: str, timeout: float = 5.0) -> Any:
    result: dict[str, Any] = {}
    error: list[BaseException] = []

    def worker() -> None:
        try:
            result["response"] = api.get(path)
        except BaseException as exc:  # pragma: no cover - surfaced below
            error.append(exc)

    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()
    worker_thread.join(timeout)
    assert worker_thread.is_alive() is False, f"GET {path} did not finish within {timeout}s"
    assert not error, error
    return result["response"]


def _sleep_for(clock: _Clock):
    async def sleep(dt: float) -> None:
        clock.advance(dt)

    return sleep


def _run(func, *args):
    return anyio.run(func, *args)


def _drain_event_frames(
    store: ProjectStore,
    *,
    poll: float,
    keepalive: float,
    max_seconds: float,
    after_hello: Any | None = None,
) -> tuple[_Clock, list[tuple[float, list[tuple[str, Any]]]]]:
    clock = _Clock()
    frames: list[tuple[float, list[tuple[str, Any]]]] = []

    async def run() -> None:
        with anyio.fail_after(5):
            gen = event_frames(
                store,
                "robot",
                is_disconnected=lambda: False,
                poll=poll,
                keepalive=keepalive,
                max_seconds=max_seconds,
                clock=clock,
                sleep=_sleep_for(clock),
            )
            first = True
            try:
                while True:
                    raw = await gen.__anext__()
                    frames.append((clock.t, _parse_sse(raw)))
                    if first:
                        first = False
                        if after_hello is not None:
                            after_hello()
            except StopAsyncIteration:
                pass
            await gen.aclose()

    _run(run)
    return clock, frames


def test_sse_hello_then_store_mutations(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    threads = ProjectThreadStore(store)
    clock = _Clock()

    async def run() -> None:
        with anyio.fail_after(5):
            gen = event_frames(
                store,
                "robot",
                is_disconnected=lambda: False,
                poll=0.05,
                keepalive=0.2,
                max_seconds=5,
                clock=clock,
                sleep=_sleep_for(clock),
            )
            hello_frames = _parse_sse(await gen.__anext__())
            hello = next(payload for kind, payload in hello_frames if kind == "hello")
            assert hello["project_id"] == "robot"
            assert hello["revision"] == 1
            assert hello["thread_count"] == 0
            assert hello["review_count"] == 0
            assert hello["poll_seconds"] == 0.05
            assert "server_time" in hello

            created = threads.create_thread(
                "robot",
                {"revision": 1, "object_id": "mcu"},
                {"kind": "human", "id": "owner"},
                "Please review this net.",
            )
            created_frames = _parse_sse(await gen.__anext__())
            assert any(
                kind == "change"
                and any(
                    row["type"] == "thread.created" and row["id"] == created["thread_id"]
                    for row in payload["changes"]
                )
                for kind, payload in created_frames
                if kind == "change"
            ), created_frames

            threads.append_event(
                "robot",
                created["thread_id"],
                "comment",
                {"kind": "human", "id": "owner"},
                "Follow up.",
            )
            reply_frames = _parse_sse(await gen.__anext__())
            assert any(
                kind == "change"
                and any(
                    row["type"] == "thread.event"
                    and row["id"] == created["thread_id"]
                    and row["seq"] == 2
                    for row in payload["changes"]
                )
                for kind, payload in reply_frames
                if kind == "change"
            ), reply_frames

            store.save("robot", snapshot("Build a documented inspection robot"), expected_revision=1)
            revision_frames = _parse_sse(await gen.__anext__())
            assert any(
                kind == "change"
                and any(row["type"] == "revision.saved" and row["seq"] == 2 for row in payload["changes"])
                for kind, payload in revision_frames
                if kind == "change"
            ), revision_frames

            keepalive_seen = False
            for _ in range(16):
                parsed = _parse_sse(await gen.__anext__())
                if any(kind == "comment" and payload == "keepalive" for kind, payload in parsed):
                    keepalive_seen = True
                    break
            assert keepalive_seen
            await gen.aclose()

    _run(run)


def test_unknown_project_is_404(tmp_path: Path) -> None:
    api, _store = _app(tmp_path)
    missing = _get_with_timeout(api, "/v1/projects/missing/events")
    assert missing.status_code == 404
    assert missing.json()["detail"]["type"] == "not_found"


def test_sse_headers_and_self_ending_stream(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVENT_MAX_SECONDS", "0.2")
    monkeypatch.setenv("HARDWARE_SPLICER_EVENT_POLL_SECONDS", "0.05")
    monkeypatch.setenv("HARDWARE_SPLICER_EVENT_KEEPALIVE_SECONDS", "10")
    api, store = _app(tmp_path)
    _seed(api)
    response = _get_with_timeout(api, "/v1/projects/robot/events")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    frames = _parse_sse(response.text)
    hello = next(payload for kind, payload in frames if kind == "hello")
    assert hello["project_id"] == "robot"
    assert hello["revision"] == 1
    assert active_stream_count(store, "robot") == 0
    again = _get_with_timeout(api, "/v1/projects/robot/events")
    assert again.status_code == 200
    assert active_stream_count(store, "robot") == 0


def test_stream_cap_is_429(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVENT_MAX_STREAMS", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_EVENT_MAX_SECONDS", "0.2")
    monkeypatch.setenv("HARDWARE_SPLICER_EVENT_POLL_SECONDS", "0.05")
    api, store = _app(tmp_path)
    _seed(api)
    key = stream_slot_key(store, "robot")
    assert _acquire_stream(key, 1)
    try:
        assert active_stream_count(store, "robot") == 1
        blocked = _get_with_timeout(api, "/v1/projects/robot/events")
        assert blocked.status_code == 429
        assert blocked.json()["detail"]["type"] == "too_many_streams"
    finally:
        _release_stream(key)
    assert active_stream_count(store, "robot") == 0


def test_disconnect_releases_stream_slot(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    disconnected = {"value": False}
    clock = _Clock()

    async def run() -> None:
        with anyio.fail_after(5):
            gen = start_project_event_stream(
                store,
                "robot",
                is_disconnected=lambda: disconnected["value"],
                poll=0.05,
                keepalive=10,
                max_seconds=5,
                clock=clock,
                sleep=_sleep_for(clock),
            )
            assert active_stream_count(store, "robot") == 1
            hello = _parse_sse(await gen.__anext__())
            assert any(kind == "hello" for kind, _ in hello)
            disconnected["value"] = True
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()
            await gen.aclose()
            assert active_stream_count(store, "robot") == 0

    _run(run)


def test_max_seconds_expiry_releases_stream_slot(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    clock = _Clock()

    async def run() -> None:
        with anyio.fail_after(5):
            gen = start_project_event_stream(
                store,
                "robot",
                poll=0.05,
                keepalive=10,
                max_seconds=0.1,
                clock=clock,
                sleep=_sleep_for(clock),
            )
            assert active_stream_count(store, "robot") == 1
            hello = _parse_sse(await gen.__anext__())
            assert any(kind == "hello" for kind, _ in hello)
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()
            await gen.aclose()
            assert active_stream_count(store, "robot") == 0

    _run(run)


def test_generator_close_releases_stream_slot(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    clock = _Clock()

    async def run() -> None:
        with anyio.fail_after(5):
            gen = start_project_event_stream(
                store,
                "robot",
                poll=0.05,
                keepalive=10,
                max_seconds=5,
                clock=clock,
                sleep=_sleep_for(clock),
            )
            assert active_stream_count(store, "robot") == 1
            hello = _parse_sse(await gen.__anext__())
            assert any(kind == "hello" for kind, _ in hello)
            await gen.aclose()
            assert active_stream_count(store, "robot") == 0

    _run(run)


def test_stream_and_presence_do_not_change_project_bytes(tmp_path: Path) -> None:
    api, store = _app(tmp_path)
    _seed(api)
    threads = ProjectThreadStore(store)
    created = threads.create_thread(
        "robot",
        {"revision": 1, "object_id": "mcu"},
        {"kind": "human", "id": "owner"},
        "Please review this net.",
    )
    reviews = ProjectReviewStore(store)
    reviews.create(
        "robot",
        snapshot("Build a documented inspection robot"),
        base_revision=1,
        created_by="agent",
    )
    pin_dir = tmp_path / "robot" / "artifact_pins"
    pin_dir.mkdir()
    (pin_dir / "00000001.json").write_text("{}\n", encoding="utf-8")
    before = _hash_tree(tmp_path / "robot")
    clock = _Clock()

    async def run() -> None:
        with anyio.fail_after(5):
            gen = event_frames(
                store,
                "robot",
                poll=0.05,
                keepalive=10,
                max_seconds=0,
                clock=clock,
                sleep=_sleep_for(clock),
            )
            hello = _parse_sse(await gen.__anext__())
            assert any(kind == "hello" for kind, _ in hello)
            await gen.aclose()

    _run(run)
    heartbeat = api.post(
        "/v1/projects/robot/presence",
        json={"client_id": "browser-tab-1", "name": "Pat", "mode": "review"},
    )
    assert heartbeat.status_code == 200, heartbeat.text
    listed = api.get("/v1/projects/robot/presence")
    assert listed.status_code == 200
    assert listed.json()["participants"][0]["client_id"] == "browser-tab-1"
    gone = api.delete("/v1/projects/robot/presence/browser-tab-1")
    assert gone.status_code == 200
    listed_after = api.get("/v1/projects/robot/presence")
    assert listed_after.json()["participants"] == []

    assert _hash_tree(tmp_path / "robot") == before
    assert created["thread_id"]
    envelope = store.load("robot")
    assert envelope["revision"] == 1
    assert envelope["snapshot"]["machineProject"]["purpose"] == "Build an inspection robot"


def test_event_frames_ends_at_max_seconds_not_after_full_poll(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)

    def mutate() -> None:
        store.save("robot", snapshot("Build a documented inspection robot"), expected_revision=1)

    clock, frames = _drain_event_frames(
        store,
        poll=10,
        keepalive=15,
        max_seconds=0.2,
        after_hello=mutate,
    )
    assert clock.t == pytest.approx(0.2)
    kinds = [kind for _t, parsed in frames for kind, _payload in parsed]
    assert kinds == ["hello"]
    assert all(stamp <= 0.2 for stamp, _parsed in frames)


def test_event_frames_keepalive_follows_last_emit_not_poll(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    clock, frames = _drain_event_frames(
        store,
        poll=10,
        keepalive=15,
        max_seconds=40,
    )
    keepalive_times = [
        stamp
        for stamp, parsed in frames
        if any(kind == "comment" and payload == "keepalive" for kind, payload in parsed)
    ]
    assert keepalive_times == [15, 30]
    assert all(stamp <= 40 for stamp, _parsed in frames)
    kinds = [kind for _t, parsed in frames for kind, _payload in parsed]
    assert kinds[0] == "hello"
    assert kinds[1:] == ["comment", "comment"]
    assert clock.t == pytest.approx(40.0)


def test_never_started_aclose_releases_stream_slot(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    clock = _Clock()

    async def run() -> None:
        with anyio.fail_after(5):
            gen = start_project_event_stream(
                store,
                "robot",
                poll=0.05,
                keepalive=10,
                max_seconds=5,
                clock=clock,
                sleep=_sleep_for(clock),
            )
            assert active_stream_count(store, "robot") == 1
            await gen.aclose()
            assert active_stream_count(store, "robot") == 0

    _run(run)


def test_streaming_response_teardown_without_iterating_releases_slot(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    clock = _Clock()
    response = build_event_stream_response(
        store,
        "robot",
        poll=0.05,
        keepalive=10,
        max_seconds=5,
        clock=clock,
        sleep=_sleep_for(clock),
    )
    assert active_stream_count(store, "robot") == 1
    assert response.background is not None

    async def tear_down() -> None:
        with anyio.fail_after(5):
            await response.background()

    _run(tear_down)
    assert active_stream_count(store, "robot") == 0


def test_slot_lease_double_release_is_noop(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    clock = _Clock()

    async def run() -> None:
        with anyio.fail_after(5):
            gen = start_project_event_stream(
                store,
                "robot",
                poll=0.05,
                keepalive=10,
                max_seconds=5,
                clock=clock,
                sleep=_sleep_for(clock),
            )
            assert active_stream_count(store, "robot") == 1
            lease = gen.lease
            lease.release()
            assert active_stream_count(store, "robot") == 0
            lease.release()
            assert active_stream_count(store, "robot") == 0
            await gen.aclose()
            assert active_stream_count(store, "robot") == 0

    _run(run)


def test_lifetime_clock_ends_after_hello_without_another_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reads = {"n": 0}
    from hardware_splicer import project_events_api as events_api

    real_state = events_api.project_state

    def counting_state(path):
        reads["n"] += 1
        return real_state(path)

    monkeypatch.setattr(events_api, "project_state", counting_state)
    clock = _Clock()

    async def run() -> None:
        with anyio.fail_after(5):
            gen = start_project_event_stream(
                store,
                "robot",
                poll=10,
                keepalive=15,
                max_seconds=0.2,
                clock=clock,
                sleep=_sleep_for(clock),
            )
            hello = _parse_sse(await gen.__anext__())
            assert any(kind == "hello" for kind, _ in hello)
            assert reads["n"] == 1
            clock.advance(1.0)
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()
            assert reads["n"] == 1
            await gen.aclose()
            assert active_stream_count(store, "robot") == 0

    _run(run)

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.project_thread_api import create_project_thread_router
from hardware_splicer.project_thread_store import ProjectThreadStore


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


def client(tmp_path: Path) -> TestClient:
    store = ProjectStore(tmp_path)
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_thread_router(ProjectThreadStore(store)))
    return TestClient(app)


def _seed(api: TestClient) -> None:
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": snapshot(), "expected_revision": 0},
    )
    assert saved.status_code == 200


def _create(api: TestClient, **overrides: object) -> dict:
    payload = {
        "anchor": {"revision": 1, "object_id": "mcu"},
        "author": {"kind": "human", "id": "owner"},
        "body": "Please review this net.",
    }
    payload.update(overrides)
    created = api.post("/v1/projects/robot/threads", json=payload)
    assert created.status_code == 201, created.text
    return created.json()["thread"]


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == "threads":
            continue
        digest.update(str(relative).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_thread_api_create_list_get_round_trip(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)
    thread = _create(api)
    assert thread["status"] == "open"
    assert thread["events"][0]["seq"] == 1
    assert thread["events"][0]["author_verified"] is False

    listed = api.get("/v1/projects/robot/threads")
    assert listed.status_code == 200
    assert listed.json()["ok"] is True
    assert listed.json()["threads"][0]["thread_id"] == thread["thread_id"]

    loaded = api.get(f"/v1/projects/robot/threads/{thread['thread_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["thread"]["events"][0]["seq"] == 1


def test_thread_api_resolve_reopen_and_invalid_state(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)
    thread = _create(api)

    too_soon = api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={"type": "reopen", "author": {"kind": "human", "id": "owner"}, "body": "no"},
    )
    assert too_soon.status_code == 409
    assert too_soon.json()["detail"]["type"] == "thread_state"

    resolved = api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={"type": "resolve", "author": {"kind": "human", "id": "owner"}, "body": "done"},
    )
    assert resolved.status_code == 201
    assert resolved.json()["event"]["author_verified"] is False
    assert api.get(f"/v1/projects/robot/threads/{thread['thread_id']}").json()["thread"]["status"] == "resolved"

    again = api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={"type": "resolve", "author": {"kind": "human", "id": "owner"}},
    )
    assert again.status_code == 409
    assert again.json()["detail"]["type"] == "thread_state"

    reopened = api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={"type": "reopen", "author": {"kind": "human", "id": "owner"}, "body": "again"},
    )
    assert reopened.status_code == 201
    assert api.get(f"/v1/projects/robot/threads/{thread['thread_id']}").json()["thread"]["status"] == "open"


def test_thread_api_expected_event_seq_conflict(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)
    thread = _create(api)
    reply = api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={
            "type": "comment",
            "author": {"kind": "human", "id": "owner"},
            "body": "follow up",
            "expected_event_seq": 1,
        },
    )
    assert reply.status_code == 201
    stale = api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={
            "type": "comment",
            "author": {"kind": "human", "id": "owner"},
            "body": "stale",
            "expected_event_seq": 1,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["type"] == "thread_conflict"


def test_thread_api_anchor_validation(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)

    cases = [
        {
            "anchor": {"revision": 1},
            "author": {"kind": "human", "id": "owner"},
            "body": "missing target",
        },
        {
            "anchor": {"revision": 0, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "rev 0",
        },
        {
            "anchor": {"revision": 9, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "too new",
        },
        {
            "anchor": {
                "revision": 1,
                "artifact": {"relative": "docs/../secret.kicad_pcb", "kind": "pcb"},
            },
            "author": {"kind": "human", "id": "owner"},
            "body": "dotdot",
        },
        {
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "x" * 4001,
        },
        {
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "",
        },
        {
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "bot", "id": "x"},
            "body": "bad kind",
        },
        {
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "agent", "id": ""},
            "body": "missing agent",
        },
    ]
    for payload in cases:
        response = api.post("/v1/projects/robot/threads", json=payload)
        assert response.status_code == 422, payload
        assert response.json()["detail"]["type"] == "invalid_request"


def test_thread_api_rejects_authority_keys(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)
    authorized = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "a", "authorized": True},
            "body": "nope",
        },
    )
    assert authorized.status_code == 422
    assert authorized.json()["detail"]["type"] == "invalid_request"

    release = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu", "release": True},
            "author": {"kind": "human", "id": "a"},
            "body": "nope",
        },
    )
    assert release.status_code == 422
    assert release.json()["detail"]["type"] == "invalid_request"


def test_thread_api_path_traversal_and_list_filters(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)
    first = _create(api)
    second = _create(
        api,
        anchor={"revision": 1, "object_id": "motor"},
        body="Motor thread",
    )
    api.post(
        f"/v1/projects/robot/threads/{second['thread_id']}/events",
        json={"type": "resolve", "author": {"kind": "human", "id": "owner"}},
    )

    traversal = api.get("/v1/projects/%2E%2E%2Fx/threads")
    assert traversal.status_code in {404, 422}
    if traversal.status_code == 422:
        assert traversal.json()["detail"]["type"] == "invalid_identifier"
    bad_thread = api.get("/v1/projects/robot/threads/%2E%2E%2Fx")
    assert bad_thread.status_code in {404, 422}
    if bad_thread.status_code == 422:
        assert bad_thread.json()["detail"]["type"] == "invalid_identifier"
    assert not (tmp_path.parent / "x").exists()

    by_object = api.get("/v1/projects/robot/threads", params={"object_id": "mcu"})
    assert [row["thread_id"] for row in by_object.json()["threads"]] == [first["thread_id"]]
    open_rows = api.get("/v1/projects/robot/threads", params={"status": "open"})
    assert [row["thread_id"] for row in open_rows.json()["threads"]] == [first["thread_id"]]
    resolved_rows = api.get("/v1/projects/robot/threads", params={"status": "resolved"})
    assert [row["thread_id"] for row in resolved_rows.json()["threads"]] == [second["thread_id"]]


def test_thread_api_does_not_change_project_or_review_bytes(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)
    review = reviews.create("robot", snapshot("Candidate purpose"), created_by="agent")
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_thread_router(ProjectThreadStore(store)))
    api = TestClient(app)

    project_dir = tmp_path / "robot"
    before = _hash_tree(project_dir)
    thread = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "Discuss the candidate",
        },
    ).json()["thread"]
    api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={"type": "comment", "author": {"kind": "human", "id": "owner"}, "body": "Reply"},
    )
    api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={"type": "resolve", "author": {"kind": "human", "id": "owner"}, "body": "Closed"},
    )
    assert _hash_tree(project_dir) == before
    assert store.load("robot")["revision"] == 1
    assert reviews.get("robot", review["review_id"])["status"] == "pending"


def test_thread_api_corrupt_thread_is_project_thread_error(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)
    thread = _create(api)
    (
        tmp_path / "robot" / "threads" / thread["thread_id"] / "thread.json"
    ).write_text("{not-json", encoding="utf-8")
    listed = api.get("/v1/projects/robot/threads")
    assert listed.status_code == 500
    assert listed.json()["detail"]["type"] == "project_thread_error"
    loaded = api.get(f"/v1/projects/robot/threads/{thread['thread_id']}")
    assert loaded.status_code == 500
    assert loaded.json()["detail"]["type"] == "project_thread_error"


def test_thread_api_structurally_corrupt_records_are_project_thread_error(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)
    thread = _create(api)
    thread_dir = tmp_path / "robot" / "threads" / thread["thread_id"]
    thread_path = thread_dir / "thread.json"
    valid_thread = thread_path.read_text(encoding="utf-8")
    thread_path.write_text("{}\n", encoding="utf-8")
    listed = api.get("/v1/projects/robot/threads")
    assert listed.status_code == 500
    assert listed.json()["detail"]["type"] == "project_thread_error"
    loaded = api.get(f"/v1/projects/robot/threads/{thread['thread_id']}")
    assert loaded.status_code == 500
    assert loaded.json()["detail"]["type"] == "project_thread_error"

    thread_path.write_text(valid_thread, encoding="utf-8")
    (thread_dir / "events" / "00000001.json").write_text("{}\n", encoding="utf-8")
    listed = api.get("/v1/projects/robot/threads")
    assert listed.status_code == 500
    assert listed.json()["detail"]["type"] == "project_thread_error"

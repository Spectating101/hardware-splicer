from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.operator_identity import hash_operator_token
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


def _operator_env(monkeypatch, token: str = "operator-secret", *, operator_id: str = "alice", kind: str = "human") -> str:
    monkeypatch.setenv(
        "HARDWARE_SPLICER_OPERATOR_TOKENS",
        json.dumps({hash_operator_token(token): {"id": operator_id, "kind": kind}}),
    )
    return token


def test_thread_api_no_token_stays_unverified(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)
    thread = _create(api)
    assert thread["events"][0]["author"] == {"kind": "human", "id": "owner"}
    assert thread["events"][0]["author_verified"] is False
    assert "verified_by" not in thread["events"][0]


def test_thread_api_valid_token_verifies_author_from_registry(tmp_path: Path, monkeypatch) -> None:
    token = _operator_env(monkeypatch)
    api = client(tmp_path)
    _seed(api)
    created = api.post(
        "/v1/projects/robot/threads",
        json={"anchor": {"revision": 1, "object_id": "mcu"}, "body": "Verified note"},
        headers={"X-HS-Operator-Token": token},
    )
    assert created.status_code == 201, created.text
    event = created.json()["thread"]["events"][0]
    assert event["author"] == {"kind": "human", "id": "alice"}
    assert event["author_verified"] is True
    assert event["verified_by"] == "operator-token"
    assert token not in created.text

    matching = api.post(
        f"/v1/projects/robot/threads/{created.json()['thread']['thread_id']}/events",
        json={
            "type": "comment",
            "author": {"kind": "human", "id": "alice"},
            "body": "same author",
        },
        headers={"X-HS-Operator-Token": token},
    )
    assert matching.status_code == 201, matching.text
    assert matching.json()["event"]["author"] == {"kind": "human", "id": "alice"}
    assert matching.json()["event"]["author_verified"] is True
    assert matching.json()["event"]["verified_by"] == "operator-token"


def test_thread_api_client_author_conflict_is_422(tmp_path: Path, monkeypatch) -> None:
    token = _operator_env(monkeypatch)
    api = client(tmp_path)
    _seed(api)
    conflict = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "bob"},
            "body": "wrong name",
        },
        headers={"X-HS-Operator-Token": token},
    )
    assert conflict.status_code == 422
    assert conflict.json()["detail"]["type"] == "invalid_request"
    assert conflict.json()["detail"]["message"] == "author does not match the verified operator"
    assert api.get("/v1/projects/robot/threads").json()["threads"] == []


def test_thread_api_invalid_token_is_401_and_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    _operator_env(monkeypatch)
    api = client(tmp_path)
    _seed(api)
    rejected = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "should not land",
        },
        headers={"X-HS-Operator-Token": "not-the-token"},
    )
    assert rejected.status_code == 401
    assert rejected.json()["detail"]["type"] == "operator_token_invalid"
    assert "not-the-token" not in rejected.text
    assert api.get("/v1/projects/robot/threads").json()["threads"] == []
    threads_root = tmp_path / "robot" / "threads"
    assert not threads_root.exists() or list(threads_root.iterdir()) == []


def test_thread_api_invalid_token_on_append_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    token = _operator_env(monkeypatch)
    api = client(tmp_path)
    _seed(api)
    thread = _create(api)
    before = api.get(f"/v1/projects/robot/threads/{thread['thread_id']}").json()["thread"]
    rejected = api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={"type": "comment", "author": {"kind": "human", "id": "owner"}, "body": "nope"},
        headers={"X-HS-Operator-Token": "wrong-token"},
    )
    assert rejected.status_code == 401
    assert rejected.json()["detail"]["type"] == "operator_token_invalid"
    after = api.get(f"/v1/projects/robot/threads/{thread['thread_id']}").json()["thread"]
    assert after["comment_count"] == before["comment_count"]
    assert len(after["events"]) == len(before["events"])


@pytest.mark.parametrize(
    "author",
    ["bob", [], True, 5, {"kind": "human", "id": "x", "authorized": True}],
)
def test_thread_api_verified_token_rejects_invalid_author_shapes(
    tmp_path: Path, monkeypatch, author: object
) -> None:
    token = _operator_env(monkeypatch)
    api = client(tmp_path)
    _seed(api)
    rejected = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": author,
            "body": "should not land",
        },
        headers={"X-HS-Operator-Token": token},
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["detail"]["type"] == "invalid_request"
    assert rejected.json()["detail"]["message"] == "author does not match the verified operator"
    assert api.get("/v1/projects/robot/threads").json()["threads"] == []
    threads_root = tmp_path / "robot" / "threads"
    assert not threads_root.exists() or list(threads_root.iterdir()) == []


@pytest.mark.parametrize(
    "author",
    ["bob", [], True, 5, {"kind": "human", "id": "x", "authorized": True}],
)
def test_thread_api_verified_event_rejects_invalid_author_shapes(
    tmp_path: Path, monkeypatch, author: object
) -> None:
    token = _operator_env(monkeypatch)
    api = client(tmp_path)
    _seed(api)
    thread = _create(api)
    rejected = api.post(
        f"/v1/projects/robot/threads/{thread['thread_id']}/events",
        json={"type": "comment", "author": author, "body": "should not land"},
        headers={"X-HS-Operator-Token": token},
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["detail"]["type"] == "invalid_request"
    assert rejected.json()["detail"]["message"] == "author does not match the verified operator"
    loaded = api.get(f"/v1/projects/robot/threads/{thread['thread_id']}").json()["thread"]
    assert loaded["comment_count"] == 1
    assert len(loaded["events"]) == 1


def test_thread_api_authorization_header_is_not_an_operator_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_OPERATOR_TOKENS", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_OPERATOR_TOKENS_FILE", raising=False)
    api = client(tmp_path)
    _seed(api)
    created = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "proxied app auth",
        },
        headers={"Authorization": "Bearer app-api-key"},
    )
    assert created.status_code == 201, created.text
    event = created.json()["thread"]["events"][0]
    assert event["author"] == {"kind": "human", "id": "owner"}
    assert event["author_verified"] is False
    assert "verified_by" not in event


def test_thread_api_authorization_bearer_ignored_with_live_registry(tmp_path: Path, monkeypatch) -> None:
    token = _operator_env(monkeypatch, operator_id="alice", kind="human")
    api = client(tmp_path)
    _seed(api)
    created = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "app bearer must stay unverified",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201, created.text
    event = created.json()["thread"]["events"][0]
    assert event["author"] == {"kind": "human", "id": "owner"}
    assert event["author_verified"] is False
    assert "verified_by" not in event


def test_thread_api_invalid_operator_header_not_rescued_by_authorization(
    tmp_path: Path, monkeypatch
) -> None:
    token = _operator_env(monkeypatch)
    api = client(tmp_path)
    _seed(api)
    rejected = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "header wins",
        },
        headers={
            "X-HS-Operator-Token": "not-the-token",
            "Authorization": f"Bearer {token}",
        },
    )
    assert rejected.status_code == 401
    assert rejected.json()["detail"]["type"] == "operator_token_invalid"
    assert api.get("/v1/projects/robot/threads").json()["threads"] == []


def test_thread_api_operator_header_without_registry_is_503(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_OPERATOR_TOKENS", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_OPERATOR_TOKENS_FILE", raising=False)
    api = client(tmp_path)
    _seed(api)
    rejected = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "missing registry",
        },
        headers={"X-HS-Operator-Token": "any-token"},
    )
    assert rejected.status_code == 503
    assert rejected.json()["detail"]["type"] == "operator_registry_error"


@pytest.mark.parametrize("blank", ["", "  "])
def test_thread_api_blank_tokens_env_does_not_use_file(
    tmp_path: Path, monkeypatch, blank: str
) -> None:
    token = "operator-secret"
    registry_path = tmp_path / "operator-tokens.json"
    registry_path.write_text(
        json.dumps({hash_operator_token(token): {"id": "file-user", "kind": "agent"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS", blank)
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS_FILE", str(registry_path))
    api = client(tmp_path)
    _seed(api)
    rejected = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "blank env must not use file",
        },
        headers={"X-HS-Operator-Token": token},
    )
    assert rejected.status_code == 503
    assert rejected.json()["detail"]["type"] == "operator_registry_error"
    assert rejected.json()["detail"]["message"] == "operator token registry is not configured"
    assert api.get("/v1/projects/robot/threads").json()["threads"] == []


def test_thread_api_registry_error_is_503(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS", "{not-json")
    api = client(tmp_path)
    _seed(api)
    rejected = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "broken registry",
        },
        headers={"X-HS-Operator-Token": "any-token"},
    )
    assert rejected.status_code == 503
    assert rejected.json()["detail"]["type"] == "operator_registry_error"


def test_thread_api_position_anchor_round_trip(tmp_path: Path) -> None:
    api = client(tmp_path)
    _seed(api)
    created = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {
                "revision": 1,
                "artifact": {"relative": "board.kicad_pcb", "kind": "pcb"},
                "position": {"x_mm": 1.23456, "y_mm": -2.0},
            },
            "author": {"kind": "human", "id": "owner"},
            "body": "here",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["thread"]["anchor"]["position"] == {"x_mm": 1.235, "y_mm": -2.0}
    listed = api.get("/v1/projects/robot/threads")
    assert listed.json()["threads"][0]["anchor"]["position"] == {"x_mm": 1.235, "y_mm": -2.0}
    loaded = api.get(f"/v1/projects/robot/threads/{created.json()['thread']['thread_id']}")
    assert loaded.json()["thread"]["anchor"]["position"] == {"x_mm": 1.235, "y_mm": -2.0}

    missing_artifact = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu", "position": {"x_mm": 1.0, "y_mm": 2.0}},
            "author": {"kind": "human", "id": "owner"},
            "body": "no artifact",
        },
    )
    assert missing_artifact.status_code == 422
    assert missing_artifact.json()["detail"]["type"] == "invalid_request"


@pytest.mark.parametrize("x_mm", [10**1000, -(10**1000)])
def test_thread_api_huge_int_position_is_422(tmp_path: Path, x_mm: int) -> None:
    api = client(tmp_path)
    _seed(api)
    rejected = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {
                "revision": 1,
                "artifact": {"relative": "board.kicad_pcb", "kind": "pcb"},
                "position": {"x_mm": x_mm, "y_mm": 0},
            },
            "author": {"kind": "human", "id": "owner"},
            "body": "huge int",
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["type"] == "invalid_request"

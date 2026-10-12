from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

try:
    import pytest_timeout  # noqa: F401

    pytestmark = pytest.mark.timeout(10)
except ImportError:
    pytestmark = []

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_events_api import create_project_events_router
from hardware_splicer.project_presence import (
    PresenceLimitError,
    PresenceValidationError,
    delete_presence,
    list_presence,
    put_presence,
)
from hardware_splicer.project_store import ProjectStore


def snapshot() -> dict:
    return {
        "projectId": "robot",
        "projectName": "Inspection robot",
        "currentStage": "design",
        "machineProject": {
            "project_id": "robot",
            "name": "Inspection robot",
            "purpose": "Build an inspection robot",
        },
    }


def _project(tmp_path: Path) -> tuple[ProjectStore, Path]:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    return store, tmp_path / "robot"


def _api(tmp_path: Path) -> TestClient:
    store = ProjectStore(tmp_path)
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_events_router(store))
    return TestClient(app)


def _seed(api: TestClient) -> None:
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": snapshot(), "expected_revision": 0},
    )
    assert saved.status_code == 200


def _operator_env(monkeypatch, token: str = "operator-secret", *, operator_id: str = "alice", kind: str = "human") -> str:
    monkeypatch.setenv(
        "HARDWARE_SPLICER_OPERATOR_TOKENS",
        json.dumps({hash_operator_token(token): {"id": operator_id, "kind": kind}}),
    )
    return token


def test_put_and_list_unverified_self_declared_name(tmp_path: Path) -> None:
    _store, project_dir = _project(tmp_path)
    put_presence(
        project_dir,
        {
            "client_id": "browser-tab-1",
            "name": "Pat",
            "object_id": "mcu",
            "mode": "review",
        },
    )
    listed = list_presence(project_dir)
    assert listed["ok"] is True
    assert len(listed["participants"]) == 1
    row = listed["participants"][0]
    assert row["client_id"] == "browser-tab-1"
    assert row["name"] == "Pat"
    assert row["object_id"] == "mcu"
    assert row["mode"] == "review"
    assert row["verified"] is False
    assert row["operator"] is None
    assert row["seen_seconds_ago"] == 0


def test_ttl_expiry_and_stale_cleanup_with_injectable_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_PRESENCE_TTL_SECONDS", "45")
    _store, project_dir = _project(tmp_path)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("hardware_splicer.project_presence._utc_now", lambda: now)

    put_presence(project_dir, {"client_id": "browser-tab-1", "name": "Pat"})
    put_presence(project_dir, {"client_id": "browser-tab-2", "name": "Quinn"})
    assert {row["client_id"] for row in list_presence(project_dir)["participants"]} == {
        "browser-tab-1",
        "browser-tab-2",
    }

    later = now + timedelta(seconds=46)
    monkeypatch.setattr("hardware_splicer.project_presence._utc_now", lambda: later)
    assert list_presence(project_dir)["participants"] == []
    assert (project_dir / "presence" / "browser-tab-1.json").is_file()

    stale = now + timedelta(seconds=45 * 10)
    monkeypatch.setattr("hardware_splicer.project_presence._utc_now", lambda: stale)
    assert list_presence(project_dir)["participants"] == []
    assert not (project_dir / "presence" / "browser-tab-1.json").exists()
    assert not (project_dir / "presence" / "browser-tab-2.json").exists()


def test_verified_token_uses_registry_id_and_ignores_conflicting_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _operator_env(monkeypatch)
    api = _api(tmp_path)
    _seed(api)
    posted = api.post(
        "/v1/projects/robot/presence",
        json={"client_id": "browser-tab-9", "name": "not-alice", "mode": "compare"},
        headers={"X-HS-Operator-Token": token},
    )
    assert posted.status_code == 200, posted.text
    body = posted.json()
    assert body["ok"] is True
    assert body["ttl_seconds"] == 45

    listed = api.get("/v1/projects/robot/presence")
    assert listed.status_code == 200
    row = listed.json()["participants"][0]
    assert row["name"] == "alice"
    assert row["verified"] is True
    assert row["operator"] == {"id": "alice", "kind": "human"}
    assert token not in listed.text


def test_invalid_token_is_401_and_registry_error_is_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _operator_env(monkeypatch)
    api = _api(tmp_path)
    _seed(api)
    rejected = api.post(
        "/v1/projects/robot/presence",
        json={"client_id": "browser-tab-1"},
        headers={"X-HS-Operator-Token": "unknown-token"},
    )
    assert rejected.status_code == 401
    assert rejected.json()["detail"]["type"] == "operator_token_invalid"
    assert api.get("/v1/projects/robot/presence").json()["participants"] == []

    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS", "{not-json")
    broken = api.post(
        "/v1/projects/robot/presence",
        json={"client_id": "browser-tab-1"},
        headers={"X-HS-Operator-Token": "operator-secret"},
    )
    assert broken.status_code == 503
    assert broken.json()["detail"]["type"] == "operator_registry_error"


def test_validation_rejects_unknown_authority_and_bad_fields(tmp_path: Path) -> None:
    _store, project_dir = _project(tmp_path)
    with pytest.raises(PresenceValidationError):
        put_presence(project_dir, {"client_id": "short", "name": "Pat"})
    with pytest.raises(PresenceValidationError):
        put_presence(
            project_dir,
            {"client_id": "browser-tab-1", "name": "Pat", "authority": "verified"},
        )
    with pytest.raises(PresenceValidationError):
        put_presence(
            project_dir,
            {"client_id": "browser-tab-1", "authorized": True},
        )
    with pytest.raises(PresenceValidationError):
        put_presence(
            project_dir,
            {"client_id": "browser-tab-1", "extra": "nope"},
        )
    with pytest.raises(PresenceValidationError):
        put_presence(
            project_dir,
            {"client_id": "browser-tab-1", "name": "x" * 81},
        )
    with pytest.raises(PresenceValidationError):
        put_presence(
            project_dir,
            {"client_id": "browser-tab-1", "name": "bad\nname"},
        )
    with pytest.raises(PresenceValidationError):
        put_presence(
            project_dir,
            {"client_id": "browser-tab-1", "object_id": "x" * 201},
        )
    with pytest.raises(PresenceValidationError):
        put_presence(
            project_dir,
            {"client_id": "browser-tab-1", "mode": "admin"},
        )

    api = _api(tmp_path)
    rejected = api.post(
        "/v1/projects/robot/presence",
        json={"client_id": "browser-tab-1", "release": "build_ready"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["type"] == "invalid_request"


def test_path_traversal_client_id_rejected(tmp_path: Path) -> None:
    _store, project_dir = _project(tmp_path)
    with pytest.raises(PresenceValidationError):
        put_presence(project_dir, {"client_id": "../escape-me"})
    with pytest.raises(PresenceValidationError):
        delete_presence(project_dir, "../escape-me")

    api = _api(tmp_path)
    traversed = api.delete("/v1/projects/robot/presence/../escape-me")
    assert traversed.status_code in {404, 405, 422}


def test_presence_file_cap(tmp_path: Path) -> None:
    _store, project_dir = _project(tmp_path)
    for index in range(200):
        put_presence(project_dir, {"client_id": f"browser-{index:03d}-xx"})
    with pytest.raises(PresenceLimitError):
        put_presence(project_dir, {"client_id": "browser-201-xxxx"})
    put_presence(project_dir, {"client_id": "browser-000-xx", "name": "refresh"})
    listed = list_presence(project_dir)
    assert len(listed["participants"]) == 100
    assert listed["participants"] == sorted(
        listed["participants"], key=lambda row: row["client_id"]
    )


def test_presence_api_cap_is_429(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("hardware_splicer.project_presence.MAX_PRESENCE_FILES", 2)
    api = _api(tmp_path)
    _seed(api)
    assert api.post("/v1/projects/robot/presence", json={"client_id": "apitab-aaa"}).status_code == 200
    assert api.post("/v1/projects/robot/presence", json={"client_id": "apitab-bbb"}).status_code == 200
    blocked = api.post("/v1/projects/robot/presence", json={"client_id": "apitab-ccc"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["type"] == "too_many_presence"


def test_delete_is_idempotent_and_unknown_project_is_404(tmp_path: Path) -> None:
    api = _api(tmp_path)
    _seed(api)
    posted = api.post("/v1/projects/robot/presence", json={"client_id": "browser-tab-1"})
    assert posted.status_code == 200
    deleted = api.delete("/v1/projects/robot/presence/browser-tab-1")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    again = api.delete("/v1/projects/robot/presence/browser-tab-1")
    assert again.status_code == 200
    missing = api.get("/v1/projects/missing/presence")
    assert missing.status_code == 404
    assert missing.json()["detail"]["type"] == "not_found"


def test_symlinked_presence_dir_and_file_are_not_followed(tmp_path: Path) -> None:
    _store, project_dir = _project(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "browser-tab-1.json").write_text(
        json.dumps(
            {
                "client_id": "browser-tab-1",
                "name": "leaked",
                "object_id": None,
                "mode": None,
                "seen_at": datetime.now(timezone.utc).isoformat(),
                "verified": False,
                "operator": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (project_dir / "presence").symlink_to(outside)
    listed = list_presence(project_dir)
    assert listed["participants"] == []
    with pytest.raises((OSError, PresenceValidationError, RuntimeError)):
        put_presence(project_dir, {"client_id": "browser-tab-2", "name": "Pat"})
    assert (outside / "browser-tab-2.json").exists() is False

    real = tmp_path / "robot2"
    store = ProjectStore(tmp_path)
    store.save("robot2", {**snapshot(), "projectId": "robot2", "machineProject": {**snapshot()["machineProject"], "project_id": "robot2"}}, expected_revision=0)
    put_presence(real, {"client_id": "browser-tab-3", "name": "Pat"})
    target = real / "presence" / "browser-tab-3.json"
    decoy = real / "presence" / "browser-tab-4.json"
    decoy.symlink_to(target)
    names = {row["client_id"] for row in list_presence(real)["participants"]}
    assert names == {"browser-tab-3"}
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["name"] == "Pat"

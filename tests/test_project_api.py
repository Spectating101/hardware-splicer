from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_store import ProjectStore


def client(tmp_path: Path) -> TestClient:
    app = FastAPI()
    app.include_router(create_project_router(ProjectStore(tmp_path)))
    return TestClient(app)


def project_snapshot(stage: str = "design") -> dict:
    return {
        "projectId": "robot",
        "projectName": "Robot",
        "mode": "salvage",
        "currentStage": stage,
        "graph": {
            "phrase": "robot",
            "nodes": [{"id": "mcu"}],
            "edges": [],
        },
        "evidence": {
            "firmware_authorized": False,
            "power_authorized": False,
        },
    }


def test_project_crud_and_history(tmp_path: Path) -> None:
    api = client(tmp_path)

    first = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": project_snapshot(), "expected_revision": 0},
    )
    assert first.status_code == 200
    assert first.json()["project"]["revision"] == 1

    second = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": project_snapshot("verify"), "expected_revision": 1},
    )
    assert second.status_code == 200
    assert second.json()["project"]["revision"] == 2

    latest = api.get("/v1/projects/robot")
    assert latest.status_code == 200
    assert latest.json()["project"]["snapshot"]["currentStage"] == "verify"

    historical = api.get("/v1/projects/robot?revision=1")
    assert historical.json()["project"]["snapshot"]["currentStage"] == "design"

    listed = api.get("/v1/projects")
    assert listed.status_code == 200
    assert listed.json()["projects"][0]["project_id"] == "robot"


def test_project_conflict_and_invalid_identifier_errors(tmp_path: Path) -> None:
    api = client(tmp_path)
    api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": project_snapshot(), "expected_revision": 0},
    )

    conflict = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": project_snapshot(), "expected_revision": 0},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["type"] == "revision_conflict"

    invalid = api.put(
        "/v1/projects/%2E%2E%2Frobot/snapshot",
        json={"snapshot": project_snapshot(), "expected_revision": 0},
    )
    assert invalid.status_code in {404, 422}


def test_duplicate_archive_and_delete(tmp_path: Path) -> None:
    api = client(tmp_path)
    api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": project_snapshot(), "expected_revision": 0},
    )

    duplicated = api.post(
        "/v1/projects/robot/duplicate",
        json={"target_project_id": "robot-copy"},
    )
    assert duplicated.status_code == 201
    assert duplicated.json()["project"]["snapshot"]["projectId"] == "robot-copy"

    archived = api.patch("/v1/projects/robot/archive", json={"archived": True})
    assert archived.status_code == 200
    assert archived.json()["project"]["archived"] is True
    assert [
        row["project_id"] for row in api.get("/v1/projects").json()["projects"]
    ] == ["robot-copy"]

    deleted = api.delete("/v1/projects/robot-copy")
    assert deleted.status_code == 200
    assert api.get("/v1/projects/robot-copy").status_code == 404

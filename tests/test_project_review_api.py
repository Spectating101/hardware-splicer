from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_store import ProjectStore


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


def client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(create_project_router(ProjectStore(tmp_path)))
    return TestClient(app)


def test_review_api_create_list_load_accept_and_revision_link(tmp_path) -> None:
    api = client(tmp_path)
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": snapshot(), "expected_revision": 0},
    )
    assert saved.status_code == 200

    created = api.post(
        "/v1/projects/robot/reviews",
        json={
            "base_revision": 1,
            "candidate_snapshot": snapshot("Build an autonomous inspection robot"),
            "created_by": "agent",
            "note": "Proposed autonomy change",
        },
    )
    assert created.status_code == 201
    review = created.json()["review"]
    assert review["status"] == "pending"
    assert review["summary"]["project_fields_changed"] == 1

    listed = api.get("/v1/projects/robot/reviews")
    assert listed.status_code == 200
    assert listed.json()["reviews"][0]["review_id"] == review["review_id"]

    loaded = api.get(f"/v1/projects/robot/reviews/{review['review_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["review"]["candidate_snapshot"]["machineProject"]["purpose"].startswith(
        "Build an autonomous"
    )

    accepted = api.post(
        f"/v1/projects/robot/reviews/{review['review_id']}/decision",
        json={"decision": "accepted", "actor": "owner", "note": "Approved"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["review"]["decision"]["accepted_revision"] == 2

    revisions = api.get("/v1/projects/robot/revisions")
    assert revisions.status_code == 200
    assert revisions.json()["revisions"][0]["review_id"] == review["review_id"]


def test_review_api_rejects_stale_acceptance_and_invalid_decision(tmp_path) -> None:
    api = client(tmp_path)
    api.put("/v1/projects/robot/snapshot", json={"snapshot": snapshot(), "expected_revision": 0})
    created = api.post(
        "/v1/projects/robot/reviews",
        json={
            "candidate_snapshot": snapshot("Candidate purpose"),
            "created_by": "agent",
        },
    ).json()["review"]
    api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": snapshot("Concurrent edit"), "expected_revision": 1},
    )

    stale = api.post(
        f"/v1/projects/robot/reviews/{created['review_id']}/decision",
        json={"decision": "accepted", "actor": "owner"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["type"] == "revision_conflict"

    invalid = api.post(
        f"/v1/projects/robot/reviews/{created['review_id']}/decision",
        json={"decision": "maybe", "actor": "owner"},
    )
    assert invalid.status_code == 422


def test_review_api_rejection_does_not_create_revision(tmp_path) -> None:
    api = client(tmp_path)
    api.put("/v1/projects/robot/snapshot", json={"snapshot": snapshot(), "expected_revision": 0})
    review = api.post(
        "/v1/projects/robot/reviews",
        json={"candidate_snapshot": snapshot("Rejected purpose"), "created_by": "agent"},
    ).json()["review"]

    rejected = api.post(
        f"/v1/projects/robot/reviews/{review['review_id']}/decision",
        json={"decision": "rejected", "actor": "owner"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["review"]["status"] == "rejected"
    revisions = api.get("/v1/projects/robot/revisions").json()["revisions"]
    assert [row["revision"] for row in revisions] == [1]

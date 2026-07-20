from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.machine_project_api import create_machine_project_router


def project_payload() -> dict:
    return {
        "project_id": "robot",
        "name": "Inspection robot",
        "purpose": "Inspect a building",
        "subsystems": [
            {
                "subsystem_id": "control",
                "name": "Control",
                "domain": "firmware",
            }
        ],
    }


def client() -> TestClient:
    app = FastAPI()
    app.include_router(create_machine_project_router())
    return TestClient(app)


def test_edit_api_returns_validated_candidate_and_semantic_diff() -> None:
    response = client().post(
        "/v1/machine-projects/edit",
        json={
            "project": project_payload(),
            "operations": [
                {
                    "type": "upsert_requirement",
                    "payload": {
                        "requirement_id": "req-runtime",
                        "statement": "The robot shall operate for 90 minutes.",
                        "kind": "performance",
                        "allocated_to": ["control"],
                    },
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["requirements"][0]["requirement_id"] == "req-runtime"
    assert body["summary"]["added"] == 1
    assert body["diff"]["object_changes"][0]["collection"] == "requirements"


def test_edit_api_rejects_authority_fabrication() -> None:
    response = client().post(
        "/v1/machine-projects/edit",
        json={
            "project": project_payload(),
            "operations": [
                {
                    "type": "upsert_subsystem",
                    "payload": {
                        "subsystem_id": "control",
                        "authority": "verified",
                    },
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_machine_edit"
    assert "require evidence workflows" in response.json()["detail"]["message"]

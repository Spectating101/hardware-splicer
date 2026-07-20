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
                "subsystem_id": "power",
                "name": "Power",
                "domain": "electrical",
                "component_ids": ["battery"],
            }
        ],
        "components": [
            {
                "component_id": "battery",
                "name": "Battery",
                "domain": "electrical",
                "subsystem_id": "power",
                "authority": "declared",
            }
        ],
    }


def client() -> TestClient:
    app = FastAPI()
    app.include_router(create_machine_project_router())
    return TestClient(app)


def test_record_evidence_api_returns_reviewable_candidate() -> None:
    response = client().post(
        "/v1/machine-projects/record-evidence",
        json={
            "project": project_payload(),
            "evidence": {
                "evidence_id": "battery-voltage",
                "kind": "multimeter_capture",
                "basis": "instrument",
                "supports": ["battery"],
                "authority": "measured",
                "simulated": False,
            },
            "promotions": [
                {"collection": "components", "object_id": "battery", "authority": "measured"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["components"][0]["authority"] == "measured"
    assert body["project"]["evidence"][0]["evidence_id"] == "battery-voltage"
    assert body["review_required"] is True
    assert {flag["code"] for flag in body["diff"]["object_changes"][0]["review_flags"]} == {
        "authority_escalation"
    }


def test_record_evidence_api_rejects_simulated_physical_promotion() -> None:
    response = client().post(
        "/v1/machine-projects/record-evidence",
        json={
            "project": project_payload(),
            "evidence": {
                "evidence_id": "battery-sim",
                "kind": "digital_twin",
                "basis": "simulation",
                "supports": ["battery"],
                "authority": "verified",
                "simulated": True,
            },
            "verification": {
                "verification_id": "verify-battery-sim",
                "name": "Battery simulation",
                "method_type": "analysis",
                "status": "passed",
                "target_ids": ["battery"],
                "evidence_ids": ["battery-sim"],
            },
            "promotions": [
                {"collection": "components", "object_id": "battery", "authority": "verified"}
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_evidence_promotion"
    assert "simulated evidence cannot promote physical" in response.json()["detail"]["message"]

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def project(authority: str, purpose: str) -> dict:
    unresolved = [] if authority == "verified" else ["logic_voltage"]
    return {
        "project_id": "robot",
        "name": "Robot",
        "purpose": purpose,
        "subsystems": [
            {
                "subsystem_id": "drive",
                "name": "Drive",
                "domain": "mechanical",
                "component_ids": ["driver"],
                "interface_ids": ["command"],
            }
        ],
        "components": [
            {
                "component_id": "driver",
                "name": "Driver",
                "domain": "electrical",
                "subsystem_id": "drive",
                "authority": authority,
            }
        ],
        "interfaces": [
            {
                "interface_id": "command",
                "name": "Command",
                "kind": "control",
                "endpoints": [
                    {"object_id": "drive", "port": "controller"},
                    {"object_id": "driver", "port": "enable"},
                ],
                "contracts": [
                    {
                        "contract_type": "electrical",
                        "values": ({"logic_voltage_v": 3.3} if not unresolved else {}),
                        "unresolved_fields": unresolved,
                        "authority": authority,
                    }
                ],
                "authority": authority,
            }
        ],
    }


def test_diff_endpoint_reports_authority_review_and_summary(tmp_path: Path) -> None:
    app = create_product_app(project_store=ProjectStore(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/v1/machine-projects/diff",
            json={
                "base": project("unknown", "Move through the workshop."),
                "candidate": project("verified", "Inspect the workshop."),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {
        "added": 0,
        "removed": 0,
        "modified": 2,
        "project_fields_changed": 1,
        "review_required": True,
    }
    assert body["review_required"] is True
    flags = {
        flag["code"]
        for change in body["diff"]["object_changes"]
        for flag in change["review_flags"]
    }
    assert flags == {"authority_escalation"}

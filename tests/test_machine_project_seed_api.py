from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def test_intake_seed_endpoint_returns_cross_discipline_project(tmp_path: Path) -> None:
    app = create_product_app(project_store=ProjectStore(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/v1/machine-projects/from-intake",
            json={
                "intake": {
                    "project_name": "inspection_mount",
                    "goal": "Build a remotely aimed inspection camera mount.",
                    "available_parts": [
                        {"name": "ESP32", "type": "microcontroller", "condition": "salvaged"},
                        {"name": "Pan servo", "type": "servo", "condition": "salvaged"},
                        {"name": "5V supply", "type": "power_source", "condition": "owned"},
                    ],
                    "constraints": {"runtime_min": 45, "battery_voltage_v": 5.0},
                }
            },
        )

    assert response.status_code == 200
    body = response.json()
    project = body["project"]
    assert project["schema_version"] == "hardware_splicer.machine_project.v1"
    assert {row["domain"] for row in project["subsystems"]} >= {
        "system",
        "mechanical",
        "electrical",
        "firmware",
    }
    assert project["interfaces"] == []
    assert {row["code"] for row in body["traceability_issues"]} == {
        "unverified_requirement"
    }

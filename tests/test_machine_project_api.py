from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_product_app(project_store=ProjectStore(tmp_path)))


def test_machine_project_schema_and_session_migration(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        schema = api.get("/v1/machine-projects/schema")
        assert schema.status_code == 200
        assert schema.json()["schema"]["title"] == "MachineProject"

        migrated = api.post(
            "/v1/machine-projects/from-session",
            json={
                "session": {
                    "projectId": "robot-drive",
                    "projectName": "Robot drive",
                    "goal": "Build a mobile inspection robot",
                    "mode": "salvage",
                    "currentStage": "design",
                    "graph": {
                        "nodes": [
                            {"id": "controller", "data": {"label": "ESP32"}},
                            {"id": "driver", "data": {"label": "Motor driver"}},
                        ],
                        "edges": [
                            {"id": "command", "source": "controller", "target": "driver"}
                        ],
                    },
                }
            },
        )

        assert migrated.status_code == 200
        body = migrated.json()
        assert body["project"]["schema_version"] == "hardware_splicer.machine_project.v1"
        assert body["project"]["components"][0]["authority"] == "proposed"
        assert body["project"]["interfaces"][0]["authority"] == "unknown"
        assert body["project"]["interfaces"][0]["contracts"][0]["unresolved_fields"]
        assert body["project"]["discipline_payloads"]["splice_session"]["mode"] == "salvage"


def test_machine_project_validation_rejects_broken_references(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        response = api.post(
            "/v1/machine-projects/validate",
            json={
                "project": {
                    "project_id": "broken",
                    "name": "Broken machine",
                    "purpose": "Prove API validation",
                    "subsystems": [
                        {
                            "subsystem_id": "control",
                            "name": "Control",
                            "domain": "firmware",
                            "component_ids": ["missing"],
                        }
                    ],
                }
            },
        )

        assert response.status_code == 422
        assert "unknown object" in response.text


def test_release_assessment_never_promotes_unverified_machine(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        response = api.post(
            "/v1/machine-projects/assess-release",
            json={
                "requested_state": "build_ready",
                "project": {
                    "project_id": "unsafe",
                    "name": "Unsafe machine",
                    "purpose": "Exercise conservative release assessment",
                    "requirements": [
                        {
                            "requirement_id": "req-estop",
                            "statement": "The machine shall stop on emergency stop.",
                            "kind": "safety",
                        }
                    ],
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["allowed"] is False
        assert body["assessment"]["achieved_state"] in {"concept", "design_ready"}
        assert {row["code"] for row in body["assessment"]["blockers"]} >= {
            "unverified_requirement",
            "safety_not_closed",
            "release_state_not_reached",
        }

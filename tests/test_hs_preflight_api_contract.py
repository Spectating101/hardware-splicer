from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _payload() -> dict:
    parts = [
        {"name": "robot computer", "type": "computer", "part_id": "computer", "quantity": 1},
        {"name": "motor controller", "type": "microcontroller", "part_id": "mcu", "quantity": 1},
        {"name": "encoder motor", "type": "dc_motor", "part_id": "wheel-motor", "quantity": 2},
        {"name": "motor driver", "type": "motor_driver", "part_id": "motor-driver", "quantity": 1},
        {"name": "protected battery", "type": "power_source", "part_id": "battery", "quantity": 1},
        {"name": "chassis", "type": "mechanical_structure", "part_id": "chassis", "quantity": 1},
    ]
    inventory = [{"part_id": row["part_id"], "quantity": row["quantity"]} for row in parts]
    return {
        "intake": {
            "project_name": "preflight-ui-rover",
            "goal": "Prepare a low-speed indoor differential-drive inspection rover with ninety-minute runtime, emergency motor isolation, and a current-limited first-motion procedure.",
            "mode": "greenfield",
            "candidate_revision": "candidate-r1",
            "available_parts": parts,
            "constraints": {
                "robot_genre": "rover", "runtime_min": 90, "maximum_width_mm": 500,
                "battery_voltage_v": 12, "battery_capacity_ah": 8, "battery_usable_fraction": 0.8,
                "continuous_power_w": 45, "supply_current_limit_a": 20, "peak_current_a": 12,
                "emergency_stop_required": True, "first_motion_current_limited": True,
            },
            "bom": inventory,
            "physical_instances": inventory,
            "fabrication_artifacts": [
                {"artifact_id": "chassis-step", "artifact_kind": "step", "revision": "candidate-r1", "content_hash": "sha256:fixture-step"},
                {"artifact_id": "firmware-build", "artifact_kind": "firmware", "revision": "candidate-r1", "content_hash": "sha256:fixture-firmware"},
            ],
        },
        "engineering_sources": [
            {"source_id": "reference-repository", "source_type": "repository", "uri": "https://example.invalid/reference-rover", "revision": "fixture-commit", "authority_ceiling": "declared", "claims": ["Reference differential-drive architecture."]},
            {"source_id": "assembly-observation", "source_type": "video", "uri": "https://example.invalid/assembly-video", "revision": "selected-video-fixture", "authority_ceiling": "observed", "claims": ["Observed cable routing; not physical verification."]},
        ],
        "declared_conflicts": [],
        "skip_vision": True,
    }


def test_preflight_payload_generates_and_persists_real_guided_plan(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    app = create_product_app(project_store=store)
    payload = _payload()
    with TestClient(app) as client:
        generated = client.post("/v1/engineering/plan", json=payload)
        assert generated.status_code == 200, generated.text
        plan = generated.json()["plan"]
        project_id = plan["machine_project"]["project_id"]
        assert plan["schema_version"] == "hardware_splicer.guided_engineering_plan.v1"
        assert len(plan["engineering_source_graph"]["sources"]) == 2
        assert plan["robot_topology"]["robot_genre"] == "rover"
        assert plan["manufacturing_closure"]
        assert plan["engineering_execution_plan"]
        assert len(plan["operator_guide"]["steps"]) >= 12
        assert plan["engineering_status"]["next_actions"]
        readiness = plan["engineering_readiness"]
        assert readiness["fabrication_authorized"] is False
        assert readiness["flash_authorized"] is False
        assert readiness["power_on_authorized"] is False
        assert readiness["motion_authorized"] is False
        assert readiness["release_authorized"] is False
        saved = client.post("/v1/engineering/plans/save", json={**payload, "project_id": project_id})
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["project_id"] == project_id
        assert body["revision"] == 1
        assert body["plan"]["engineering_status"]["next_actions"]
        listed = client.get("/v1/projects")
        assert listed.status_code == 200
        assert any(row["project_id"] == project_id for row in listed.json()["projects"])

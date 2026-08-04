from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def test_product_api_mounts_status_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/status" in paths
    assert "/v1/engineering/status/schema" in paths


def test_status_endpoint_returns_ranked_source_action_from_existing_plan() -> None:
    response = TestClient(create_product_app()).post(
        "/v1/engineering/status",
        json={
            "plan": {
                "machine_project": {
                    "project_id": "status-api",
                    "verifications": [],
                    "discipline_payloads": {},
                },
                "engineering_source_graph": {
                    "unresolved_source_ids": ["missing-model"],
                    "conflicts": [],
                },
                "robot_topology": {"topology_id": "generic", "unresolved": []},
                "engineering_analysis": {"findings": []},
                "manufacturing_closure": {"checks": []},
                "engineering_execution_plan": {"unresolved": []},
                "change_impact": {"impacts": [], "unresolved": []},
                "missing_info": [],
                "engineering_readiness": {"status": "blocked"},
            }
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall_status"] == "blocked"
    assert body["current_phase"] == "source"
    assert body["next_action"]["action_id"] == "next-source"
    assert body["next_action"]["route"] == "/v1/engineering/sources/resolve-conflicts"
    assert body["automatic_execution"] is False
    assert body["fabrication_authorized"] is False
    assert body["flash_authorized"] is False
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_authorized"] is False


def test_status_endpoint_can_generate_status_from_fresh_intake() -> None:
    response = TestClient(create_product_app()).post(
        "/v1/engineering/status",
        json={
            "skip_vision": True,
            "intake": {
                "project_name": "fresh-status-rover",
                "goal": "Design a compact inspection rover.",
                "available_parts": [
                    {"name": "drive motor", "type": "dc_motor", "quantity": 2},
                    {"name": "battery", "type": "power_source", "quantity": 1},
                ],
                "constraints": {"width_mm": 250, "runtime_min": 60},
            },
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == "fresh-status-rover"
    assert body["engineering_status"]["summary"]["blocking_count"] > 0
    assert body["engineering_readiness"]["next_action_id"] == body["engineering_status"]["next_action_id"]
    assert body["engineering_status"]["metadata"]["motion_authorized"] is False

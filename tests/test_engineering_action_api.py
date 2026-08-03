from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def _plan() -> dict:
    return {
        "machine_project": {
            "project_id": "action-api",
            "components": [],
            "interfaces": [],
            "artifacts": [],
            "evidence": [],
            "verifications": [],
            "discipline_payloads": {},
        },
        "engineering_source_graph": {
            "unresolved_source_ids": ["missing-model"],
            "conflicts": [],
        },
        "robot_topology": {"topology_id": "generic", "links": [], "joints": [], "actuators": [], "sensors": [], "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"checks": [], "unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "blocked"},
    }


def test_product_api_mounts_action_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/actions/schema" in paths
    assert "/v1/engineering/actions/prepare" in paths


def test_action_api_prepares_current_ranked_action() -> None:
    response = TestClient(create_product_app()).post(
        "/v1/engineering/actions/prepare",
        json={"plan": _plan()},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    prepared = body["prepared_action"]
    assert prepared["action"]["action_id"] == "next-source"
    assert prepared["payload"]["unresolved_source_ids"] == ["missing-model"]
    assert body["automatic_execution"] is False
    assert body["physical_action"] is False
    assert body["fabrication_authorized"] is False
    assert body["flash_authorized"] is False
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_authorized"] is False


def test_action_api_rejects_unknown_action_id() -> None:
    response = TestClient(create_product_app()).post(
        "/v1/engineering/actions/prepare",
        json={"plan": _plan(), "action_id": "next-does-not-exist"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_engineering_action"

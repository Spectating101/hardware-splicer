from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _rover_request() -> dict:
    return {
        "skip_vision": True,
        "intake": {
            "project_name": "compact-inspection-rover",
            "goal": "Design a compact differential drive indoor inspection rover.",
            "available_parts": [
                {"name": "drive motor", "type": "dc_motor", "quantity": 2},
                {"name": "battery pack", "type": "power_source", "quantity": 1},
                {"name": "depth camera", "type": "camera", "quantity": 1},
            ],
            "constraints": {
                "width_mm": 250,
                "runtime_min": 90,
                "maximum_speed_mps": 0.3,
            },
        },
    }


def test_product_api_mounts_engineering_routes() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])

    assert "/v1/engineering/schemas" in paths
    assert "/v1/engineering/sources/reconcile" in paths
    assert "/v1/engineering/topology" in paths
    assert "/v1/engineering/analysis" in paths
    assert "/v1/engineering/change-impact" in paths
    assert "/v1/engineering/plan" in paths
    assert "/v1/engineering/plans/save" in paths


def test_engineering_plan_endpoint_synthesizes_bounded_rover_candidate() -> None:
    client = TestClient(create_product_app())

    response = client.post("/v1/engineering/plan", json=_rover_request())

    assert response.status_code == 200, response.text
    body = response.json()
    plan = body["plan"]
    assert plan["archetype"] == "rover"
    assert plan["robot_topology"]["robot_genre"] == "rover"
    assert "engineering_analysis" in plan
    assert plan["machine_project"]["project_id"] == "compact-inspection-rover"
    assert body["engineering_readiness"]["candidate_machine_synthesized"] is True
    assert body["engineering_readiness"]["power_on_authorized"] is False
    assert body["engineering_readiness"]["release_authorized"] is False


def test_engineering_plan_save_persists_one_reviewable_snapshot(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    request = _rover_request()
    request.update({"project_id": "saved-rover", "expected_revision": 0})

    response = client.post("/v1/engineering/plans/save", json=request)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == "saved-rover"
    assert body["revision"] == 1
    saved = store.load("saved-rover")
    snapshot = saved["snapshot"]
    assert snapshot["snapshot_schema_version"] == "hardware_splicer.engineering_project_snapshot.v1"
    assert snapshot["projectId"] == "saved-rover"
    assert snapshot["machineProject"]["project_id"] == "saved-rover"
    assert snapshot["engineeringSourceGraph"]["schema_version"] == "hardware_splicer.engineering_source_graph.v1"
    assert snapshot["robotTopology"]["schema_version"] == "hardware_splicer.robot_topology.v1"
    assert snapshot["engineeringAnalysis"]["schema_version"] == "hardware_splicer.engineering_analysis.v1"
    assert snapshot["changeImpact"]["schema_version"] == "hardware_splicer.change_impact_graph.v1"
    assert snapshot["engineeringReadiness"]["power_on_authorized"] is False


def test_engineering_plan_save_uses_optimistic_revision_checks(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    request = _rover_request()
    request.update({"project_id": "revisioned-rover", "expected_revision": 0})

    first = client.post("/v1/engineering/plans/save", json=request)
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1

    request["expected_revision"] = 1
    second = client.post("/v1/engineering/plans/save", json=request)
    assert second.status_code == 200, second.text
    assert second.json()["revision"] == 2

    stale = client.post("/v1/engineering/plans/save", json=request)
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["type"] == "engineering_plan_revision_conflict"
    assert store.load("revisioned-rover")["revision"] == 2


def test_source_reconciliation_endpoint_keeps_conflict_blocking() -> None:
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/sources/reconcile",
        json={
            "engineering_sources": [
                {
                    "source_id": "manual-a",
                    "source_type": "manual",
                    "revision": "a",
                    "claims": [
                        {
                            "claim_id": "claim-a",
                            "subject_id": "battery",
                            "predicate": "voltage_v",
                            "value": 12,
                        }
                    ],
                },
                {
                    "source_id": "manual-b",
                    "source_type": "manual",
                    "revision": "b",
                    "claims": [
                        {
                            "claim_id": "claim-b",
                            "subject_id": "battery",
                            "predicate": "voltage_v",
                            "value": 24,
                        }
                    ],
                },
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["blocking_conflict_count"] == 1
    assert body["graph"]["conflicts"][0]["blocking"] is True


def test_analysis_endpoint_reports_failures_without_authorizing_operation() -> None:
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/analysis",
        json={
            "intake": {
                "goal": "Revise a rover after tipping and brownout.",
                "available_parts": [{"name": "drive motor", "type": "dc_motor", "quantity": 2}],
                "constraints": {
                    "support_width_mm": 200,
                    "combined_cg_height_mm": 400,
                    "static_tilt_margin_deg": 20,
                    "supply_current_limit_a": 5,
                    "peak_current_a": 12,
                },
            }
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["blocking_finding_count"] >= 2
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_authorized"] is False


def test_change_impact_endpoint_never_restores_release_after_field_failure() -> None:
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/change-impact",
        json={
            "intake": {
                "project_name": "field-rover",
                "goal": "Revise the field rover after tipping and a logic rail brownout.",
                "baseline_revision": 7,
                "available_parts": [
                    {"name": "drive motor", "type": "dc_motor", "quantity": 2},
                    {"name": "camera mast", "type": "mechanical_structure"},
                ],
                "field_failure": "The tall payload caused tipping and the 5 V rail dropped during acceleration.",
            }
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["change_impact"]["mode"] == "field_evolution"
    assert body["blocking_impact_count"] > 0
    assert body["release_authority_preserved"] is False
    assert {"mechanical", "electrical", "control", "safety"}.issubset(
        set(body["affected_domains"])
    )

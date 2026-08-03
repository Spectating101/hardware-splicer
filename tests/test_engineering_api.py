from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def test_product_api_mounts_engineering_routes() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])

    assert "/v1/engineering/schemas" in paths
    assert "/v1/engineering/sources/reconcile" in paths
    assert "/v1/engineering/topology" in paths
    assert "/v1/engineering/change-impact" in paths
    assert "/v1/engineering/plan" in paths


def test_engineering_plan_endpoint_synthesizes_bounded_rover_candidate() -> None:
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/plan",
        json={
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
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    plan = body["plan"]
    assert plan["archetype"] == "rover"
    assert plan["robot_topology"]["robot_genre"] == "rover"
    assert plan["machine_project"]["project_id"] == "compact-inspection-rover"
    assert body["engineering_readiness"]["candidate_machine_synthesized"] is True
    assert body["engineering_readiness"]["power_on_authorized"] is False
    assert body["engineering_readiness"]["release_authorized"] is False


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


def test_change_impact_endpoint_never_restores_release_after_field_failure() -> None:
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/change-impact",
        json={
            "intake": {
                "project_name": "field-rover",
                "goal": "Revise the field rover after tipping and a logic rail brownout.",
                "mode": "evolve",
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
    assert body["blocking_impact_count"] > 0
    assert body["release_authority_preserved"] is False
    assert {"mechanical", "electrical", "control", "safety"}.issubset(
        set(body["affected_domains"])
    )

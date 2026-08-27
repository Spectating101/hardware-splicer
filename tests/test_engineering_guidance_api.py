from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _request() -> dict:
    return {
        "skip_vision": True,
        "intake": {
            "project_name": "guided-api-rover",
            "goal": "Design and build a low-speed indoor inspection rover.",
            "engineering_sources": [
                {
                    "source_id": "motor-datasheet",
                    "source_type": "datasheet",
                    "revision": "rev-c",
                    "authority_ceiling": "declared",
                    "claims": [
                        {
                            "subject_id": "drive-motor",
                            "predicate": "rated_voltage_v",
                            "value": 12,
                        }
                    ],
                }
            ],
            "available_parts": [
                {"name": "drive motor", "type": "dc_motor", "quantity": 2},
                {"name": "battery", "type": "power_source", "quantity": 1},
                {"name": "camera", "type": "camera", "quantity": 1},
            ],
            "constraints": {
                "battery_energy_wh": 100,
                "continuous_power_w": 40,
                "runtime_min": 90,
                "supply_current_limit_a": 10,
                "peak_current_a": 8,
            },
        },
    }


def test_product_mounts_guide_and_source_review_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/guide" in paths
    assert "/v1/engineering/sources/resolve-conflicts" in paths
    assert "/v1/engineering/sources/select-boundary" in paths


def test_guide_endpoint_uses_inline_sources_and_returns_no_operation_authority() -> None:
    response = TestClient(create_product_app()).post(
        "/v1/engineering/guide",
        json=_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    guide = body["operator_guide"]
    assert guide["project_id"] == "guided-api-rover"
    assert len(guide["steps"]) == 15
    assert guide["metadata"]["power_on_authorized"] is False
    assert guide["metadata"]["motion_authorized"] is False
    assert guide["metadata"]["release_authorized"] is False
    assert body["engineering_readiness"]["operator_guide_generated"] is True
    assert body["engineering_readiness"]["source_provenance_complete"] is True


def test_saved_guided_plan_persists_guide_bridge_and_source_adapter(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    request = _request()
    request.update({"project_id": "saved-guided-rover", "expected_revision": 0})

    response = TestClient(create_product_app(store)).post(
        "/v1/engineering/plans/save",
        json=request,
    )

    assert response.status_code == 200, response.text
    snapshot = store.load("saved-guided-rover")["snapshot"]
    assert snapshot["currentStage"] == "guided_engineering_plan"
    assert snapshot["operatorGuide"]["schema_version"] == "hardware_splicer.robot_operator_guide.v1"
    assert snapshot["verificationBridge"]["schema_version"] == "hardware_splicer.engineering_verification_bridge.v1"
    assert snapshot["sourceAdapter"]["schema_version"] == "hardware_splicer.engineering_source_adapter.v1"
    assert snapshot["engineeringReadiness"]["power_on_authorized"] is False
    assert snapshot["engineeringReadiness"]["motion_authorized"] is False
    assert snapshot["engineeringReadiness"]["release_authorized"] is False


def test_source_conflict_review_routes_record_human_decision() -> None:
    client = TestClient(create_product_app())
    graph_response = client.post(
        "/v1/engineering/sources/reconcile",
        json={
            "engineering_sources": [
                {
                    "source_id": "model-v1",
                    "source_type": "cad",
                    "revision": "v1",
                    "claims": [
                        {
                            "claim_id": "claim-v1",
                            "subject_id": "battery",
                            "predicate": "voltage_v",
                            "value": 12,
                        }
                    ],
                },
                {
                    "source_id": "model-v2",
                    "source_type": "cad",
                    "revision": "v2",
                    "claims": [
                        {
                            "claim_id": "claim-v2",
                            "subject_id": "battery",
                            "predicate": "voltage_v",
                            "value": 24,
                        }
                    ],
                },
            ]
        },
    )
    assert graph_response.status_code == 200, graph_response.text
    graph = graph_response.json()["graph"]
    conflict_id = graph["conflicts"][0]["conflict_id"]

    decision_response = client.post(
        "/v1/engineering/sources/resolve-conflicts",
        json={
            "graph": graph,
            "decisions": [
                {
                    "conflict_id": conflict_id,
                    "disposition": "selected",
                    "selected_claim_id": "claim-v2",
                    "reason": "Use the complete v2 electrical revision.",
                    "reviewer": "system-engineer",
                    "reviewed_at": "2026-08-04T02:00:00+08:00",
                }
            ],
        },
    )
    assert decision_response.status_code == 200, decision_response.text
    reviewed = decision_response.json()
    assert reviewed["blocking_conflict_count"] == 0
    conflict = reviewed["graph"]["conflicts"][0]
    assert conflict["selected_claim_id"] == "claim-v2"
    assert conflict["metadata"]["reviewer"] == "system-engineer"


def test_revision_boundary_rejects_mixed_conflicting_revisions() -> None:
    client = TestClient(create_product_app())
    graph = client.post(
        "/v1/engineering/sources/reconcile",
        json={
            "engineering_sources": [
                {
                    "source_id": "model-v1",
                    "source_type": "cad",
                    "revision": "v1",
                    "claims": [
                        {
                            "claim_id": "claim-v1",
                            "subject_id": "battery",
                            "predicate": "voltage_v",
                            "value": 12,
                        }
                    ],
                },
                {
                    "source_id": "model-v2",
                    "source_type": "cad",
                    "revision": "v2",
                    "claims": [
                        {
                            "claim_id": "claim-v2",
                            "subject_id": "battery",
                            "predicate": "voltage_v",
                            "value": 24,
                        }
                    ],
                },
            ]
        },
    ).json()["graph"]

    response = client.post(
        "/v1/engineering/sources/select-boundary",
        json={
            "graph": graph,
            "selection": {
                "selected_source_ids": ["model-v1", "model-v2"],
                "reason": "Attempt to mix both revisions.",
            },
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["blocking_conflict_count"] == 1
    assert response.json()["graph"]["conflicts"][0]["disposition"] == "blocked_pending_revision_selection"

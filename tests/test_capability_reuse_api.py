from __future__ import annotations

from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.capability_reuse_api import create_capability_reuse_router
from hardware_splicer.product_api import create_product_app


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_capability_reuse_router())
    return TestClient(app)


def _project(camera: str = "OV3660") -> dict:
    return {
        "project_id": "vision-project",
        "name": "Vision Core",
        "purpose": "Embedded vision baseline",
        "lifecycle_state": "verify",
        "requested_release_state": "design_ready",
        "subsystems": [
            {
                "subsystem_id": "vision-electrical",
                "name": "Vision electrical",
                "domain": "electrical",
                "component_ids": ["camera"],
            }
        ],
        "components": [
            {
                "component_id": "camera",
                "name": "Camera sensor",
                "domain": "electrical",
                "subsystem_id": "vision-electrical",
                "source": "new",
                "part": {
                    "manufacturer": "OmniVision",
                    "manufacturer_part_number": camera,
                },
                "authority": "declared",
            }
        ],
    }


def _manifest(revision: str, camera: str) -> dict:
    return {
        "schema_version": "hardware_splicer.capability_manifest.v1",
        "capability_id": "vision-core",
        "revision": revision,
        "dependencies": [
            {
                "dependency_id": "component:camera:sensor_identity",
                "kind": "component_identity",
                "resolved": True,
                "value": camera,
            },
            {
                "dependency_id": "interface:wifi:v1",
                "kind": "interface_contract",
                "resolved": True,
                "value": "vision-config-v1",
            },
        ],
    }


def _evidence() -> list[dict]:
    return [
        {
            "evidence_id": "ev-camera",
            "depends_on": ["component:camera:sensor_identity"],
            "dependencies_complete": True,
        },
        {
            "evidence_id": "ev-wifi",
            "depends_on": ["interface:wifi:v1"],
            "dependencies_complete": True,
        },
    ]


def _economics_record() -> dict:
    return {
        "schema_version": "hardware_splicer.derivative_economics.v1",
        "currency": "TWD",
        "labor_rate_per_hour": 500,
        "comparison": {
            "mode": "parallel_cleanroom",
            "baseline_requirements_hash": "sha256:req",
            "reuse_requirements_hash": "sha256:req",
            "baseline_exit_criteria_hash": "sha256:exit",
            "reuse_exit_criteria_hash": "sha256:exit",
            "inputs_frozen_before_execution": True,
            "reuse_result_hidden_from_baseline": True,
            "baseline_private_reuse_assets_excluded": True,
            "intervention_log_complete": True,
            "same_measurement_policy": True,
        },
        "baseline": {
            "completion_state": "completed",
            "human_active_hours": 20,
            "elapsed_hours": 30,
            "model_tool_cost": 1000,
            "external_service_cost": 500,
            "development_consumables_cost": 1500,
            "physical_retest_hours": 8,
            "authority_violations": 0,
        },
        "reuse": {
            "completion_state": "completed",
            "human_active_hours": 6,
            "elapsed_hours": 12,
            "model_tool_cost": 700,
            "external_service_cost": 200,
            "development_consumables_cost": 900,
            "physical_retest_hours": 3,
            "authority_violations": 0,
        },
        "hypothesis_gate": {},
    }


def test_freeze_endpoint_projects_canonical_machine_project() -> None:
    response = _client().post(
        "/v1/capabilities/freeze",
        json={
            "project": _project(),
            "project_revision": "project-r7",
            "capability_id": "vision-core",
            "revision": "vision-a-r1",
            "dependency_specs": [
                {
                    "object_id": "camera",
                    "dependency_id": "component:camera:sensor_identity",
                    "resolved": True,
                }
            ],
        },
    )

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["status"] == "machine_project_projection"
    assert manifest["source_boundary"]["project_content_hash"].startswith("sha256:")
    assert manifest["metadata"]["alternate_engineering_truth_store"] is False


def test_derive_and_adjudicate_endpoints_preserve_frozen_prediction_hash() -> None:
    client = _client()
    prediction_response = client.post(
        "/v1/capabilities/derive",
        json={
            "baseline_manifest": _manifest("a", "OV2640"),
            "candidate_manifest": _manifest("b", "OV3660"),
            "inherited_evidence_items": _evidence(),
        },
    )
    assert prediction_response.status_code == 200
    prediction = prediction_response.json()
    assert prediction["prediction_hash"].startswith("sha256:")

    adjudication_response = client.post(
        "/v1/capabilities/derive/adjudicate",
        json={
            "prediction": prediction,
            "expected_invalidated_evidence_ids": ["ev-camera"],
            "adjudicator": "outer-reviewer",
            "adjudication_basis": "independent dependency audit",
        },
    )
    assert adjudication_response.status_code == 200
    adjudication = adjudication_response.json()
    assert adjudication["prediction_hash"] == prediction["prediction_hash"]
    assert adjudication["score"]["correctly_invalidated_count"] == 1
    assert adjudication["score"]["unnecessarily_invalidated_count"] == 0


def test_adjudication_endpoint_rejects_tampered_prediction() -> None:
    client = _client()
    prediction = client.post(
        "/v1/capabilities/derive",
        json={
            "baseline_manifest": _manifest("a", "OV2640"),
            "candidate_manifest": _manifest("b", "OV3660"),
            "inherited_evidence_items": _evidence(),
        },
    ).json()
    tampered = deepcopy(prediction)
    tampered["impact_report"]["results"][0]["status"] = "retained"

    response = client.post(
        "/v1/capabilities/derive/adjudicate",
        json={
            "prediction": tampered,
            "expected_invalidated_evidence_ids": ["ev-camera"],
            "adjudicator": "outer-reviewer",
            "adjudication_basis": "independent dependency audit",
        },
    )

    assert response.status_code == 422
    assert "prediction_hash_mismatch" in response.json()["detail"]["error"]["validation_errors"]


def test_derivative_metrics_endpoint_does_not_upgrade_physical_authority() -> None:
    response = _client().post(
        "/v1/capabilities/derivative-metrics",
        json={
            "record": {
                "schema_version": "hardware_splicer.platform_derivative_evidence.v1",
                "artifact_accounting": {
                    "validated_artifact_count_total": 10,
                    "validated_artifact_count_inherited": 8,
                    "validated_artifact_count_new_or_changed": 2,
                },
                "evidence_accounting": {
                    "required_evidence_count": 20,
                    "valid_inherited_evidence_count": 14,
                    "invalidated_inherited_evidence_count": 6,
                    "should_invalidate_inherited_evidence_count": 6,
                    "unnecessarily_invalidated_evidence_count": 0,
                },
                "effort_accounting": {
                    "baseline_type": "measured",
                    "baseline_independent_build_hours": 100,
                    "derivative_engineering_hours": 30,
                },
                "physical_retest": {
                    "blank_slate_test_count": 10,
                    "tests_reused_or_safely_waived": 6,
                    "tests_rerun": 4,
                },
                "authority": {"violations": 0},
                "hypothesis_gate": {},
            }
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["hypothesis_gate"]["result"] == "PASS"
    assert report["metadata"]["physical_authority_granted"] is False
    assert report["metadata"]["automatic_authorization"] is False


def test_derivative_economics_endpoint_evaluates_cleanroom_comparator_only() -> None:
    response = _client().post(
        "/v1/capabilities/derivative-economics",
        json={"record": _economics_record()},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["hypothesis_gate"]["result"] == "PASS"
    assert report["metrics"]["human_intervention_ratio"] == 0.3
    assert report["metadata"]["production_unit_economics_proven"] is False
    assert report["metadata"]["physical_authority_granted"] is False


def test_routes_are_mounted_on_canonical_product_app() -> None:
    paths = {getattr(route, "path", None) for route in create_product_app().routes}

    assert "/v1/capabilities/freeze" in paths
    assert "/v1/capabilities/derive" in paths
    assert "/v1/capabilities/derive/adjudicate" in paths
    assert "/v1/capabilities/derivative-metrics" in paths
    assert "/v1/capabilities/derivative-economics" in paths

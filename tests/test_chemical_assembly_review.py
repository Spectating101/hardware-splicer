from __future__ import annotations

import asyncio
import copy

import pytest
from fastapi.testclient import TestClient

from eval.chemical_materials.three_layer_enclosure_v1 import request_body, run, scenarios
from hardware_splicer.mcp_backend_gateway import operation_catalog, dispatch_operation, task_operation_manifest
from hardware_splicer.product_api import create_product_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_product_app())


def test_three_layer_declared_screen_is_not_physical_validation(client):
    result = client.post("/v1/engineering/chemical/enclosure/assembly-review",
                         json=request_body())
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["result"] == "bounded_assembly_screen_consistent_but_unverified"
    assert not data["project_modified"]
    assert data["material"]["selected_screen"]["component_id"] == "candidate-pc_blend"
    assert data["material"]["selected_screen"]["passed_numeric_criteria"] == 2
    assert data["mechanical"]["geometry_computed_check_count"] >= 1
    assert data["mechanical"]["fit_computed_check_count"] >= 1
    assert data["mechanical"]["fit_failed_check_ids"] == []
    assert data["electrical"]["erc_error_count"] == 0
    assert data["required_next_validation"]
    for field in (
        "build_readiness_authorized", "release_authorized",
        "material_compatibility_verified", "fabrication_authorized",
        "thermal_safety_evaluated", "electrical_insulation_evaluated",
        "full_brep_collision_evaluated",
    ):
        assert data[field] is False, field


def test_three_layer_local_benchmark_all_expected_checks():
    report = run()
    assert report["passing_count"] == report["scenario_count"] == 11
    indexed = {row["scenario"]: row for row in report["scenarios"]}
    assert "electrical_rule_errors" in indexed["electrical_driver_conflict"]["finding_codes"]
    assert "mechanical_fit_blocked" in indexed["actual_declared_collision"]["finding_codes"]
    assert "incomparable_candidate_criteria" in indexed["unequal_material_constraints"]["finding_codes"]
    assert "electrical_component_identity_unmapped" in indexed["unmapped_electrical_component"]["finding_codes"]
    assert "board_enclosure_mount_pair_missing" in indexed["disconnected_selected_mount"]["finding_codes"]


def test_malformed_geometry_pass_status_is_not_authority(client):
    scenario = next(s for s in scenarios() if s["id"] == "forged_pass_report")
    result = client.post("/v1/engineering/chemical/enclosure/assembly-review",
                         json=scenario["body"])
    assert result.status_code == 200
    actual = result.json()
    assert actual["result"] == "assembly_screen_blocked"
    assert actual["mechanical"]["fit_failed_check_ids"]


def test_three_layer_rejects_cross_project_identity(client):
    data = request_body()
    data["electrical_design"]["project_id"] = "different-project"
    result = client.post("/v1/engineering/chemical/enclosure/assembly-review",
                         json=data)
    assert result.status_code == 422
    assert result.json()["detail"]["type"] == "invalid_chemical_model_input"


def test_three_layer_untracked_electrical_component_blocks(client):
    data = request_body()
    data["electrical_design"]["components"][1]["component_id"] = "outside"
    data["electrical_design"]["pins"][1]["component_id"] = "outside"
    result = client.post("/v1/engineering/chemical/enclosure/assembly-review",
                         json=data)
    assert result.status_code == 200
    assert any(row["code"] == "electrical_component_identity_unmapped"
               for row in result.json()["blocking_findings"])


def test_three_layer_is_mcp_callable_and_manifest_discoverable(client):
    ops = operation_catalog(client.app)
    op = next(row for row in ops
              if row["path"] == "/v1/engineering/chemical/enclosure/assembly-review")
    result = asyncio.run(dispatch_operation(
        op["operation_id"], app=client.app, json_body=request_body()))
    assert result["status_code"] == 200
    assert result["body"]["result"] == "bounded_assembly_screen_consistent_but_unverified"
    manifest = task_operation_manifest("chemical_enclosure_assembly", client.app)
    assert op["operation_id"] in manifest["workflow_operation_ids"]
    assert not manifest["authority_contract"]["automatic_execution"]


@pytest.mark.parametrize("selection", [
    "candidate-asa", "missing-candidate",
])
def test_invalid_or_blocked_selected_material_never_yields_build_auth(client, selection):
    data = request_body()
    data["selected_enclosure_id"] = selection
    result = client.post("/v1/engineering/chemical/enclosure/assembly-review", json=data)
    assert result.status_code in {200, 422}
    if result.status_code == 200:
        assert not result.json()["build_readiness_authorized"]
        assert result.json()["result"] == "assembly_screen_blocked"



def test_nan_clearance_box_cannot_fake_a_pass(client):
    data = request_body()
    data["clearance_boxes"][1]["minimum_mm"][2] = float("nan")
    from hardware_splicer.chemical_api import EnclosureAssemblyReviewRequest
    from hardware_splicer.chemical_assembly_review import review_enclosure_assembly
    request = EnclosureAssemblyReviewRequest.model_validate(data)
    with pytest.raises(ValueError, match="Nonfinite"):
        review_enclosure_assembly(**{
            name: getattr(request, name) for name in request.model_fields
        })


def test_nan_electrical_limits_rejected(client):
    data = request_body()
    data["electrical_design"]["nets"][0]["voltage_min_v"] = float("nan")
    from hardware_splicer.chemical_api import EnclosureAssemblyReviewRequest
    from hardware_splicer.chemical_assembly_review import review_enclosure_assembly
    request = EnclosureAssemblyReviewRequest.model_validate(data)
    with pytest.raises(ValueError, match="Nonfinite"):
        review_enclosure_assembly(**{
            name: getattr(request, name) for name in request.model_fields
        })

from __future__ import annotations

import asyncio
import copy
import math
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from eval.practical_chemistry.decision_benchmark_v1 import run, scenarios
from hardware_splicer.mcp_backend_gateway import (
    dispatch_operation, operation_catalog, task_operation_manifest,
)
from hardware_splicer.practical_chemistry import (
    assess_practical_chemistry, catalog, practical_catalog_summary,
)
from hardware_splicer.product_api import create_product_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_product_app())


def job(**overrides):
    return {
        "task": "bond_joint", "primary_material": "PP",
        "material_identity": "verified",
        "battery_status": "removed", "electrical_state": "off",
        **overrides,
    }


def test_catalog_sources_real_and_no_unattributed_proposals():
    report = catalog()
    assert report["schema_version"].endswith(".v1")
    assert len(report["sources"]) >= 10
    assert len(report["methods"]) >= 10
    for source in report["sources"]:
        assert source["id"] and source["scope"] and source["claim"]
        u = urlparse(source["url"])
        assert u.scheme == "https" and u.netloc and not u.netloc.endswith(".invalid")
    ids = {entry["id"] for entry in report["sources"]}
    for method in report["methods"]:
        assert method["source_ids"]
        assert all(source in ids for source in method["source_ids"])
        assert method["failure_modes"] and method["validation"]
        assert method["cost_class"]
    assert practical_catalog_summary()["source_claims_unverified_against_current_revisions"]


def test_practical_benchmark_all_curated_adversarial_cases():
    result = run()
    assert result["cases_total"] == len(scenarios()) == 31
    assert result["cases_passed"] == result["cases_total"], [
        row for row in result["cases"] if not row["pass"]
    ]


def test_pp_has_specific_family_claim_not_generic_epoxy():
    report = assess_practical_chemistry(**job())
    by_id = {option["approach_id"]: option for option in report["approaches"]}
    assert report["decision"] == "options_for_validation"
    assert by_id["polyolefin_dp8010"]["status"] == "candidate_for_validation"
    assert by_id["polyolefin_dp8010"]["source_claims"][0]["publisher"] == "3M"
    assert by_id["engineered_plastic_dp100"]["status"] == "blocked"
    assert "no_evidence_for_target_substrate" in by_id["engineered_plastic_dp100"]["hard_blockers"]
    assert report["selected_method"] is None
    assert not report["ready_to_execute_steps"]
    assert not report["chemical_handling_authorized"]


@pytest.mark.parametrize("battery_status", ["damaged", "installed", "unknown"])
def test_battery_hazards_stop_board_cleaner(battery_status):
    report = assess_practical_chemistry(
        task="clean_flux", primary_material="FR4", material_identity="verified",
        electrical_state="off", battery_status=battery_status,
        keepouts_confirmed=True,
    )
    assert report["decision"] == "stop_and_escalate"
    assert report["candidate_approach_ids_for_validation"] == []
    assert all(method["status"] == "blocked" for method in report["approaches"])


def test_energized_adhesive_never_approved():
    report = assess_practical_chemistry(**job(electrical_state="energized"))
    assert report["decision"] == "stop_and_escalate"
    assert not report["candidate_approach_ids_for_validation"]


def test_unknown_grade_or_adjacent_material_disables_direct_candidate():
    unconfirmed = assess_practical_chemistry(**job(material_identity="claimed"))
    pp = next(m for m in unconfirmed["approaches"] if m["approach_id"] == "polyolefin_dp8010")
    assert pp["status"] == "research_required"
    flux = assess_practical_chemistry(
        task="clean_flux", primary_material="FR4", material_identity="verified",
        battery_status="removed", electrical_state="off", keepouts_confirmed=True,
        adjacent_materials=["unknown"],
    )
    assert flux["decision"] == "research_or_replace"
    assert flux["candidate_approach_ids_for_validation"] == []


def test_required_zero_residue_excludes_lubricated_contact_cleaner():
    outcome = assess_practical_chemistry(
        task="clean_contacts", primary_material="gold_contact",
        material_identity="verified", battery_status="removed",
        electrical_state="off", residue_tolerance="none",
    )
    options = {entry["approach_id"]: entry for entry in outcome["approaches"]}
    assert options["contact_clean_801b"]["status"] == "blocked"
    assert "residual_film_prohibited" in options["contact_clean_801b"]["hard_blockers"]
    assert options["contact_clean_409b"]["status"] == "candidate_for_validation"


def test_coating_without_keepouts_is_research_not_ready():
    report = assess_practical_chemistry(
        task="coat_pcb", primary_material="FR4",
        material_identity="verified", battery_status="removed",
        electrical_state="off",
    )
    assert report["decision"] == "research_or_replace"
    for entry in report["approaches"]:
        assert "unplanned_masking" in entry["conditions_to_research_before_trial"]


def test_aggressive_asa_solvent_not_automatically_trial_ready():
    report = assess_practical_chemistry(
        task="finish_surface", primary_material="ASA",
        material_identity="verified", battery_status="removed",
        electrical_state="off", keepouts_confirmed=True,
    )
    assert report["candidate_approach_ids_for_validation"] == []
    item = report["approaches"][0]
    assert item["status"] == "research_required"
    assert "aggressive_solvent_specialist_review_required" in item["conditions_to_research_before_trial"]


def test_real_economic_calculation_uses_only_supplied_failure_path():
    report = assess_practical_chemistry(**job(
        currency="TWD",
        cost_quotes={"polyolefin_dp8010": {
            "consumables_cost": 180, "labor_minutes": 50,
            "hourly_labor_cost": 300, "testing_cost": 50,
            "equipment_allocation": 20, "replacement_cost": 700,
            "probability_of_success": 0.8,
            "failed_attempt_disposal_cost": 40,
        }}
    ))
    selected = next(e for e in report["approaches"] if e["approach_id"] == "polyolefin_dp8010")
    economic = selected["economics"]
    assert economic["currency"] == "TWD"
    assert economic["declared_attempt_cost"] == 500
    assert economic["conditional_expected_total_cost"] == 648
    assert economic["break_even_success_probability_min_exclusive"] == 0.72973
    assert economic["conditional_expected_cost_below_direct_replacement"]
    assert economic["probability_source"] == "caller_assumption_not_estimated_by_hs"
    assert report["selected_method"] is None


def test_low_success_probability_changes_cost_result_not_chemical_eligibility():
    def analyze(p):
        return assess_practical_chemistry(**job(
            cost_quotes={"polyolefin_dp8010": {
                "consumables_cost": 180, "labor_minutes": 50,
                "hourly_labor_cost": 300, "testing_cost": 50,
                "equipment_allocation": 20, "replacement_cost": 700,
                "probability_of_success": p,
                "failed_attempt_disposal_cost": 40,
            }}
        ))["approaches"][0]
    low = analyze(.5)
    high = analyze(.9)
    assert not low["economics"]["conditional_expected_cost_below_direct_replacement"]
    assert high["economics"]["conditional_expected_cost_below_direct_replacement"]
    assert low["status"] == high["status"] == "candidate_for_validation"


def test_no_probability_no_fake_expected_value():
    report = assess_practical_chemistry(**job(
        cost_quotes={"polyolefin_dp8010": {
            "consumables_cost": 180, "labor_minutes": 50,
            "hourly_labor_cost": 300, "testing_cost": 50,
            "equipment_allocation": 20, "replacement_cost": 700,
            "failed_attempt_disposal_cost": 40,
        }}
    ))
    econ = next(x for x in report["approaches"] if x["approach_id"] == "polyolefin_dp8010")["economics"]
    assert econ["conditional_expected_total_cost"] is None
    assert econ["break_even_success_probability_min_exclusive"] == 0.72973
    assert not econ["failure_path_and_probability_verified"]


@pytest.mark.parametrize("invalid", [
    {"consumables_cost": -1, "labor_minutes": 1, "hourly_labor_cost": 1,
     "testing_cost": 1, "equipment_allocation": 1},
    {"consumables_cost": 1, "labor_minutes": float("nan"), "hourly_labor_cost": 1,
     "testing_cost": 1, "equipment_allocation": 1},
    {"consumables_cost": 1, "labor_minutes": 1, "hourly_labor_cost": 1,
     "testing_cost": 1, "equipment_allocation": 1, "probability_of_success": .5},
    {"consumables_cost": 1, "labor_minutes": 1, "hourly_labor_cost": 1,
     "testing_cost": 1, "equipment_allocation": 1, "probability_of_success": 1.1,
     "replacement_cost": 100, "failed_attempt_disposal_cost": 1},
])
def test_invalid_cost_assumptions_fail_closed(invalid):
    with pytest.raises(ValueError):
        assess_practical_chemistry(**job(cost_quotes={"polyolefin_dp8010": invalid}))


def test_unmatched_economics_approach_rejected():
    with pytest.raises(ValueError):
        assess_practical_chemistry(**job(
            cost_quotes={"fictional_chemical": {"consumables_cost": 100,
                         "labor_minutes": 10, "hourly_labor_cost": 100,
                         "testing_cost": 5, "equipment_allocation": 5}}
        ))


def test_practical_api_and_canonical_mcp_calls(client):
    data = job()
    catalog_response = client.get("/v1/engineering/chemical/practical/catalog")
    assert catalog_response.status_code == 200, catalog_response.text
    assert catalog_response.json()["approach_count"] >= 10
    response = client.post("/v1/engineering/chemical/practical/assess", json=data)
    assert response.status_code == 200, response.text
    assert response.json()["candidate_approach_ids_for_validation"] == ["polyolefin_dp8010"]
    op = next(row for row in operation_catalog(client.app)
              if row["path"] == "/v1/engineering/chemical/practical/assess")
    result = asyncio.run(dispatch_operation(op["operation_id"], app=client.app, json_body=data))
    assert result["status_code"] == 200
    assert result["body"]["selected_method"] is None
    manifest = task_operation_manifest("practical_chemistry_repair", app=client.app)
    assert op["operation_id"] in manifest["workflow_operation_ids"]
    assert not manifest["authority_contract"]["automatic_execution"]


def test_practical_api_validation_is_bounded(client):
    response = client.post("/v1/engineering/chemical/practical/assess", json={
        **job(), "primary_material": "my-invented-material",
    })
    assert response.status_code == 422
    response = client.post("/v1/engineering/chemical/practical/assess", json={
        **job(), "service_temperature_c": 2000,
    })
    assert response.status_code == 422



def test_omitted_electrical_and_battery_status_never_assumed_safe(client):
    reply = client.post("/v1/engineering/chemical/practical/assess", json={
        "task": "clean_flux", "primary_material": "FR4",
        "material_identity": "verified", "keepouts_confirmed": True,
    })
    assert reply.status_code == 200, reply.text
    data = reply.json()
    assert data["decision"] == "stop_and_escalate"
    assert "power_not_confirmed_isolated" in data["global_blockers"]
    assert "battery_not_confirmed_removed" in data["global_blockers"]
    assert data["candidate_approach_ids_for_validation"] == []

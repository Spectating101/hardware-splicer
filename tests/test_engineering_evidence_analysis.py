"""Evidence-aware restoration and multi-donor hypothesis analysis."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.engineering_mission_contract import normalize_engineering_mission
from hardware_splicer.engineering_repair_differential import repair_differential
from hardware_splicer.engineering_multi_donor_compatibility import evaluate_multi_donor_compatibility
from hardware_splicer.project_intake import plan_project_from_intake, splice_and_build_from_intake

ROOT=Path(__file__).resolve().parents[1]


def scenario(name):
    return json.loads((ROOT/"examples"/"dual_track"/name).read_text(encoding="utf-8"))


def novel():
    body=scenario("splice_four_marketplace_donors_unverified.json")
    return normalize_engineering_mission(body),body["engineering_materials"]


def test_repair_differential_references_actual_zebra_family_manual():
    body=scenario("repair_ls2208_unverified.json")
    mission=normalize_engineering_mission(body)
    result=repair_differential(mission,body["repair_intake"])
    assert result["profile_id"]=="zebra_symbol_ls2208"
    assert result["manufacturer_reference"]["url"].startswith("https://www.zebra.com/")
    assert result["source_status"]=="manufacturer_family_manual_plus_unverified_seller_report"
    assert result["root_cause_verified"] is False
    assert result["may_perform_repair_or_power"] is False
    assert "host" in " ".join(result["family_documentation_facts"]).lower()


def test_reported_cut_cable_prioritizes_cable_hypothesis_but_doesnt_diagnose():
    body=scenario("repair_ls2208_unverified.json")
    result=repair_differential(normalize_engineering_mission(body),body["repair_intake"])
    first=result["alternative_hypotheses"][0]
    assert first["hypothesis_id"]=="severed_interface_cable"
    assert first["priority"]=="investigate_early"
    assert first["root_cause_proven"] is False
    assert len(result["alternative_hypotheses"])==4
    assert all(not x["supported_diagnosis"] for x in result["alternative_hypotheses"])


def test_unrecognized_device_does_not_match_ls2208_profile():
    body=scenario("repair_ls2208_unverified.json")
    mission=normalize_engineering_mission(body)
    mission["original_device"]="Unknown damaged appliance"
    result=repair_differential(mission,body["repair_intake"])
    assert result["alternative_hypotheses"]==[]
    assert result["root_cause_verified"] is False


def test_four_donor_proposal_maps_distinct_sources_and_explicit_function_tags():
    mission, materials=novel()
    report=evaluate_multi_donor_compatibility(mission,materials)
    assert report["candidate_count"]==4
    assert report["distinct_source_hypotheses"]==4
    assert report["verified_distinct_physical_donors"]==0
    assert len(report["proposed_interfaces"])==3
    assert report["all_proposed_links_physically_blocked"] is True
    assert all(not c["verified_functional_coverage"] for c in report["function_coverage"])
    assert [r["coverage_status"] for r in report["function_coverage"]]==[
        "HYPOTHESIZED_NOT_VERIFIED","HYPOTHESIZED_NOT_VERIFIED",
        "HYPOTHESIZED_NOT_VERIFIED","PARTIAL_CLAIM_GAP",
    ]
    assert all(not link["safe_to_wire"] for link in report["proposed_interfaces"])


def test_apple_mouse_button_cannot_count_as_verified_emergency_stop():
    mission,material=novel()
    report=evaluate_multi_donor_compatibility(mission,material)
    stop=next(r for r in report["function_coverage"] if "stop" in r["required_function"])
    assert stop["candidate_hypotheses"]==[]
    assert stop["partial_candidate_hypotheses"]==["mouse_button_switch"]
    assert stop["coverage_status"]=="PARTIAL_CLAIM_GAP"


def test_missing_protocol_voltage_connector_blocks_speculative_interfaces():
    mission,material=novel()
    report=evaluate_multi_donor_compatibility(mission,material)
    assert all(l["comparison_status"]=="BLOCKED_UNKNOWN_INTERFACE" for l in report["proposed_interfaces"])
    assert all(len(l["missing_interface_facts"])>=2 for l in report["proposed_interfaces"])


def test_declaration_mismatch_is_a_review_flag_not_measurement_or_authority():
    mission,material=novel()
    data=copy.deepcopy(material)
    data["component_hypotheses"][0]["interface"]={"protocol":"USB","voltage_v":5.0,"connector":"A"}
    data["component_hypotheses"][2]["interface"]={"protocol":"UART","voltage_v":3.3,"connector":"B"}
    report=evaluate_multi_donor_compatibility(mission,data)
    link=next(l for l in report["proposed_interfaces"] if l["connection_id"]=="scanner_to_compute")
    assert link["comparison_status"]=="DECLARED_MISMATCH_NEEDS_ENGINEER"
    assert sorted(link["declared_mismatch_fields"])==["protocol","voltage_v"]
    assert link["safe_to_wire"] is False


def test_declared_matching_specs_never_prove_wiring():
    mission,material=novel()
    data=copy.deepcopy(material)
    for index in [0,2]:
        data["component_hypotheses"][index]["interface"]={"protocol":"USB","voltage_v":5.0,"connector":"A"}
    report=evaluate_multi_donor_compatibility(mission,data)
    link=next(l for l in report["proposed_interfaces"] if l["connection_id"]=="scanner_to_compute")
    assert link["comparison_status"]=="PAPER_ONLY_MATCH_UNVERIFIED"
    assert link["electrical_connection_proven"] is False
    assert report["can_claim_new_product"] is False


@pytest.mark.parametrize("bad",[
    {"verified":True},
    {"physical_evidence":"I measured it"},
    {"authorized_for_fabrication":True},
    {"safe_to_wire":True},
])
def test_caller_cannot_smuggle_verified_status_into_hypothesis(bad):
    mission,material=novel()
    data=copy.deepcopy(material)
    data["component_hypotheses"][0].update(bad)
    with pytest.raises(ValueError):
        evaluate_multi_donor_compatibility(mission,data)


def test_wrong_donor_ref_is_refused_not_reassigned_to_other_donor():
    mission,material=novel()
    data=copy.deepcopy(material)
    data["component_hypotheses"][0]["source_ref"]="ruten:something_else"
    with pytest.raises(ValueError,match="non-mission"):
        evaluate_multi_donor_compatibility(mission,data)


def test_duplicate_candidate_id_is_refused():
    mission,material=novel()
    data=copy.deepcopy(material)
    data["component_hypotheses"][1]["candidate_id"]=data["component_hypotheses"][0]["candidate_id"]
    with pytest.raises(ValueError,match="duplicate"):
        evaluate_multi_donor_compatibility(mission,data)


def test_arbitrary_required_function_must_match_exact_tag():
    mission,material=novel()
    data=copy.deepcopy(material)
    data["component_hypotheses"][0]["function_tags"]=["decoding things maybe"]
    with pytest.raises(ValueError,match="required_functions"):
        evaluate_multi_donor_compatibility(mission,data)


def test_empty_materials_fail_coverage_without_fake_components():
    mission,_=novel()
    report=evaluate_multi_donor_compatibility(mission,None)
    assert report["candidate_count"]==0
    assert all(c["coverage_status"]=="UNMAPPED_GAP" for c in report["function_coverage"])


def test_direct_project_plan_embeds_analyzed_unverified_compatibility(monkeypatch):
    monkeypatch.setenv("QWEN_DISABLED","1")
    plan=plan_project_from_intake(scenario("splice_four_marketplace_donors_unverified.json"),skip_vision=True)
    report=plan["multi_donor_compatibility"]
    assert report["candidate_count"]==4
    assert report["verified_distinct_physical_donors"]==0
    assert plan["engineering_mission"]["type"]=="novel_splice"


def test_repair_build_serializes_hypotheses_without_unrelated_circuit(tmp_path):
    body=scenario("repair_ls2208_unverified.json")
    result=splice_and_build_from_intake(body,out_dir=tmp_path/"repair",export_gerber=False)
    diag=result["repair_investigation"]["differential_diagnosis"]
    assert diag["profile_id"]=="zebra_symbol_ls2208"
    assert diag["root_cause_verified"] is False
    assert len(diag["alternative_hypotheses"])==4
    assert not (tmp_path/"repair"/"build_compilation").exists()


def test_multi_donor_build_writes_compatibility_artifact_but_no_physical_pass(tmp_path,monkeypatch):
    monkeypatch.setenv("QWEN_DISABLED","1")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_DISABLED","1")
    body=scenario("splice_four_marketplace_donors_unverified.json")
    result=splice_and_build_from_intake(body,out_dir=tmp_path/"splice",export_gerber=False)
    assert result["compile_ok"] is True
    assert result["mission_success"] is False
    report=result["multi_donor_compatibility"]
    assert report["candidate_count"]==4
    assert report["verified_distinct_physical_donors"]==0
    path=Path(result["artifacts"]["multi_donor_compatibility"])
    assert path.is_file()
    assert json.loads(path.read_text())["can_claim_new_product"] is False

"""Independent restoration-versus-novel-product evidence gates."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.engineering_mission_contract import (
    evaluate_engineering_mission,
    normalize_engineering_mission,
)
from hardware_splicer.project_intake import (
    plan_project_from_intake,
    splice_and_build_from_intake,
)

ROOT = Path(__file__).resolve().parents[1]


def _source(file):
    return json.loads((ROOT / "examples" / "dual_track" / file).read_text(encoding="utf-8"))


def test_no_implicit_repair_mission_from_repair_intake_or_fixture():
    # The historical "repair cafe" demo is actually RC splicing;
    # don't silently rebrand it as original function repair.
    intake = json.loads((ROOT/"examples/intakes/splice_robot_drive_vision_repair_brief.json").read_text())
    assert "repair_intake" in intake
    assert normalize_engineering_mission(intake) is None


def test_restore_contract_is_unambiguous():
    mission = normalize_engineering_mission(_source("repair_ls2208_unverified.json"))
    assert mission["type"] == "restorative_repair"
    assert mission["original_device"] == "Symbol LS2208 barcode scanner"
    assert mission["source_refs_are_physical_evidence"] is False
    assert len(mission["source_refs"]) == 1


def test_new_product_has_distinct_requirement_list_and_multiple_sources():
    mission = normalize_engineering_mission(_source("splice_four_marketplace_donors_unverified.json"))
    assert mission["type"] == "novel_splice"
    assert len(mission["source_refs"]) == 4
    assert len(mission["required_functions"]) == 4
    assert mission["minimum_distinct_donors"] == 2


@pytest.mark.parametrize("mission", [
    {"type":"restorative_repair","original_device":"scanner","original_function":"scan","source_refs":["x","y"]},
    {"type":"novel_splice","new_product":"scanner machine","source_refs":["x"],"required_functions":["scan","move"]},
    {"type":"novel_splice","new_product":"machine","source_refs":["a","b"],"required_functions":["scan","move"],"minimum_distinct_donors":True},
    {"type":"novel_splice","new_product":"machine","source_refs":["a","a"],"required_functions":["scan","move"]},
    {"type":"restorative_repair","original_device":"scanner","original_function":"scan","source_refs":["x"],"mission_success":True},
    {"type":"restorative_repair","original_device":"scanner","original_function":"scan","source_refs":["x"],"physical_authority_granted":True},
    {"type":"repair","original_device":"scanner","original_function":"scan","source_refs":["x"]},
])
def test_invalid_or_user_forged_authority_refused(mission):
    with pytest.raises(ValueError):
        normalize_engineering_mission({"engineering_mission":mission})


@pytest.mark.parametrize("mode", ["restorative_repair","novel_splice"])
def test_compile_and_preloaded_circuit_cannot_prove_a_physical_mission(mode):
    mission=normalize_engineering_mission(_source(
        "repair_ls2208_unverified.json" if mode=="restorative_repair"
        else "splice_four_marketplace_donors_unverified.json"
    ))
    report=evaluate_engineering_mission(mission,build_id="robot_drive_base",
        compiler_passed=True,salvage_package={"splice_plan":{"reusable_blocks":[
            {"source":"circuit_functional_salvage","name":"preloaded fixture"},
        ]}})
    assert report["compile"]["carrier_compile_passed"] is True
    assert report["compile"]["circuit_backed_fixture_or_candidate_blocks"]==1
    assert report["compile"]["circuit_backed_blocks_prove_physical_function"] is False
    assert report["mission_success"] is False
    assert report["verified_interface_count_from_this_execution"]==0
    assert not report["human_operator_physical_authority_granted"]
    assert len(report["open_acceptance_gates"])>=4


def test_intake_plan_preserves_mission_truth_independent_of_recommendation(monkeypatch):
    monkeypatch.setenv("QWEN_DISABLED","1")
    intake=_source("repair_ls2208_unverified.json")
    plan=plan_project_from_intake(intake,skip_vision=True)
    assert plan["engineering_mission"]["type"]=="restorative_repair"
    assert plan["engineering_mission"]["original_function"].startswith("scan a barcode")
    assert plan["engineering_mission"]["physical_authority_granted"] is False
    assert plan["planning_mode"] == "repair_investigation_only"
    assert plan["recommended_build_id"] is None
    assert plan["compilation_authorized_from_diagnostic_plan"] is False


def test_explicit_repair_build_prohibits_unrelated_fallback_circuit(tmp_path,monkeypatch):
    monkeypatch.setenv("QWEN_DISABLED","1")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_DISABLED","1")
    intake=_source("repair_ls2208_unverified.json")
    result=splice_and_build_from_intake(intake,out_dir=tmp_path/"repair",export_gerber=False)
    # An original-function repair must NOT compile an unrelated adapter.
    assert result["ok"] is False
    assert result["compile_ok"] is False
    assert result["build_id"] is None
    assert result["mission_success"] is False
    assert not (tmp_path/"repair"/"build_compilation").exists()
    assert result["repair_investigation"]["candidate_fault_root_cause"] is None
    assert result["repair_investigation"]["repair_instructions_validated"] is False
    assert Path(result["artifacts"]["repair_investigation"]).exists()
    eval=result["engineering_mission_evaluation"]
    assert eval["type"]=="restorative_repair"
    assert eval["mission_success"] is False
    path=Path(result["artifacts"]["engineering_mission_evaluation"])
    assert path.exists()
    assert json.loads(path.read_text())["verdict"].startswith("BLOCKED")


def test_explicit_splice_build_emits_blocked_truth_even_with_drc_pass(tmp_path,monkeypatch):
    monkeypatch.setenv("QWEN_DISABLED","1")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_DISABLED","1")
    intake=_source("splice_four_marketplace_donors_unverified.json")
    result=splice_and_build_from_intake(intake,out_dir=tmp_path/"splice",export_gerber=False)
    assert result["ok"] is False  # New-product mission not actually completed
    assert result["compile_ok"] is True  # But intermediate carrier CAD compiled
    assert result["mission_success"] is False
    eval=result["engineering_mission_evaluation"]
    assert eval["type"]=="novel_splice"
    assert eval["compile"]["carrier_compile_passed"] is True
    assert eval["verified_physical_donor_count_from_this_execution"]==0
    assert eval["new_product_functionally_tested"] is False
    assert len(eval["source_refs"])==4


def test_scenario_runner_repair_mode_does_not_fall_into_generic_engine(tmp_path):
    from hardware_splicer.project_intake import run_project_intake

    intake=_source("repair_ls2208_unverified.json")
    result=run_project_intake(intake,out_dir=tmp_path/"repair_scenario",start_splicer=False)
    assert result["compile_ok"] is False
    assert result["mission_success"] is False
    assert result["build_id"] is None
    assert Path(result["artifacts"]["repair_investigation"]).exists()
    assert not (tmp_path/"repair_scenario"/"ROBOTICS_SIMULATION.json").exists()

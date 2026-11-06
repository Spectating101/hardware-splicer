"""Adversarial tests for HS-native CM5 dual touch requirement replay."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import pytest

from hardware_splicer.cyberdeck_packaging_workflow import (
    run, PackagingInputError, _native_spec,
)
from mecha_splicer.spec import ClamshellTerminalSpec

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"examples/cyberdeck/dual_touch/cm5_native_replay"
REQ=json.loads((BASE/"requirements.json").read_text())


def test_native_replay_matches_versioned_evidence_and_preserves_hard_limit():
    result=run(REQ)
    evidence=json.loads((BASE/"evidence/hs_packaging_report.json").read_text())
    assert result==evidence
    assert result["requirements"]["screens"]==2
    assert result["requirements"]["physical_keyboard"] is False
    assert result["minimum_nominal_fit_mm"]==20
    assert result["hard_constraint_met"] is False
    assert result["decision"]=="reject_hard_envelope_research_alternative_requires_user_approval"
    assert [(x["closed_thickness_mm"],x["compute_to_panel_clearance_mm"]) for x in result["profiles"]]==[
        (18.0,-0.735),(19.0,0.265),(20.0,1.265),(21.0,2.265)]
    assert result["profiles"][0]["status"]=="fails_nominal_fit"
    assert result["profiles"][1]["status"]=="fails_nominal_fit"
    assert result["profiles"][2]["status"]=="counterfactual_exceeds_hard_limit"
    assert result["calculated_minimum_nominal_thickness_mm"]==19.735
    assert "cm5-to-panel" in str(result["profiles"][0]["native_mechanical_fit_checks"])
    assert not result["fabrication_authorized"] and not result["safe_to_power"]
    assert result["fpc_overflow_mm"]==29.0
    assert result["fpc_gate"]=="straight_FPC_exceeds_body"


def test_native_bundle_uses_real_cm5_and_two_identical_winstar_screens():
    result=run(REQ)
    lines={row["item"]:row for row in result["native_bom"]}
    assert lines["Radxa CM5 V2.21"]["qty"]==1
    assert lines["Winstar WF50DTYA3MNG10-000"]["qty"]==2
    assert not any("Waveshare" in x or "RS485" in x for x in lines)
    assert any("CM5" in row["message"] for row in result["native_dfm"])
    spec=json.loads((BASE/"evidence/native_project_spec.json").read_text())
    p=ClamshellTerminalSpec.model_validate(spec["clamshell_terminal"])
    assert p.compute_architecture=="cm5_dual_dsi"
    assert p.input_surface_mode=="dual_touch"
    assert p.lid_h_mm==5.8 and p.closed_gap_mm==0.8
    assert p.case_w_mm==155 and p.case_d_mm==80
    assert p.base_h_mm+p.lid_h_mm+p.closed_gap_mm==20


def test_regenerated_hs_native_scad_matches_checked_in_artifacts(tmp_path):
    result=run(REQ,out=tmp_path)
    assert result["decision"].startswith("reject_hard_envelope")
    for name in (
        "base_shell.scad","lid_shell.scad","clamshell_open_preview.scad",
        "dual_touch_visual_preview.scad","mecha_splicer.bundle.json",
    ):
        assert (tmp_path/"native_mecha"/name).read_bytes()==(
            BASE/"evidence/native_mecha"/name).read_bytes()
    for name in ("hs_packaging_report.json","native_project_spec.json","machine_project.json"):
        assert (tmp_path/name).read_bytes()==(BASE/"evidence"/name).read_bytes()


def test_native_machine_project_blocks_physical_release():
    result=run(REQ)
    release=result["release_assessment"]
    assert release
    assert release["requested_state"]=="build_ready"
    assert release["achieved_state"]!="operationally_authorized"
    assert release["blockers"]
    codes={b["code"] for b in release["blockers"]}
    assert "safety_not_closed" in codes
    assert "verification_not_passed" in codes


@pytest.mark.parametrize("change",[
    {"input_mode":"physical_keyboard"},
    {"physical_keyboard":True},
    {"panel_count":1},
    {"panel_count":3},
    {"compute_architecture":"dual_esp32"},
])
def test_requirements_fail_closed_against_wrong_product(change):
    data=deepcopy(REQ);data.update(change)
    with pytest.raises(PackagingInputError):
        run(data)


def test_panel_suffix_change_refuses_unqualified_equivalent():
    data=deepcopy(REQ);data["panel"]["mpn"]="WF50DTYA3MNG10"
    with pytest.raises(PackagingInputError,match="revision"):
        run(data)


def test_sourcing_evidence_is_required():
    data=deepcopy(REQ);data["panel"]["manufacturer_source_url"]=""
    with pytest.raises(PackagingInputError,match="source"):
        run(data)


def test_computing_stack_increase_forces_new_candidate_or_no_fit():
    data=deepcopy(REQ);data["lower_stack"]["mating_mm"]+=1.0
    r=run(data)
    assert r["profiles"][0]["compute_to_panel_clearance_mm"]<0
    assert r["profiles"][2]["native_mechanical_fit"]=="blocked"
    assert r["minimum_nominal_fit_mm"]==21
    assert not r["hard_constraint_met"]


def test_panel_thickness_increase_invalidates_prior_nominal_candidate():
    data=deepcopy(REQ);data["panel"]["thickness_mm"]+=0.8
    r=run(data)
    assert not r["profiles"][2]["nominal_research_fit"]
    assert r["minimum_nominal_fit_mm"]==21


def test_hard_max_alteration_only_changes_release_policy_not_fit_math():
    data=deepcopy(REQ);data["body"]["hard_max_thickness_mm"]=20
    r=run(data)
    assert r["hard_constraint_met"]
    assert r["profiles"][0]["compute_to_panel_clearance_mm"]==-0.735
    assert r["profiles"][1]["compute_to_panel_clearance_mm"]==0.265
    assert r["fabrication_authorized"] is False
    assert r["release_assessment"]["blockers"]


def test_no_assumption_change_silently_grants_fabrication():
    data=deepcopy(REQ);data["lower_stack"]["mating_mm"]=0.6
    r=run(data)
    assert r["fabrication_authorized"] is False
    assert r["release_assessment"]["blockers"]


def test_invalid_native_thin_architecture_not_accepted_as_keyboard():
    candidate=json.loads((BASE/"evidence/native_project_spec.json").read_text())
    spec=candidate["clamshell_terminal"]
    spec["input_surface_mode"]="physical_keyboard"
    with pytest.raises(ValueError):
        ClamshellTerminalSpec.model_validate(spec)


def test_native_floor_mismatch_is_rejected():
    data=deepcopy(REQ);data["lower_stack"]["back_wall_mm"]=0.85
    with pytest.raises(PackagingInputError,match="FDM shell"):
        run(data)

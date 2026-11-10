"""Actual PrusaSlicer toolpath claims and provenance checks.

CI source audit may run without full private machine-specific G-code;
a separate live re-slice verifies the native runner. Full 12 G-code
records are present on the user's authorized Optiplex for local audit.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.function_print_slicer import (
    read_statistics,audit_slicer_report,_assert_valid_profile
)
from hardware_splicer.function_print_feedback import (
    interpret_feedback,audit_feedback
)

ROOT=Path(__file__).resolve().parents[1]/"examples/print_function_pilot/pcb_service_stand"
OUT=ROOT/"slicer_results"
CAD=ROOT/"generated"
LOCAL=Path("/tmp/hs-real-slicer-benchmark-v2-20261110")

def sources():
    return [json.loads((ROOT/file).read_text()) for file in (
        "design_request.json","slicer_profile.json","feedback_policy.json",
        "generated/FUNCTION_GEOMETRY_EVALUATION.json",
        "slicer_results/SLICER_COMPARISON.json",
        "slicer_results/MASS_FEEDBACK.json",
    )]

def test_twelve_real_slicer_receipts_and_output_grammar_are_sealed():
    req,profile,policy,cad,report,feedback=sources()
    assert report["actual_slicer_executed"] and report["all_calls_successful"]
    assert report["attempt_count"]==12
    assert report["PrusaSlicer_version_text"].startswith("PrusaSlicer-2.9.2")
    assert len(report["PrusaSlicer_executable_sha256"])==64
    assert all(x["slicer_exit_code"]==0 and x["slice_status"]=="valid_gcode"
               and x["gcode_released_for_physical_printer"] is False
               for x in report["case_results"])
    assert len({x["slicer_output_sha256"] for x in report["case_results"]})==12
    assert [x["profile"] for x in report["profile_rankings"]]==["standard_020","draft_028"]
    # The repository's fast-core job intentionally has no optional OCP/
    # CadQuery installation. The dedicated native-CAD CI job runs this
    # same test with those dependencies present; fast core skips only
    # the actual STEP/STL roundtrip assertion.
    pytest.importorskip("cadquery")
    pytest.importorskip("trimesh")
    native=audit_slicer_report(req,profile,cad_dir=CAD,out=OUT,require_gcode=False)
    assert native["actual_native_slice_count"]==12
    assert native["physical_print_authorized"] is False

def test_slicer_mass_is_not_a_CAD_density_proxy():
    req,profile,policy,cad,report,feedback=sources()
    by={(r["profile"],r["design"]):r for r in report["case_results"]}
    assert by["standard_020","solid_plate"]["slicer_stats"]["filament_mass_g"]==29.0
    assert by["standard_020","ladder_58"]["slicer_stats"]["filament_mass_g"]==20.21
    assert by["standard_020","minimal_52"]["slicer_stats"]["filament_mass_g"]==17.95
    assert by["draft_028","solid_plate"]["slicer_stats"]["filament_mass_g"]==31.13
    assert by["draft_028","minimal_52"]["slicer_stats"]["filament_mass_g"]==18.27
    assert by["standard_020","ladder_58"]["slicer_stats"]["estimated_time_s"]==7132
    assert by["draft_028","ladder_58"]["slicer_stats"]["estimated_time_s"]==5765
    assert report["profile_rankings"][0]["relative_slicer_filament_reduction_pct"]==30.3
    assert report["profile_rankings"][1]["relative_slicer_filament_reduction_pct"]==32.9

def test_nominal_and_guarded_rankings_are_different_not_claimed_physical_proof():
    req,profile,policy,cad,report,feedback=sources()
    assert feedback["analysis_mode"].startswith("post-hoc")
    audit=audit_feedback(req,profile,policy,report,cad,feedback)
    assert audit["selected_nominal"]==["minimal_52","minimal_52"]
    assert audit["selected_guarded"]==["ladder_58","ladder_58"]
    assert audit==json.loads((OUT/"FEEDBACK_AUDIT.json").read_text())
    assert all(row["selection"]["nominal"]["filament_saving_vs_plate_percent"]>35
               for row in feedback["cases"])
    assert all(row["selection"]["guarded"]["filament_saving_vs_plate_percent"]>30
               for row in feedback["cases"])
    assert not feedback["printer_execution_authorized"]
    for study in feedback["cases"]:
        minimal=next(x for x in study["candidate_results"] if x["id"]=="minimal_52")
        ladder=next(x for x in study["candidate_results"] if x["id"]=="ladder_58")
        assert minimal["nominal_slicer_proxy_pass"] is True
        assert minimal["guarded_slicer_proxy_pass"] is False
        assert ladder["guarded_slicer_proxy_pass"] is True
        assert not minimal["physical_tip_test_completed"]

def test_changed_material_density_or_unverified_printer_authority_refused():
    req,profile,policy,cad,report,feedback=sources()
    modified=copy.deepcopy(profile)
    modified["filament"]["nominal_density_g_cm3"]=1.02
    with pytest.raises(ValueError,match="nominal material density"):
        _assert_valid_profile(modified,req)
    modified=copy.deepcopy(profile)
    modified["machine"]["machine_profile_physically_verified"]=True
    with pytest.raises(ValueError,match="physical calibration"):
        _assert_valid_profile(modified,req)
    modified=copy.deepcopy(profile)
    modified["release_authority"]["printer_control_authorized"]=True
    with pytest.raises(ValueError,match="printer release authority"):
        _assert_valid_profile(modified,req)

def test_feedback_cannot_be_promoted_to_physical_or_edit_slicer_mass():
    req,profile,policy,cad,report,feedback=sources()
    tamper=copy.deepcopy(feedback)
    tamper["cases"][0]["selection"]["guarded"]["chosen"]="minimal_52"
    with pytest.raises(ValueError,match="ranking changed"):
        audit_feedback(req,profile,policy,report,cad,tamper)
    unsafe=copy.deepcopy(policy)
    unsafe["design_authority"]["physical_mass_observed"]=True
    with pytest.raises(ValueError,match="unverified printed mass"):
        interpret_feedback(req,profile,unsafe,report,cad)

def test_source_manifest_or_slice_profile_mismatch_rejected():
    req,profile,policy,cad,report,feedback=sources()
    mismatch=copy.deepcopy(report)
    mismatch["slicer_profile_sha256"]="a"*64
    with pytest.raises(ValueError,match="other input geometry or print profile"):
        interpret_feedback(req,profile,policy,mismatch,cad)
    mismatch=copy.deepcopy(cad)
    mismatch["alternatives"][0]["numeric_feasible"]=False
    with pytest.raises(ValueError,match="original CAD feasibility label"):
        interpret_feedback(req,profile,policy,report,mismatch)

def test_native_gcode_roundtrip_and_mutation_when_local_private_files_exist(tmp_path):
    req,profile,policy,cad,report,feedback=sources()
    if not LOCAL.is_dir():
        pytest.skip("original 12 G-code binaries are intentionally not redistributed")
    pytest.importorskip("cadquery")
    pytest.importorskip("trimesh")
    assert audit_slicer_report(req,profile,cad_dir=CAD,out=LOCAL,require_gcode=True)["actual_native_slice_count"]==12
    original=(LOCAL/"standard_020__minimal_52.gcode").read_text()
    stats=read_statistics(original,layer=profile["profiles"][0])
    assert stats["filament_mass_g"]==17.95
    assert stats["estimated_time_s"]==6339
    corrupted=original.replace("; fill_density = 20%","; fill_density = 35%")
    with pytest.raises(ValueError,match="G-code output profile discrepancy"):
        read_statistics(corrupted,layer=profile["profiles"][0])

def test_slicer_output_metadata_is_not_fabrication_approval():
    req,profile,policy,cad,report,feedback=sources()
    assert report["printer_profile_physically_calibrated"] is False
    assert report["fabrication_or_physical_printer_execution_authorized"] is False
    assert policy["design_authority"]["physical_print_passed"] is False
    assert profile["release_authority"]["gcode_safe_to_execute_on_unverified_machine"] is False
    for item in report["case_results"]:
        assert item["gcode_released_for_physical_printer"] is False
        assert item["slicer_stats"]["filament_mass_g"]>0
        assert item["slicer_stats"]["gcode_lines"]>1000

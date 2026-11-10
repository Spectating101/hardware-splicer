"""Hinge 2-leaf native slicer, provenance and no-fabrication authority gates."""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest

HERE=Path(__file__).resolve().parents[1]/"examples/functional_hinge_cyberdeck"
SCRIPT=HERE/"verify_independent_slicing.py"
spec=importlib.util.spec_from_file_location("hs_independent_hinge_slicer",SCRIPT)
checker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

def src():
    return checker.inspect()

def test_all_real_fdm_attempts_match_source_part_hashes_and_print_profile():
    req,profile,record=src()
    assert len(record["source_jobs"])==8
    assert record["slicer_version"].startswith("PrusaSlicer-2.9.2")
    assert len(record["native_slicer_executable_sha256"])==64
    assert record["all_model_slices_succeeded"]
    assert not record["fabrication_released"]
    assert record["no_physical_printer_or_hardware_calibration"]
    assert profile["materials"]["supports"] is False
    assert profile["authority"]["support_free_horizontal_holes_verified"] is False
    assert set(x["design"] for x in record["source_jobs"])=={"balanced_60","reinforced_64"}
    assert set(x["printed_part"] for x in record["source_jobs"])=={"lower_leaf","upper_leaf"}
    assert set(x["layer_profile"] for x in record["source_jobs"])=={"std_020","draft_028"}
    for case in record["source_jobs"]:
        assert case["status"]=="sliced" and case["slicer_exit_code"]==0
        assert case["gcode_authorized_for_hardware"] is False
        assert 0<case["native_slicer_report"]["filament_mass_g"]<200
        # Thin 8–13mm shells legitimately have ~30–65 layers, depending
        # on layer height; do not demand a hundred printed layers.
        assert case["native_slicer_report"]["layer_markers"]>=25
        assert len(case["gcode_sha256"])==64

def test_two_part_estimates_and_model_preference_are_observed_not_guessed():
    req,profile,record=src()
    rows={(x["profile"],x["design"]):x for x in record["summaries"]}
    assert rows["std_020","balanced_60"]["slicer_estimated_two_part_filament_g"]==50.37
    assert rows["std_020","reinforced_64"]["slicer_estimated_two_part_filament_g"]==51.28
    assert rows["draft_028","balanced_60"]["slicer_estimated_two_part_filament_g"]==59.8
    assert rows["draft_028","reinforced_64"]["slicer_estimated_two_part_filament_g"]==60.67
    for p in ("std_020","draft_028"):
        assert (rows[p,"balanced_60"]["slicer_estimated_two_part_filament_g"]
               < rows[p,"reinforced_64"]["slicer_estimated_two_part_filament_g"])
    assert rows["std_020","balanced_60"]["slicer_estimated_two_print_jobs_seconds"]==20677
    assert rows["draft_028","balanced_60"]["slicer_estimated_two_print_jobs_seconds"]==19033
    for x in record["summaries"]:
        assert x["horizontal_hinge_bore_overhang_physically_qualified"] is False
        assert x["metal_pin_not_in_slicer_mass"]

def test_plain_source_records_cannot_claim_purchased_shaft_or_routed_cable():
    source=json.loads((HERE/"reference_spec.json").read_text())
    record=json.loads((HERE/"native_fdm_results.json").read_text())
    assert source["source_authority"]["existing_device_teardown_measured"] is False
    assert source["cable"]["actual_cable_geometry_routed"] is False
    assert source["mechanical"]["shaft_retention_design_verified"] is False
    assert record["gcode_file_bytes_not_committed"] is True
    assert record["no_routed_cable_or_shaft_retention_test"] is True

def test_slicer_source_rejects_tampered_profile(tmp_path,monkeypatch):
    import shutil
    tmp=tmp_path/"different_study"
    tmp.mkdir()
    for p in ("reference_spec.json","fdm_profile.json","native_fdm_results.json"):
        shutil.copyfile(HERE/p,tmp/p)
    (tmp/"generated").mkdir()
    shutil.copyfile(HERE/"generated/HINGE_EVALUATION.json",tmp/"generated/HINGE_EVALUATION.json")
    (tmp/"generated/candidates").mkdir()
    for design in ("balanced_60","reinforced_64"):
        (tmp/"generated/candidates"/design).mkdir()
        for part in ("lower_leaf","upper_leaf"):
            shutil.copyfile(HERE/"generated/candidates"/design/(part+".stl"),
                            tmp/"generated/candidates"/design/(part+".stl"))
    wrong=json.loads((tmp/"fdm_profile.json").read_text())
    wrong["materials"]["infill_percent"]=99
    (tmp/"fdm_profile.json").write_text(json.dumps(wrong))
    monkeypatch.setattr(checker,"HERE",tmp)
    with pytest.raises(ValueError,match="printer profile was changed"):
        checker.inspect()

def test_source_hash_gate_can_run_without_native_slicer_on_ci():
    request,profile,slicer=src()
    assert slicer["source_spec_sha256"]==checker.sha(request)
    assert slicer["source_profile_sha256"]==checker.sha(profile)

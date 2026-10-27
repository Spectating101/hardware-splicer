from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.system_example_microdrone import assess_microdrone, generate_package

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return (
        json.loads((ROOT / "examples/system_examples/microdrone_sensor_deck_001.json").read_text()),
        json.loads((ROOT / "examples/robotics_guidance/crazyflie_custom_sensor_deck.json").read_text()),
    )


def test_complete_cross_domain_assessment_is_not_flight_authority():
    design, guidance = fixture()
    report = assess_microdrone(design, guidance_scenario=guidance)
    assert report["preliminary_checks_pass"] is True
    assert report["verdict"] == "DESIGN_REVIEW_BLOCKED"
    envelope = report["mass_and_power"]
    assert envelope["proposed_total_mass_g"] == 31.4
    assert envelope["project_mass_headroom_g"] == pytest.approx(0.6)
    assert envelope["project_deck_current_headroom_ma"] == pytest.approx(26.0)
    assert envelope["vendor_deck_current_headroom_ma"] == pytest.approx(46.0)
    assert envelope["estimated_deck_electrical_power_w"] == pytest.approx(0.162)
    assert envelope["estimated_hover_load_per_motor_n"] == pytest.approx(0.07698, abs=0.00001)
    assert envelope["flight_time_projection_min"] is None
    assert len(report["reviewable_architecture"]["interfaces"]) == 4
    assert report["artifact_authority"]["motors_start_authorized"] is False
    assert report["artifact_authority"]["flight_authorized"] is False
    assert "unverified_deck_pinout_and_native_eda" in report["blockers"]


@pytest.mark.parametrize("key,new_value,expected", [
    ("proposed_deck_mass_g", 4.0, "estimated_deck_mass_within_project_limit"),
    ("proposed_deck_peak_current_ma", 90.0, "estimated_deck_current_within_project_limit"),
    ("proposed_deck_peak_current_ma", 110.0, "estimated_deck_current_within_vendor_rail_limit"),
    ("deck_vcc_v", 5.0, "deck_rail_nominal_voltage_matches_reference"),
])
def test_exceeding_real_limits_is_refused_with_explicit_blocker(key, new_value, expected):
    design, guidance = fixture()
    design["candidate"][key]["value"] = new_value
    report = assess_microdrone(design, guidance_scenario=guidance)
    assert report["preliminary_checks_pass"] is False
    assert expected in report["blockers"]
    assert not report["artifact_authority"]["flight_authorized"]


def test_four_motor_and_reference_scenario_identity_cannot_drift():
    design, guidance = fixture()
    design["baseline"]["motor_count"] = 3
    with pytest.raises(ValueError, match="four motor"):
        assess_microdrone(design, guidance_scenario=guidance)
    design, guidance = fixture()
    guidance["scenario_id"] = "different"
    with pytest.raises(ValueError, match="cross-reference"):
        assess_microdrone(design, guidance_scenario=guidance)


def test_estimates_cannot_be_promoted_to_unverified_measurements():
    design, guidance = fixture()
    design["candidate"]["proposed_deck_mass_g"]["measured"] = True
    with pytest.raises(ValueError, match="unmeasured mass"):
        assess_microdrone(design, guidance_scenario=guidance)


def test_missing_required_disarm_is_blocking():
    design, guidance = fixture()
    design["requirements"]["preserve_emergency_disarm"] = False
    report = assess_microdrone(design, guidance_scenario=guidance)
    assert "emergency_disarm_is_required" in report["blockers"]


def test_declared_external_evidence_can_never_grant_flight_authority():
    design, guidance = fixture()
    candidate = design["candidate"]
    for domain in ("electrical", "mechanical", "firmware", "simulation"):
        for key, val in candidate[domain].items():
            if isinstance(val, bool):
                candidate[domain][key] = True
    candidate["firmware"]["flight_controller_source_revision"] = "placeholder"
    candidate["firmware"]["radio_firmware_source_revision"] = "placeholder"
    candidate["simulation"]["simulator_version"] = "placeholder"
    report = assess_microdrone(design, guidance_scenario=guidance)
    assert "actual_material_and_mounting_measurements_missing" in report["blockers"]
    assert report["artifact_authority"]["manufacturing_authorized"] is False
    assert report["artifact_authority"]["flight_authorized"] is False


def test_package_is_source_bound_and_refuses_overwrite(tmp_path):
    design, guidance = fixture()
    output = tmp_path / "system"
    receipt = generate_package(design, guidance, output)
    for name, record in receipt["files"].items():
        body = (output / name).read_bytes()
        assert hashlib.sha256(body).hexdigest() == record["sha256"]
        assert len(body) == record["bytes"]
    assert (output / "ARCHITECTURE_CONTRACT.json").is_file()
    assert (output / "PHYSICAL_EVIDENCE_GATE.json").is_file()
    assert not receipt["all_physical_actions_authorized"]
    with pytest.raises(FileExistsError):
        generate_package(design, guidance, output)


def test_mutating_one_design_input_changes_receipt_hash(tmp_path):
    design, guidance = fixture()
    first = generate_package(design, guidance, tmp_path / "a")
    edited = copy.deepcopy(design)
    edited["candidate"]["proposed_deck_mass_g"]["value"] = 2.5
    second = generate_package(edited, guidance, tmp_path / "b")
    assert first["source_design_sha256"] != second["source_design_sha256"]
    assert first["files"]["MICRODRONE_ASSESSMENT.json"]["sha256"] != second["files"]["MICRODRONE_ASSESSMENT.json"]["sha256"]


def test_nonfinite_inputs_fail_before_report_generation():
    design, guidance = fixture()
    design["candidate"]["proposed_deck_peak_current_ma"]["value"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        assess_microdrone(design, guidance_scenario=guidance)

"""Operator bench capture must never turn fixture claims into physical authority."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from hardware_splicer.donor_characterization_v1 import (
    create_donor_capture_template, evaluate_donor_capture, FIELDS,
)
from hardware_splicer.donor_to_device_v1 import build_donor_to_device_review

ROOT=Path(__file__).resolve().parents[1]
INTAKE=ROOT/"examples/intakes/splice_robot_drive_brief.json"
FIXTURE=ROOT/"examples/fixtures/splice_donor_rc_motor_board.json"


def prepare(tmp_path):
    baseline=build_donor_to_device_review(
        intake_path=INTAKE, donor_fixture_path=FIXTURE,
        output_dir=tmp_path/"baseline",
    )
    packet=json.loads((tmp_path/"baseline/DONOR_CAPTURE_TEMPLATE.json").read_text())
    packet.update({
        "capture_id":"synthetic_test_only",
        "operator_id":"fixture-testing",
        "recorded_at":"2026-10-22T10:00:00+08:00",
        "simulated":False,
        "instruments":[
            {"instrument_id":"DMM-A","instrument_type":"multimeter",
             "calibration_status":"valid"},
            {"instrument_id":"CAL-A","instrument_type":"digital_calipers",
             "calibration_status":"valid"},
        ],
    })
    packet["donor_characterization"]["physical_donor_id"]="synthetic-validation-fixture"
    return baseline, packet


def set_reading(packet,key,value,unit=None,instrument=None):
    row=next(x for x in packet["measurements"] if x["measurement_id"]==key)
    row.update({
        "value":value,"status":"measured",
        "unit":unit or FIELDS[key][0],
        "instrument_id":instrument or ("CAL-A" if FIELDS[key][1]=="mechanical" else "DMM-A")
    })


def inspect(tmp_path, baseline, packet):
    file=tmp_path/"capture.json"
    file.write_text(json.dumps(packet))
    return evaluate_donor_capture(
        capture_path=file,
        intake_sha256=baseline["source"]["intake_sha256"],
        fixture_sha256=baseline["source"]["donor_fixture_sha256"],
    )


def test_generated_template_is_unfilled_cannot_pass_as_physical_capture(tmp_path):
    baseline, template=prepare(tmp_path)
    assert len(template["measurements"])==len(FIELDS)
    assert not any(m["value"] is not None for m in template["measurements"])
    assert template["schema_version"]=="bench_topology_capture.v1"
    assert not baseline["physical_donor_characterization"]
    assert (tmp_path/"baseline/DONOR_CAPTURE_TEMPLATE.json").is_file()


def test_synthetic_operator_readings_remain_unverified_with_source_provenance(tmp_path):
    baseline, packet=prepare(tmp_path)
    set_reading(packet,"battery_open_circuit_v",7.6)
    set_reading(packet,"motor_left_winding_ohm",7.0)
    set_reading(packet,"motor_right_winding_ohm",7.4)
    set_reading(packet,"wheel_left_diameter_mm",54.0)
    set_reading(packet,"wheel_right_diameter_mm",54.0)
    set_reading(packet,"axle_spacing_mm",138.0)
    report=inspect(tmp_path,baseline,packet)
    assert report["status"]=="measured_inputs_with_conflicts_review_required"
    assert report["input_fields_observed"]==6
    assert {x["id"] for x in report["conflicts"]}=={"battery_exceeds_declared_motor_rating"}
    assert report["accepted_readings"]["axle_spacing_mm"]["unit"]=="mm"
    assert not report["physical_donor_fully_characterized"]
    assert not report["motor_motion_authorized"]
    integrated=build_donor_to_device_review(
        intake_path=INTAKE,donor_fixture_path=FIXTURE,
        donor_capture_path=tmp_path/"capture.json",
        output_dir=tmp_path/"integrated")
    assert integrated["physical_donor_characterization"]["input_fields_observed"]==6
    assert integrated["mechanical_inputs"]["cad_model_generated"] is False
    assert integrated["mechanical_inputs"]["operator_reported_geometry"]["axle_spacing_mm"]["value"]==138
    assert len(integrated["acceptance_gates"])==7
    assert all(g["state"]=="open" for g in integrated["acceptance_gates"])
    assert (tmp_path/"integrated/DONOR_CAPTURE_AUDIT.json").is_file()
    assert integrated["device_work_package"]["physical_donor_evidence"]["capture_sha256"].startswith("sha256:")
    assert any(w.get("source_domain")=="donor_characterization"
               for w in integrated["device_work_package"]["work_steps"])
    assert integrated["device_work_package"]["engineering_readiness"]=="blocked"
    assert not integrated["release_authorized"]


def test_asymmetric_winding_readings_quarantine_motor_pair(tmp_path):
    baseline, packet=prepare(tmp_path)
    set_reading(packet,"motor_left_winding_ohm",3.0)
    set_reading(packet,"motor_right_winding_ohm",8.0)
    report=inspect(tmp_path,baseline,packet)
    assert any(x["id"]=="motor_winding_mismatch" for x in report["conflicts"])


@pytest.mark.parametrize("bad", [
    lambda p:p.update(simulated=True),
    lambda p:p.update(simulated=None),
    lambda p:p["donor_characterization"].update(intake_sha256="sha256:wrong"),
    lambda p:p.update(recorded_at="2026-10-22T10:00:00"),
    lambda p:p.update(operator_id=""),
    lambda p:p["donor_characterization"].update(physical_donor_id=""),
])
def test_unsafe_or_cross_donor_capture_rejected(tmp_path,bad):
    baseline, packet=prepare(tmp_path)
    bad(packet)
    with pytest.raises(ValueError):
        inspect(tmp_path,baseline,packet)


def test_unmatched_or_calibration_unknown_instrument_cannot_upgrade_reading(tmp_path):
    baseline, packet=prepare(tmp_path)
    set_reading(packet,"battery_open_circuit_v",7.6)
    packet["instruments"][0]["calibration_status"]="unknown"
    r=inspect(tmp_path,baseline,packet)
    assert r["input_fields_observed"]==0
    assert r["unqualified_readings"][0]["reason"]=="instrument_provenance_not_qualified"
    assert not r["release_authorized"]


@pytest.mark.parametrize("bad", [float("nan"),float("inf"),True,-1,0,1000])
def test_bad_voltage_measurement_fails_closed(tmp_path,bad):
    baseline, packet=prepare(tmp_path)
    set_reading(packet,"battery_open_circuit_v",bad)
    # JSON can encode NaN by default; the audited importer must still reject it.
    with pytest.raises(ValueError):
        inspect(tmp_path,baseline,packet)


def test_duplicate_and_unknown_measurement_id_block(tmp_path):
    baseline, packet=prepare(tmp_path)
    packet["measurements"].append(dict(packet["measurements"][0]))
    with pytest.raises(ValueError,match="duplicate"):
        inspect(tmp_path,baseline,packet)
    packet["measurements"].pop()
    packet["measurements"][0]["measurement_id"]="invented_motor_reading"
    with pytest.raises(ValueError,match="unknown"):
        inspect(tmp_path,baseline,packet)


def test_volt_units_cannot_be_forged_from_millivolts(tmp_path):
    baseline, packet=prepare(tmp_path)
    set_reading(packet,"battery_open_circuit_v",7.6,unit="mV")
    with pytest.raises(ValueError,match="unit mismatch"):
        inspect(tmp_path,baseline,packet)


def test_missing_mating_photo_never_authenticates_real_donor(tmp_path):
    baseline, packet=prepare(tmp_path)
    set_reading(packet,"wheel_left_diameter_mm",54.0)
    packet["artifacts"][0]["uri"]="photo://placeholder-does-not-prove-anything"
    result=inspect(tmp_path,baseline,packet)
    assert not result["source_attestations"]
    assert not result["all_measurement_evidence_independently_authenticated"]

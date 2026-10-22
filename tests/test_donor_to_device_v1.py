"""Native source/intake audit contracts; no real donor hardware is present."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.donor_to_device_v1 import build_donor_to_device_review

ROOT=Path(__file__).resolve().parents[1]
INTAKE=ROOT/"examples/intakes/splice_robot_drive_brief.json"
FIXTURE=ROOT/"examples/fixtures/splice_donor_rc_motor_board.json"


def evaluate(tmp_path, *, intake=INTAKE, fixture=FIXTURE, splice=None, out=None):
    return build_donor_to_device_review(
        intake_path=intake,donor_fixture_path=fixture,
        splice_result_path=splice,output_dir=out,
    )


def mutate(tmp_path, original, change):
    payload=json.loads(Path(original).read_text(encoding="utf-8"))
    change(payload)
    dest=tmp_path/Path(original).name
    dest.write_text(json.dumps(payload),encoding="utf-8")
    return dest


def test_existing_rc_rover_donor_generates_real_sourced_review_with_all_gates_open(tmp_path):
    out=tmp_path/"review"
    report=evaluate(tmp_path,out=out)
    assert report["schema"]=="hardware_splicer.donor_to_device_review.v1"
    assert report["status"]=="blocked_until_donor_characterization"
    assert report["case_id"]=="robot_drive_from_rc_toy"
    assert report["target_build_id"]=="robot_drive_base"
    assert report["source"]["fixture_is_measured_physical_donor"] is False
    assert report["donor_inventory_count"]==5
    assert report["electrical"]["two_motor_running_current_claim_a"]==0.9
    assert report["electrical"]["two_motor_stall_current_claim_a"]==1.8
    assert report["electrical"]["direct_battery_to_motor_voltage_mismatch"] is True
    assert len(report["reuse_actions"])==3
    assert report["reuse_actions"][2]["action"]=="do_not_cut_or_reuse_yet"
    assert len(report["acceptance_gates"])==7
    assert all(g["state"]=="open" for g in report["acceptance_gates"])
    assert report["splice_feasibility"]["overall_status"]=="unknown"
    assert report["carrier_compilation"]["status"]=="not_run_in_this_review"
    assert report["engineering_modules"]["mechanical"]=="solidcraft_freecad_requires_actual_donor_dimensions"
    assert report["mechanical_inputs"]["cad_model_generated"] is False
    assert report["estimated_replacement_cost_ntd"] is None
    assert report["estimated_resale_value_ntd"] is None
    assert not report["physical_build_complete"]
    assert not report["fabrication_authorized"]
    assert not report["motor_motion_authorized"]
    assert report["device_work_package"]["engineering_readiness"]=="blocked"
    assert not report["device_work_package"]["build_or_repair_completed"]
    assert all(not item["compatibility_verified"]
               for item in report["device_work_package"]["required_parts"])
    for name in ("DONOR_DEVICE_REVIEW.json","DONOR_DEVICE_WORK_PACKAGE.json",
                 "DONOR_EVIDENCE_GATES.json","DONOR_DEVICE_README.md"):
        assert (out/name).is_file()
    assert json.loads((out/"DONOR_DEVICE_REVIEW.json").read_text())==report


def test_repeated_source_inputs_produce_identical_hash_bound_review(tmp_path):
    a=evaluate(tmp_path,out=tmp_path/"a")
    b=evaluate(tmp_path,out=tmp_path/"b")
    assert a==b
    assert (tmp_path/"a/DONOR_DEVICE_REVIEW.json").read_bytes()==(
        tmp_path/"b/DONOR_DEVICE_REVIEW.json").read_bytes()


def test_donor_board_identity_conflict_rejected(tmp_path):
    intake=mutate(tmp_path,INTAKE,lambda x:x["circuit"]["boards"][0].update(board_id="wrong_board"))
    with pytest.raises(ValueError,match="identity"):
        evaluate(tmp_path,intake=intake)


def test_incomplete_donor_driver_never_passes_as_reusable(tmp_path):
    fixture=mutate(tmp_path,FIXTURE,lambda x:x["reusable_blocks"][0]["extractability"].update(
        {"class":"board_section_cut_candidate"}))
    with pytest.raises(ValueError,match="unsafe"):
        evaluate(tmp_path,fixture=fixture)


def test_donor_fixture_cannot_pretend_voltage_bench_gate_closed(tmp_path):
    fixture=mutate(tmp_path,FIXTURE,lambda x:x["evidence_gates"][0].update(status="closed"))
    with pytest.raises(ValueError,match="measurements"):
        evaluate(tmp_path,fixture=fixture)


def test_missing_or_invalid_motor_stall_claim_is_rejected(tmp_path):
    for invalid in (0.25,None,False,-1):
        intake=mutate(tmp_path,INTAKE,lambda x:x["available_parts"][1].update(
            stall_current_a=invalid))
        with pytest.raises(ValueError):
            evaluate(tmp_path,intake=intake)


def test_voltage_mismatch_is_derived_not_hardcoded(tmp_path):
    intake=mutate(tmp_path,INTAKE,lambda x:x["constraints"].update(
        battery_voltage_v=6.0))
    r=evaluate(tmp_path,intake=intake)
    assert r["electrical"]["direct_battery_to_motor_voltage_mismatch"] is False
    assert r["status"]=="blocked_until_donor_characterization"
    assert not r["electrical"]["motor_drive_rail_verified"]


def test_accepted_splice_demo_never_poses_as_physically_approved_board(tmp_path):
    evidence={"schema_version":"hardware_splicer.splice_demo_result.v1",
              "case_id":"robot_drive_from_rc_toy",
              "evaluation":{"passed":True},
              "metrics":{"build_id":"robot_drive_base","drc_pass":True}}
    source=tmp_path/"SPLICE_DEMO_RESULT.json"
    source.write_text(json.dumps(evidence))
    r=evaluate(tmp_path,splice=source)
    comp=r["carrier_compilation"]
    assert comp["status"]=="demo_drc_reported_artifact_unbound"
    assert comp["carrier_drc_pass"]
    assert comp["carrier_artifact_sha256"] is None
    assert comp["native_kicad_receipt_independently_rechecked"] is False
    assert not r["power_on_authorized"]


def test_wrong_build_id_or_case_cannot_adopt_another_splice_receipt(tmp_path):
    for mutate_case in (
        {"case_id":"printer_motion_stage"},
        {"metrics":{"build_id":"plotter_motion_stage","drc_pass":True}},
    ):
        evidence={"schema_version":"hardware_splicer.splice_demo_result.v1",
                  "case_id":"robot_drive_from_rc_toy",
                  "evaluation":{"passed":True},
                  "metrics":{"build_id":"robot_drive_base","drc_pass":True}}
        evidence.update(mutate_case)
        source=tmp_path/"other-splice.json"
        source.write_text(json.dumps(evidence))
        with pytest.raises(ValueError,match="not bound"):
            evaluate(tmp_path,splice=source)


def test_failed_splice_receipt_creates_blocked_compilation_state(tmp_path):
    evidence={"schema_version":"hardware_splicer.splice_demo_result.v1",
              "case_id":"robot_drive_from_rc_toy",
              "evaluation":{"passed":False},
              "metrics":{"build_id":"robot_drive_base","drc_pass":False}}
    path=tmp_path/"bad-splice.json"
    path.write_text(json.dumps(evidence))
    r=evaluate(tmp_path,splice=path)
    assert r["carrier_compilation"]["status"]=="blocked_compile_or_drc"
    assert r["carrier_compilation"]["carrier_artifact_sha256"] is None


def test_nonempty_destination_must_not_be_overwritten(tmp_path):
    dest=tmp_path/"review"
    dest.mkdir()
    (dest/"other-agents-work.json").write_text('{"untouched":true}')
    with pytest.raises(ValueError,match="empty"):
        evaluate(tmp_path,out=dest)
    assert (dest/"other-agents-work.json").read_text()=='{"untouched":true}'

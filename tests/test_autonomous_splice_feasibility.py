"""Independent software behavior and fail-closed electrical truth verification."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hardware_splicer.virtual_splice_reference_cell import (
    VirtualInspectionCell, run_virtual_reference_cases, audit_bounded_sequences,
)
from hardware_splicer.autonomous_splice_feasibility import evaluate_splice_feasibility

ROOT=Path(__file__).resolve().parents[1]


def source_record():
    # The source archive is an existing dated observation record, not a
    # fabricated "physical verification" fixture.
    record=json.loads((ROOT/"docs/evaluations"/"AUTONOMOUS_PUBLIC_DONOR_INVESTIGATION_2026-10-20.json").read_text())
    return {
        "schema_version":"hardware_splicer.autonomous_evidence_controller.v1",
        "physical_operations_executed":record["physical_operations_executed"],
        "repair":record["repair_analysis"],
        "splicing":record["splicing_analysis"],
        "proposed_engineering_revision":record["proposed_engineering_revision"],
    }


def test_normal_virtual_controller_cycle_requires_explicit_arm_motion_and_scan():
    c=VirtualInspectionCell()
    assert c.dispatch("load")["to"]=="inhibited"
    assert c.dispatch("interlock_closed")["to"]=="inhibited"
    assert c.dispatch("reset")["to"]=="ready"
    assert c.dispatch("scan","TEST")["to"]=="ready"
    assert c.dispatch("load")["to"]=="indexing"
    assert c.dispatch("scan","PREMATURE")["to"]=="indexing"
    assert c.dispatch("motion_complete")["to"]=="await_scan"
    assert c.dispatch("scan","00123")["to"]=="complete"
    assert c.completed_count==1
    assert c.dispatch("ack")["to"]=="ready"
    assert c.barcode is None
    assert not any(row["physical_hardware_actuated"] for row in c.event_history)


def test_stop_requires_explicit_reclosed_interlock_and_reset():
    c=VirtualInspectionCell()
    for event in ("interlock_closed","reset","load","stop","reset","load"):
        c.dispatch(event)
    assert c.state=="inhibited"
    assert not c.virtual_index_requested
    c.dispatch("interlock_closed")
    assert c.state=="inhibited"
    c.dispatch("reset")
    assert c.state=="ready"


@pytest.mark.parametrize("fault",["motion_timeout","limit_fault"])
def test_fault_requires_rearm_and_no_virtual_motion_during_fault(fault):
    c=VirtualInspectionCell()
    for event in ("interlock_closed","reset","load",fault):
        c.dispatch(event)
    assert c.state=="fault"
    assert not c.interlock_reported_closed
    assert not c.virtual_index_requested
    c.dispatch("reset")
    assert c.state=="inhibited"
    c.dispatch("interlock_closed")
    c.dispatch("reset")
    assert c.state=="ready"
    assert fault in c.faults


@pytest.mark.parametrize("bad_code",["", " ","é","Z"*97])
def test_invalid_virtual_scan_latches_fault(bad_code):
    c=VirtualInspectionCell()
    for event in ("interlock_closed","reset","load","motion_complete"):
        c.dispatch(event)
    c.dispatch("scan",bad_code)
    assert c.state=="fault"
    assert c.completed_count==0
    assert not c.interlock_reported_closed


def test_suite_checks_synthetic_only_and_does_not_promote_safety_authority():
    output=run_virtual_reference_cases()
    assert output["passed"]==output["total"]==8
    assert output["software_reference_logic_passed"] is True
    assert output["physical_product_works"] is False
    assert output["actual_safety_stop_verified"] is False


def test_bounded_state_exhaustion_has_no_sequence_invariant_violation():
    a=audit_bounded_sequences(max_depth=4)
    assert a["sequences_checked"]==7380
    assert a["violations"]==[]
    assert a["passed"] is True
    assert a["physical_hardware_evaluated"] is False


@pytest.mark.parametrize("bad_depth",[0,6,True,0.5,"4"])
def test_bounded_oracle_rejects_invalid_work_budget(bad_depth):
    with pytest.raises(ValueError):
        audit_bounded_sequences(max_depth=bad_depth)


def test_source_scoped_feasibility_uses_actual_hs_electrical_constraints():
    output=evaluate_splice_feasibility(source_record())
    assert output["virtual_control_software"]["passed"]==8
    assert output["bounded_software_state_audit"]["passed"]
    assert output["conditional_motor_driver_plan"]["planner_result"]=="blocked"
    missing=output["conditional_motor_driver_plan"]["missing_evidence"]
    for term in ("load_current_estimate","supply_rail","control_signal_voltage","l298n_output_current_rating","flyback_or_driver_protection"):
        assert term in missing
    assert output["conditional_motor_driver_plan"]["motor_type_measured"] is False
    assert output["physical_gate_count_open"]==6
    assert output["novel_product_functionally_proven"] is False


def test_claimed_physical_mission_success_from_sources_is_rejected():
    record=source_record()
    record["splicing"]["mission_success"]=True
    with pytest.raises(ValueError,match="claimed completed"):
        evaluate_splice_feasibility(record)


def test_claimed_measured_donor_from_source_is_rejected():
    record=source_record()
    record["proposed_engineering_revision"]["new_product_revision"]["donor_measured_or_integrated"]=True
    with pytest.raises(ValueError,match="physical integration"):
        evaluate_splice_feasibility(record)


def test_missing_epson_motion_candidate_is_hard_stop():
    record=source_record()
    record["splicing"]["candidate_source_audit"]=[
        r for r in record["splicing"]["candidate_source_audit"]
        if r["candidate_id"]!="epson_paper_motion"
    ]
    with pytest.raises(ValueError,match="motion-source"):
        evaluate_splice_feasibility(record)


def test_sdk_mcp_tool_supports_offline_evidence_replay(monkeypatch):
    from hardware_splicer import sdk,mcp_server
    record=source_record()
    result=sdk.validate_virtual_splice_feasibility(source_research=record)
    assert result["novel_product_functionally_proven"] is False
    tools=asyncio.run(mcp_server.list_tools())
    assert any(x.name=="hs_validate_virtual_splice_feasibility" for x in tools)
    payload=asyncio.run(mcp_server.call_tool("hs_validate_virtual_splice_feasibility",{"source_research":record}))
    mcp=json.loads(payload[0].text)
    assert mcp["virtual_control_software"]["passed"]==8
    assert mcp["conditional_motor_driver_plan"]["planner_result"]=="blocked"
    assert not mcp["physical_actions_authorized"]

def test_repository_archived_source_observation_can_replay_without_fetch():
    archived=json.loads((ROOT/"docs/evaluations"/"AUTONOMOUS_PUBLIC_DONOR_INVESTIGATION_2026-10-20.json").read_text())
    result=evaluate_splice_feasibility(archived)
    assert result["virtual_control_software"]["passed"]==8
    assert result["novel_product_functionally_proven"] is False

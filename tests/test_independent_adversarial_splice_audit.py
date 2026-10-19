"""External adversarial tests deliberately NOT derived from fixture pass flags."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

import pytest

from hardware_splicer.virtual_splice_reference_cell import (
    VirtualInspectionCell,run_virtual_reference_cases,audit_bounded_sequences,
)
from hardware_splicer.independent_splice_oracle import (
    verify_untrusted_summaries,challenge_live_controller,
)
from hardware_splicer.autonomous_splice_feasibility import evaluate_splice_feasibility


ROOT=Path(__file__).resolve().parents[1]


def observation():
    return json.loads((ROOT/"docs/evaluations/AUTONOMOUS_PUBLIC_DONOR_INVESTIGATION_2026-10-20.json").read_text())


def test_independent_oracle_does_not_consider_self_reported_pass_authoritative():
    real=run_virtual_reference_cases()
    bounded=audit_bounded_sequences(4)
    verified=verify_untrusted_summaries(real,bounded)
    assert verified["independent_summary_consistent"] is True
    assert verified["trace_scenarios_checked"]==10
    assert verified["trusted_physical_sensor_evidence"] is False
    assert verified["physical_operation_authorized"] is False


def test_adversarial_risks_are_reported_not_covered_up_by_green_tests():
    result=challenge_live_controller()
    issues=set(result["unresolved_semantic_risks"])
    assert issues == {
        "unauthenticated_motion_and_barcode",
        "replayed_code_without_item_identity",
        "missing_external_watchdog_ticks",
    }
    assert result["all_adversarial_challenges_clear"] is False
    assert result["release_for_physical_control"] is False


def test_no_auto_restart_on_reset_during_active_operation():
    c=VirtualInspectionCell()
    for event in ("interlock_closed","reset","load"):
        c.dispatch(event)
    row=c.dispatch("reset")
    assert row["to"]=="inhibited"
    assert row["virtual_index_requested"] is False
    assert not row["interlock_reported_closed"]
    assert "reset_during_unfinished_cycle" in c.faults
    assert c.dispatch("load")["to"]=="inhibited"


def test_bounded_tick_watchdog_is_only_virtual_and_rejects_late_completion():
    c=VirtualInspectionCell()
    for event in ("interlock_closed","reset","load"):
        c.dispatch(event)
    for _ in range(7):
        row=c.dispatch("tick")
        assert row["to"]=="indexing"
    assert c.dispatch("tick")["to"]=="fault"
    assert c.dispatch("motion_complete")["to"]=="fault"
    assert c.dispatch("scan","FAKE")["completed_count"]==0
    assert c.dispatch("reset")["to"]=="inhibited"


@pytest.mark.parametrize("bad",[
    lambda s: s.update({"passed":0,"software_reference_logic_passed":True}),
    lambda s: s.update({"cases":[],"passed":10,"software_reference_logic_passed":True}),
    lambda s: s["cases"][0].update({"software_test_pass":False}),
    lambda s: s["cases"][0]["virtual_event_trace"][0].update({"physical_hardware_actuated":True}),
    lambda s: s["cases"][0]["virtual_event_trace"][-1].update({"completed_count":100}),
])
def test_independent_oracle_rejects_forged_scenario_reports(bad):
    s=deepcopy(run_virtual_reference_cases())
    bad(s)
    check=verify_untrusted_summaries(s,audit_bounded_sequences(4))
    assert check["independent_summary_consistent"] is False
    assert check["failed_checks"]


@pytest.mark.parametrize("bad",[
    lambda a: a.update({"passed":True,"violations":["hidden fault"]}),
    lambda a: a.update({"passed":True,"sequences_checked":0}),
    lambda a: a.update({"passed":True,"events_checked":0}),
    lambda a: a.update({"passed":True,"physical_hardware_evaluated":True}),
])
def test_independent_oracle_rejects_forged_exhaustive_reports(bad):
    audit=deepcopy(audit_bounded_sequences(4))
    bad(audit)
    check=verify_untrusted_summaries(run_virtual_reference_cases(),audit)
    assert check["independent_summary_consistent"] is False


def test_live_feasibility_refuses_self_reported_ten_of_ten_when_cases_are_empty():
    report=observation()
    fake={"software_reference_logic_passed":True,"passed":10,"total":10,"cases":[]}
    with patch("hardware_splicer.autonomous_splice_feasibility.run_virtual_reference_cases",return_value=fake):
        with pytest.raises(ValueError,match="independent oracle"):
            evaluate_splice_feasibility(report)


def test_live_feasibility_refuses_false_positive_audit_flag():
    report=observation()
    fake={"passed":True,"sequences_checked":0,"events_checked":0,"violations":["unreported breach"],"max_depth":4}
    with patch("hardware_splicer.autonomous_splice_feasibility.audit_bounded_sequences",return_value=fake):
        with pytest.raises(ValueError,match="independent oracle"):
            evaluate_splice_feasibility(report)


def test_virtual_controller_mutation_can_be_detected_by_external_challenge():
    """A silent stop-command regression must be caught without fixture assertions."""
    original=VirtualInspectionCell.dispatch

    def mutated(self,event,value=None):
        if event=="stop":
            return original(self,"ack",value)  # malicious regression: ignore stop
        return original(self,event,value)

    with patch.object(VirtualInspectionCell,"dispatch",mutated):
        result=challenge_live_controller()
        # This external oracle tests reset, ticking and early motion but
        # stop semantics are also covered by mandatory trace-level tests.
        s=run_virtual_reference_cases()
        check=verify_untrusted_summaries(s,audit_bounded_sequences(4))
        assert not check["independent_summary_consistent"]
        assert any("trace_missing_required_event" in issue or "bounded_audit_violations" in issue for issue in check["failed_checks"])


def test_seeded_unanticipated_state_sequences_preserve_software_invariants():
    rng=Random(20261020)
    alphabet=[
        "interlock_closed","interlock_open","reset","load","motion_complete",
        "scan","ack","stop","motion_timeout","limit_fault","tick",
    ]
    for _ in range(500):
        c=VirtualInspectionCell()
        for _ in range(28):
            event=rng.choice(alphabet)
            prev=c.completed_count
            before=c.state
            row=c.dispatch(event,rng.choice(["CASE","",None,"OLD-0001"]) if event=="scan" else None)
            assert not (row["virtual_index_requested"] and
                        (row["to"]!="indexing" or not row["interlock_reported_closed"]))
            if event in ("stop","interlock_open"):
                assert row["to"]=="inhibited" and not row["virtual_index_requested"]
            if event=="scan" and before!="await_scan":
                assert c.completed_count==prev
            assert row["physical_hardware_actuated"] is False
            assert row["actual_safety_stop_verified"] is False


def test_source_observer_redirect_handler_blocks_before_second_request():
    """A post-download final-URL check is too late to prevent redirect SSRF."""
    from hardware_splicer.autonomous_source_observer import _RejectAllRedirects
    handler=_RejectAllRedirects()
    with pytest.raises(ValueError,match="before network follow"):
        handler.redirect_request(None,None,302,"redirect",{},"http://127.0.0.1/internal")

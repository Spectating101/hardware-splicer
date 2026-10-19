"""Independent adversarial evidence oracle for the virtual HS inspection cell.

Unlike the scenario runner, this oracle defines acceptance *outside* the
software-under-test's expected results and summary booleans. It also reports
when the model can be fooled by unauthenticated synthetic event sequences.
This is NOT a safety certification or proof of real machine behavior.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .virtual_splice_reference_cell import VirtualInspectionCell

SCHEMA="hardware_splicer.independent_splice_oracle.v1"
_REQUIRED = {
    "normal_cycle": ("ready", 1),
    "stop_during_motion": ("inhibited", 0),
    "premature_scan_rejected": ("complete", 1),
    "motion_timeout_fail_closed": ("fault", 0),
    "limit_fault_fail_closed": ("fault", 0),
    "reset_requires_interlock": ("indexing", 0),
    "stop_requires_explicit_rearm": ("ready", 0),
    "reset_during_indexing_inhibits": ("inhibited", 0),
    "virtual_tick_limit_inhibits": ("fault", 0),
    "invalid_scan_fault": ("fault", 0),
}
_EVENT_ALPHABET_SIZE = 10


def verify_untrusted_summaries(scenario_report: Mapping[str,Any], bounded_report: Mapping[str,Any])->dict[str,Any]:
    """Reject misleading self-reported pass flags or inconsistent traces."""
    issues=[]
    cases=scenario_report.get("cases")
    if not isinstance(cases,list):
        cases=[]
        issues.append("missing_case_traces")
    observed={}
    for row in cases:
        if not isinstance(row,Mapping):
            issues.append("bad_case_row")
            continue
        name=row.get("case")
        if not isinstance(name,str) or name not in _REQUIRED or name in observed:
            issues.append("unexpected_or_duplicate_scenario")
            continue
        observed[name]=row
        expected_state,expected_completed=_REQUIRED[name]
        if (row.get("actual_end_state")!=expected_state or
            row.get("actual_completed_count")!=expected_completed or
            row.get("software_test_pass") is not True):
            issues.append(f"scenario_incorrect:{name}")
        trace=row.get("virtual_event_trace")
        if not isinstance(trace,list) or not trace:
            issues.append(f"scenario_missing_trace:{name}")
            continue
        if row.get("real_sensor_observed") is not False or row.get("real_motor_command_issued") is not False:
            issues.append(f"scenario_false_physical_claim:{name}")
        actual_events=[x.get("event") for x in trace if isinstance(x,Mapping)]
        required_event={
            "stop_requires_explicit_rearm":"stop",
            "stop_during_motion":"interlock_open",
            "virtual_tick_limit_inhibits":"tick",
            "motion_timeout_fail_closed":"motion_timeout",
            "limit_fault_fail_closed":"limit_fault",
        }.get(name)
        if required_event and required_event not in actual_events:
            issues.append(f"trace_missing_required_event:{name}")
        previous_state="inhibited"
        previous_completed=0
        for step in trace:
            if not isinstance(step,Mapping):
                issues.append(f"trace_malformed:{name}")
                break
            if step.get("from")!=previous_state:
                issues.append(f"trace_discontinuous:{name}")
            event=step.get("event")
            state=step.get("to")
            completed=step.get("completed_count")
            if type(completed) is not int or completed<previous_completed:
                issues.append(f"trace_counter_invalid:{name}")
                break
            if completed>previous_completed and not (event=="scan" and previous_state=="await_scan" and state=="complete"):
                issues.append(f"trace_phantom_completion:{name}")
            if event in ("stop","interlock_open") and (state!="inhibited" or step.get("virtual_index_requested") is not False):
                issues.append(f"trace_stop_failure:{name}")
            if event=="reset" and previous_state in ("indexing","await_scan") and state=="ready":
                issues.append(f"trace_reset_without_abort:{name}")
            if step.get("virtual_index_requested") and (state!="indexing" or not step.get("interlock_reported_closed")):
                issues.append(f"trace_motion_gate_failure:{name}")
            if step.get("physical_hardware_actuated") is not False or step.get("actual_safety_stop_verified") is not False:
                issues.append(f"trace_false_physical_claim:{name}")
            previous_state=state
            previous_completed=completed
        if trace[-1].get("to")!=row.get("actual_end_state") or trace[-1].get("completed_count")!=row.get("actual_completed_count"):
            issues.append(f"trace_summary_conflict:{name}")

    if set(observed)!=set(_REQUIRED):
        issues.append("missing_required_scenarios")
    if (scenario_report.get("passed")!=len(_REQUIRED)
        or scenario_report.get("total")!=len(_REQUIRED)
        or scenario_report.get("software_reference_logic_passed") is not True):
        issues.append("contradictory_scenario_summary")
    if scenario_report.get("physical_product_works") is not False or scenario_report.get("physical_operation_authorized") is not False:
        issues.append("false_real_product_claim")

    if not isinstance(bounded_report,Mapping):
        bounded_report={}
        issues.append("missing_bounded_audit")
    depth=bounded_report.get("max_depth")
    if type(depth) is not int or not 1<=depth<=5:
        issues.append("invalid_bounded_depth")
    else:
        expected_sequences=sum(_EVENT_ALPHABET_SIZE**d for d in range(1,depth+1))
        expected_steps=sum(d*_EVENT_ALPHABET_SIZE**d for d in range(1,depth+1))
        if bounded_report.get("sequences_checked")!=expected_sequences:
            issues.append("false_bounded_sequence_count")
        if bounded_report.get("events_checked")!=expected_steps:
            issues.append("false_bounded_event_count")
    if bounded_report.get("passed") is not True or bounded_report.get("violations") != []:
        issues.append("bounded_audit_violations_or_false_pass")
    if bounded_report.get("physical_hardware_evaluated") is not False:
        issues.append("false_bounded_physical_claim")
    return {
        "schema_version":SCHEMA,
        "independent_summary_consistent":not issues,
        "failed_checks":sorted(set(issues)),
        "trace_scenarios_checked":len(observed),
        "trusted_physical_sensor_evidence":False,
        "physical_operation_authorized":False,
    }


def challenge_live_controller() -> dict[str,Any]:
    """Actively exercise scenarios not written by the original fixture author."""
    findings=[]
    def execute(label,events):
        cell=VirtualInspectionCell()
        for e,value in events:
            cell.dispatch(e,value)
        return {"challenge":label,"state":cell.state,"completed":cell.completed_count,
                "virtual_index_requested":cell.virtual_index_requested,
                "faults":list(cell.faults)}
    ready=[("interlock_closed",None),("reset",None),("load",None)]

    fake=execute("unauthenticated_motion_and_barcode",ready + [
        ("motion_complete",None),("scan","FORGED-0001"),
    ])
    findings.append({
        **fake,
        "risk":"HIGH: externally supplied synthetic events can record completion without authenticating real motion or scanner",
        "issue_open":fake["completed"]>0,
        "not_a_real_inspection":True,
    })

    duplicate=execute("replayed_code_without_item_identity",ready + [
        ("motion_complete",None),("scan","DUPLICATE-ITEM"),
        ("ack",None),("load",None),("motion_complete",None),("scan","DUPLICATE-ITEM"),
    ])
    findings.append({
        **duplicate,
        "risk":"MEDIUM: repeated synthetic barcode events can count as separate cycles without identifying distinct physical items",
        "issue_open":duplicate["completed"]>=2,
        "not_a_real_inspection":True,
    })

    missing_clock=execute("missing_external_watchdog_ticks",ready + [
        ("ack",None) for _ in range(100)
    ])
    findings.append({
        **missing_clock,
        "risk":"HIGH: tick-based virtual budget cannot enforce any timeout unless a trusted independent clock injects ticks",
        "issue_open":missing_clock["state"]=="indexing",
        "not_a_real_inspection":True,
    })

    stop=execute("stop_while_indexing",ready + [
        ("stop",None),
    ])
    findings.append({
        **stop,
        "risk":"software stop must inhibit indexing and require separate re-arm",
        "issue_open":stop["state"]!="inhibited" or stop["virtual_index_requested"],
        "not_a_real_inspection":True,
    })

    reset=execute("reset_mid_indexing",ready + [
        ("reset",None),("load",None),
    ])
    findings.append({
        **reset,
        "risk":"reset must abort active virtual operation and require separate re-arming",
        "issue_open":reset["state"] not in ("inhibited","fault"),
        "not_a_real_inspection":True,
    })

    clock=execute("synthetic_tick_limit",ready + [
        ("tick",None) for _ in range(8)
    ] + [("motion_complete",None),("scan","LATE")])
    findings.append({
        **clock,
        "risk":"if ticks ARE supplied in simulation, exceeding the configured index budget must prevent completion",
        "issue_open":clock["state"]!="fault" or clock["completed"]!=0,
        "not_a_real_inspection":True,
    })

    unexpected=execute("premature_motion_complete",[
        ("interlock_closed",None),("reset",None),
        ("motion_complete",None),("scan","OUT-OF-ORDER"),
    ])
    findings.append({
        **unexpected,
        "risk":"out-of-order synthetic motion and barcode events must not close a cycle",
        "issue_open":unexpected["completed"]!=0,
        "not_a_real_inspection":True,
    })
    return {
        "schema_version":"hardware_splicer.independent_adversarial_challenges.v1",
        "challenges":findings,
        "unresolved_semantic_risks":[x["challenge"] for x in findings if x["issue_open"]],
        "all_adversarial_challenges_clear":not any(x["issue_open"] for x in findings),
        "physical_specimen_tested":False,
        "release_for_physical_control":False,
    }

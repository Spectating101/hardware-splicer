"""Independent adversarial audit and mutation challenge for PR #153 successor.

Runs real local HS code on synthetic events with intentionally broken dispatch
variants. Zero real hardware, payments, sellers or non-allowlisted browsing.
"""
from __future__ import annotations

from contextlib import contextmanager
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from hardware_splicer.virtual_splice_reference_cell import (
    VirtualInspectionCell,run_virtual_reference_cases,audit_bounded_sequences,
)
from hardware_splicer.independent_splice_oracle import (
    verify_untrusted_summaries,challenge_live_controller,
)


@contextmanager
def mutated_dispatch(name):
    original=VirtualInspectionCell.dispatch
    def injected(self,event,value=None):
        if name=="ignore_stop" and event=="stop":
            return original(self,"ack",value)
        if name=="ignore_ticks" and event=="tick":
            return original(self,"ack",value)
        result=original(self,event,value)
        if name=="allow_unacknowledged_reset" and event=="reset" and result["from"]=="indexing":
            self.state="ready"
            self.interlock_reported_closed=True
            result.update({"to":"ready","interlock_reported_closed":True})
        if name=="credit_out_of_order_scan" and event=="scan" and result["from"] not in ("await_scan","fault"):
            self.completed_count+=1
            self.state="complete"
            result.update({"to":"complete","completed_count":self.completed_count})
        return result
    with patch.object(VirtualInspectionCell,"dispatch",injected):
        yield


def run_independent_redteam()->dict:
    scenario=run_virtual_reference_cases()
    bounded=audit_bounded_sequences(4)
    independently_checked=verify_untrusted_summaries(scenario,bounded)
    behavior=challenge_live_controller()
    if not independently_checked["independent_summary_consistent"]:
        raise RuntimeError("unmodified controller unexpectedly fails baseline integrity audit")

    mutants=[]
    for name in (
        "ignore_stop","ignore_ticks","allow_unacknowledged_reset","credit_out_of_order_scan",
    ):
        with mutated_dispatch(name):
            challenge=challenge_live_controller()
            mutated_cases=run_virtual_reference_cases()
            mutated_audit=audit_bounded_sequences(4)
            checked=verify_untrusted_summaries(mutated_cases,mutated_audit)
        issues={
            x["challenge"] for x in challenge["challenges"]
            if x["issue_open"] and x["challenge"] in {
                "stop_while_indexing","synthetic_tick_limit",
                "reset_mid_indexing","premature_motion_complete",
            }
        }
        killed=bool(issues or checked["failed_checks"])
        mutants.append({
            "mutation":name,
            "independent_oracle_detected":killed,
            "behavioral_invariant_violations":sorted(issues),
            "trace_or_summary_failures":checked["failed_checks"],
        })

    forged=deep_summary_forgery(scenario,bounded)
    return {
        "schema_version":"hardware_splicer.independent_adversarial_mutation_audit.v1",
        "assessment":"read-only synthetic software adversarial exercise; no verified field instrumentation",
        "baseline_scenarios":scenario["total"],
        "baseline_bounded_sequences":bounded["sequences_checked"],
        "baseline_independent_summary":independently_checked,
        "adversarial_cases":behavior,
        "mutants_tested":len(mutants),
        "mutants_detected":sum(m["independent_oracle_detected"] for m in mutants),
        "mutation_challenges":mutants,
        "contradictory_report_injections":forged,
        "open_real_world_critical_risks":behavior["unresolved_semantic_risks"],
        "physical_controller_release":"BLOCKED",
        "physical_devices_observed":0,
        "physical_stop_circuit_tested":False,
        "physical_scanner_tested":False,
        "physical_motion_actuated":False,
    }


def deep_summary_forgery(scenario,bounded):
    from copy import deepcopy
    bad1=deepcopy(scenario)
    bad1["passed"]=0
    bad1["software_reference_logic_passed"]=True
    bad2=deepcopy(bounded)
    bad2["passed"]=True
    bad2["violations"]=["intentionally concealed failure"]
    checks=[
        verify_untrusted_summaries(bad1,bounded),
        verify_untrusted_summaries(scenario,bad2),
    ]
    return [{
        "injection":name,
        "oracle_rejected":not x["independent_summary_consistent"],
        "reason_codes":x["failed_checks"],
    } for name,x in zip(
        ("false_green_scenario_count","false_green_audit_with_violations"),
        checks,
    )]


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    result=run_independent_redteam()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    print(json.dumps({
        "mutants_detected":result["mutants_detected"],
        "mutants_tested":result["mutants_tested"],
        "contradictory_reports_rejected":sum(x["oracle_rejected"] for x in result["contradictory_report_injections"]),
        "open_real_world_critical_risks":result["open_real_world_critical_risks"],
        "physical_controller_release":result["physical_controller_release"],
        "out":str(args.out),
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

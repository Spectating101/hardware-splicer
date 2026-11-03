#!/usr/bin/env python3
"""Independent read-only audit of the new actual-engine state-transition dossier.

This validates source chronology, measurement integrity, condition attribution,
reported-vs-measured distinction and full prohibition of physical authority.
It does NOT confer real root-cause accuracy on a retrospectively selected case.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path


EXPECTED = [
    ("T0","input_loading_suspected","laptop_main_input_loading_or_protection_trip_unverified"),
    ("T1","board_input_short_reported","laptop_downstream_main_input_short_reported"),
    ("T2","component_short_localized_reported","laptop_input_mlcc_short_isolation_reported"),
    ("T3","second_boot_fault_after_rail_recovery","laptop_secondary_startup_fault_after_main_rail_restoration"),
    ("T4","rtc_dependent_boot_state_reported","laptop_rtc_dependent_startup_state_unverified"),
]
ORIGINAL = ["battery_charge_path_fault"]*3+["laptop_usb_c_port_or_input_path_fault"]*2
SOURCE_MEASUREMENTS = {
    "T0":[(19.9,"V")],
    "T1":[(19.0,"V"),(2.3,"A")],
    "T2":[(1.3,"A")],
    "T3":[(19.9,"V"),(40.0,"mA"),(3.3,"V")],
    "T4":[],
}
HAZARDOUS = {"current_injection","flammable_solvent_heating",
             "component_rework","powered_rtc_connection"}


def need(cond,reason):
    if not cond:raise ValueError("E5250 source-state integrity FAIL: "+reason)


def audit(case_path:Path,baseline_path:Path,trace_path:Path):
    case=json.loads(case_path.read_text())
    baseline=json.loads(baseline_path.read_text())
    report=json.loads(trace_path.read_text())
    need(case["source"]["article_url"]=="https://sorinelectronics.co.uk/dell-laptop-not-charging/",
         "source thread changed")
    need(case["chronology"][-1]["id"]=="T5" and case["chronology"][-1]["allowed_in_engine"] is False,
         "future owner functional outcome entered engine")
    need(report["source_file_sha256"]==hashlib.sha256(case_path.read_bytes()).hexdigest(),
         "source file changed")
    need(report["baseline_engine_output_sha256"]==hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
         "original actual-engine failure rewritten")
    need(report["original_unmodified_trace_was_compared"] is True and
         report["actual_existing_evaluator_used"] is True, "not actually exercising original engine")
    need(report["study_classification"]=="known_case_post_failure_development_not_new_unseen_validation",
         "known case falsely described as unbiased blind data")
    need(report["HS_independent_measurements"]==report["physical_repairs_by_HS"]==0 and
         report["source_measurements_reported"]==7,"fictional HS hardware work")
    need(report["physical_repair_approved"] is False and
         report["part_number_verified"] is False and
         report["real_customer_product_acceptance"]=="NOT_VERIFIED",
         "physical authority or customer acceptance fabricated")
    rows=report["machine_state_progression"]
    need(len(rows)==len(EXPECTED)==5,"not five actual stages")
    need([x["stage"] for x in rows]==[x[0] for x in EXPECTED],"out-of-order stages")
    need(len(baseline["stages"])==5 and
         [x["real_engine_output"]["repair_guide"]["top_fault"] for x in baseline["stages"]]==ORIGINAL,
         "original false guesses were removed")
    events_known=[]
    for row,(stage,expected_state,expected_fault),original_fault in zip(rows,EXPECTED,ORIGINAL):
        events=row["input_source_event_records"]
        need(events[:len(events_known)]==events_known,"rewritten prior source event")
        newly=events[len(events_known):]
        events_known=events
        need(all(x["stage_id"]==stage for x in newly),"future-stage event introduced prematurely")
        need(all(x["provenance"]=="third_party_source_report" and
                 x["actor"]=="external_technician" and
                 x["HS_instrument_verified"] is False and
                 x["repair_authorized"] is False for x in events),
             "typed event claimed independent measurements or safety authorization")
        measurements=[(float(x["value"]),x["unit"]) for x in newly
                      if x["event_type"]=="measurement"]
        need(measurements==SOURCE_MEASUREMENTS[stage],"numeric source readings changed")
        need(all(x["condition"] and x["source_url"]==case["source"]["article_url"]
                 for x in events),"measurement lacks state or provenance")
        need(row["input_source_measurements_known"]==[
             x["event_id"] for x in events if x["event_type"]=="measurement"],"measurement IDs hidden")
        need(row["typed_event_ids_known"]==[x["event_id"] for x in events],
             "typed event IDs altered")
        actual=row["actual_engine_output"]
        state=row["actual_evidence_state"]
        need(actual["case_id"]==case["case_id"]+"__"+stage,
             "wrong machine or actual engine case")
        need(actual["evidence_state"]==state,
             "current engine output and the independent state summary disagree")
        need(state["state"]==expected_state and
             state["fault_id"]==expected_fault and
             actual["repair_guide"]["top_fault"]==expected_fault and
             row["stateful_engine_fault"]==expected_fault,
             "typed evidence did not control real repair diagnosis")
        need(row["original_engine_fault"]==original_fault,
             "original failed hypothesis overwritten")
        need(actual["physical_repair_ready"] is False and
             actual["verdict"]!="solvable_now" and
             actual["verdict_scope"]=="software_workflow_only_not_repaired_product",
             "unsafe physical or software ready claim")
        need(actual["board_session"]["session_id"],
             "production board session not exercised")
        need(state["component_failure_independently_verified"] is False and
             state["source_is_ground_truth"] is False and
             state["independently_verified_HS_measurement_count"]==0 and
             state["physical_repair_ready"] is False and
             state["parts_purchase_authorized"] is False and
             state["power_or_rework_authorized"] is False,
             "external evidence converted into validated repair")
        need(state["source_reported_numeric_measurement_count"]==
             len(row["input_source_measurements_known"]),"measurements duplicated/omitted")
        need(state["confidence_type"]=="qualitative_state_support_only_no_probability",
             "uncalibrated state given fake probability")
        need(row["source_reported_state_not_verified_root_cause"] is True and
             row["source_result_not_used_to_promote_physical_authority"] is True,
             "state claimed physical root truth")
        # Every material transition includes actual supporting source references
        # and explains what older guesses were contradicted.
        need(state["source_evidence_ids_supporting"],"transition lacks supporting evidence")
        need(state["hypotheses_contradicted_by_record"],"stale fault explanation omitted")
    need(len(events_known)>0,"no typed source observations")
    interventions=[e["signal"] for e in events_known if e["event_type"]=="intervention"]
    need(set(interventions)==HAZARDOUS and len(interventions)==4,
         "hazardous source actions were omitted or normalized as safe")
    return {
        "source_audit":"PASS",
        "unmodified_baseline_preserved":True,
        "real_engine_chronology":5,
        "actual_typed_power_state_transitions":5,
        "third_party_numeric_source_measurements":7,
        "HS_independent_numeric_measurements":0,
        "HS_performed_physical_repair":False,
        "hypothesis_improvement_is_development_only":True,
        "independent_root_cause_accuracy":"NOT_CLAIMED",
        "physical_product_release":"BLOCKED",
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--case",type=Path,required=True)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--trace",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(audit(args.case,args.baseline,args.trace),indent=2))

#!/usr/bin/env python3
"""Independent acceptance test of the *evidence integrity*, not of repair accuracy."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

def h(data):
    return hashlib.sha256(data).hexdigest()

def require(ok,msg):
    if not ok: raise ValueError("E5250 dossier audit: "+msg)

def audit(case_path:Path,out:Path):
    case=json.loads(case_path.read_text())
    trace=json.loads((out/"WHOLE_PRODUCT_ENGINE_TRACE.json").read_text())
    graded=json.loads((out/"WHOLE_PRODUCT_DISPOSITION.json").read_text())
    ledger=json.loads((out/"WHOLE_PRODUCT_SOURCE_LEDGER.json").read_text())
    manifest=json.loads((out/"WHOLE_PRODUCT_MANIFEST.json").read_text())
    dossier=(out/"WHOLE_PRODUCT_RESTORATION_DOSSIER.md").read_text()
    original_hash=h(case_path.read_bytes())
    require(trace["source_sha256"]==graded["original_source_sha256"]==ledger["source_sha256"]==manifest["source_sha256"]==original_hash,"wrong original evidence")
    require(trace["actual_existing_engine"] is True,"no real engine called")
    require([s["stage_id"] for s in trace["stages"]]==["T0","T1","T2","T3","T4"],"T5 outcome leaked or source checkpoint missing")
    require(len({s["stage_id"] for s in trace["stages"]})==5,"duplicate engine event")
    observations=[]
    for s in trace["stages"]:
        event=next(x for x in case["chronology"] if x["id"]==s["stage_id"])
        observations+=event["previously_known_observations"]
        record=s["real_engine_input"]
        expected={
            "case_id":case["case_id"]+"__"+event["id"],
            "title":case["title"],
            "device_hint":"Dell Latitude E5250 business laptop",
            "symptoms":list(observations),
            "source_url":case["source"]["article_url"],
            "source_kind":"public_technician_retrospective_chronological_replay",
            "observed_actions":[],
            "notes":"Third-party technician observations only. HS has not tested this hardware.",
            "expected_lane":"",
        }
        require(record==expected,"future information, source outcome, wrong device or fabricated data in engine input")
        inp_h=h(json.dumps(record,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode())
        require(s["real_engine_input_sha256"]==inp_h,"input integrity hash does not match")
        require(s["source_final_outcome_given_to_engine"] is False,"false final-outcome independence")
        require(s["HS_measured_or_modified_hardware"] is False,"false physical measurement")
        response=s["real_engine_output"]
        require(response["case_id"]==record["case_id"],"wrong engine case")
        require(response["verdict_scope"]=="software_workflow_only_not_repaired_product" and
                response["physical_repair_ready"] is False,"software score promoted into hardware approval")
        require(response["repair_guide"]["top_fault"] is not None,
                "original engine returned no leading hypothesis")
        row=next(x for x in graded["stage_predictions"] if x["stage"]==s["stage_id"])
        require(row["top_fault"]==response["repair_guide"]["top_fault"] and
                row["software_workflow_verdict"]==response["verdict"] and
                row["diagnostic_family"]==response["repair_guide"]["family"],
                "post-hoc engineering disposition rewrote original model output")
        observed_measurements=[m["id"] for e in case["chronology"] if e["id"]<=s["stage_id"] for m in e["source_measurements"]]
        require(s["source_measurement_ids_known_at_this_stage"]==observed_measurements,"injected future measurement to early stage")
    require(graded["actual_engine_evaluation_count"]==5,"false full workflow claim")
    require(graded["source_reported_numeric_readings"]==7 and
            graded["HS_instrumented_measurement_count"]==0,"invented HS measurements")
    require(graded["source_reported_physical_interventions"]==4 and
            graded["HS_performed_physical_interventions"]==0,"invented HS repair")
    require(graded["source_reported_functional_gates"]==3 and
            graded["source_functional_gate_denominator"]==8 and
            graded["HS_independently_verified_functional_gates"]==0,
            "full device acceptance inflated")
    require(graded["physical_repair_authority"]=="BLOCKED" and
            graded["full_product_customer_release"]=="BLOCKED" and
            graded["part_purchase_authority"]=="BLOCKED", "unsafe premature release")
    require(graded["energized_current_injection_RTC_hotplug_and_flammable_solvent_authorized"] is False,
            "historical dangerous intervention adopted as physical instruction")
    require(graded["commercial_costs"].startswith("UNKNOWN"),"fabricated profit estimate")
    require(graded["component_diagnosis_accuracy"].startswith("UNSCORABLE"),
            "retrospective case wrongly treated as accurate prospective repair")
    require(ledger["source_chronology"]==case["chronology"] and
            ledger["source_interventions_not_HS_actions"]==case["source_reported_interventions"],
            "source chronicle or repair history rewritten")
    require("SAFETY STOP" in dossier and "Source-reported functional gates: 3/8" in dossier and
            "HS independently verified: 0/8" in dossier and
            "Product release disposition" in dossier,
            "human operator report missing safety, functionality or release")
    require(manifest["HS_performed_physical_repair"] is False,"manifest invents physical work")
    require(len(manifest["artifacts"])==4,"incorrect dossier artifact count")
    for filename,hashvalue in manifest["artifacts"].items():
        require(h((out/filename).read_bytes())==hashvalue,"tampered generated report "+filename)
    return {"audit":"PASS","original_source_hash":original_hash,
            "third_party_case_count":1,"real_Circuit_AI_stages":5,
            "source_technician_numeric_readings":7,
            "source_interventions":4,"source_verified_functional_gates":[3,8],
            "HS_hardware_measurements":0,"HS_physical_repairs":0,
            "HS_customer_grade_acceptance":False,
            "physical_repair_and_purchase": "BLOCKED",
            "not_an_untouched_holdout":True}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--case",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(audit(args.case,args.out),indent=2))

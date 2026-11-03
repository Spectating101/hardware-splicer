#!/usr/bin/env python3
"""Qualify real-device repair/reuse pilots WITHOUT inventing physical outcomes.

This consumes existing Hardware-Splicer repair/salvage cases. Public OEM/iFixit
references count as repair documentation only, NEVER observed test evidence.
Actual physical measurements must be submitted as separate original files
with SHA-256 receipts and operator review before even a preliminary outcome.
No autonomous energization, flight, or resale authorization is generated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA="hardware_splicer.real_hardware_recovery_pilot_catalog.v1"
KIND={"repair","repurpose","rebuild"}
SAFETY={"low_voltage","battery_and_private_data","power_and_private_data",
        "low_voltage_mechanism","flight_critical_battery"}
CASE_FILE="apps/circuit-ai/eval/real_repair_cases/cases.json"
LIFECYCLE=("intake","diagnose","source_documentation","measure","repair_or_rebuild",
           "functional_test","operator_review","outcome")

def require(ok:bool,msg:str)->None:
    if not ok:raise ValueError("HS actual-hardware pilot gate: "+msg)

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def check_evidence(evidence_root:Path,case:dict,receipts:list[dict])->dict:
    required=set(case["required_evidence"])
    approved=set()
    errors=[]
    for record in receipts:
        if not isinstance(record,dict):errors.append("receipt object expected");continue
        gate=record.get("gate")
        if gate not in required:errors.append("unknown gate "+str(gate));continue
        if gate in approved:errors.append("duplicate gate "+str(gate));continue
        rel=Path(str(record.get("source_path","")))
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            errors.append("unsafe evidence reference");continue
        path=(evidence_root/rel).resolve()
        if not path.is_relative_to(evidence_root.resolve()) or not path.is_file():
            errors.append("original operator evidence file absent: "+str(rel));continue
        payload=path.read_bytes()
        if len(payload)<24 or sha(payload)!=record.get("sha256"):
            errors.append("operator evidence SHA256 mismatch "+str(rel));continue
        if record.get("finding") not in ("observed_pass","observed_fail","inconclusive"):
            errors.append("missing explicit operator finding");continue
        if not isinstance(record.get("observed_at_utc"),str) or "T" not in record["observed_at_utc"]:
            errors.append("missing observation timestamp");continue
        if not isinstance(record.get("operator_role"),str) or len(record["operator_role"])<3:
            errors.append("missing operator reviewer role");continue
        if record["finding"]=="observed_pass":approved.add(gate)
        else:errors.append("real operator finding not pass "+str(gate))
    return {"evidence_passed":len(approved),"required_gates":len(required),
            "missing_gates":sorted(required-approved),"receipt_issues":errors,
            "all_evidence_checks_pass":bool(required==approved and not errors)}

def validate(root:Path,catalog_path:Path,receipts_path:Path|None=None,evidence_root:Path|None=None)->dict[str,Any]:
    cat=json.loads(catalog_path.read_text())
    require(cat["schema_version"]==SCHEMA,"unexpected catalog schema")
    pilots=cat["pilots"]
    require(cat["pilot_count"]==len(pilots)>=6,"pilot count changed")
    require(cat["existing_verifiable_engine"]["real_hardware_outcomes_verified_in_this_study"]==0,
            "unfounded claim of physical repair")
    original_cases=json.loads((root/CASE_FILE).read_text())
    known_cases={x["case_id"] for x in original_cases}
    receipts={} if receipts_path is None else json.loads(receipts_path.read_text())
    require(isinstance(receipts,dict),"receipts should be keyed by pilot id")
    results=[]
    seen=set()
    for case in pilots:
        name=case["id"]
        require(isinstance(name,str) and name not in seen,"duplicate pilot id")
        seen.add(name)
        require(case["kind"] in KIND and case["safety_class"] in SAFETY,
                "invalid physical pilot class "+name)
        require(case["status"]=="candidate_no_hardware",
                "software plan may not claim physical verification "+name)
        require(case["operator_evidence"]==[],
                "do not insert invented observation receipts into source catalog "+name)
        require(case["authority"]["physical_device_tested"] is False and
                case["authority"]["restored_or_rebuilt"] is False and
                case["authority"]["flight_authorized"] is False and
                case["authority"]["operator_power_on_approved"] is False and
                case["authority"]["customer_data_access_authorized"] is False and
                case["authority"]["resale_ready"] is False,
                "software may not grant actual hardware, flight, customer data or sale authority")
        require(set(case["economic_actuals"])=={
            "purchase_cost","parts_cost","repair_labor_minutes","energy_cost",
            "recovery_or_sale_value"} and all(x is None for x in case["economic_actuals"].values()),
            "actual restoration economics cannot be fabricated")
        require(case["existing_hs_paths"],"reuse existing HS capabilities rather than create a parallel product")
        for existing in case["existing_hs_paths"]:
            require((root/existing).is_file(),"existing HS source path missing: "+existing)
        ref=case["existing_case_id"]
        if ref is not None:require(ref in known_cases,"claimed HS repair case does not exist "+str(ref))
        required=case["required_evidence"]
        require(len(required)==len(set(required)) and len(required)>=5,
                "insufficient/duplicate real measured evidence gate")
        require({"ownership_and_consent","human_operator_signoff"}.issubset(required),
                "real-device ownership/human review cannot be skipped")
        require(len(case["stop_conditions"])>=2,"missing stop conditions for actual hardware")
        require(all(x.get("source_role")=="public_technical_documentation_not_physical_test"
                    for x in case["source_references"]), "documentation is not physical proof")
        require(set(x["url"] for x in case["source_references"])==
                set(case["guides"]),"source citation link mismatch")
        if case["safety_class"] in ("battery_and_private_data","power_and_private_data"):
            require("data_sanitization_or_return_policy_receipt" in required,
                    "personal data return/erase rules required for computing assets")
        if case["safety_class"]=="flight_critical_battery":
            require({"virtual_SITL_failsafe_logs",
                     "propeller_free_bench_motor_and_failsafe_test",
                     "new_or_qualified_undamaged_battery_receipt"}.issubset(required),
                    "drone flight critical proof insufficient")
            require("flight_authorized" in case["authority"] and
                    case["authority"]["flight_authorized"] is False,
                    "junk drone may NOT be authorized to fly")
        if case["id"] in receipts:
            e_root=evidence_root or root
            state=check_evidence(e_root,case,receipts[case["id"]])
        else:
            state={"evidence_passed":0,"required_gates":len(required),
                   "missing_gates":sorted(required),"receipt_issues":[],
                   "all_evidence_checks_pass":False}
        verdict="evidence_complete_pending_external_operator_review" if state["all_evidence_checks_pass"] else "PLAN_ONLY_NO_PHYSICAL_EVIDENCE"
        results.append({
            "pilot_id":name,
            "recommended_priority":case["rank"],
            "preliminary_product_output":case["final_product"],
            "existing_HS_case":ref,"existing_HS_source_paths":case["existing_hs_paths"],
            "required_real_operator_evidence":state,
            "verdict":verdict,
            "physical_product_verified":False,
            "may_energize_or_assemble_automatically":False,
            "outdoor_flight_authorized":False,
            "customer_device_data_access_authorized":False,
            "commercial_value_measured":False,
        })
    require(not (set(receipts)-seen),"receipts for unrecognized pilot")
    require(all(case["verdict"]=="PLAN_ONLY_NO_PHYSICAL_EVIDENCE" for case in results)
            if receipts_path is None else True,
            "source catalog must not bootstrap a fake physical test")
    return {"schema_version":"hardware_splicer.real_hardware_pilot_acceptance.v1",
            "software_plan_candidates_checked":len(results),
            "existing_real_repair_case_references":len(original_cases),
            "operator_evidence_files_submitted":sum(x["required_real_operator_evidence"]["evidence_passed"] for x in results),
            "verified_actual_hardware_repair_outcomes":0,
            "fully_qualified_flightworthy_drones":0,
            "new_parallel_repair_web_app_created":False,
            "pilot_evaluations":results,
            "require_real_owned_donor_and_human_reviews":True,
            "physical_hardware_operating_authority_granted":False}

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root",type=Path,default=Path("."))
    ap.add_argument("--catalog",type=Path,default=Path("examples/real_hardware_recovery/pilots_2026_11.json"))
    ap.add_argument("--receipts",type=Path)
    ap.add_argument("--evidence-root",type=Path)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    result=validate(args.root,args.catalog,args.receipts,args.evidence_root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"candidates":result["software_plan_candidates_checked"],
                      "actual_verified_repairs":result["verified_actual_hardware_repair_outcomes"],
                      "flightworthy_drones":result["fully_qualified_flightworthy_drones"],
                      "plan_only":sum(x["verdict"]=="PLAN_ONLY_NO_PHYSICAL_EVIDENCE" for x in result["pilot_evaluations"])},indent=2))

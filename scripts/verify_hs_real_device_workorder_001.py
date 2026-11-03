#!/usr/bin/env python3
"""Independent acceptance of six real-device operator bench packets.

This separate verifier does not import the compiler. Tests data lineage,
actual original Circuit-AI lane prompts, function outcomes and null evidence.
Unowned hardware and fabricated measurements never receive an acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import runpy
from pathlib import Path

STAGES=("intake","safety_isolation","diagnosis","compatibility",
        "supervised_bench","full_product_acceptance")
EXPECTED_SCHEMA="hardware_splicer.real_device_field_work_order.v1"
REPAIR_LANES="apps/circuit-ai/src/intelligence/repair_lane_packs.py"
CATALOG="examples/real_hardware_recovery/pilots_2026_11.json"
CASES="apps/circuit-ai/eval/real_repair_cases/cases.json"

def require(condition,why):
    if not condition:raise ValueError("HS real-device work order independent gate: "+why)

def verify(root:Path,work_dir:Path,pilot_id:str)->dict:
    src=root/CATALOG
    cat=json.loads(src.read_text())
    pilot=next((x for x in cat["pilots"] if x["id"]==pilot_id),None)
    require(pilot is not None,"unknown pilot")
    packet=json.loads((work_dir/"FIELD_WORK_ORDER.json").read_text())
    card=(work_dir/"HUMAN_BENCH_CARD.md").read_text()
    require(packet["schema_version"]==EXPECTED_SCHEMA and packet["pilot_id"]==pilot_id,
            "wrong target or work-order schema")
    require(packet["source_pilot_catalog_sha256"]==hashlib.sha256(src.read_bytes()).hexdigest(),
            "stale or mutated pilot source")
    require(packet["hardware_state"]=="NO_DONOR_ASSIGNED",
            "software unexpectedly claims a field device")
    require(packet["product_goal"]==pilot["final_product"],
            "actual finished-product requirement dropped")
    require(packet["original_existing_HS_paths"]==pilot["existing_hs_paths"],
            "existing HS repair/salvage source lineage altered")
    require(all((root/p).is_file() for p in packet["original_existing_HS_paths"]),
            "declared reused source code absent")
    cases={x["case_id"]:x for x in json.loads((root/CASES).read_text())}
    source_case=pilot.get("existing_case_id")
    if source_case:
        require(packet["reused_source_repair_case"]==source_case and
                packet["source_repair_case_reference"]==cases[source_case]["source_url"],
                "source repair reference not faithfully carried")
    else:
        require(packet["source_repair_case_reference"] is None,
                "invented repair case reference")
    lanes=runpy.run_path(str(root/REPAIR_LANES))["LANE_PACKS"]
    lane_id=packet["reused_repair_lane_id"]
    if lane_id:
        require(packet["source_existing_repair_lane_path"]==REPAIR_LANES and
                lane_id in lanes,"existing Circuit-AI lane is not linked")
        expected=lanes[lane_id]
        require(packet["source_repair_lane_evidence_prompts"]==expected["evidence_prompts"],
                "existing source repair lane evidence prompts changed")
        task_instructions={x["instruction"] for x in packet["product_specific_stages"]}
        require(set(expected["measurements"]).issubset(task_instructions),
                "existing repair-lane diagnostic measurements missing")
        require(set(expected["stop_conditions"]).issubset(set(packet["safety_stop_conditions"])),
                "original repair-lane stop authority dropped")
    else:
        require(packet["source_existing_repair_lane_path"] is None and
                not packet["source_repair_lane_evidence_prompts"],
                "fabricated Circuit-AI device lane")
    tasks=packet["product_specific_stages"]
    require(len(tasks)>=10 and len({x["task_id"] for x in tasks})==len(tasks),
            "incomplete or duplicated real-device bench instructions")
    require({x["stage"] for x in tasks}==set(STAGES),
            "not all real-product stages covered")
    require([x["stage"] for x in tasks]==sorted(
            (x["stage"] for x in tasks),key=lambda x:STAGES.index(x)),
            "operator procedure stages out of physical execution order")
    require(all(x["status"]=="NOT_PERFORMED" and x["evidence_sha256"] is None and
                x["observed_by"] is None and x["observed_at_utc"] is None for x in tasks),
            "fictional task completion")
    requirements=packet["required_physical_evidence_gates"]
    require(set(x["evidence_gate"] for x in requirements)==set(pilot["required_evidence"]),
            "source physical evidence gate lost or invented")
    require(all(x["status"]=="NOT_SUBMITTED" and
                x["source_evidence_file"] is None and x["sha256"] is None and
                x["observed_value"] is None and x["operator_review"] is None for x in requirements),
            "fabricated operator field evidence")
    readings=packet["measurable_acceptance_template"]
    require(len(readings)>=3 and len({x["measurement_id"] for x in readings})==len(readings),
            "no actual measured test slots")
    for r in readings:
        require(r["unit"] and r["source_of_acceptable_limits"] and
                all(r[x] is None for x in (
                    "accepted_min","accepted_max","observed_value",
                    "instrument_id","observed_at_utc","operator_signature")),
                "an actual value or accepted limit was invented")
    require(packet["operator_identity_redacted"] is None and
            packet["owner_consent_document"] is None and
            packet["device_model_label"] is None,
            "fictional field device/consent")
    require(set(packet["source_guides_not_actual_evidence"])==set(pilot["guides"]),
            "source documentation incorrectly changed")
    costs=packet["estimated_and_actual_economics"]
    require(all(v is None for v in costs.values()),
            "fabricated repair economics or sale claim")
    eval=packet["evaluation"]
    require(eval["verdict"]=="AWAITING_OWNED_DONOR_AND_ORIGINAL_MEASUREMENTS",
            "premature successful repair verdict")
    require(all(not val for key,val in eval.items() if key!="verdict"),
            "physical, power, flight, commercial, or customer-data authority incorrectly assigned")
    require("NO OWNED DONOR OR PHYSICAL TEST" in card and
            "all unmeasured" in card and
            "## Actual observations" in card and
            "## Immediate stop conditions" in card,
            "human operator card misrepresents physical scope")
    for t in tasks:
        require("- [ ] "+t["instruction"] in card,
                "operator procedure not printed")
    return {"schema_version":"hardware_splicer.real_device_operator_workorder_acceptance.v1",
            "pilot_id":pilot_id,
            "source_catalog_SHA256":packet["source_pilot_catalog_sha256"],
            "existing_circuit_ai_repair_lane_reused":lane_id,
            "field_steps_written":len(tasks),
            "source_measurement_slots_blank":len(readings),
            "required_evidence_gates_open":len(requirements),
            "all_original_source_lanes_and_cases_preserved":True,
            "actual_owned_device_supplied":False,
            "actual_device_bench_measurements_supplied":False,
            "real_complete_product_repaired_or_built":False,
            "device_power_or_drone_flight_authorized":False}

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root",default=".",type=Path)
    ap.add_argument("--work-dir",required=True,type=Path)
    ap.add_argument("--pilot",required=True)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    result=verify(a.root,a.work_dir,a.pilot)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

#!/usr/bin/env python3
"""Independent checks on the HS canonical repair intake bridge.

Deliberately does not import the bridge compiler. It verifies source workorder
and donor SHA, original HS repair intake representation, no guessed parts or
power/flight authority, and no embedded original private evidence bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

RECEIPT_SCHEMA="hardware_splicer.real_donor_intake_bridge_receipt.v1"
MODEL_SCHEMA="hardware_splicer.repair_intake.v1"
PROJECT_PILOT_PREFIX="hs_real_device_"
ORIGINAL_LABELS={"owner_consent","redacted_device_photo","fault_observation"}

def check(ok,msg):
    if not ok:raise ValueError("HS independent canonical field bridge test: "+msg)

def digest(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(root:Path,workdir:Path,pilot:str,donor_file:Path,output:Path)->dict:
    sys.path.insert(0,str((root/"src").resolve()))
    from hardware_splicer.repair_intake import extract_repair_context
    work=workdir/"FIELD_WORK_ORDER.json"
    w=json.loads(work.read_text())
    record=json.loads(donor_file.read_text())
    case=json.loads((output/"PROJECT_INTAKE.json").read_text())
    receipt=json.loads((output/"REAL_DONOR_INTAKE_BRIDGE_RECEIPT.json").read_text())
    check(receipt["schema_version"]==RECEIPT_SCHEMA and
          receipt["source_operator_input_sha256"]==digest(donor_file) and
          receipt["source_field_work_order_sha256"]==digest(work),
          "bridge donor/workorder provenance changed")
    check(w["pilot_id"]==pilot==record["pilot_id"] and
          case["project_name"]==PROJECT_PILOT_PREFIX+pilot,
          "wrong sourced device/workorder")
    ctx=extract_repair_context(case)
    check(ctx["schema_version"]==MODEL_SCHEMA and
          ctx["device_hint"]==record["device_model_redacted"] and
          ctx["symptoms"]==record["device_symptoms_observed"] and
          ctx["repro_steps"]==record["safe_reproduction_observations"],
          "original canonical repair context lost real donor observation")
    check(case.get("available_parts")==[],
          "unmeasured donor components invented")
    field=case["field_donor_source"]
    check(field["pilot_id"]==pilot and
          field["source_work_order_sha256"]==digest(work) and
          field["original_evidence_not_embedded"] is True and
          field["user_owner_authorization_independently_verified"] is False and
          field["original_source_device_parts_identified_and_qualified"] is False and
          field["operator_bench_measurements_independently_verified"] is False and
          field["physical_product_complete"] is False,
          "evidence/power ownership improperly promoted")
    entries=field["original_field_evidence_manifest"]
    check(len(entries)==3 and {x["purpose"] for x in entries}==ORIGINAL_LABELS,
          "original donor intake files unaccounted")
    for src in entries:
        observed=record["original_operator_files"][src["purpose"]]
        check(src["SHA256"]==observed["sha256"] and src["original_file_bytes"]>=24 and
              src["authenticity_or_consent_claim_independently_verified"] is False,
              "upstream original file provenance or scope changed")
    serialized=json.dumps(case)
    for orig in record["original_operator_files"].values():
        check(orig["source_path"] not in serialized,
              "private original operator filesystem evidence leaked to canonical intake")
    checks=(
       "source_file_integrity_only_no_authenticity_proof",
       "existing_HS_canonical_repair_intake_used",
       "physical_donor_reported_by_operator_not_independently_certified",
    )
    check(all(receipt[k] is True for k in checks) and
          receipt["source_original_files_checked"]==3 and
          receipt["electronics_components_assumed"]==0,
          "canonical source payload audit not complete")
    prohibited=(
       "actual_repair_verified","device_power_on_authorized",
       "motion_or_drone_flight_authorized","customer_data_access_authorized",
       "fabrication_or_resale_authorized"
    )
    check(all(receipt[k] is False for k in prohibited),
          "canonical intake makes unsafe physical authority claim")
    check(receipt["verdict"]=="DONOR_INTAKE_FILE_INTEGRITY_ONLY__AWAITING_REAL_MEASUREMENTS",
          "premature repaired device acceptance")
    return {
        "schema_version":"hardware_splicer.real_donor_canonical_intake_acceptance.v1",
        "original_work_order_sha256":digest(work),
        "original_donor_record_sha256":digest(donor_file),
        "canonical_existing_repair_context_schema":ctx["schema_version"],
        "owner_consent_and_field_document_file_hashes_carried":3,
        "no_guessed_source_components":True,
        "original_private_source_files_not_embedded":True,
        "real_physical_device_or_consent_authenticity_independently_verified":False,
        "actual_device_repaired":False,
        "physical_power_or_motion_authorized":False,
        "external_device_hardware_data_required":True
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("root","workdir","donor","output","acceptance"):
        ap.add_argument("--"+name,required=True,type=Path)
    ap.add_argument("--pilot",required=True)
    a=ap.parse_args()
    out=verify(a.root,a.workdir,a.pilot,a.donor,a.output)
    a.acceptance.write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out,indent=2))

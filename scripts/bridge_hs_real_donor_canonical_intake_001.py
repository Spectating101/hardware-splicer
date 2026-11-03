#!/usr/bin/env python3
"""Bridge an observed, owned real donor into HS's EXISTING canonical PROJECT_INTAKE.

This does NOT repair hardware. It does not verify ownership/consent authenticity
or grant power-on, flight, data access, fabrication, sale, or repair completion.
It validates only operator-submitted file identity and the original HS work
order, then invokes the canonical hardware_splicer.repair_intake normalization.
Do not add guessed electronics, design fixtures, OEM ratings, or virtual parts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from scripts.admit_hs_real_device_bench_evidence_001 import verify_original
from scripts.verify_hs_real_device_workorder_001 import verify

SCHEMA="hardware_splicer.real_donor_field_intake.v1"
OUT_SCHEMA="hardware_splicer.real_donor_intake_bridge_receipt.v1"
REDACT=re.compile(r"\b(?:\d[\s-]?){14,17}\b",re.ASCII)
LABELS={"owner_consent","redacted_device_photo","fault_observation"}

def require(cond,why):
    if not cond:raise ValueError("HS real-donor intake bridge: "+why)

def sha(blob:bytes)->str:return hashlib.sha256(blob).hexdigest()

def template(root:Path,workdir:Path,pilot_id:str)->dict:
    check=verify(root,workdir,pilot_id)
    work_file=workdir/"FIELD_WORK_ORDER.json"
    source=json.loads(work_file.read_text())
    return {
       "schema_version":SCHEMA,
       "pilot_id":pilot_id,
       "original_work_order_sha256":sha(work_file.read_bytes()),
       "device_model_redacted":None,
       "device_symptoms_observed":[],
       "when_fault_occurs":None,
       "safe_reproduction_observations":[],
       "operator_notes_redacted":None,
       "reported_condition":"UNKNOWN_UNINSPECTED",
       "original_operator_files":{
           name:{"source_path":None,"sha256":None} for name in
           ("owner_consent","redacted_device_photo","fault_observation")
       },
       "operator_attestation":{
           "owns_or_has_documented_permission":False,
           "serial_imei_account_information_redacted":False,
           "actual_technician_has_inspected_this_device":False,
           "inspection_did_not_require_unsafe_power_or_motion":False
       },
       "actual_hardware_measurements_submitted":False,
       "actual_power_on_authorized":False,
       "actual_product_repaired":False,
       "outdoor_drone_flight_authorized":False,
       "_operator_instruction":"Fill with real field observations. Keep private owner data out of files, photos and model text. Store original receipts outside source control; do not upload them to public CI.",
    }

def validate_and_bridge(root:Path,workdir:Path,pilot_id:str,donor:Path,
                        evidence_root:Path,out:Path)->dict:
    import sys
    sys.path.insert(0,str((root/"src").resolve()))
    from hardware_splicer.repair_intake import apply_repair_intake_context,extract_repair_context
    verify(root,workdir,pilot_id)
    original_work=workdir/"FIELD_WORK_ORDER.json"
    work=json.loads(original_work.read_text())
    incoming=json.loads(donor.read_text())
    require(incoming.get("schema_version")==SCHEMA and incoming.get("pilot_id")==pilot_id,
            "wrong donor case or schema")
    require(incoming.get("original_work_order_sha256")==sha(original_work.read_bytes()),
            "original work order changed")
    flags=incoming.get("operator_attestation")
    require(isinstance(flags,dict) and
            all(flags.get(key) is True for key in (
                "owns_or_has_documented_permission",
                "serial_imei_account_information_redacted",
                "actual_technician_has_inspected_this_device",
                "inspection_did_not_require_unsafe_power_or_motion")),
            "need explicit technician attestation and owner/redaction clearance")
    for key in ("actual_hardware_measurements_submitted","actual_power_on_authorized",
                "actual_product_repaired","outdoor_drone_flight_authorized"):
        require(incoming.get(key) is False,
                "field intake cannot grant power/flight/repair or claim real measurements")
    observed=incoming.get("device_symptoms_observed")
    require(isinstance(observed,list) and 1<=len(observed)<=12 and
            all(isinstance(x,str) and 4<=len(x.strip())<=200 for x in observed),
            "actual donor needs specific operator-observed symptoms")
    name=incoming.get("device_model_redacted")
    require(isinstance(name,str) and 4<=len(name.strip())<=140,
            "actual donor model label missing")
    texts=[name,*observed]
    for key in ("when_fault_occurs","operator_notes_redacted"):
        value=incoming.get(key)
        if value is not None:
            require(isinstance(value,str) and len(value)<=600,
                    "invalid operator text "+key)
            texts.append(value)
    for text in texts:
        require(not REDACT.search(text) and
                not any(k in text.lower() for k in ("imei:", "serial number:", "password:", "passcode:")),
                "potential owner identity/secret found in textual field; redact first")
    steps=incoming.get("safe_reproduction_observations")
    require(isinstance(steps,list) and len(steps)<=10 and
            all(isinstance(x,str) and 5<=len(x)<=300 and
                not REDACT.search(x) for x in steps),
            "invalid safe observation")
    condition=incoming.get("reported_condition")
    require(condition in {"UNKNOWN_UNINSPECTED","DEENERGIZED_VISUAL_INSPECTION",
                          "DEENERGIZED_CONTINUITY_ONLY"},
            "unsafe or unverified power-on/physical observation asserted")
    supplied=incoming.get("original_operator_files")
    require(isinstance(supplied,dict) and set(supplied)==LABELS,
            "original field file inventory incomplete")
    evidence=[]
    for label in sorted(LABELS):
        record=supplied[label]
        require(isinstance(record,dict) and
                set(record)=={"source_path","sha256"},
                "unrecognized original file evidence metadata")
        size=verify_original(record["source_path"],evidence_root,record["sha256"])
        evidence.append({"purpose":label,"SHA256":record["sha256"],"original_file_bytes":size,
                         "original_file_contents_not_copied_into_repo":True,
                         "authenticity_or_consent_claim_independently_verified":False})
    require(not out.exists() or not any(out.iterdir()),"refuse to overwrite existing real donor evidence")
    out.mkdir(parents=True,exist_ok=True)
    intake={
       "project_name":"hs_real_device_"+pilot_id,
       "goal":"Diagnose and assess restoration of actual donor: "+work["product_goal"],
       "salvage_mode":pilot_id in {"framework_reuse_mini_pc","printer_scrap_camera_slider",
                                   "salvaged_quad_bench_only"},
       "repair_intake":{
           "device_hint":name,
           "symptoms":observed,
           "when_it_fails":incoming.get("when_fault_occurs") or "",
           "repro_steps":steps,
           "operator_notes":incoming.get("operator_notes_redacted") or "",
       },
       "available_parts":[],
       "evidence_notes":[
           "human-reported physical donor intake; owner permission independently unverified",
           "device power and repair not authorized",
           "original work order SHA256: "+incoming["original_work_order_sha256"],
       ],
       "field_donor_source":{
           "pilot_id":pilot_id,
           "operator_attestation_recorded":True,
           "reported_condition":condition,
           "source_work_order_sha256":incoming["original_work_order_sha256"],
           "original_field_evidence_manifest":evidence,
           "original_evidence_not_embedded":True,
           "user_owner_authorization_independently_verified":False,
           "original_source_device_parts_identified_and_qualified":False,
           "operator_bench_measurements_independently_verified":False,
           "physical_product_complete":False,
       },
    }
    canonical=apply_repair_intake_context(intake)
    ctx=extract_repair_context(canonical)
    require(ctx["device_hint"]==name and ctx["symptoms"]==observed,
            "existing HS canonical repair normalization lost actual field observations")
    require(canonical["available_parts"]==[] and not canonical["field_donor_source"]["physical_product_complete"],
            "invented components or physical outcomes")
    manifest={
       "schema_version":OUT_SCHEMA,
       "source_field_work_order_sha256":incoming["original_work_order_sha256"],
       "source_operator_input_sha256":sha(donor.read_bytes()),
       "source_existing_repair_context_schema":ctx["schema_version"],
       "source_original_files_checked":len(evidence),
       "source_file_integrity_only_no_authenticity_proof":True,
       "original_owner_identity_or_private_files_embedded":False,
       "existing_HS_canonical_repair_intake_used":True,
       "physical_donor_reported_by_operator_not_independently_certified":True,
       "electronics_components_assumed":0,
       "actual_repair_verified":False,
       "device_power_on_authorized":False,
       "motion_or_drone_flight_authorized":False,
       "customer_data_access_authorized":False,
       "fabrication_or_resale_authorized":False,
       "verdict":"DONOR_INTAKE_FILE_INTEGRITY_ONLY__AWAITING_REAL_MEASUREMENTS",
    }
    (out/"PROJECT_INTAKE.json").write_text(json.dumps(canonical,indent=2)+"\n")
    (out/"REAL_DONOR_INTAKE_BRIDGE_RECEIPT.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--workdir",type=Path,required=True)
    p.add_argument("--pilot",required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--donor",type=Path,help="Real owner/technician supplied donor record; absent with --template")
    p.add_argument("--files-root",type=Path,help="Private on-disk original evidence root; must not upload to public CI")
    p.add_argument("--template",action="store_true")
    a=p.parse_args()
    if a.template:
        require(a.donor is None and a.files_root is None,"template must not claim real donor")
        body=template(a.root,a.workdir,a.pilot)
        a.output.mkdir(parents=True,exist_ok=True)
        (a.output/"DONOR_INPUT_TEMPLATE.json").write_text(json.dumps(body,indent=2)+"\n")
        print(json.dumps({"template_only":True,"original_donor_evidence_count":0,
                          "device_power_on_authorized":False},indent=2))
    else:
        require(a.donor is not None and a.files_root is not None,"real intake needs original evidence files")
        print(json.dumps(validate_and_bridge(a.root,a.workdir,a.pilot,a.donor,a.files_root,a.output),indent=2))

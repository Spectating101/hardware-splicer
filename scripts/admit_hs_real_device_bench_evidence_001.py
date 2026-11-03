#!/usr/bin/env python3
"""Read a human's bench evidence into the EXISTING HS field-workorder gates.

This is an offline, never-powered evidence handoff. Receipts and measurement
files must be genuinely supplied by the technician and hash-match, but SHA
and self-reported readings cannot independently certify the physical device,
calibration, source chemistry, firmware, safety or commercial value.
No electrical actuation, flight, product success or resale authority is issued.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from scripts.evaluate_real_hardware_recovery_pilots_001 import check_evidence
from scripts.verify_hs_real_device_workorder_001 import verify

SESSION_SCHEMA="hardware_splicer.real_device_operator_bench_session.v1"

def need(cond,reason):
    if not cond:raise ValueError("HS real-device operator handoff: "+reason)

def sha(buf):return hashlib.sha256(buf).hexdigest()

def verify_original(path:Path,root:Path,expected:str)->int:
    ref=Path(str(path))
    need(not ref.is_absolute() and ".." not in ref.parts and ref.parts,
         "outside operator evidence root")
    absolute=(root/ref).resolve()
    need(absolute.is_relative_to(root.resolve()),"evidence path escapes root")
    need(absolute.is_file(),"original evidence file missing")
    file=absolute.read_bytes()
    need(len(file)>=24 and len(file)<80_000_000,"operator file size invalid")
    need(isinstance(expected,str) and len(expected)==64 and
         sha(file)==expected,"operator evidence SHA256 incorrect")
    return len(file)

def valid_timestamp(raw):
    need(isinstance(raw,str) and len(raw)>18,"operator timestamp missing")
    try:dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
    except ValueError as exc:raise ValueError("operator timestamp invalid") from exc
    need(dt.tzinfo is not None and dt.utcoffset()==timezone.utc.utcoffset(dt),
         "operator observed_at must be UTC")
    need(dt.year>=2020,"implausible operator timestamp")
    return dt.isoformat()

def run(root:Path,workdir:Path,pilot:str,session_file:Path,files_root:Path)->dict:
    baseline=verify(root,workdir,pilot)
    work_path=workdir/"FIELD_WORK_ORDER.json"
    work=json.loads(work_path.read_text())
    session=json.loads(session_file.read_text())
    need(session.get("schema_version")==SESSION_SCHEMA,"unsupported operator session schema")
    need(session.get("pilot_id")==pilot,"physical evidence attached to incorrect product")
    need(session.get("original_work_order_sha256")==sha(work_path.read_bytes()),
         "field work order source changed since operator intake")
    need(session.get("actual_product_completed") is False and
         session.get("operating_authority_requested") is False and
         session.get("commercial_resale_authorized") is False,
         "operator record cannot claim product/actuation/sale success")
    gates=work["required_physical_evidence_gates"]
    ids={x["evidence_gate"] for x in gates}
    receipts=session.get("original_evidence_receipts",[])
    need(isinstance(receipts,list),"operator receipts must be list")
    known=set()
    for row in receipts:
        need(isinstance(row,dict),"operator receipt record malformed")
        name=row.get("gate")
        need(name in ids and name not in known,
             "unknown or repeated field evidence gate")
        known.add(name)
        # Reuse original HS SHA-check + no generated proof acceptance logic.
        verify_original(row.get("source_path"),files_root,row.get("sha256"))
        valid_timestamp(row.get("observed_at_utc"))
        need(row.get("finding") in ("observed_pass","observed_fail","inconclusive"),
             "unreviewed operator evidence result")
        need(isinstance(row.get("operator_role"),str) and len(row["operator_role"])>=3,
             "operator role absent")
    existing_evidence=check_evidence(files_root,{"required_evidence":list(ids)},receipts)
    # The existing HS gate correctly records an inconclusive/failed physical
    # observation as NOT ACCEPTED for repair success. Its receipt_issues are
    # nevertheless valid observation statuses at *ingestion* time. Distinguish
    # those known nonpassing findings from structural or SHA invalidity.
    nonpassing={"real operator finding not pass "+row["gate"]
                for row in receipts if row["finding"]!="observed_pass"}
    need(set(existing_evidence["receipt_issues"]).issubset(nonpassing),
         "existing HS evidence admission rejected malformed submitted receipts")
    expected={x["measurement_id"]:x for x in work["measurable_acceptance_template"]}
    measurements=session.get("original_measurements",[])
    need(isinstance(measurements,list),"measurements must be list")
    seen=set()
    summarized=[]
    for item in measurements:
        need(isinstance(item,dict),"operator measurement malformed")
        key=item.get("measurement_id")
        need(key in expected and key not in seen,"unexpected/duplicate source measurement")
        seen.add(key)
        model=expected[key]
        need(item.get("unit")==model["unit"],"source unit changed for "+key)
        value=item.get("observed_value")
        if model["unit"]=="categorical":
            need(isinstance(value,str) and 1<=len(value)<=128,
                 "missing categorical diagnostic value")
        else:
            need(type(value) in (float,int) and math.isfinite(value),
                 "measurement must be real finite number in source units")
        need(isinstance(item.get("instrument_id"),str) and
             len(item["instrument_id"].strip())>=3,
             "meter/instrument identifier required")
        valid_timestamp(item.get("observed_at_utc"))
        need(isinstance(item.get("operator_role"),str) and
             len(item["operator_role"].strip())>=3,
             "human measurement operator role missing")
        evidence_bytes=verify_original(item.get("source_path"),files_root,item.get("sha256"))
        summarized.append({"measurement_id":key,"unit":model["unit"],
                           "original_evidence_bytes":evidence_bytes,
                           "physical_instrument_calibration_independently_confirmed":False,
                           "actual_measurement_truth_independently_confirmed":False,
                           "value_within_original_OEM_limits_qualified":False})
    all_reqs={x["evidence_gate"] for x in gates}
    results={
      "schema_version":"hardware_splicer.real_device_bench_handoff_verification.v1",
      "pilot_id":pilot,
      "original_work_order_sha256":session["original_work_order_sha256"],
      "original_source_lane_and_case_verified":baseline["all_original_source_lanes_and_cases_preserved"],
      "required_original_physical_evidence_gates":len(all_reqs),
      "operator_files_sha256_admitted":len(receipts),
      "operator_pass_findings_recorded":existing_evidence["evidence_passed"],
      "operator_inconclusive_or_failed_findings_recorded":len(nonpassing),
      "operator_inconclusive_or_failed_findings_are_not_gate_passes":True,
      "required_original_gates_unmet":existing_evidence["missing_gates"],
      "operator_measurement_files_sha256_admitted":len(summarized),
      "measurement_fields_not_yet_submitted":sorted(set(expected)-seen),
      "submitted_measurement_metadata":summarized,
      "input_operator_session_is_self_reported":True,
      "source_OEM_limits_independently_verified":False,
      "device_actually_repaired_or_rebuilt_independently_verified":False,
      "physical_safety_or_hardware_motion_authorized":False,
      "drone_flight_authorized":False,
      "customer_account_access_authorized":False,
      "commercial_value_realized_and_verified":False,
      "verdict":"OPERATOR_EVIDENCE_FILE_INTEGRITY_RECORDED_NOT_PHYSICAL_CERTIFICATION"
                if receipts or measurements else "AWAITING_ACTUAL_OPERATOR_EVIDENCE",
    }
    return results

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("root","workdir","files-root","session","output"):
        ap.add_argument("--"+name,required=True,type=Path)
    ap.add_argument("--pilot",required=True)
    a=ap.parse_args()
    report=run(a.root,a.workdir,a.pilot,a.session,a.files_root)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"pilot":report["pilot_id"],
          "operator_files":report["operator_files_sha256_admitted"],
          "measurements":report["operator_measurement_files_sha256_admitted"],
          "physical_safety_authorized":False,
          "verdict":report["verdict"]},indent=2))

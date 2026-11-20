#!/usr/bin/env python3
"""Independent review-preflight for proposed G1 physical evidence bundles.

Files and their receipt hashes can be checked, but human identities,
calibration legitimacy, measurement independence, safe wiring and original
device provenance CANNOT be proven from an editable manifest. Never authorizes
PCB fabrication or bench energization, even for a completely filled packet.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

REQUIRED_ROLES = (
    "source_fault_limit_record",
    "fuse_dc_coordination_review",
    "earth_ground_commonmode_review",
    "load_mount_thermal_record",
    "as_built_identity_and_photos",
    "primary_native_capture",
    "primary_registers",
    "primary_session",
    "reference_native_export",
    "reference_calibration_certificate",
    "clock_trace",
    "independent_signed_review",
)
REQUIRED_TEXT = (
    "run_id","operator_id","independent_reviewer_id",
    "load_mpn","source_model","source_serial",
    "fuse_link_mpn","fuse_holder_mpn","reference_meter_model",
    "reference_meter_serial","reference_calibration_valid_until_utc",
    "primary_sensor_serial","reference_capture_clock","start_utc","end_utc"
)
REQUIRED_NUMERIC = (
    "source_current_limit_a","primary_shunt_measured_ohms",
    "reference_shunt_measured_ohms","measured_max_clock_offset_ms"
)


def sha256(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()


def parse_utc(s: str) -> datetime:
    if not isinstance(s,str) or not s.endswith("Z"):
        raise ValueError("UTC fields require literal Z time")
    t=datetime.fromisoformat(s[:-1]+"+00:00")
    if t.utcoffset()!=timezone.utc.utcoffset(t):
        raise ValueError("UTC time contains invalid offset")
    return t


def verify_primary_receipt(paths: dict[str,Path]) -> str | None:
    try:
        sess=json.loads(paths["primary_session"].read_text(encoding="utf8"))
        if sess.get("capture_kind")!="DECLARED_BENCH_CAPTURE" or sess.get("source_kind")!="linux_i2c":
            return "Primary receipt is missing verified declaration of a non-fixture capture; reject TEST_FIXTURE"
        if sess.get("status")!="COMPLETE" or sess.get("completed_samples",0) < 3:
            return "Primary acquisition receipt is incomplete"
        for name, role in (("samples.csv","primary_native_capture"),
                           ("registers.jsonl","primary_registers")):
            metadata=sess.get("files",{}).get(name,{})
            if metadata.get("sha256")!=sha256(paths[role]) or metadata.get("bytes")!=paths[role].stat().st_size:
                return "Primary session raw capture/hash/byte-length mismatch: "+name
        return None
    except (KeyError, OSError, ValueError, TypeError):
        return "Primary session receipt could not be interpreted"


def screen_packet(packet: dict, base_dir: Path) -> dict:
    problems=[]
    roles={}
    hashes={}
    if packet.get("schema")!="hardware_splicer.witness_g1_bench_packet.v1":
        problems.append("Unexpected packet schema")
    if packet.get("capture_kind")!="DECLARED_BENCH_CAPTURE":
        problems.append("No declared physical bench capture (fixture or blank claims are HOLD)")
    for name in REQUIRED_TEXT:
        value=packet.get(name)
        if not isinstance(value,str) or not value.strip() or value.strip().upper() in ("NOT_SELECTED","UNKNOWN","TBD","NONE","TEST_FIXTURE"):
            problems.append("Missing or placeholder "+name)
    for name in REQUIRED_NUMERIC:
        value=packet.get(name)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            problems.append("Missing or nonfinite "+name)
            continue
        if value <= 0 and name!="measured_max_clock_offset_ms":
            problems.append("Nonpositive "+name)
        if value < 0 and name=="measured_max_clock_offset_ms":
            problems.append("Negative measured clock offset")
    if packet.get("operator_id") and packet.get("operator_id")==packet.get("independent_reviewer_id"):
        problems.append("Reviewer cannot be identical to operator")
    if packet.get("load_mpn")!="RE65G12R0C02":
        problems.append("Load differs from screened precision candidate; design revision required")
    if packet.get("fuse_holder_mpn")!="0031.3551":
        problems.append("Holder differs from existing footprint; schematic review required")
    if isinstance(packet.get("source_current_limit_a"),(int,float)) and packet["source_current_limit_a"] > .65:
        problems.append("Declared source current limit exceeds the candidate 0.65 A envelope")
    try:
        start,end=parse_utc(packet["start_utc"]),parse_utc(packet["end_utc"])
        expiry=parse_utc(packet["reference_calibration_valid_until_utc"])
        if not start<end or expiry<end:
            problems.append("Capture time or reference calibration validity inconsistent")
    except (KeyError, ValueError, TypeError):
        problems.append("Invalid capture/reference calibration UTC interval")
    files=packet.get("files")
    if not isinstance(files,list):
        problems.append("No evidence file inventory")
        files=[]
    seen_paths=set()
    root=base_dir.resolve()
    for item in files:
        if not isinstance(item,dict):
            problems.append("Non-object file record")
            continue
        role=item.get("role")
        if role not in REQUIRED_ROLES or role in roles:
            problems.append("Unknown or duplicate required role: "+str(role))
            continue
        roles[role]=None
        supplied=item.get("path")
        reported=item.get("sha256")
        if not isinstance(supplied,str) or not supplied or Path(supplied).is_absolute():
            problems.append("Missing or nonrelative file path for "+role)
            continue
        if not isinstance(reported,str) or not re.fullmatch(r"[0-9a-f]{64}",reported):
            problems.append("Missing or invalid SHA-256 for "+role)
            continue
        raw_path=(root/supplied)
        p=raw_path.resolve()
        if (".." in Path(supplied).parts or
            not p.is_relative_to(root) or
            any(node.is_symlink() for node in (raw_path,*raw_path.parents) if node!=root) or
            not p.is_file()):
            problems.append("Missing/unsafe evidence path for "+role)
            continue
        if p in seen_paths:
            problems.append("Same physical file reused for independent evidence role "+role)
            continue
        seen_paths.add(p)
        digest=sha256(p)
        if digest!=reported:
            problems.append("Evidence SHA-256 mismatch for "+role)
            continue
        # Identical bytes across independent acquisition/review channels are
        # prohibited, even if they were stored at different paths.
        if digest in hashes:
            problems.append("Identical content across evidence roles "+hashes[digest]+" and "+role)
            continue
        hashes[digest]=role
        roles[role]=p
    for role in REQUIRED_ROLES:
        if role not in roles:
            problems.append("Required evidence role absent: "+role)
    if all(isinstance(roles.get(r),Path) for r in
           ("primary_session","primary_native_capture","primary_registers")):
        result=verify_primary_receipt(roles)
        if result:
            problems.append(result)
    if all(isinstance(roles.get(r),Path) for r in
           ("primary_native_capture","reference_native_export")):
        if roles["primary_native_capture"]==roles["reference_native_export"]:
            problems.append("Reference acquisition cannot be the primary data")
    if len(problems)>50:
        problems=problems[:50]+["Additional issues omitted; this is a bounded preview"]
    return {
        "schema":"hardware_splicer.witness_g1_evidence_preflight.v1",
        "status":"HOLD_MISSING_OR_CONFLICTED_EVIDENCE" if problems else
                 "STRUCTURALLY_FILLED_FOR_INDEPENDENT_HUMAN_REVIEW_ONLY",
        "structural_problems":problems,
        "structural_check_only":True,
        "document_custody_proven":False,
        "instrument_calibration_proven":False,
        "source_isolation_proven":False,
        "earth_commonmode_safe":False,
        "protection_coordination_proven":False,
        "external_clock_synchronized_proven":False,
        "independent_operator_identity_proven":False,
        "metrological_agreement_proven":False,
        "physical_ready":False,
        "fabrication_allowed":False,
        "energization_authorized":False,
        "requires_independent_qualified_engineering_review":True,
        "machine_hashes_never_establish_physical_source_authenticity":True,
    }


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True,help="New report file, not an existing path")
    p.add_argument("--fail-if-held",action="store_true")
    args=p.parse_args(argv)
    if args.out.exists():
        p.error("Output path exists; cannot overwrite evidence")
    try:
        packet=json.loads(args.packet.read_text(encoding="utf-8"))
        if not isinstance(packet,dict):
            raise ValueError("packet must be a JSON object")
        result=screen_packet(packet,args.packet.resolve().parent)
    except (OSError,TypeError,ValueError) as exc:
        result={"schema":"hardware_splicer.witness_g1_evidence_preflight.v1",
                "status":"HOLD_INVALID_PACKET","structural_problems":[str(exc)],
                "physical_ready":False,"fabrication_allowed":False,
                "energization_authorized":False}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"problems":len(result["structural_problems"]),
                      "physical_ready":False,"out":str(args.out)}))
    # A complete packet is for real human review, never for fabrication release.
    return 2 if args.fail_if_held else 0


if __name__=="__main__":
    raise SystemExit(main())

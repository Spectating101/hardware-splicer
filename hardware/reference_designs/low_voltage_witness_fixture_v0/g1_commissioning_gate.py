#!/usr/bin/env python3
"""Combine all G1 evidence / protection / dual-DMM traces, fail closed.

The integrated checker never grants physical commissioning or fabrication;
all file and device identity evidence is editable, and only an independent
authorized engineer can inspect sources, grounding, calibration, instrument
trigger aperture and hardware. This program detects some omissions and
contradictions; it is not a hardware safety certifier.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import g1_evidence_gate as bench
import protection_preflight as protect
import reference_scpi_bracket as scpi
import measurement_screen as primary_reference_csv

HERE=Path(__file__).resolve().parent
REF_SCHEMA="hardware_splicer.bracketed_scpi_reference.v1"
MIN_SAMPLES=183


def sha256(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ts(x:str)->datetime:
    if not isinstance(x,str) or not x.endswith("Z"):
        raise ValueError("Reference timestamp must be UTC Z")
    return datetime.fromisoformat(x[:-1]+"+00:00")


def check_reference(session_path:Path)->dict:
    errors=[]
    details={}
    try:
        root=session_path.resolve().parent
        x=json.loads(session_path.read_text(encoding="utf8"))
        if x.get("schema")!=REF_SCHEMA:
            errors.append("Unknown SCPI reference source schema")
        if x.get("capture_kind")!="DECLARED_REFERENCE_BRACKETED_UNVERIFIED":
            errors.append("TEST_FIXTURE or otherwise unverified reference claim")
        if x.get("source_kind")!="dual_scpi_meters":
            errors.append("Not actually declared as two independent SCPI meters")
        if x.get("status")!="COMPLETE_SOFTWARE_TIMESTAMP_BRACKETED_ONLY":
            errors.append("Incomplete bracketed reference acquisition")
        counts=x.get("samples_captured")
        if isinstance(counts,bool) or not isinstance(counts,int) or counts<MIN_SAMPLES:
            errors.append("Insufficient reference samples for planned 3-minute/1Hz witness")
        if x.get("reference_meter_paths_distinct") is not True:
            errors.append("Missing distinct physical resource paths")
        if x.get("instrument_aperture_times_verified") is not False:
            errors.append("Unsupported assertion of instrument aperture verification")
        i=x.get("identifiers",{})
        if not isinstance(i,dict):
            i={}
        left,right=i.get("shunt_idn"),i.get("bus_idn")
        if not all(isinstance(v,str) and v.strip() and
                   "SYNTHETIC" not in v.upper() and "FAKE" not in v.upper()
                   for v in (left,right)) or left==right:
            errors.append("No distinct plausible real DMM *IDN? identities")
        resource_claims=i.get("resource_names_claimed")
        if (not isinstance(resource_claims,(list,tuple)) or
            len(resource_claims)!=2 or
            not all(isinstance(z,str) and z.strip() for z in resource_claims) or
            resource_claims[0]==resource_claims[1]):
            errors.append("No two explicit distinct meter VISA resource declarations")
        if x.get("calibration_status_verified") is True or x.get("clock_synchronization_verified") is True:
            # This producer has no means to independently confirm these:
            errors.append("Unjustified physical calibration or clock verification claim")
        files=x.get("files",{})
        inputs={}
        for fname in ("reference-preview.csv","reference-query-raw.jsonl"):
            target=root/fname
            if target.is_symlink() or not target.is_file():
                errors.append("Missing or linked reference evidence: "+fname)
                continue
            meta=files.get(fname,{})
            if meta.get("sha256")!=sha256(target) or meta.get("bytes")!=target.stat().st_size:
                errors.append("Mismatched reference trace receipt/hash: "+fname)
                continue
            inputs[fname]=target
        if len(inputs)==2:
            with inputs["reference-preview.csv"].open(newline="",encoding="utf8") as f:
                rows=list(csv.DictReader(f))
            raw=[json.loads(s) for s in
                 inputs["reference-query-raw.jsonl"].read_text(encoding="utf8").splitlines()]
            if len(rows)!=len(raw) or len(rows)!=counts:
                errors.append("Reference CSV/SCPI trace/sample count diverges")
            else:
                previous=None
                for index,(row,trace) in enumerate(zip(rows,raw)):
                    try:
                        if trace["index"]!=index or trace["true_instrument_aperture_proven"] is not False:
                            raise ValueError("Invalid raw sample sequence or aperture overclaim")
                        if row["timestamp_utc"]!=trace["host_reference_midpoint_utc"]:
                            raise ValueError("Normalized reference timestamp not bound to trace")
                        stamp=ts(row["timestamp_utc"])
                        if previous is not None and not .5<=(stamp-previous).total_seconds()<=1.5:
                            raise ValueError("Reference timestamps out of 1Hz coverage range")
                        previous=stamp
                        for role,key in (("bus","voltage_v"),("shunt","shunt_voltage_v")):
                            item=trace[role]
                            value=float(row[key])
                            reported=float(item["voltage_v"])
                            if (not math.isfinite(value) or value<=0 or
                                not math.isfinite(reported) or reported<=0 or
                                not math.isclose(value,reported,rel_tol=2e-8,abs_tol=1e-10)):
                                raise ValueError("Reference CSV value does not match native SCPI response")
                            if item.get("aperture_time_verified") is not False:
                                raise ValueError("SCPI response cannot prove instrument aperture")
                            raw_value=scpi.parse_voltage(item["response_raw"],max_abs_v=(20 if role=="bus" else .2))
                            if not math.isclose(raw_value,reported,rel_tol=2e-8,abs_tol=1e-10):
                                raise ValueError("Recorded value differs from original SCPI response")
                            before,after=ts(item["query_start_utc"]),ts(item["query_end_utc"])
                            if before>after or not before<=stamp<=after:
                                raise ValueError("Reference CSV midpoint not bracketed by DMM queries")
                            if item.get("command")!=("MEAS:VOLT:DC? 20" if role=="bus" else "MEAS:VOLT:DC? 0.2"):
                                raise ValueError("Unexpected SCPI range measurement command")
                            if not 0<=float(item["query_latency_ms"])<=750:
                                raise ValueError("SCPI query latency limit violated")
                        if not 0<=float(trace["host_query_center_skew_ms"])<=250:
                            raise ValueError("Host query timing skew violated")
                    except (TypeError,KeyError,ValueError,scpi.ReferenceCaptureError) as err:
                        errors.append(f"Invalid SCPI sample {index}: {err}")
                        break
                if previous is not None and rows:
                    first=ts(rows[0]["timestamp_utc"])
                    if (previous-first).total_seconds()<MIN_SAMPLES-3:
                        errors.append("Reference 3-minute observation duration not established")
                details["normalized_samples"]=len(rows)
        else:
            details["normalized_samples"]=0
        details["provisional_source_identifiers"]={
            "shunt":left,"bus":right
        }
    except (OSError,ValueError,TypeError,KeyError) as err:
        errors.append("Unreadable reference packet: "+str(err))
    return {
        "structural_status":"TRACE_STRUCTURALLY_INTACT_NOT_TIMING_PROVEN" if not errors
                            else "REFERENCE_TRACE_HOLD",
        "problems":errors,
        "details":details,
        "reference_source_physically_authenticated":False,
        "instrument_aperture_time_proven":False,
        "external_timebase_proven":False,
        "physical_ready":False
    }



def crosscheck_primary_reference(packet_file: Path, reference_session_path: Path) -> dict:
    """Bind the bench manifest to the SCPI raw export and paired primary samples.

    This is *structural* clock pairing, not external synchronization or an
    instrument's actual ADC aperture. Call only after the standalone source
    evidence validators have succeeded: they establish safe path confinement.
    """
    issues = []
    result = {
        "status": "CROSS_STREAM_BINDING_HOLD",
        "problems": issues,
        "paired_samples": 0,
        "max_observed_host_timestamp_delta_ms": None,
        "reference_bytes_bound_to_g1_manifest": False,
        "absolute_clock_alignment_verified": False,
        "physical_measurement_independence_verified": False,
        "physical_ready": False,
    }
    try:
        packet = json.loads(packet_file.read_text(encoding="utf-8"))
        ref_session = json.loads(reference_session_path.read_text(encoding="utf-8"))
        roles = {record["role"]: record for record in packet["files"]}
        ref_export = roles["reference_native_export"]
        ref_receipt = ref_session["files"]["reference-preview.csv"]
        if ref_export.get("sha256") != ref_receipt.get("sha256"):
            issues.append("G1 reference native export SHA differs from SCPI receipt")
        else:
            result["reference_bytes_bound_to_g1_manifest"] = True
        reference_serial = packet.get("reference_meter_serial")
        identifiers = ref_session.get("identifiers", {})
        serials = [
            item.split(",")[2].strip()
            for item in (identifiers.get("shunt_idn"), identifiers.get("bus_idn"))
            if isinstance(item, str) and len(item.split(",")) >= 3
        ]
        if not isinstance(reference_serial, str) or reference_serial not in serials:
            issues.append("G1 reference serial not present in a native SCPI *IDN? response")
        root = packet_file.resolve().parent
        p = root / roles["primary_native_capture"]["path"]
        r = root / ref_export["path"]
        primary = primary_reference_csv._read(
            p, ("timestamp_utc", "voltage_v", "current_a"), 1.5
        )
        reference = primary_reference_csv._read(
            r, ("timestamp_utc", "voltage_v", "shunt_voltage_v"), 1.5
        )
        if len(primary) != len(reference) or len(primary) < MIN_SAMPLES:
            issues.append("G1 primary/reference pair count must match and reach 183")
        else:
            allowed = packet.get("measured_max_clock_offset_ms")
            if (isinstance(allowed, bool) or not isinstance(allowed, (float, int))
                    or not math.isfinite(allowed) or allowed < 0 or allowed > 200):
                issues.append("Claimed maximum clock offset is missing or exceeds 200 ms screening policy")
            else:
                offsets = [
                    abs((p_row["timestamp"] - r_row["timestamp"]).total_seconds()) * 1000
                    for p_row, r_row in zip(primary, reference)
                ]
                maximum = max(offsets)
                result["paired_samples"] = len(primary)
                result["max_observed_host_timestamp_delta_ms"] = maximum
                if maximum > 200 or maximum > allowed:
                    issues.append("Primary/reference host timestamps cannot be paired inside claimed budget")
                if (primary[-1]["timestamp"]-primary[0]["timestamp"]).total_seconds() < 179:
                    issues.append("Primary observation does not span three-minute witness")
                start = bench.parse_utc(packet["start_utc"])
                end = bench.parse_utc(packet["end_utc"])
                if (primary[0]["timestamp"] < start or
                        primary[-1]["timestamp"] > end or
                        reference[0]["timestamp"] < start or
                        reference[-1]["timestamp"] > end):
                    issues.append("Primary/reference samples lie outside the declared G1 window")
    except (OSError, KeyError, ValueError, TypeError, IndexError,
            primary_reference_csv.ScreeningError) as exc:
        issues.append("Cross-stream evidence unreadable or inconsistent: " + str(exc))
    if not issues:
        result["status"] = "PAIRED_HOST_TIMESTAMPS_ONLY_UNVERIFIED_APERTURE"
    return result


def evaluate(evidence:Path,protection:Path,reference_session:Path)->dict:
    e=bench.screen_packet(json.loads(evidence.read_text()),evidence.resolve().parent)
    p=protect.assess(json.loads(protection.read_text()))
    r=check_reference(reference_session)
    paired = (crosscheck_primary_reference(evidence, reference_session)
              if not e["structural_problems"] and not r["problems"] else
              {"status": "NOT_CHECKED_UNVERIFIED_SOURCE_INPUTS",
               "problems": [], "paired_samples": 0,
               "absolute_clock_alignment_verified": False,
               "physical_ready": False})
    blocks=[]
    if e["structural_problems"]:
        blocks.append("Physical evidence dossier contains "+str(len(e["structural_problems"]))+" structural problems")
    if p["missing_evidence"] or p["contradictions"]:
        blocks.append("Source/fuse/thermal preflight has "+str(len(p["missing_evidence"]))+
                      " missing requirements and "+str(len(p["contradictions"]))+" contradictions")
    if r["problems"]:
        blocks.append("Reference query trace has "+str(len(r["problems"]))+" errors")
    if paired["problems"]:
        blocks.append("Primary/reference sources are not correctly bound: "+str(len(paired["problems"]))+" errors")
    return {
        "schema":"hardware_splicer.witness_g1_combined_preflight.v1",
        "status":"STRUCTURAL_CONFLICTS_HOLD" if blocks else
                 "FOUR_STRUCTURAL_CHECKS_ONLY_HUMAN_REVIEW_REQUIRED",
        "physical_evidence_status":e["status"],
        "protection_status":p["structural_status"],
        "reference_status":r["structural_status"],
        "primary_reference_link_status":paired["status"],
        "primary_reference_link_problems":paired["problems"],
        "primary_reference_pairs_checked":paired["paired_samples"],
        "reasons":blocks,
        "evidence_hashes":{"g1_packet":sha256(evidence),
                           "protection_input":sha256(protection),
                           "reference_session":sha256(reference_session)},
        "reference_problems":r["problems"],
        "unclosed":[
            "Actual independent qualified engineering approval of source/fuse fault energy, isolated supply, host earth and wiring",
            "Assembled load/chassis/thermal proof and real part inventory",
            "Genuine device identities and original vendor certificates; unverified manifests may be forged",
            "True ADC aperture/external-clock synchronization; even well-aligned paired CSV host timestamps cannot establish it",
            "Independently characterized 10milliohm reference and justified uncertainty threshold",
            "Authorized physical commissioning and second operator reproduction",
        ],
        "all_tests_software_only":True,
        "fabrication_allowed":False,
        "energization_authorized":False,
        "physical_ready":False,
        "metrological_agreement_proven":False,
        "instrument_authenticity_verified":False,
        "external_timebase_verified":False,
    }


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--g1-packet",type=Path,required=True)
    ap.add_argument("--protection-input",type=Path,required=True)
    ap.add_argument("--reference-session",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args(argv)
    if args.out.exists():
        ap.error("Output exists; evidence must not be silently overwritten")
    try:
        result=evaluate(args.g1_packet,args.protection_input,args.reference_session)
    except (OSError,ValueError,TypeError) as err:
        result={"schema":"hardware_splicer.witness_g1_combined_preflight.v1",
                "status":"INVALID_INPUT_HOLD","reasons":[str(err)],
                "fabrication_allowed":False,"energization_authorized":False,
                "physical_ready":False}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"physical_ready":False,
                      "out":str(args.out)}))
    return 2


if __name__=="__main__":
    raise SystemExit(main())

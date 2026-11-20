#!/usr/bin/env python3
"""Fail-closed G1 protection evidence preflight for the 5V witness station.

Numerical consistency & completeness checks only. A digitally populated
manifest cannot authenticate a power supply, fuse curves, fault waveform,
earth isolation, load mounting or human review. It NEVER permits energization.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
SCHEMA="hardware_splicer.witness_g1_protection_preflight.v1"


def numeric(d: dict, key: str, label: str, missing: list[str]) -> float | None:
    v=d.get(key)
    if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<=0:
        missing.append("Missing or invalid positive "+label)
        return None
    return float(v)


def named(d: dict, key: str, label: str, missing: list[str]) -> str | None:
    x=d.get(key)
    if not isinstance(x,str) or not x.strip() or x.strip().upper() in (
        "NOT_SELECTED","UNKNOWN","NONE","TBD","PLACEHOLDER","TEST_FIXTURE"):
        missing.append("Unselected/unspecified "+label)
        return None
    return x.strip()


def flag(d: dict,key: str,label: str,missing: list[str]) -> bool:
    v=d.get(key)
    if v is not True:
        missing.append("Independent evidence not established: "+label)
        return False
    return True


def assess(packet: dict) -> dict:
    missing=[]
    contradictions=[]
    if not isinstance(packet,dict):
        packet={}
    if packet.get("schema")!=SCHEMA:
        missing.append("Unknown evidence schema")
    normal=packet.get("normal_operation") or {}
    source=packet.get("source") or {}
    fuse=packet.get("fuse") or {}
    wiring=packet.get("wiring") or {}
    thermal=packet.get("thermal") or {}
    review=packet.get("review") or {}
    if not all(isinstance(s,dict) for s in (normal,source,fuse,wiring,thermal,review)):
        raise ValueError("Every top-level section must be an object")
    vbus=numeric(normal,"maximum_j2_bus_voltage_v","J2 maximum voltage",missing)
    current=numeric(normal,"normal_current_upper_bound_a","normal maximum current",missing)
    load=numeric(normal,"load_worst_case_power_w","normal load power bound",missing)
    voltage_source=numeric(source,"voltage_limit_v","source maximum voltage",missing)
    ilim=numeric(source,"set_current_limit_a","source set current limit",missing)
    sustained=numeric(source,"measured_sustained_short_current_a","measured sustained-short current",missing)
    peak=numeric(source,"measured_peak_short_current_a","measured prospective fault peak",missing)
    latency=numeric(source,"measured_current_limit_response_ms","source current-limit response time",missing)
    link_in=numeric(fuse,"nominal_current_a","fuse nominal current",missing)
    link_v=numeric(fuse,"dc_voltage_rating_v","fuse DC voltage rating",missing)
    link_i=numeric(fuse,"dc_breaking_current_a","fuse DC interrupt rating",missing)
    cable_a=numeric(wiring,"continuous_current_ampacity_a","conductor continuous current",missing)
    terminal_a=numeric(wiring,"connector_dc_current_rating_a","connector current rating",missing)
    derate=numeric(thermal,"derated_allowable_load_w_at_actual_ambient","physically mounted load derated W",missing)
    measured_t=thermal.get("measured_load_temperature_c")
    if (isinstance(measured_t,bool) or not isinstance(measured_t,(int,float)) or
            not math.isfinite(measured_t)):
        missing.append("Missing or invalid finite measured load temperature C")
        measured_t=None
    named(source,"manufacturer","source manufacturer",missing)
    named(source,"model","source model",missing)
    named(source,"serial","source serial",missing)
    named(fuse,"fuse_link_mpn","fuse link exact MPN",missing)
    named(wiring,"cable_assembly_mpn","wiring/harness identification",missing)
    named(thermal,"mounting_part","load thermal chassis/mount identity",missing)
    reviewer=named(review,"engineering_reviewer","engineering reviewer identity",missing)
    operator=named(review,"operator","operator identity",missing)
    if reviewer and operator and reviewer==operator:
        contradictions.append("Independent reviewer and operator identity are the same")
    if fuse.get("holder_mpn")!="0031.3551":
        contradictions.append("Holder differs from original PCB candidate; requires new geometry and datasheet review")
    for section,keys in (
        (source,("independent_source_limit_test_verified","isolation_and_earth_review_verified",
                 "independent_fault_shutdown_review_verified")),
        (fuse,("time_current_curve_verified","clearing_at_measured_sustained_fault_current_verified",
                "manufacturer_fuse_link_holder_match_verified","holder_thermal_derating_checked")),
        (wiring,("independent_short_and_shield_review_verified",)),
        (thermal,("independent_thermal_mount_review_verified",)),
        (review,("actual_source_and_fuse_identification_confirmed","source_characterization_physical"))
    ):
        for k in keys:
            flag(section,k,k,missing)
    if vbus is not None and vbus>5.25:
        contradictions.append("Maximum J2 voltage exceeds planned 5.25 V envelope")
    if voltage_source is not None and voltage_source>5.25:
        contradictions.append("Source voltage limit exceeds nominal design ceiling")
    if ilim is not None and ilim>.65:
        contradictions.append("Source set current limit exceeds 0.65 A review candidate")
    if sustained is not None and ilim is not None and sustained > ilim*1.01:
        contradictions.append("Measured sustained short current exceeds current-limit set point")
    if peak is not None and sustained is not None and peak+1e-9<sustained:
        contradictions.append("Measured peak current < sustained short current, inconsistent waveform")
    if current is not None and ilim is not None and current>ilim:
        contradictions.append("Maximum normal load current cannot be supplied below specified current limit")
    if load is not None and load>2.5:
        contradictions.append("Normal-load maximum power exceeds 2.5 W")
    if link_i is not None and peak is not None and link_i<peak:
        contradictions.append("Fuse DC interrupt rating lower than prospective fault peak current")
    if link_v is not None and voltage_source is not None and link_v<voltage_source:
        contradictions.append("Fuse DC voltage rating below maximum source output")
    if cable_a is not None and sustained is not None and cable_a<sustained:
        contradictions.append("Conductor continuous ampacity below sustained fault current")
    if terminal_a is not None and sustained is not None and terminal_a<sustained:
        contradictions.append("Connector current rating below sustained fault current")
    if derate is not None and load is not None and derate<load:
        contradictions.append("Mount/ambient derated load power below conservative normal load power")
    # Do not claim a fuse clears below its rating. Actual trip/clearing evidence
    # may still be needed for energy protection, but is not automatically accepted.
    fuse_not_reliably_clearing=None
    if sustained is not None and link_in is not None:
        fuse_not_reliably_clearing=sustained<=link_in
        if fuse_not_reliably_clearing:
            contradictions.append(
                "Sustained current <= fuse nominal: fuse cannot be counted on for automatic fault clearing")
    if latency is not None and latency>500:
        contradictions.append("Current-limit response slower than illustrative 500ms ceiling; verify physical transient")
    if measured_t is not None and (measured_t < -50 or measured_t>250):
        contradictions.append("Reported load temperature outside plausible candidate reporting range")
    if vbus is not None and current is not None and load is not None and load>vbus*current*1.01:
        contradictions.append("Reported load power exceeds bus voltage x normal maximum current")
    return {
        "schema":"hardware_splicer.witness_g1_protection_screen.v1",
        "structural_status":("NUMERIC_CONTRADICTIONS_HOLD" if contradictions else
                             "MISSING_PHYSICAL_EVIDENCE_HOLD" if missing else
                             "FILLED_FOR_INDEPENDENT_ENGINEER_REVIEW_ONLY"),
        "missing_evidence":missing,
        "contradictions":contradictions,
        "fuse_clearing_cannot_be_relied_on_at_sustained_limit":fuse_not_reliably_clearing,
        "potential_continuous_source_output_w_if_setpoint_real":
            round(vbus*ilim,6) if vbus is not None and ilim is not None else None,
        "primary_fault_protection_demonstrated":False,
        "source_output_isolation_proven":False,
        "fuse_coordination_validated_by_machine":False,
        "operator_review_authenticated":False,
        "fabrication_allowed":False,
        "energization_authorized":False,
        "physical_ready":False,
        "reason":"All engineering release authority remains external to editable evidence files; qualified reviewer must verify original vendor records, measurements, circuit and actual devices.",
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    if args.out.exists():
        parser.error("Output exists; never overwrite prior evidence")
    try:
        input_dict=json.loads(args.input.read_text())
        result=assess(input_dict)
    except (OSError,ValueError,TypeError) as e:
        result={"schema":"hardware_splicer.witness_g1_protection_screen.v1",
                "structural_status":"INVALID_EVIDENCE_HOLD",
                "reason":str(e),"fabrication_allowed":False,"energization_authorized":False,"physical_ready":False}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":result["structural_status"],
                      "fabrication_allowed":False,"energization_authorized":False,
                      "out":str(args.out)}))
    return 2  # permanently requires independent human and physical review


if __name__=="__main__":
    raise SystemExit(main())

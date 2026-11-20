#!/usr/bin/env python3
"""Frozen-vendor-source comparison and bounded incomplete metrology estimate.

This is a *research selection tool*, NOT an instrument configuration
utility.  It does not send commands to any power supply or DMM and cannot
validate a real source, 5.25 V transients, fuse clearance, grounding,
metrological calibration or readiness to fabricate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
CATALOG=HERE/"G1_SOURCE_AND_FUSE_CANDIDATES_20261120.json"
SCHEMA="hardware_splicer.witness_g1_source_candidate_evidence.v1"

# Frozen expected claims, independently reviewed as source *leads*, not
# trusted user-supplied approvals. Source updates require a code review.
FROZEN={
 "rigol_dp832a_ch1": {
   "brand":"RIGOL","model":"DP832A","output_channel":"CH1",
   "rated_max_v":30,"rated_max_a":3,
   "programmable_ovp":True,"programmable_ocp":True,
   "ovp_software_range_max_v":33,"ocp_software_range_max_a":3.3,
 },
 "siglent_spd3303xe_ch1": {
   "brand":"SIGLENT","model":"SPD3303X-E","output_channel":"CH1",
   "rated_max_v":32,"rated_max_a":3.2,
   "programmable_ovp":False,"programmable_ocp":True,
   "ovp_software_range_max_v":None,"ocp_software_range_max_a":None,
 },
 "siglent_spd4000x_family":{
   "brand":"SIGLENT","model":"SPD4000X SERIES","output_channel":None,
   "rated_max_v":None,"rated_max_a":None,
   "programmable_ovp":True,"programmable_ocp":True,
   "ovp_software_range_max_v":None,"ocp_software_range_max_a":None,
 },
}


def sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def require_pos(x, label):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0:
        raise ValueError(f"{label} must be positive finite")
    return float(x)


def catalogue_review(data:dict)->dict:
    if data.get("schema")!=SCHEMA:
        raise ValueError("Unknown source-research catalogue")
    items=data.get("source_candidates")
    if not isinstance(items,list) or len(items)!=len(FROZEN):
        raise ValueError("Candidate inventory changed without engineering review")
    if {x.get("id") for x in items} != set(FROZEN):
        raise ValueError("Unknown or duplicated source candidate")
    for row in items:
        known=FROZEN[row["id"]]
        if any(row.get(key)!=v for key,v in known.items()):
            raise ValueError("Vendor/OCP/OVP facts changed: independent source review required for "+row["id"])
    nominal=require_pos(data.get("nominal_source_set_v"),"nominal_set_v")
    limit=require_pos(data.get("max_j2_v"),"max_j2_v")
    ovp=require_pos(data.get("source_ovp_candidate_v"),"ovp_target")
    ocp=require_pos(data.get("source_ocp_candidate_a"),"ocp_target")
    rmin=require_pos(data.get("min_worst_case_load_ohms"),"minimum load R")
    if not (math.isclose(nominal,5.0,abs_tol=1e-9) and
            math.isclose(ovp,5.2,abs_tol=1e-9) and
            math.isclose(limit,5.25,abs_tol=1e-9) and
            math.isclose(ocp,.65,abs_tol=1e-9) and
            math.isclose(rmin,11.82654,abs_tol=1e-6)):
        raise ValueError("Pinned 5V/5.2V-OVP/.65A/12ohm operating model changed; independent design review required")
    current=limit/rmin
    if not current < ocp:
        raise ValueError("Normal worst-case load current exceeds proposed OCP")
    ranked=[]
    for row in items:
        documented_ovp=FROZEN[row["id"]]["programmable_ovp"]
        documented_ocp=FROZEN[row["id"]]["programmable_ocp"]
        exact_model=bool(FROZEN[row["id"]]["output_channel"])
        usable=bool(documented_ovp and documented_ocp and exact_model)
        reason=(
            "Candidate with vendor-documented configurable OVP+OCP: CONDITIONAL BORROW REVIEW ONLY."
            if usable else
            "FAIL strict ceiling: vendor documentation explicitly denies user-configurable OVP."
            if not documented_ovp else
            "HOLD: series description lacks exact model/channel/range."
        )
        ranked.append({
            "id":row["id"],"brand":row["brand"],"model":row["model"],
            "configured_ovp_capability_documented":documented_ovp,
            "configured_ocp_capability_documented":documented_ocp,
            "exact_channel_reviewed":exact_model,
            "supplier_specification_fit_for_borrow_review":usable,
            "physical_overvoltage_limit_enforced":False,
            "actual_peak_short_current_checked":False,
            "physical_ovp_trip_observed":False,
            "review":reason
        })
    fuse=data.get("fuse",{})
    if (fuse.get("holder_mpn")!="0031.3551" or
        fuse.get("selected_link_mpn") is not None or
        fuse.get("can_clear_source_limited_sustained_0_65a") is not False or
        fuse.get("holder_ac_rating_is_not_fuse_dc_rating") is not True):
        raise ValueError("Fuse-link/holder qualification claim changed; hold")
    return {
        "schema":"hardware_splicer.witness_g1_source_suitability.v1",
        "research_scope":"VENDOR_DOCUMENTS_NOT_SOURCE_PROOF",
        "normal_worst_case_current_a":current,
        "nominal_setpoint_v":nominal,
        "planned_ovp_trip_v":ovp,
        "planned_ocp_trip_a":ocp,
        "maximum_j2_voltage_v":limit,
        "candidate_comparison":ranked,
        "preferred_borrow_candidate":"rigol_dp832a_ch1",
        "borrow_candidate_physically_available":False,
        "real_source_identity_verified":False,
        "actual_ovp_peak_below_ceiling_proven":False,
        "source_fault_waveform_proven":False,
        "dc_fuse_link_selected":False,
        "fuse_role":"RETAIN HOLDER AS UNQUALIFIED COMPONENT; NO CREDIT FOR AUTOMATIC CLEARING",
        "fabrication_allowed":False,
        "energization_authorized":False,
        "physical_ready":False,
    }


def metrology_bound(data:dict)->dict:
    # 5V / (12 + 0.075) from original hypothetical SPICE equivalent.
    # This is an expected register-fixture operating point, not hardware.
    i=5/12.075
    vbus=i*12
    vshunt=i*.01
    primary_shunt_tolerance_pct=1.0
    reference_shunt_tolerance_pct=1.0
    dmm_shunt_uv=(.015/100*vshunt+.004/100*.2)*1e6
    dmm_bus_mv=(.015/100*vbus+.004/100*20)*1e3
    r_voltage_pct=(dmm_shunt_uv*1e-6/vshunt)*100
    bus_voltage_pct=dmm_bus_mv/1000/vbus*100
    aggregate=primary_shunt_tolerance_pct+reference_shunt_tolerance_pct+r_voltage_pct+bus_voltage_pct
    return {
        "scope":"INCOMPLETE_WORST_CASE_PRECALIBRATION_ALLOWANCE_NOT_PHYSICAL_ACCURACY",
        "nominal_current_a_simulated":i,
        "simulated_j2_voltage_v":vbus,
        "reference_shunt_voltage_mV_simulated":vshunt*1000,
        "reference_10mohm_initial_tolerance_pct":reference_shunt_tolerance_pct,
        "primary_15mohm_initial_tolerance_pct":primary_shunt_tolerance_pct,
        "hypothetical_sdm3055_200mV_dcv_abs_error_uV":dmm_shunt_uv,
        "hypothetical_sdm3055_20V_dcv_abs_error_mV":dmm_bus_mv,
        "hypothetical_shunt_dmm_fraction_pct":r_voltage_pct,
        "hypothetical_bus_dmm_fraction_pct":bus_voltage_pct,
        "incomplete_simple_additive_worst_case_pct":aggregate,
        "physical_0_75pct_discrimination_justified":False,
        "one_percent_physical_agreement_justified":False,
        "omissions":[
            "No calibration certificates or shunt resistance measurements",
            "Primary INA228 current/voltage ADC absolute accuracy and calibration",
            "Timing and noncoincident ADC aperture uncertainty",
            "Thermal EMF, noise, temperature drift, sensor correlation",
            "Actual earthing and bus measurement topology",
            "Instrument conditions (warm-up, slow-rate mode, 23±5°C) not verified"
        ],
        "source":"https://www.siglenteu.com/wp-content/uploads/dlm_uploads/2023/04/SDM3055_Datasheet_E04A-1.pdf",
    }


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalogue",type=Path,default=CATALOG)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args(argv)
    if args.out.exists():
        ap.error("Output exists; source evidence must not be overwritten")
    try:
        data=json.loads(args.catalogue.read_text(encoding="utf8"))
        review=catalogue_review(data)
        review["incomplete_metrology"]=metrology_bound(data)
        review["catalogue_sha256"]=sha(args.catalogue)
    except (ValueError,TypeError,KeyError,OSError) as exc:
        review={
            "schema":"hardware_splicer.witness_g1_source_suitability.v1",
            "research_scope":"INVALID_OR_CHANGED_INPUT_HOLD",
            "errors":[str(exc)],
            "fabrication_allowed":False,
            "energization_authorized":False,
            "physical_ready":False
        }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(review,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"scope":review["research_scope"],"out":str(args.out),
                      "energization_authorized":False}))
    return 2


if __name__=="__main__":
    raise SystemExit(main())

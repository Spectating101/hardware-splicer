"""Reconcile real slicer-estimated plastic mass with HS functional fit/stability.

The previously CAD-volume-derived density factor was an assumption; actual
G-code extrusion estimates are more specific, while still uncalibrated.
This module reopens ONLY the numerical static tipping proxy, preserving
the actual BREP/mesh/fit checks and unverified fabrication authority.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any,Mapping

from .function_print_geometry import canonical,validate_design
from .function_print_slicer import _assert_valid_profile

SCHEMA="hs.slicer_mass_feedback_policy.v1"
RESULT="hs.function_print_slicer_feedback.v1"

def _source_gate(req:Mapping[str,Any],profile:Mapping[str,Any],policy:Mapping[str,Any])->None:
    validate_design(req)
    _assert_valid_profile(profile,req)
    if policy.get("schema")!=SCHEMA:
        raise ValueError("unknown feedback safety/selection protocol")
    if policy.get("objective")!="minimize actual-slicer-estimated filament mass among candidates satisfying all geometry constraints and chosen tip-proxy screen":
        raise ValueError("selection objective changed")
    if policy.get("provenance")!="Exploratory post-slice sensitivity analysis; guard band chosen for stress testing, not empirically calibrated reliability":
        raise ValueError("post hoc uncertainty method falsely relabelled")
    allowed={
        "assumed_filament_mass_lower_fraction":(.5,1.),
        "assumed_board_mass_lower_fraction":(.5,1.),
        "assumed_lateral_force_upper_fraction":(1.,1.8)
    }
    for key,(lo,hi) in allowed.items():
        value=policy.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:
            raise ValueError("unknown guard-band multiplier: "+key)
    for key in ("minimum_nominal_tip_factor","minimum_guarded_tip_factor"):
        if type(policy.get(key)) not in (int,float) or not 1<=policy[key]<=3:
            raise ValueError("invalid assumed acceptance ratio")
    if any(policy.get("design_authority",{}).values()):
        raise ValueError("unverified printed mass cannot be relabelled physical measurement")

def _tip_factor(part_g:float,board_g:float,depth_mm:float,push_n:float,height_mm:float)->float:
    return (part_g+board_g)/1000*9.81*(depth_mm/2)/1000/(push_n*height_mm/1000)

def interpret_feedback(req:Mapping[str,Any],profile:Mapping[str,Any],
                       policy:Mapping[str,Any],report:Mapping[str,Any],
                       cad_report:Mapping[str,Any])->dict[str,Any]:
    """Pure, deterministic post-hoc mass sensitivity; zero physical claims."""
    _source_gate(req,profile,policy)
    if report.get("schema")!="hs.native_slicer_geometry_benchmark.v1" or not report.get("all_calls_successful"):
        raise ValueError("actual native-slicer model run missing")
    expected_source=hashlib.sha256(canonical(req)).hexdigest()
    expected_profile=hashlib.sha256(canonical(profile)).hexdigest()
    if (report["design_source_sha256"]!=expected_source
            or report["slicer_profile_sha256"]!=expected_profile):
        raise ValueError("slicer result belongs to other input geometry or print profile")
    alternatives={x["id"]:x for x in req["alternatives"]}
    source_cad={x["id"]:x for x in cad_report["alternatives"]}
    if (cad_report.get("schema")!="hs.function_to_printable_cad_trial.v1"
            or cad_report.get("source_design_sha256")!=expected_source):
        raise ValueError("independent source CAD evaluation does not match design")
    if set(alternatives)!=set(source_cad):
        raise ValueError("not every original real CAD body was independently validated")
    rows=[]
    for layer in profile["profiles"]:
        record=[]
        for item in req["alternatives"]:
            row=next((r for r in report["case_results"]
                      if r["profile"]==layer["id"] and r["design"]==item["id"]),None)
            if not row or row.get("slice_status")!="valid_gcode":
                raise ValueError("missing native G-code material estimate")
            if "filament_mass_g" not in row["slicer_stats"]:
                raise ValueError("slicer estimated plastic mass absent")
            mass=row["slicer_stats"]["filament_mass_g"]
            if not math.isfinite(mass) or mass<=0:
                raise ValueError("invalid estimated filament mass")
            # Explicitly reopen only the old mass-derived tipping proxy.
            # All other nonstability gates are independently confirmed by
            # native CAD STEP/STL reimport at the pipeline boundary.
            origin=source_cad[item["id"]]
            if row["cad_numeric_feasible"]!=origin["numeric_feasible"]:
                raise ValueError("original CAD feasibility label changed")
            force=req["stability"]["hypothetical_lateral_force_n"]
            height=14+req["board"]["nominal_height_mm"]
            board=req["board"]["nominal_mass_g"]
            nominal=_tip_factor(mass,board,item["depth_mm"],force,height)
            conservative=_tip_factor(
                mass*policy["assumed_filament_mass_lower_fraction"],
                board*policy["assumed_board_mass_lower_fraction"],
                item["depth_mm"],
                force*policy["assumed_lateral_force_upper_fraction"],
                height,
            )
            other_pass=all(
                passed for check,passed in origin["checks"].items()
                if check!="static_tip_proxy_under_assumptions"
            )
            if row.get("slicer_exit_code")!=0 or row.get("gcode_released_for_physical_printer") is not False:
                other_pass=False
            record.append({
                "id":item["id"],
                "geometry_nonstability_gates_pass":other_pass,
                "slicer_estimated_filament_g":mass,
                "slicer_estimated_print_time_s":row["slicer_stats"]["estimated_time_s"],
                "original_CAD_feasible":row["cad_numeric_feasible"],
                "source_gcode_sha256":row["slicer_output_sha256"],
                "nominal_tip_factor_using_slicer_mass":round(nominal,3),
                "guarded_tip_factor_using_slicer_mass":round(conservative,3),
                "nominal_slicer_proxy_pass":other_pass and nominal>=policy["minimum_nominal_tip_factor"],
                "guarded_slicer_proxy_pass":other_pass and conservative>=policy["minimum_guarded_tip_factor"],
                "physical_tip_test_completed":False,
                "actual_mass_measured":False,
            })
        options={}
        for kind in ("nominal","guarded"):
            feasible=sorted(
                (r for r in record if r[f"{kind}_slicer_proxy_pass"]),
                key=lambda x:(x["slicer_estimated_filament_g"],x["slicer_estimated_print_time_s"],x["id"])
            )
            options[kind]={
                "feasible_order":[r["id"] for r in feasible],
                "chosen":feasible[0]["id"] if feasible else None,
                "chosen_estimated_filament_g":feasible[0]["slicer_estimated_filament_g"] if feasible else None,
                "chosen_estimated_time_s":feasible[0]["slicer_estimated_print_time_s"] if feasible else None,
            }
        baseline=next(x for x in record if x["id"]=="solid_plate")
        for selection in options.values():
            if selection["chosen"] is not None:
                selection["filament_saving_vs_plate_percent"]=round(100*(
                    1-selection["chosen_estimated_filament_g"]/baseline["slicer_estimated_filament_g"]
                ),1)
        rows.append({"profile":layer["id"],"candidate_results":record,
                     "selection":options,
                     "nominal_chose_different_than_previous_CAD":options["nominal"]["chosen"]!=report["native_CAD_audit"]["selected"],
                     "guarded_chose_different_than_previous_CAD":options["guarded"]["chosen"]!=report["native_CAD_audit"]["selected"]})
    return {
        "schema":RESULT,"project_id":req["project_id"],
        "slicer_report_sha256":hashlib.sha256(canonical(report)).hexdigest(),
        "feedback_policy_sha256":hashlib.sha256(canonical(policy)).hexdigest(),
        "source_design_sha256":expected_source,
        "source_slicer_profile_sha256":expected_profile,
        "analysis_mode":"post-hoc sensitivity screen, not prespecified blind calibration",
        "mass_provenance":"native PrusaSlicer G-code material estimate, NOT weighed print",
        "static_model_has_no_slide_fatigue_creep_adhesion_or_FEA_verification":True,
        "printer_execution_authorized":False,
        "cases":rows,
    }

def audit_feedback(req:Mapping[str,Any],profile:Mapping[str,Any],
                   policy:Mapping[str,Any],slicer_report:Mapping[str,Any],
                   cad_report:Mapping[str,Any],feedback:Mapping[str,Any])->dict[str,Any]:
    expected=interpret_feedback(req,profile,policy,slicer_report,cad_report)
    if expected!=feedback:
        raise ValueError("slicer feedback ranking changed from recorded numeric evidence")
    if feedback["printer_execution_authorized"] is not False:
        raise ValueError("printing authority falsely added")
    return {"feedback_recomputed":True,
            "profile_count":len(feedback["cases"]),
            "physical_authority":False,
            "selected_nominal":[x["selection"]["nominal"]["chosen"] for x in feedback["cases"]],
            "selected_guarded":[x["selection"]["guarded"]["chosen"] for x in feedback["cases"]]}

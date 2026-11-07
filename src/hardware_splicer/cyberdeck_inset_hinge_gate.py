"""HS closed-footprint hinge acceptance: geometry != manufactured product.

Consumes native Mecha-Splicer/CGAL artifacts, prior HS CM4 stack report,
and exact Winstar #000 manufacturer dimensional/electrical specifications.
No fabricated lifecycle, driver, backlight, or battery authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .machine_project import (
    AuthorityState, EvidenceRef, MachineProject, Requirement, RequirementKind,
    VerificationMethod, VerificationStatus, VerificationType, ReleaseState,
)

SCHEMA="hardware_splicer.inset_hinge_qualification_input.v1"
RESULT="hardware_splicer.inset_hinge_qualification.v1"
EXPECTED_PDF="https://www.winstar.com.tw/d/676/WF50DTYA3MNG10-000.pdf"


def _sha(path:Path)->str:
    return "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_unfounded_claims(q:dict,spec:dict,cad:dict,prior:dict,panels:dict)->None:
    if q.get("schema")!=SCHEMA:
        raise ValueError("qualification input schema mismatch")
    if q.get("panel_mpn")!="WF50DTYA3MNG10-000" or q.get("panel_manufacturer_datasheet")!=EXPECTED_PDF:
        raise ValueError("exact 2-lane panel datasheet/revision required")
    if [q.get("panel_x_mm"),q.get("panel_y_mm"),q.get("panel_thickness_nominal_mm")]!=[127.6,73.3,3.45]:
        raise ValueError("panel geometry must match exact -000 manufacturer source")
    if q.get("panel_thickness_tolerance_mm")!=0.5:
        raise ValueError("vendor 3.45mm ±0.5mm mechanical tolerance must not be suppressed")
    if q.get("panel_no_mounting_holes") is not True:
        raise ValueError("bare panel lacks module screw holes")
    if q.get("lcd_count")!=2 or q.get("commercialization_required") is not False:
        raise ValueError("two-screen personal engineering, not a commercial launch")
    if not 0<q.get("bondline_thickness_assumption_mm",-1)<1:
        raise ValueError("positive explicit bonding allowance is required")
    if not 1<=q.get("required_research_clearance_mm",0)<=3:
        raise ValueError("do not erase the 1mm nominal component separation guard")
    for key in ("battery_protection_qualified","lcd_backlight_power_driver_qualified",
                 "dual_dsi_linux_verified","hinge_flex_dynamic_bend_verified",
                 "physical_bench_test_performed","user_approved_hinge_rear_opening"):
        if q.get(key) is not False:
            raise ValueError("no claimed external qualification exists for "+key)
    if (q.get("lcd_backlight_voltage_min_v"),
        q.get("lcd_backlight_voltage_max_v"),
        q.get("lcd_backlight_nominal_current_a")) != (19.6,23.8,0.04):
        raise ValueError("exact Winstar backlight power domain was changed")
    p=spec.get("clamshell_terminal",{})
    if p.get("compute_architecture")!="cm4_dual_dsi" or p.get("input_surface_mode")!="dual_touch":
        raise ValueError("wrong CM4 dual-touch architecture")
    if p.get("hinge_style")!="inset_side_pins":
        raise ValueError("native inset hinge must be the CAD actually tested")
    if not (p.get("case_w_mm")==155 and p.get("case_d_mm")==80
            and round(p.get("base_h_mm",0)+p.get("lid_h_mm",0)+p.get("closed_gap_mm",0),3)==18):
        raise ValueError("nominal shell is no longer the 155x80x18 design")
    for key in ("hinge_rear_relief_length_mm","hinge_base_rear_relief_height_mm",
                "hinge_inset_from_rear_mm","hinge_outer_d_mm","wall_mm","floor_mm"):
        if type(p.get(key)) not in (int,float):
            raise ValueError("missing explicit native geometry field: "+key)
    if prior.get("schema")!="hs.cyberdeck_cm4_stack_replay.v1":
        raise ValueError("prior source is not HS-native mechanical fit")
    if prior["manufacturing_authorized"] is not False:
        raise ValueError("upstream nominal CM4 was incorrectly authorized")
    if cad.get("schema")!="hs.clamshell_ssh_cad.v1":
        raise ValueError("missing actual native OpenSCAD/CGAL evidence")
    if cad.get("closed_envelope",{}).get("hinge_style")!="inset_side_pins":
        raise ValueError("CGAL tested the wrong hinge revision")
    if cad.get("closed_envelope",{}).get("hinge_projection_mm")!=0.0:
        raise ValueError("hinge still exceeds outer footprint")
    if [cad.get("closed_envelope",{}).get("width_mm"),
        cad.get("closed_envelope",{}).get("depth_without_hinge_mm"),
        cad.get("closed_envelope",{}).get("closed_thickness_mm")]!=[155.0,80.0,18.0]:
        raise ValueError("reported CAD bounding envelope changed")
    if [row.get("angle_deg") for row in cad.get("cgal_interference_sweep",[])]!=[0,-30,-60,-90,-135,-165]:
        raise ValueError("not all required real CGAL poses were measured")
    if any(row.get("interference_mesh")!="EMPTY" for row in cad["cgal_interference_sweep"]):
        raise ValueError("CAD hinge sweep collides and may not be accepted")
    for part in ("base_shell","lid_shell"):
        m=cad.get("mesh",{}).get(part,{})
        if m.get("nonmanifold_edges")!=0 or m.get("bbox_mm",[])[0:2]!=[155.0,80.0]:
            raise ValueError("native STL mesh is invalid or exterior hinge protrudes")
    if cad.get("actual_unit_assembled") is not False:
        raise ValueError("cannot upgrade unbuilt CAD to physically assembled")
    if panels.get("schema")!="hardware_splicer.inset_hinge_panel_collision_cgal.v1":
        raise ValueError("no real CGAL panel proxy verification")
    if [x.get("angle_deg") for x in panels.get("angles",[])]!=[0,-30,-60,-90,-135,-165]:
        raise ValueError("panel proxy run missing hinge pose")
    if panels.get("nominal_two_half_CGAL_collision_free") is not True or any(
            x.get("intersection")!="EMPTY" for x in panels["angles"]):
        raise ValueError("nominal display clashes with opposite half")
    if panels.get("vendor_max_panel_collides_with_lid_floor") is not True or (
            panels.get("vendor_max_panel_inside_nominal_lid",{}).get("intersection")!="NONEMPTY"):
        raise ValueError("no positive CGAL proof of vendor +0.5mm panel thickness conflict")
    if panels.get("FPC_dynamic_collision_verified") is not False or (
            panels.get("physical_build_authorized") is not False):
        raise ValueError("panel box CAD cannot authorize FPC or actual hardware")


def _canonical_release()->dict:
    requirements=[
        ("closed-profile","CGAL native model fits 155x80x18 in closed pose",RequirementKind.PERFORMANCE,VerificationStatus.PASSED),
        ("kinematic-sweep","Six native shell-only CGAL hinge poses non-colliding",RequirementKind.PERFORMANCE,VerificationStatus.PASSED),
        ("screen-mount","Both panels retained with +0.5mm manufacturer Z and a serviceable backing",RequirementKind.PERFORMANCE,VerificationStatus.FAILED),
        ("electrical","Correct 19.6-23.8V LED current regulators and backlight switching",RequirementKind.SAFETY,VerificationStatus.PLANNED),
        ("safe-cell","Protected cell, swelling space, safe charging and thermal route",RequirementKind.SAFETY,VerificationStatus.PLANNED),
        ("flex","Actual display FPC connector geometry and repeated hinge-bend life",RequirementKind.SAFETY,VerificationStatus.PLANNED),
        ("linux-dsi","Independent DSI0/DSI1, touch I2C, SSH and virtual keyboard",RequirementKind.FUNCTIONAL,VerificationStatus.PLANNED),
        ("rear-strength","Rear wall cut-out, hinge pin strength/retention and exposed screen edge are acceptable",RequirementKind.SAFETY,VerificationStatus.PLANNED),
    ]
    evidence=[
        EvidenceRef(evidence_id="cad-native",kind="HS native Mecha-Splicer and OpenSCAD CGAL",
                    basis="Computational shell-only meshes and intersection checks",
                    ref="evidence/design_evidence.json",authority=AuthorityState.PROPOSED,
                    simulated=True,supports=["r-closed-profile","r-kinematic-sweep"])
    ]
    mp=MachineProject(
        project_id="HS-CM4-INSET-PIN-QUALIFICATION",
        name="Inset side pin + dual Winstar panel mounting test",
        purpose="Commercial-grade engineering quality and cost, without go-to-market",
        requested_release_state=ReleaseState.BUILD_READY,
        requirements=[Requirement(requirement_id="r-"+i,statement=description,
             kind=kind,verification_method_ids=["v-"+i],authority=AuthorityState.DECLARED)
            for i,description,kind,status in requirements],
        verifications=[VerificationMethod(verification_id="v-"+i,name="Verify "+i,
             method_type=VerificationType.ANALYSIS if status in {
                     VerificationStatus.PASSED,VerificationStatus.FAILED} else VerificationType.TEST,
             status=status,requirement_ids=["r-"+i],
             evidence_ids=["cad-native"] if status==VerificationStatus.PASSED else [])
             for i,description,kind,status in requirements],
        evidence=evidence,
        metadata={"no_manufacturing_or_use_authority":True,"screen_mounting_fail_closed":True},
    )
    release=mp.assess_release()
    return {"machine_project":mp.model_dump(mode="json"),
            "release_assessment":release.model_dump(mode="json")}


def evaluate(q:dict,spec:dict,cad:dict,prior:dict,panels:dict)->dict:
    _reject_unfounded_claims(q,spec,cad,prior,panels)
    p=spec["clamshell_terminal"]
    actual_screen_y_end=(p["case_d_mm"]+q["panel_y_mm"])/2
    supported_shell_y_end=p["case_d_mm"]-p["hinge_rear_relief_length_mm"]
    unsupported=max(0,actual_screen_y_end-supported_shell_y_end)
    thick_max=q["panel_thickness_nominal_mm"]+q["panel_thickness_tolerance_mm"]
    bond=q["bondline_thickness_assumption_mm"]
    # Each half independently needs enough Z to secure the maximum allowed
    # panel with adhesive/backing; this calculation does not qualify bond life.
    needed_lid=p["floor_mm"]+thick_max+bond
    lid_slack_nominal=p["lid_h_mm"]-needed_lid
    cm4=prior["sweep"][1]
    if cm4["lid_height_mm"]!=p["lid_h_mm"]:
        raise ValueError("prior HS nominal stack selection changed")
    lower_panel_under_min=p["floor_mm"]+max(
        q["battery_naked_cell_height_mm"],
        0.8+5.078) + q["required_research_clearance_mm"]+thick_max
    needed_total_thick=needed_lid+p["closed_gap_mm"]+lower_panel_under_min
    # Include no unqualified battery/BMS thickness in arithmetic; adding that
    # would make minimum WORSE, not better.
    shortfall=needed_total_thick-18.0
    backlight_min=q["lcd_backlight_voltage_min_v"]*q["lcd_backlight_nominal_current_a"]
    backlight_max=q["lcd_backlight_voltage_max_v"]*q["lcd_backlight_nominal_current_a"]
    release=_canonical_release()
    return {
        "schema":RESULT,
        "source":"native_Mecha-Splicer+real_CGAL+prior_HS_MechanicalFit+exact_Winstar_datasheet",
        "tested_geometry":{
            "closed_body_xyz_mm":[155,80,18],
            "hinge_style":"inset_side_pins",
            "barrel_max_external_projection_mm":0,
            "CGAL_six_shell_angles_pass":True,
            "nominal_full_thickness_screen_boxes_cross_half_tested":True,
            "full_screen_and_FPC_sweep_tested":False,
            "actual_vendor_STEP_model_used":False,
            "physical_pin_insertion_tested":False,
        },
        "retention":{
            "manufacturer_nominal_panel_thickness_mm":q["panel_thickness_nominal_mm"],
            "manufacturer_tolerance_plus_minus_mm":q["panel_thickness_tolerance_mm"],
            "research_bondline_allowance_mm":bond,
            "selected_upper_lid_height_mm":p["lid_h_mm"],
            "minimum_upper_lid_for_panel_max_mm":round(needed_lid,3),
            "selected_lid_missing_mm":round(max(0,-lid_slack_nominal),3),
            "vendor_max_panel_collides_inside_nominal_lid_CGAL":True,
            "rear_swing_relief_starts_y_mm":round(supported_shell_y_end,3),
            "display_ends_y_mm":round(actual_screen_y_end,3),
            "unsupported_screen_rear_edge_mm":round(unsupported,3),
            "mounting_holes_on_panel":False,
            "physically_serviceable_screen_retainer":False,
            "screen_retention_gate":"BLOCKED",
        },
        "worst_case_packaging":{
            "minimum_closed_thickness_mm":round(needed_total_thick,3),
            "minimum_closed_if_no_bondline_mm":round(needed_total_thick-bond,3),
            "shortfall_to_18mm_mm":round(shortfall,3),
            "calculation_is_a_lower_bound_without_BMS_or_mating_uncertainty":True,
            "nominal_18mm_pass_does_not_survive_vendor_Z_tolerance":True,
        },
        "electrical":{
            "LCD_backlight_voltage_domain_v":[19.6,23.8],
            "LCD_backlight_current_a_each":0.04,
            "LCD_backlight_power_w_each":[round(backlight_min,3),round(backlight_max,3)],
            "two_backlights_w":[round(backlight_min*2,3),round(backlight_max*2,3)],
            "voltage_input_NOT_directly_5V_or_cell":True,
            "requires_current_controlled_boost":True,
            "backlight_driver_qualified":False,
            "two_linux_DSI_panels_verified":False,
            "two_GT928_touch_inputs_verified":False,
        },
        "mechanical_and_service":{
            "rear_shell_open_across_width_mm":p["hinge_rear_relief_length_mm"],
            "base_rear_upper_clearance_cut_mm":p["hinge_base_rear_relief_height_mm"],
            "hinge_pin_supported_with_real_physical_load_test":False,
            "FPC_dynamic_bend_tested":False,
            "rear_dust_and_water_ingress_risk":True,
            "safe_to_build_as_proposed":False,
        },
        "machine_release":release["release_assessment"],
        "machine_project":release["machine_project"],
        "decision":"CGAL_KINEMATIC_PASS_COMPONENT_RETENTION_AND_TOLERANCE_FAIL",
        "component_procuring_authorized":False,
        "manufacturing_authorized":False,
        "safe_to_power":False,
        "next_engineering_experiments":[
          "Select actual 2-lane panel driver and bench test two separate DSI/touch paths",
          "Find screen fastening/support solution that preserves ±0.5mm vendor Z tolerance",
          "Design inset side hinge with full rear screen support and flex bend loop",
          "Select protected slim cell, charger and regulated 20-24V current-driven backlights",
          "Re-run native CAD with complete connectors, battery, retention and tolerances",
        ]
    }


def run(input_file:Path,out:Path)->dict:
    input_file=input_file.resolve()
    root=input_file.parent
    q=json.loads(input_file.read_text())
    sfile=(root/q["source_spec"]).resolve()
    cfile=(root/q["source_cad_evidence"]).resolve()
    priorfile=(root/q["source_cm4_report"]).resolve()
    panelsfile=(root/q["source_panel_CGAL_report"]).resolve()
    spec=json.loads(sfile.read_text())
    cad=json.loads(cfile.read_text())
    prior=json.loads(priorfile.read_text())
    panels=json.loads(panelsfile.read_text())
    # Refuse a stale cached CAD result after the source is changed.
    for part in ("base_shell","lid_shell"):
        meshfile=cfile.parent/(part+".stl")
        if "sha256:"+cad["mesh"][part]["sha256"]!=_sha(meshfile):
            raise ValueError("CAD evidence does not match native actual STL bytes for "+part)
    result=evaluate(q,spec,cad,prior,panels)
    result["provenance"]={
        "qualification_input_sha256":_sha(input_file),
        "native_spec_sha256":_sha(sfile),
        "native_CGAL_report_sha256":_sha(cfile),
        "prior_HS_CM4_fit_sha256":_sha(priorfile),
        "nominal_plus_worst_case_panel_CGAL_sha256":_sha(panelsfile),
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    return result


def main() -> None:
    a=argparse.ArgumentParser()
    a.add_argument("--qualification",required=True,type=Path)
    a.add_argument("--out",required=True,type=Path)
    args=a.parse_args()
    report=run(args.qualification,args.out)
    print(json.dumps({"decision":report["decision"],
        "hinge_closed_external_projection_mm":report["tested_geometry"]["barrel_max_external_projection_mm"],
        "screen_rear_unsupported_mm":report["retention"]["unsupported_screen_rear_edge_mm"],
        "nominal_case_18mm_research_minimum_mm":report["worst_case_packaging"]["minimum_closed_thickness_mm"],
        "two_backlights_w":report["electrical"]["two_backlights_w"],
        "fabrication_authorized":report["manufacturing_authorized"]},indent=2))


if __name__=="__main__":
    main()

"""HS requirement-driven dual-DSI CM5 packaging replay.

Uses native MechanicalFit, MachineProject release checks and Mecha-Splicer
CAD/BOM. No imported ad-hoc CadQuery model and no physical authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .mechanical_fit import build_mechanical_fit_report
from .step_geometry import MechanicalGeometryReport
from .machine_project import (
    AuthorityState, EvidenceRef, MachineProject, ReleaseState, Requirement,
    RequirementKind, VerificationMethod, VerificationStatus, VerificationType,
)

SCHEMA = "hs.cyberdeck_dual_touch_input.v1"
OUT_SCHEMA = "hs.cyberdeck_dual_touch_packaging.v1"


class PackagingInputError(ValueError):
    pass


def _positive(value: Any, name: str) -> float:
    if type(value) not in (float, int) or not 0 < value < 500:
        raise PackagingInputError(f"{name} must be a positive measured or explicitly assumed mm value")
    return float(value)


def _check_input(data: dict) -> None:
    if data.get("schema") != SCHEMA:
        raise PackagingInputError("unknown input schema")
    if data.get("input_mode") != "dual_touch" or data.get("physical_keyboard") is not False:
        raise PackagingInputError("product explicitly requires TWO touchscreens, NO physical keyboard")
    if data.get("compute_architecture") != "cm5_dual_dsi":
        raise PackagingInputError("unsupported compute architecture")
    if data.get("panel_count") != 2:
        raise PackagingInputError("two independent touch panels required")
    for section, fields in {
        "body": ["length_mm", "width_mm", "hard_max_thickness_mm", "lid_height_mm", "closed_gap_mm"],
        "panel": ["length_mm", "width_mm", "thickness_mm", "tft_tail_extension_mm"],
        "lower_stack": ["back_wall_mm", "pcb_mm", "mating_mm", "cm5_pcba_mm", "thermal_mm",
                        "battery_mm", "research_min_clearance_mm"],
    }.items():
        if not isinstance(data.get(section), dict):
            raise PackagingInputError(f"missing {section}")
        for key in fields:
            _positive(data[section].get(key), section+"."+key)
    if data["lower_stack"]["back_wall_mm"] < 1.6:
        raise PackagingInputError("native FDM shell must use >=1.6mm floor; prior 0.85mm CAD is NOT this HS process")
    if not data["panel"].get("manufacturer_source_url"):
        raise PackagingInputError("panel source not provided")
    if not data["lower_stack"].get("cm5_geometry_source_url"):
        raise PackagingInputError("CM5 geometry source not provided")
    if data["panel"].get("mpn") != "WF50DTYA3MNG10-000":
        raise PackagingInputError("panel revision is not source-qualified in this trial")
    scenarios = data.get("thickness_scenarios_mm")
    if not isinstance(scenarios, list) or len(scenarios) < 2 or len(set(map(str,scenarios))) != len(scenarios):
        raise PackagingInputError("need at least two distinct thickness scenarios")
    for mm in scenarios:
        _positive(mm, "thickness_scenarios_mm")
    if sorted(scenarios) != scenarios:
        raise PackagingInputError("scenario sweep must be ascending")


def _box(object_id, x, y, z, dx, dy, dz):
    return {
        "object_id": object_id, "frame_id": "CM5_LOWER_CLOSED",
        "state": "closed", "minimum_mm": [x,y,z],
        "maximum_mm": [x+dx,y+dy,z+dz],
    }


def _evaluate(data: dict, thick: float) -> dict:
    b,p,s=data["body"],data["panel"],data["lower_stack"]
    length,width=b["length_mm"],b["width_mm"]
    base=thick-b["lid_height_mm"]-b["closed_gap_mm"]
    panel_x=(length-p["length_mm"])/2
    panel_y=(width-p["width_mm"])/2
    top=s["back_wall_mm"]+s["pcb_mm"]+s["mating_mm"]+s["cm5_pcba_mm"]+s["thermal_mm"]
    panel_back=base-p["thickness_mm"]
    battery_top=s["back_wall_mm"]+s["battery_mm"]
    footprint=(panel_x>=1.6 and panel_y>=1.6 and base>0 and
               p["length_mm"]<=length and p["width_mm"]<=width)
    boxes=[
        _box("cm5_with_heat_spreader",92,17,s["back_wall_mm"],56,41,top-s["back_wall_mm"]),
        _box("battery_unprotected",5,15,s["back_wall_mm"],80,50,s["battery_mm"]),
        _box("lower_touch_display",panel_x,panel_y,panel_back,p["length_mm"],p["width_mm"],p["thickness_mm"]),
        _box("custom_carrier",90,10,s["back_wall_mm"],60,58,s["pcb_mm"]),
    ]
    requirements=[
        {"requirement_id":"cm5-to-panel","first_object_id":"cm5_with_heat_spreader",
         "second_object_id":"lower_touch_display","minimum_clearance_mm":s["research_min_clearance_mm"]},
        {"requirement_id":"battery-to-panel","first_object_id":"battery_unprotected",
         "second_object_id":"lower_touch_display","minimum_clearance_mm":s["research_min_clearance_mm"]},
    ]
    geometry=MechanicalGeometryReport(project_id="HS-CM5-DUAL-TOUCH",status="declared")
    fit=build_mechanical_fit_report(geometry,clearance_boxes=boxes,clearance_requirements=requirements)
    checks={c.check_id: {
        "status":c.status.value,"clearance_mm":round(c.metadata.get("clearance_mm",0),3),
        "required_mm":c.metadata.get("minimum_clearance_mm"),
    } for c in fit.checks}
    # Source-dimension nominal outcome, not a physical tolerance or STEP-solid proof.
    nominal_pass=fit.status=="candidate" and footprint
    hard_pass=thick<=b["hard_max_thickness_mm"]
    return {
        "closed_thickness_mm":round(thick,3),
        "base_height_mm":round(base,3),
        "lid_height_mm":b["lid_height_mm"],
        "screen_gap_mm":b["closed_gap_mm"],
        "compute_stack_top_mm":round(top,3),
        "panel_back_mm":round(panel_back,3),
        "compute_to_panel_clearance_mm":round(panel_back-top,3),
        "battery_to_panel_clearance_mm":round(panel_back-battery_top,3),
        "footprint_nominal_fit":footprint,
        "native_mechanical_fit":fit.status,
        "native_mechanical_fit_checks":checks,
        "hard_thickness_requirement_pass":hard_pass,
        "nominal_research_fit":nominal_pass,
        "status": "research_candidate_within_envelope" if nominal_pass and hard_pass
                  else "fails_nominal_fit" if not nominal_pass
                  else "counterfactual_exceeds_hard_limit",
    }


def _native_spec(data: dict, candidate: dict) -> dict:
    b,p,s=data["body"],data["panel"],data["lower_stack"]
    return {
        "project_name":"HS-CM5-POCKET-DUAL-DSI-S2",
        "mode":"prototype","process":"fdm",
        "clamshell_terminal":{
            "name":"CM5 2x 5in DSI touch - CAD shell candidate only",
            "compute_architecture":"cm5_dual_dsi","input_surface_mode":"dual_touch",
            "case_w_mm":b["length_mm"],"case_d_mm":b["width_mm"],
            "base_h_mm":candidate["base_height_mm"],"lid_h_mm":b["lid_height_mm"],
            "closed_gap_mm":b["closed_gap_mm"],
            "wall_mm":1.6,"floor_mm":s["back_wall_mm"],"clearance_mm":0.3,
            "display_board_w_mm":p["length_mm"],
            "display_board_d_mm":p["width_mm"],
            "lower_touch_board_w_mm":p["length_mm"],
            "lower_touch_board_d_mm":p["width_mm"],
            "hinge_outer_d_mm":6.8,"hinge_pin_d_mm":2.0,
            "pin_radial_clearance_mm":0.35,"hinge_y_offset_mm":1.2,
            "knuckle_end_margin_mm":5.0,"knuckle_outer_length_mm":23.0,
            "knuckle_axial_gap_mm":7.0,"cable_slot_w_mm":5.2,
            "cable_slot_h_mm":3.6,"preview_open_angle_deg":-135,
        },
        "notes":"User insists on two touchscreens and hard max 18mm. Nominal shell only; FPC, thermals and mating still unknown.",
    }


def _machine_project(candidate: dict, hard_max: float) -> tuple[dict,dict]:
    lines=[
      ("r-thickness","Closed body shall not exceed specified hard thickness",RequirementKind.CONSTRAINT,
       "v-thickness",VerificationStatus.PASSED if candidate["hard_thickness_requirement_pass"] else VerificationStatus.FAILED),
      ("r-cm5-clearance","CM5-to-lower-touch-display nominal AABB clearance >=1mm research margin",RequirementKind.PERFORMANCE,
       "v-cm5-fit",VerificationStatus.PASSED if candidate["native_mechanical_fit"]=="candidate" else VerificationStatus.FAILED),
      ("r-dual-touch","Both real touchscreen panels shall operate on distinct DSI and GT928 I2C paths",RequirementKind.FUNCTIONAL,
       "v-dsi",VerificationStatus.PLANNED),
      ("r-hinge","Hinge FPC flex routing and fatigue shall be physically qualified",RequirementKind.SAFETY,
       "v-fpc",VerificationStatus.PLANNED),
      ("r-protected-power","Battery, charging, 5V, 4V and panel backlight boost shall be physically qualified",RequirementKind.SAFETY,
       "v-power",VerificationStatus.PLANNED),
      ("r-thermal","CM5 thermal path shall be verified under load",RequirementKind.SAFETY,
       "v-thermal",VerificationStatus.PLANNED),
      ("r-mating","Module-to-carrier mating and actual stack height shall be vendor-qualified",RequirementKind.SAFETY,
       "v-mating",VerificationStatus.PLANNED),
    ]
    requirements=[Requirement(requirement_id=rid,statement=stmt,kind=kind,
                              verification_method_ids=[vid],authority=AuthorityState.DECLARED)
                  for rid,stmt,kind,vid,st in lines]
    evidence=[EvidenceRef(evidence_id="e-nominal-fit",kind="native HS mechanical AABB",
                          basis="manufacturer nominal geometry and unverified mating/battery assumptions",
                          ref="hs_packaging_report.json",authority=AuthorityState.PROPOSED,
                          simulated=True,supports=["r-thickness","r-cm5-clearance"])]
    methods=[VerificationMethod(verification_id=vid,name=stmt,
                               method_type=VerificationType.ANALYSIS if st!=VerificationStatus.PLANNED else VerificationType.TEST,
                               status=st,requirement_ids=[rid],
                               evidence_ids=["e-nominal-fit"] if st==VerificationStatus.PASSED else [])
             for rid,stmt,kind,vid,st in lines]
    mp=MachineProject(project_id="HS-CM5-DUAL-TOUCH",name="Pocket dual-touch CM5",
        purpose="Compare hard pocket thickness to nominal CAD constraints",
        requested_release_state=ReleaseState.BUILD_READY,
        requirements=requirements,verifications=methods,evidence=evidence,
        metadata={"hard_max_mm":hard_max,"no_physical_keyboard":True})
    assessment=mp.assess_release()
    return mp.model_dump(mode="json"),assessment.model_dump(mode="json")


def run(data: dict, out: Path | None = None) -> dict:
    _check_input(data)
    from mecha_splicer.bundle import generate_bundle
    from mecha_splicer.spec import ProjectSpec
    profiles=[_evaluate(data,float(mm)) for mm in data["thickness_scenarios_mm"]]
    viable=[p for p in profiles if p["nominal_research_fit"]]
    chosen=viable[0] if viable else None
    hard=[p for p in viable if p["hard_thickness_requirement_pass"]]
    # This is an executable bounded search. It must NOT silently relax 18mm.
    body=data["body"]
    panel=data["panel"]
    overflow=round((body["length_mm"]-panel["length_mm"])/2+
                   panel["length_mm"]+panel["tft_tail_extension_mm"]-body["length_mm"],3)
    if overflow<=0:
        fpc="routing_still_requires_bend_and_strain_relief"
    else:
        fpc="straight_FPC_exceeds_body"
    native_bundle=None
    native_spec=None
    if chosen is not None:
        native_spec=_native_spec(data,chosen)
        ProjectSpec.model_validate(native_spec)
        native_bundle=generate_bundle(native_spec,out_dir=out/"native_mecha" if out else None)
        if native_bundle["blockers"]:
            raise PackagingInputError("native Mecha-Splicer DFM blocked proposed candidate")
        labels={row["item"] for row in native_bundle["bom"]}
        if not ("Winstar WF50DTYA3MNG10-000" in labels and "Radxa CM5 V2.21" in labels):
            raise PackagingInputError("native BOM not consistent with product architecture")
        if any("Waveshare" in label or "RS485" in label for label in labels):
            raise PackagingInputError("legacy dual-ESP32 BOM leaked into CM5 architecture")
    if chosen:
        project,release=_machine_project(chosen,body["hard_max_thickness_mm"])
    else:
        project=None
        release=None
    stack=data["lower_stack"]
    theoretical_min=(body["lid_height_mm"]+body["closed_gap_mm"]+data["panel"]["thickness_mm"]
         +stack["back_wall_mm"]+stack["pcb_mm"]+stack["mating_mm"]
         +stack["cm5_pcba_mm"]+stack["thermal_mm"]+stack["research_min_clearance_mm"])
    report={
        "schema":OUT_SCHEMA,"project":"HS-CM5-DUAL-TOUCH",
        "generator":"hardware_splicer.cyberdeck_packaging_workflow with native MechanicalFit + Mecha-Splicer + MachineProject",
        "requirements":{"closed_body_mm":[body["length_mm"],body["width_mm"]],
                        "hard_max_thickness_mm":body["hard_max_thickness_mm"],
                        "screens":2,"physical_keyboard":False},
        "profiles":profiles,
        "minimum_nominal_fit_mm":chosen["closed_thickness_mm"] if chosen else None,
        "calculated_minimum_nominal_thickness_mm":round(theoretical_min,3),
        "selected_for_native_cad_mm":chosen["closed_thickness_mm"] if chosen else None,
        "hard_constraint_met":bool(hard),
        "decision":"reject_hard_envelope_research_alternative_requires_user_approval"
                   if chosen and not hard else "no_nominal_fit" if not chosen
                   else "nominal_fit_only_with_unverified_release_blockers",
        "fpc_overflow_mm":overflow,"fpc_gate":fpc,
        "native_cad_outputs":native_bundle["outputs"] if native_bundle else [],
        "native_bom":native_bundle["bom"] if native_bundle else [],
        "native_dfm":native_bundle["dfm"] if native_bundle else [],
        "release_assessment":release,
        "unresolved":["mating_connector_stack_height", "both_DSI_linux_driver_integration",
                      "dual_GT928_I2C_path", "FPC_hinge_routing_bend_fatigue",
                      "backlight_boost_converter", "battery_BMS_swelling",
                      "thermal_path_and_load", "mechanical_tolerances",
                      "USB_ESD_and_power_integrity", "PCB_routing_and_DRC"],
        "physical_validation":False,"safe_to_power":False,"fabrication_authorized":False,
    }
    if out:
        out.mkdir(parents=True,exist_ok=True)
        (out/"hs_packaging_report.json").write_text(json.dumps(report,indent=2)+"\n")
        if native_spec:
            (out/"native_project_spec.json").write_text(json.dumps(native_spec,indent=2)+"\n")
        if project:
            (out/"machine_project.json").write_text(json.dumps(project,indent=2)+"\n")
    return report


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--requirements",type=Path,required=True)
    arg.add_argument("--out",type=Path,required=True)
    a=arg.parse_args()
    result=run(json.loads(a.requirements.read_text()),a.out)
    print(json.dumps({"decision":result["decision"],"profiles":[
        (x["closed_thickness_mm"],x["compute_to_panel_clearance_mm"],x["status"])
        for x in result["profiles"]],"native_cad_outputs":result["native_cad_outputs"],
        "fabrication_authorized":result["fabrication_authorized"]},indent=2))


if __name__=="__main__":
    main()

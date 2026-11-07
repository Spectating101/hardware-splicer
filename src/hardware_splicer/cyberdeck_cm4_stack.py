"""Source-labelled CM4 Lite dual-screen packaging through Hardware Splicer engines.

Research-only bounding-box and sensitivity calculations. Real connector, FPC,
battery protection, heat, DSI driver and assembly qualification remain blocked.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from .mechanical_fit import build_mechanical_fit_report
from .step_geometry import MechanicalGeometryReport
from .machine_project import (
    AuthorityState, EvidenceRef, MachineProject, ReleaseState, Requirement,
    RequirementKind, VerificationMethod, VerificationType,
)

SCHEMA="hs.cyberdeck_cm4_thin_stack_input.v1"
OUTPUT="hs.cyberdeck_cm4_stack_replay.v1"


def _box(name: str, a: tuple[float,float,float], size: tuple[float,float,float]) -> dict:
    return {
        "object_id":name,"frame_id":"CM4_CLOSED","state":"closed",
        "minimum_mm":[round(x,5) for x in a],
        "maximum_mm":[round(x+y,5) for x,y in zip(a,size)],
        "metadata":{"model":"nominal_AABB_only","not_full_BREP":True},
    }


def validate(p: dict) -> None:
    if p.get("schema")!=SCHEMA:
        raise ValueError("unsupported CM4 stack schema")
    r=p.get("user_constraints",{})
    if r.get("screens")!=2 or r.get("physical_keyboard") is not False:
        raise ValueError("two touchscreens and NO physical keyboard mandatory")
    if r.get("closed_max_xyz_mm")!=[155.0,80.0,18.0]:
        raise ValueError("closed form-factor hard cap must be preserved")
    if r.get("budget_status")!="assistant_proposed_not_user_authorized":
        raise ValueError("prototype budget is not an owner-approved financial limit")
    c=p.get("candidate_parts",{})
    cpu=c.get("compute",{})
    panel=c.get("panels",{})
    case=p.get("enclosure",{})
    if cpu.get("mpn")!="CM4102000" or cpu.get("emmc_gb")!=0:
        raise ValueError("CM4 Lite 2GB Wi-Fi exact part identity mismatch")
    if cpu.get("mated_geometry_source")!="https://datasheets.raspberrypi.com/cm4/cm4-datasheet.pdf":
        raise ValueError("CM4 module geometry source missing")
    if panel.get("mpn")!="WF50DTYA3MNG10-000" or panel.get("dsi_lanes")!=2:
        raise ValueError("2-lane Winstar -000 must not be swapped for 4-lane near-SKU")
    if panel.get("quantity")!=2 or not panel.get("source","").startswith("https://"):
        raise ValueError("two exact sourced displays required")
    if panel.get("dimensions_xyz_mm") != [127.6,73.3,3.45]:
        raise ValueError("manufacturer panel footprint/thickness changed, requalify exact revision")
    if c["carrier"].get("vendor_qualified") or c["carrier"].get("pcb_routed"):
        raise ValueError("CM4 trial carrier remains a declaration, not fabricated")
    if c["battery"].get("protected_pack_qualified"):
        raise ValueError("naked battery not a qualified protected pack")
    if case.get("shell_floor_mm")<1.6 or case.get("shell_wall_mm")<1.6:
        raise ValueError("FDM wall/floor cannot be silently made thinner")
    if case.get("hinge_outer_d_mm",0)<5.5 or case.get("hinge_y_offset_mm",0)<0.5:
        raise ValueError("current native external pin hinge must respect existing minimum dimensions")
    if case.get("closed_screen_gap_mm")<0.6 or case.get("minimum_research_clearance_mm")<1:
        raise ValueError("research gap/clearance must not be silently weakened")
    if any(type(x) not in (int,float) or x<=0 for x in
           [cpu["mated_package_height_mm"],c["carrier"]["pcb_thickness_mm"],
            c["battery"]["cell_thickness_mm"],case["shell_floor_mm"],
            case["closed_screen_gap_mm"]]):
        raise ValueError("invalid positive physical layer")
    sweep=case.get("upper_lid_height_sweep_mm")
    if not isinstance(sweep,list) or not sweep or sorted(sweep)!=sweep:
        raise ValueError("ordered lid-height sweep required")
    if len({str(x) for x in sweep})!=len(sweep):
        raise ValueError("duplicate lid scenarios")
    for x in sweep:
        if type(x) not in (float,int) or x<=0:
            raise ValueError("invalid lid height")
    if p.get("release_authority",{}).get("fab_authorized") is not False:
        raise ValueError("this is not an authorized manufacturing study")


def _geometry(p: dict, lid: float, changes: dict | None=None) -> dict:
    changes=changes or {}
    case=p["enclosure"]
    parts=p["candidate_parts"]
    dim=p["user_constraints"]["closed_max_xyz_mm"]
    length,width,thick=dim
    cx,cy,pt=parts["panels"]["dimensions_xyz_mm"]
    pt+=changes.get("panel_thickness_delta_mm",0)
    floor=case["shell_floor_mm"]
    wall=case["shell_wall_mm"]
    gap=case["closed_screen_gap_mm"]
    lid+=changes.get("upper_lid_delta_mm",0)
    base=thick-lid-gap
    pcb=parts["carrier"]["pcb_thickness_mm"]
    cm4_height=parts["compute"]["mated_package_height_mm"]+changes.get("cm4_mated_delta_mm",0)
    cell=parts["battery"]["cell_thickness_mm"]+changes.get("battery_delta_mm",0)
    lower_panel_back=base-pt
    cm4_top=floor+pcb+cm4_height
    battery_top=floor+cell
    upper_lid_panel_slack=lid-floor-pt
    panel_x=(length-cx)/2
    panel_y=(width-cy)/2
    inner_w=length-2*wall
    inner_d=width-2*wall
    # Two-side-by-side xy placements under screen. Native AABB detects overlap,
    # but does NOT model the actual carrier connectors, USB, mounting screws.
    boxes=[
        _box("cm4_mated_to_carrier",(91,17,floor+pcb),(55,40,cm4_height)),
        _box("naked_cell_placeholder",(3,15,floor),(80,50,cell)),
        _box("carrier_board",(91,10,floor),(60,55,pcb)),
        _box("lower_touch_display",(panel_x,panel_y,lower_panel_back),(cx,cy,pt)),
        _box("upper_touch_display",(panel_x,panel_y,base+gap),(cx,cy,pt)),
    ]
    fit=build_mechanical_fit_report(
        MechanicalGeometryReport(project_id="HS-CM4-DUAL-TOUCH",status="declared"),
        clearance_boxes=boxes,
        clearance_requirements=[
            {"requirement_id":"cm4-to-lower-screen",
             "first_object_id":"cm4_mated_to_carrier",
             "second_object_id":"lower_touch_display",
             "minimum_clearance_mm":case["minimum_research_clearance_mm"]},
            {"requirement_id":"battery-to-lower-screen",
             "first_object_id":"naked_cell_placeholder",
             "second_object_id":"lower_touch_display",
             "minimum_clearance_mm":case["minimum_research_clearance_mm"]},
            {"requirement_id":"battery-to-carrier",
             "first_object_id":"naked_cell_placeholder",
             "second_object_id":"carrier_board",
             "minimum_clearance_mm":2.0},
            {"requirement_id":"screen-glass-to-glass",
             "first_object_id":"lower_touch_display",
             "second_object_id":"upper_touch_display",
             "minimum_clearance_mm":0.6},
        ],
    )
    results={check.check_id:{"status":check.status.value,
                "measured_nominal_mm":round(check.metadata.get("clearance_mm",0),3),
                "research_required_mm":check.metadata.get("minimum_clearance_mm")}
             for check in fit.checks}
    x_fit=(cx<=inner_w and cy<=inner_d and
           3>=wall and 3+80<=91-2 and
           91+60<=length-wall and 15+50<=width-wall and
           10+55<=width-wall)
    # Even when the AABB clears, an upper lid only 0.05mm over bare-screen +
    # floor thickness is not vendor-qualified component retaining hardware.
    candidate=(fit.status=="candidate" and x_fit and
               base>0 and upper_lid_panel_slack>=-1e-7)
    return {
        "lid_height_mm":round(lid,3),
        "base_height_mm":round(base,3),
        "closed_envelope_mm":dim,
        "native_fit_status":fit.status,
        "native_checks":results,
        "cm4_display_gap_mm":round(lower_panel_back-cm4_top,3),
        "naked_battery_display_gap_mm":round(lower_panel_back-battery_top,3),
        "panel_in_lid_rigidity_slack_mm":round(upper_lid_panel_slack,3),
        "XY_declared_fit":x_fit,
        "minimum_nominal_research_fit":candidate,
        "physical_fit_or_tolerance_qualified":False,
        "manufacturer_driver_pair_qualified":False,
    }


def _spec(p: dict, row: dict) -> dict:
    dim=p["user_constraints"]["closed_max_xyz_mm"]
    a=p["candidate_parts"]["panels"]["dimensions_xyz_mm"]
    case=p["enclosure"]
    return {
      "project_name":"HS-CM4-LITE-2-THIN-TOUCH",
      "mode":"prototype","process":"fdm",
      "clamshell_terminal":{
        "name":"CM4 Lite with 2x Winstar two-lane DSI touch: nominal only",
        "compute_architecture":"cm4_dual_dsi","input_surface_mode":"dual_touch",
        "case_w_mm":dim[0],"case_d_mm":dim[1],
        "base_h_mm":row["base_height_mm"],"lid_h_mm":row["lid_height_mm"],
        "closed_gap_mm":case["closed_screen_gap_mm"],
        "wall_mm":case["shell_wall_mm"],"floor_mm":case["shell_floor_mm"],
        "clearance_mm":0.3,
        "display_board_w_mm":a[0],"display_board_d_mm":a[1],
        "lower_touch_board_w_mm":a[0],"lower_touch_board_d_mm":a[1],
        "hinge_outer_d_mm":case["hinge_outer_d_mm"],"hinge_pin_d_mm":2.0,
        "pin_radial_clearance_mm":0.35,
        "hinge_y_offset_mm":case["hinge_y_offset_mm"],"knuckle_end_margin_mm":5.0,
        "knuckle_outer_length_mm":23.0,"knuckle_axial_gap_mm":7.0,
        "cable_slot_w_mm":5.2,"cable_slot_h_mm":3.6,
        "preview_open_angle_deg":-135,
      },
      "notes":"Unverified 18mm nominal placement only; FPC, battery protection, dual Linux drivers, 5V/backlight and assembly not qualified.",
    }


def _machine(p: dict, selected: dict) -> tuple[dict,dict]:
    requirements=[
        ("nominal-fit","HS declared 155x80x18 dual-touch 1mm clearance screen/battery/compute analysis",
         RequirementKind.PERFORMANCE),
        ("physical-fit","Real purchased screen, battery, FPC, CM4 mating and case fit within tolerances",
         RequirementKind.PERFORMANCE),
        ("firmware","Two correct DSI devices + GT928 touch inputs independently functional under Linux",
         RequirementKind.FUNCTIONAL),
        ("safe-battery","Protected cell, 5V boost and backlights under measured power and thermal conditions",
         RequirementKind.SAFETY),
        ("secure-ssh","Correct host-key trust and on-screen editing controls demonstrated",
         RequirementKind.SAFETY),
        ("economic","Fully qualified build cost including PCB, battery, shipping, failed prototypes",
         RequirementKind.CONSTRAINT),
    ]
    evidence=[EvidenceRef(evidence_id="native-nominal",kind="HS MechanicalFit bounding boxes",
                          basis="Source-labelled manufacturer nominal dimensions and unverified component assumptions",
                          ref="cm4_stack_result.json",authority=AuthorityState.PROPOSED,
                          simulated=True,supports=["r-nominal-fit"])]
    mp=MachineProject(
        project_id="HS-CM4-LITE-THIN-DUAL-TOUCH",
        name="CM4 dual-touch thin case research",
        purpose="Evaluate constrained packaging and construction economics, not sales",
        requested_release_state=ReleaseState.BUILD_READY,
        requirements=[Requirement(requirement_id=f"r-{rid}",statement=stmt,kind=kind,
                      verification_method_ids=[f"v-{rid}"],authority=AuthorityState.DECLARED)
                      for rid,stmt,kind in requirements],
        verifications=[VerificationMethod(
                        verification_id=f"v-{rid}",name=f"Verify {rid}",
                        method_type=VerificationType.ANALYSIS if rid=="nominal-fit" else VerificationType.TEST,
                        requirement_ids=[f"r-{rid}"],
                        # Passing simulated nominal checks may be recorded as provisional
                        # engineering checks, never as physical authority.
                        status=("passed" if selected["minimum_nominal_research_fit"] else "failed")
                                if rid=="nominal-fit" else "planned",
                        evidence_ids=["native-nominal"] if rid=="nominal-fit" and selected["minimum_nominal_research_fit"] else [])
                      for rid,stmt,kind in requirements],
        evidence=evidence,metadata={"commercialization":False},
    )
    return mp.model_dump(mode="json"),mp.assess_release().model_dump(mode="json")


def run(p: dict, out: Path | None=None) -> dict:
    validate(p)
    from mecha_splicer.bundle import generate_bundle
    from mecha_splicer.spec import ProjectSpec
    sweep=[_geometry(p,lid) for lid in p["enclosure"]["upper_lid_height_sweep_mm"]]
    nominal=[r for r in sweep if r["minimum_nominal_research_fit"]]
    selected=next((row for row in nominal if row["lid_height_mm"]==5.1), nominal[0] if nominal else None)
    perturbations=[]
    if selected is not None:
        for variation in p["scenario_perturbations"]:
            key=variation["id"]
            diff={k:v for k,v in variation.items() if k!="id"}
            if len(diff)!=1 or list(diff)[0] not in {
                "battery_delta_mm","cm4_mated_delta_mm","upper_lid_delta_mm","panel_thickness_delta_mm"}:
                raise ValueError("unrecognized robustness perturbation")
            perturbations.append({"id":key,**_geometry(p,selected["lid_height_mm"],diff)})
    native_bundle=None
    native_spec=None
    project=None
    release=None
    if selected is not None:
        native_spec=_spec(p,selected)
        ProjectSpec.model_validate(native_spec)
        native_bundle=generate_bundle(native_spec,
             out_dir=(out/"native_mecha") if out else None)
        if native_bundle["blockers"]:
            raise RuntimeError("native Mecha-Splicer DFM says geometry is blocked")
        by_name={r["item"]:r for r in native_bundle["bom"]}
        if by_name["Raspberry Pi CM4102000 wireless Lite 2GB"]["qty"]!=1:
            raise RuntimeError("compute SKU disappeared from native HS BOM")
        if by_name["Winstar WF50DTYA3MNG10-000"]["qty"]!=2:
            raise RuntimeError("dual screens disappeared from native HS BOM")
        if any("Waveshare" in n or "RS485" in n for n in by_name):
            raise RuntimeError("wrong architecture leaked from unrelated HS cyberdeck")
        project,release=_machine(p,selected)
    price_ntd=p["candidate_parts"]["compute"]["price_ntd"]
    budget=p["user_constraints"]["target_budget_ntd"]
    case=p["enclosure"]
    limits=p["user_constraints"]["closed_max_xyz_mm"]
    # Native shell CAD places rear hinge axis at case_depth + y_offset,
    # then its barrel radius extends farther outside. This is derived from
    # existing Mecha-Splicer primitive, not an omitted cosmetic detail.
    outer_depth=round(limits[1]+case["hinge_y_offset_mm"]+case["hinge_outer_d_mm"]/2,3)
    full_footprint=[limits[0],outer_depth,limits[2]]
    whole_outer_fit=outer_depth <= limits[1]
    report={
        "schema":OUTPUT,
        "source_sha256":"sha256:"+sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),
        "engine":"HS native MechanicalFit + Mecha-Splicer clamshell + canonical MachineProject",
        "required_closed_xyz_mm":p["user_constraints"]["closed_max_xyz_mm"],
        "native_clamshell_hinge_included_xyz_mm":full_footprint,
        "whole_device_pocket_envelope_met":whole_outer_fit,
        "external_hinge_projection_mm":round(outer_depth-limits[1],3),
        "hinge_geometry_still_requires_redesign":not whole_outer_fit,
        "budget_proposal_ntd":budget,"budget_not_user_approved":True,
        "quoted_nonstrict_module_price_ntd":price_ntd,
        "panel_price_separate_currency":{"usd_each":p["candidate_parts"]["panels"]["panel_price_usd_each"],
                  "qty":2,"no_NTD_landed_quote":True},
        "unpriced":["two_panels_delivered_NTD_price","carrier_PCB_and_assembly",
                    "dual_DSI_route_and_connector","dual_panel_driver_and_backlights",
                    "hinge_FPC_qualified","protected_battery_and_boost","SD_card",
                    "thermal_spreader_and_antenna","enclosure_material_and_rework"],
        "sweep":sweep,
        "nominal_candidate_lid_height_mm":selected["lid_height_mm"] if selected else None,
        "nominal_pass_count":len(nominal),
        "sensitivity_at_chosen":perturbations,
        "sensitivity_any_failed":any(not x["minimum_nominal_research_fit"] for x in perturbations),
        "nominal_only_fit":bool(nominal),
        "selected_candidate_requires_lid_module_slack_review":bool(selected and selected["panel_in_lid_rigidity_slack_mm"]<0.3),
        "native_bom":native_bundle["bom"] if native_bundle else [],
        "native_dfm":native_bundle["dfm"] if native_bundle else [],
        "native_cad_outputs":native_bundle["outputs"] if native_bundle else [],
        "release_assessment":release,
        "decision":"NOMINAL_INTERNAL_STACK_BUT_HINGE_EXCEEDS_POCKET_LIMIT" if nominal and not whole_outer_fit
                   else "NOMINAL_ONLY_EXTREMELY_TIGHT_NOT_FABRICABLE" if nominal
                   else "NO_NOMINAL_INTERNAL_STACK_FIT",
        "manufacturing_authorized":False,"hardware_bought":False,"safe_to_power":False,
        "two_DSI_panels_tested":False,"ready_for_landed_cost_quote":True,
    }
    if out:
        out.mkdir(parents=True,exist_ok=True)
        (out/"cm4_stack_result.json").write_text(json.dumps(report,indent=2)+"\n")
        if native_spec:
            (out/"native_project_spec.json").write_text(json.dumps(native_spec,indent=2)+"\n")
        if project:
            (out/"machine_project.json").write_text(json.dumps(project,indent=2)+"\n")
    return report


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--requirements",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    report=run(json.loads(args.requirements.read_text()),args.out)
    print(json.dumps({"decision":report["decision"],
        "nominal_candidate":report["nominal_candidate_lid_height_mm"],
        "sweep":[[r["lid_height_mm"],r["cm4_display_gap_mm"],
                  r["naked_battery_display_gap_mm"],
                  r["minimum_nominal_research_fit"]] for r in report["sweep"]],
        "fragile_to_perturbation":report["sensitivity_any_failed"],
        "manufacturing_authorized":report["manufacturing_authorized"]},indent=2))


if __name__=="__main__":
    main()

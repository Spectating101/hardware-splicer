"""Genuine two-leaf cyberdeck hinge: BRep mating parts, angular sweep,
screen collision keepouts, coaxial pin and external cable-loop reservation.

This is a source-unverified *reference mechanism*, not a claimed phone
enclosure or a proven cable routing. All moving collision checks use OCP
distance and solid geometry; no AABB-only substitute is scored as a pass.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .function_print_geometry import canonical,file_sha
from .function_intent_bridge import parse_intent

SCHEMA="hs.functional_moving_hinge.v1"
OUTPUT="hs.cyberdeck_mating_hinge_cad.v1"

def validate(req:Mapping[str,Any])->dict[str,Any]:
    if req.get("schema")!=SCHEMA or req.get("project_id")!="dual_panel_cyberdeck_hinge_reference_v1":
        raise ValueError("unknown reference hinge design")
    authority=req.get("source_authority")
    if not isinstance(authority,dict) or not authority or any(v is not False for v in authority.values()):
        raise ValueError("actual screen/cable/material/hardware dimensions are NOT verified")
    d=req["design_reference"];h=req["mechanical"];c=req["cable"];p=req["printer"]
    expected={
       "panel_width_mm":152,"panel_depth_mm":78,"panel_gap_each_side_mm":4,
       "panel_backing_thickness_mm":2.4,"screen_package_thickness_mm":2.3,
       "screen_keepout_width_mm":140,"screen_keepout_depth_mm":68,
       "screen_keepout_center_y_mm":43,
    }
    if d!=expected:
        raise ValueError("unexpected uncalibrated reference panel geometry")
    if h["base_barrel_x_centres_mm"]!=[-18,18] or h["lid_barrel_x_centres_mm"]!=[-36,0,36]:
        raise ValueError("knuckle order/axial separation changed")
    if h["barrel_knuckle_length_mm"]!=14 or h["hinge_bore_nominal_diameter_mm"]!=3.5 or h["pin_nominal_diameter_mm"]!=3:
        raise ValueError("declared coaxial pin/bore geometry changed")
    if (h["minimum_radial_wall_mm"]!=1.8 or h["minimum_leaf_separation_mm"]!=.4
        or h["minimum_screen_gap_mm"]!=1 or h["folded_envelope_max_height_mm"]!=13.5
        or h["angle_start_deg"]!=0 or h["angle_end_deg"]!=180 or h["angle_sampling_step_deg"]!=5
        or h["rotation_direction"]!="-X" or h["shaft_retention_design_verified"] is not False):
        raise ValueError("mechanical acceptance/authority contract changed")
    if (c["strategy"]!="external_service_loop_outside_right_panel_footprint"
        or c["reserved_cable_bend_envelope_radius_mm"]!=9
        or c["keepout_axial_extent_mm"]!=8
        or c["minimum_keepout_to_solid_clearance_mm"]!=2
        or c["maximum_overall_width_with_keepout_mm"]!=165
        or any(c[k] is not False for k in (
            "actual_cable_geometry_routed","cable_end_connectors_measured","flex_life_tested"))):
        raise ValueError("cable bend envelope is only a clearance reservation")
    if p != {"bed_mm":[220,220,250],"nominal_nozzle_mm":.4,
             "nominal_layer_mm":.2,"nominal_density_g_cm3":1.24,
             "nominal_infill_percent":20,"printer_profile_verified":False}:
        raise ValueError("unverified nominal print profile changed")
    alts=req.get("alternatives")
    if not isinstance(alts,list) or not 3<=len(alts)<=12:
        raise ValueError("need 3 to 12 actual hinge geometries")
    ids=set()
    for alt in alts:
        if set(alt)!={"id","axis_height_mm","barrel_radius_mm","cable_keepout_start_x_mm"}:
            raise ValueError("unexpected variant parameters")
        name=alt["id"]
        if not isinstance(name,str) or not re.fullmatch(r"[a-z][a-z0-9_]{3,40}",name) or name in ids:
            raise ValueError("invalid or duplicate design identifier")
        ids.add(name)
        for key,lo,hi in (("axis_height_mm",3.5,9),("barrel_radius_mm",2.5,6.5),
                          ("cable_keepout_start_x_mm",75,84)):
            v=alt[key]
            if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:
                raise ValueError("nonfinite or invalid design variant parameter")
        if alt["barrel_radius_mm"]>=alt["axis_height_mm"]+1:
            raise ValueError("barrel would penetrate below reference panel datum")
    return dict(req)

def machine_function_intent(req:Mapping[str,Any])->dict[str,Any]:
    def r(id,kind,statement,procedure,acceptance):
        return {"id":id,"kind":kind,"statement":statement,"priority":"must",
                "verification":{"method_type":"test","procedure":procedure,
                                "acceptance":acceptance,"evidence_status":"not_collected"}}
    return {
        "schema_version":"hardware_splicer.function_intent.v1",
        "project_id":req["project_id"],"name":"Two-part foldable hinge: motion + screen and cable keepouts",
        "purpose":"Two printable reference mating leaves rotate around an unverified 3mm hinge shaft without crushing hypothetical screens",
        "intended_use":"general_device","claims":[],
        "inputs":[{"id":"two_nominal_screen_packages","medium":"mechanical envelope"},
                  {"id":"nominal_pin","medium":"unverified external fastener"}],
        "outputs":[{"id":"rotational_joint_envelope","medium":"mechanical"}],
        "requirements":[
            r("R_MATE","interface","Two leaf bodies have interleaved coaxial knuckles and declared pin/bore running clearance.",
              "Reimport STEP and mechanically trial a real rod/print coupon",{"pin_diameter_mm":3,"bore_diameter_mm":3.5}),
            r("R_SWEEP","functional","Mating solids remain clear across all 0–180 degree positions.",
              "Independently evaluate BRep distances/intersections at discrete angles then test an actual assembled hinge",
              {"sample_angle_step_deg":5,"minimum_gap_mm":.4}),
            r("R_SCREEN","functional","Reference screen packages have noninterfering swept/closed space.",
              "Physically measure real display modules and test closed display-to-display clearance",
              {"nominal_minimum_screen_gap_mm":1}),
            r("R_CABLE","constraint","Reserve a service-loop envelope external to the hinge, without falsely claiming routed cable.",
              "Identify real cable/FPC and connector dimensions, route and fatigue-test external bend radius",
              {"reserved_radius_mm":9,"proof_status":"UNVERIFIED_CABLE_ROUTING"}),
            r("R_THIN","performance","Folded CAD envelope meets declared thickness limit.",
              "Measure final assembled device and displays with calipers",{"maximum_nominal_closed_height_mm":13.5}),
            r("R_PRINT","constraint","Two printed leaves export as valid mesh and STEP; metal shaft is reference-only.",
              "Use named FDM printer, measured shaft and print calibration coupons before physical assembly",
              {"solid_printed_parts":2}),
        ],
        "functions":[
            {"id":"F_FOLD","name":"Articulate two physical leaves","requirements":["R_MATE","R_SWEEP"],
             "subsystems":["S_LOWER","S_UPPER","S_SHAFT"]},
            {"id":"F_PROTECT","name":"Protect hypothetical displays and reserve cable envelope",
             "requirements":["R_SCREEN","R_CABLE"],"subsystems":["S_LOWER","S_UPPER"]},
            {"id":"F_FABRICATE","name":"Minimize printable envelope and material",
             "requirements":["R_THIN","R_PRINT"],"subsystems":["S_LOWER","S_UPPER"]},
        ],
        "subsystems":[
            {"id":"S_LOWER","name":"Lower printable hinge leaf","domain":"mechanical",
             "purpose":"Bottom folded shell and two alternating knuckles",
             "requirements":["R_MATE","R_SWEEP","R_THIN","R_PRINT"]},
            {"id":"S_UPPER","name":"Upper printable hinge leaf","domain":"mechanical",
             "purpose":"Top folded shell and three alternating knuckles",
             "requirements":["R_MATE","R_SWEEP","R_SCREEN","R_CABLE","R_THIN","R_PRINT"]},
            {"id":"S_SHAFT","name":"Unverified 3mm separate steel pin","domain":"mechanical",
             "purpose":"Reference mating axial cylinder only; no capture mechanism validated",
             "requirements":["R_MATE"]},
        ],
        "interfaces":[{
            "id":"I_REVOLUTE_PIN","name":"Running clearance in interleaved pivot knuckles",
            "from":"S_SHAFT","to":"S_LOWER","medium":"mechanical",
            "requirements":["R_MATE","R_SWEEP"],
            "unresolved":["real pin dimensional tolerance","printed bore accuracy",
                          "bearing wear and repeated fold endurance","axial shaft retention",
                          "hinge torque and full fatigue tests"]},
            {"id":"I_UPPER_PIN","name":"Upper pivot knuckle interface",
             "from":"S_SHAFT","to":"S_UPPER","medium":"mechanical",
             "requirements":["R_MATE","R_SWEEP"],"unresolved":["shaft fit and real part print"]},
        ],
    }

def _box(dims:tuple[float,float,float],xyz:tuple[float,float,float])->Any:
    import cadquery as cq
    return cq.Workplane("XY").box(*dims,centered=(True,True,False)).translate(xyz)

def make_parts(req:Mapping[str,Any],alt:Mapping[str,Any])->dict[str,Any]:
    import cadquery as cq
    d=req["design_reference"]; h=req["mechanical"]; c=req["cable"]
    axis=float(alt["axis_height_mm"]); radius=float(alt["barrel_radius_mm"])
    bore=h["hinge_bore_nominal_diameter_mm"] / 2
    t=d["panel_backing_thickness_mm"]
    def leaf(is_upper:bool):
        # Both screen/reference panels lie in XY at OPEN-FLAT angle=0.
        center_y=-(d["panel_gap_each_side_mm"]+d["panel_depth_mm"]/2) if is_upper else (d["panel_gap_each_side_mm"]+d["panel_depth_mm"]/2)
        body=_box((d["panel_width_mm"],d["panel_depth_mm"],t),(0,center_y,0))
        centres=h["lid_barrel_x_centres_mm"] if is_upper else h["base_barrel_x_centres_mm"]
        for xc in centres:
            # Web at |Y| >= 2.2 lies OUTSIDE the 1.75 mm shaft hole.
            web_y=-5 if is_upper else 5
            web=_box((14,6,max(1.9,axis-1.7)),(xc,web_y,0))
            barrel=(cq.Workplane("YZ").center(0,axis)
                   .circle(radius).circle(bore).extrude(14)
                   .translate((xc-7,0,0)))
            body=body.union(web).union(barrel)
        result=body.combine().clean().val()
        if not result.isValid():
            raise ValueError("leaf is not a valid source CAD solid")
        return result
    lower=leaf(False);upper=leaf(True)
    nominal_pin=(cq.Workplane("YZ").center(0,axis)
                 .circle(h["pin_nominal_diameter_mm"]/2).extrude(90)
                 .translate((-45,0,0)).val())
    # Keepouts are simulated solids, explicitly NOT components for printing.
    screen_lower=_box((
         d["screen_keepout_width_mm"],d["screen_keepout_depth_mm"],
         d["screen_package_thickness_mm"]
    ),(0,d["screen_keepout_center_y_mm"],t)).val()
    screen_upper=_box((
         d["screen_keepout_width_mm"],d["screen_keepout_depth_mm"],
         d["screen_package_thickness_mm"]
    ),(0,-d["screen_keepout_center_y_mm"],t)).val()
    cable=(cq.Workplane("YZ").center(0,axis)
           .circle(c["reserved_cable_bend_envelope_radius_mm"])
           .extrude(c["keepout_axial_extent_mm"])
           .translate((alt["cable_keepout_start_x_mm"],0,0)).val())
    return {"lower_leaf":lower,"upper_leaf":upper,"shaft_reference":nominal_pin,
            "screen_lower_keepout":screen_lower,"screen_upper_keepout":screen_upper,
            "cable_service_keepout":cable}

def spin(shape:Any,alt:Mapping[str,Any],angle:float)->Any:
    axis=alt["axis_height_mm"]
    return shape.rotate((0,0,axis),(1,0,axis),-angle)

def _distance(first:Any,second:Any)->float:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    d=BRepExtrema_DistShapeShape(first.wrapped,second.wrapped)
    d.Perform()
    if not d.IsDone():
        raise ValueError("genuine OpenCascade solid-to-solid proximity failed")
    return float(d.Value())

def evaluate_motion(req:Mapping[str,Any],alt:Mapping[str,Any],parts:Mapping[str,Any],
                    *,step_deg:int|None=None)->dict[str,Any]:
    import cadquery as cq
    sampling=req["mechanical"]["angle_sampling_step_deg"] if step_deg is None else step_deg
    if type(sampling) is not int or sampling not in (1,5,10,15):
        raise ValueError("unsupported kinematic sweep sampling")
    angles=range(0,181,sampling)
    lower,upper=parts["lower_leaf"],parts["upper_leaf"]
    measures=[]
    for angle in angles:
        lid=spin(upper,alt,angle)
        scr=spin(parts["screen_upper_keepout"],alt,angle)
        clearance=_distance(lower,lid)
        screen_gap=_distance(parts["screen_lower_keepout"],scr)
        cross_clearance=min(_distance(parts["screen_lower_keepout"],lid),
                            _distance(scr,lower))
        # Euclidean distance=0 could mean contact or volume overlap. Use
        # the actual BRep Boolean only when proximity reports contact.
        shell_overlap=lower.intersect(lid).Volume() if clearance <.002 else 0.
        scr_overlap=(parts["screen_lower_keepout"].intersect(scr).Volume()
                     if screen_gap <.002 else 0.)
        cross_overlap=0.
        if cross_clearance<.002:
            cross_overlap=(parts["screen_lower_keepout"].intersect(lid).Volume()
                           + scr.intersect(lower).Volume())
        cable_gap=min(_distance(parts["cable_service_keepout"],lower),
                      _distance(parts["cable_service_keepout"],lid))
        measures.append({
            "angle_deg":angle,"shell_distance_mm":round(clearance,4),
            "shell_interference_mm3":round(shell_overlap,5),
            "screen_distance_mm":round(screen_gap,4),
            "screen_interference_mm3":round(scr_overlap,5),
            "screen_to_other_leaf_distance_mm":round(cross_clearance,4),
            "screen_to_other_leaf_interference_mm3":round(cross_overlap,5),
            "external_cable_reservation_distance_mm":round(cable_gap,4),
        })
    closed=spin(upper,alt,180)
    all_parts=cq.Compound.makeCompound([lower,closed])
    bbox=all_parts.BoundingBox()
    folded_z=bbox.zmax - bbox.zmin
    c=req["cable"];h=req["mechanical"];d=req["design_reference"]
    shaft=parts["shaft_reference"]
    checks={
        "valid_two_separate_source_leaf_solids":all(x.isValid() for x in (lower,upper)),
        "nominal_pin_clearance_both_leaves":min(
            _distance(shaft,lower),_distance(shaft,upper))>=.20,
        "minimum_hinge_radial_wall_mm":alt["barrel_radius_mm"]-h["hinge_bore_nominal_diameter_mm"]/2>=h["minimum_radial_wall_mm"],
        "moving_shells_no_BRep_intersections":not any(x["shell_interference_mm3"]>.001 for x in measures),
        "moving_shells_keep_min_nominal_gap":min(x["shell_distance_mm"] for x in measures)>=h["minimum_leaf_separation_mm"],
        "screen_mockups_no_sweep_intersection":not any(x["screen_interference_mm3"]>.001 for x in measures),
        "screen_mockups_keep_min_nominal_gap":min(x["screen_distance_mm"] for x in measures)>=h["minimum_screen_gap_mm"],
        "screens_clear_opposite_printed_leaf":(
            not any(x["screen_to_other_leaf_interference_mm3"]>.001 for x in measures)
            and min(x["screen_to_other_leaf_distance_mm"] for x in measures)>=.4
        ),
        "external_cable_corridor_avoids_printed_solids":min(
            x["external_cable_reservation_distance_mm"] for x in measures
        )>=c["minimum_keepout_to_solid_clearance_mm"],
        "folded_printed_shell_thickness_within_limit":folded_z<=h["folded_envelope_max_height_mm"],
        "cable_corridor_within_nominal_max_width":(
            alt["cable_keepout_start_x_mm"]+c["keepout_axial_extent_mm"]
            +d["panel_width_mm"]/2 <= c["maximum_overall_width_with_keepout_mm"]
        ),
        "nominal_metal_pin_not_printed":True,
    }
    return {
        "id":alt["id"],"mechanism":{"axis":"X","rotation_deg":[0,180],
                                   "rotation_direction":"negative",
                                   "moving_part":"upper_leaf","static_part":"lower_leaf",
                                   "interval_samples":len(measures),
                                   "angle_step_deg":sampling},
        "geometry":{"solid_volume_mm3":round(lower.Volume()+upper.Volume(),3),
                    "lower_volume_mm3":round(lower.Volume(),3),
                    "upper_volume_mm3":round(upper.Volume(),3),
                    "folded_solid_height_mm":round(folded_z,3),
                    "open_solid_y_extent_mm":round(max(upper.BoundingBox().ymax,lower.BoundingBox().ymax)-min(upper.BoundingBox().ymin,lower.BoundingBox().ymin),3),
                    "pin_bore_diametral_clearance_mm":round(
                        h["hinge_bore_nominal_diameter_mm"]-h["pin_nominal_diameter_mm"],3),
                    "hinge_wall_mm":round(alt["barrel_radius_mm"]-h["hinge_bore_nominal_diameter_mm"]/2,3),
                    "min_modelled_shell_gap_mm":min(x["shell_distance_mm"] for x in measures),
                    "min_modelled_screen_gap_mm":min(x["screen_distance_mm"] for x in measures),
                    "min_screen_to_other_leaf_gap_mm":min(x["screen_to_other_leaf_distance_mm"] for x in measures),
                    "min_reserved_cable_corridor_separation_mm":min(x["external_cable_reservation_distance_mm"] for x in measures)},
        "discrete_sweep":measures,
        "checks":checks,"nominal_mechanism_feasible":all(checks.values()),
        "physical_screen_or_cable_test_completed":False,
        "shaft_retention_verified":False,"actual_cable_routed":False,
        "continuous_angle_collision_certified":False,
    }

def _export(shape:Any,path:Path)->dict[str,Any]:
    import cadquery as cq
    import trimesh
    if not shape.isValid():
        raise ValueError("source solid is not a valid OCP BRep")
    st=path.with_suffix(".step")
    mesh_file=path.with_suffix(".stl")
    shape.exportStep(str(st))
    shape.exportStl(str(mesh_file),tolerance=.03,angularTolerance=.18)
    reimport=cq.importers.importStep(str(st)).val()
    tri=trimesh.load(str(mesh_file),force="mesh")
    if (not reimport.isValid() or not tri.is_watertight
        or not math.isclose(reimport.Volume(),shape.Volume(),abs_tol=.15)
        or not math.isclose(tri.volume,shape.Volume(),rel_tol=.007)):
        raise ValueError("real BRep STEP / watertight STL roundtrip failed")
    return {"step_sha256":file_sha(st),"stl_sha256":file_sha(mesh_file),
            "BRep_volume_mm3":round(shape.Volume(),3),
            "mesh_faces":len(tri.faces),"mesh_watertight":True,
            "STEP_volume_mm3":round(reimport.Volume(),3),
            "STL_volume_mm3":round(tri.volume,3),
            "fabrication_authorized":False}

def execute(req:Mapping[str,Any],out:Path)->dict[str,Any]:
    import cadquery as cq
    req=validate(req)
    if out.exists():
        raise ValueError("source results already present: refuse a silent reroll")
    function=machine_function_intent(req)
    project,gate=parse_intent(function)
    if gate["status"]!="FUNCTIONAL_CONCEPT_ONLY" or not gate["functional_traceability_pass"]:
        raise ValueError("native HS functional-intent gate rejected moving mechanism")
    if any(gate["physical_authority"].values()):
        raise ValueError("native project tried to grant physical fabrication authority")
    out.mkdir(parents=True)
    (out/"function_intent.json").write_bytes(canonical(function))
    rows=[]
    for alt in req["alternatives"]:
        parts=make_parts(req,alt)
        row=evaluate_motion(req,alt,parts)
        folder=out/"candidates"/alt["id"]
        folder.mkdir(parents=True)
        row["printed_files"]={
            name:_export(parts[name],folder/name)
            for name in ("lower_leaf","upper_leaf")
        }
        rows.append(row)
    eligible=sorted((r for r in rows if r["nominal_mechanism_feasible"]),
                    key=lambda x:(x["geometry"]["solid_volume_mm3"],x["geometry"]["folded_solid_height_mm"],x["id"]))
    chosen=eligible[0]["id"] if eligible else None
    if chosen:
        selected_alt=next(a for a in req["alternatives"] if a["id"]==chosen)
        best=make_parts(req,selected_alt)
        folder=out/"selected"
        folder.mkdir()
        # Copy the already audited candidate bytes, not a fresh export:
        # STEP metadata and mesh tessellation bytes may differ between two
        # geometrically equivalent exports, so the selected artifact should
        # preserve EXACTLY the verified source candidate SHA.
        import shutil
        for name in ("lower_leaf","upper_leaf"):
            candidate=out/"candidates"/chosen/name
            for suffix in (".step",".stl"):
                shutil.copyfile(candidate.with_suffix(suffix),(folder/name).with_suffix(suffix))
        # Actual multi-solid STEP compound including reference pin; pin is
        # NOT provided as a manufactured/validated printer part.
        for angle,label in ((0,"open_0"),(90,"half_90"),(180,"folded_180")):
            compound=cq.Compound.makeCompound([
                best["lower_leaf"],spin(best["upper_leaf"],selected_alt,angle),
                best["shaft_reference"],
            ])
            compound.exportStep(str(folder/(f"assembly_{label}.step")))
        best["cable_service_keepout"].exportStep(str(folder/"cable_service_keepout_only.step"))
    report={
        "schema":OUTPUT,"project_id":req["project_id"],
        "reference_spec_sha256":hashlib.sha256(canonical(req)).hexdigest(),
        "native_function_intent_SHA256":file_sha(out/"function_intent.json"),
        "native_function_gate":gate,
        "candidates":rows,"feasible_order":[r["id"] for r in eligible],
        "selected":chosen,
        "selection_reason":"lowest genuine printable-leaf BRep volume among candidates meeting discrete motion, screen/cable keepout and folded thickness proxy gates",
        "source_uncertainties":[
            "The screen package is an assumed BRep box, not a sourced display module.",
            "A cable keepout is NOT a routed/connected cable, connector bend test, flexible circuit or life-test.",
            "The pin is an unmeasured 3 mm metal-shaft reference, not a ready-to-fit printable fastener.",
            "A five-degree sampled sweep is NOT a continuous mathematical clearance proof.",
            "No load case, torque requirement, wall fatigue/FEM, bearing wear or shaft retention test.",
            "No real FDM printer profile, actual print, component measurements or closed-stack tolerancing.",
        ],
        "authority":{"physical_components_verified":False,"live_hardware_rotated":False,
                     "actual_cable_routed":False,"motion_fatigue_measured":False,
                     "print_completed":False,"mechanical_production_release":False},
    }
    (out/"HINGE_EVALUATION.json").write_bytes(canonical(report))
    return report

"""Post-#333 hinge retention hardware and nominal flexible-cable routing.

Real CadQuery/OCP grooved shaft and open C-ring stop geometries are
created and inspected. The cable is an angle-dependent 3D *reference*
centerline that conserves nominal free length, not a connected FPC.
No hardware datasheets, elastic circlip assembly, anchor fit, strain
relief, real cable fatigue or physical release is asserted.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any,Mapping

from .function_print_geometry import canonical,file_sha
from .functional_hinge_assembly import (
    make_parts,spin,_distance,machine_function_intent,validate as parent_validate,
)
from .function_intent_bridge import parse_intent

SCHEMA="hs.cyberdeck_hinge_retention_cable_path.v1"
OUTPUT="hs.cyberdeck_hinge_retention_route_trial.v1"

def checked_sources(req:Mapping[str,Any],parent:Mapping[str,Any])->tuple[dict,dict]:
    p=parent_validate(parent)
    if req.get("schema")!=SCHEMA or req.get("project_id")!=p["project_id"] or req.get("source_variant")!="balanced_60":
        raise ValueError("not the previously selected mechanically traced source hinge")
    if any(v is not False for v in req.get("authority",{}).values()) or not req.get("authority"):
        raise ValueError("unverified pin/cable dimensions cannot claim hardware authority")
    r=req["pin_retention"]
    expected={
        "shaft_length_mm":96,"shaft_nominal_diameter_mm":3,
        "grooves_x_centres_mm":[-45.2,45.2],
        "groove_minor_diameter_mm":2.20,"groove_axial_width_mm":.95,
        "retaining_ring_outside_diameter_mm":6.2,
        "retaining_ring_inside_diameter_mm":2.34,
        "retaining_ring_axial_thickness_mm":.70,
        "retaining_ring_opening_width_mm":1.7,
        "retaining_ring_opening_side":"positive Y",
        "min_clearance_ring_to_printed_leaf_mm":.65,
        "max_nominal_pin_float_total_mm":4.5,
        "ring_elastic_assembly_verified":False,
        "metal_ring_material_verified":False,
        "actual_hardware_sourced":False,
    }
    if r!=expected:
        raise ValueError("retainer geometry differs from registered source assumptions")
    c=req["cable_route"]
    if (c["nominal_cable_diameter_mm"]!=1.10
        or c["minimum_hypothetical_bend_radius_mm"]!=2
        or c["nominal_lower_exit_xyz_mm"]!=[81.6,16,5]
        or c["nominal_upper_exit_local_xyz_mm"]!=[81.6,-16,5]
        or c["route_x_outward_bulge_mm"]!=6.4
        or c["rightmost_total_width_limit_mm"]!=165
        or c["max_folded_route_height_mm"]!=20
        or c["original_printed_closed_height_limit_mm"]!=13.5
        or c["minimum_cable_to_printed_solid_clearance_mm"]!=2
        or c["minimum_cable_to_retainer_clearance_mm"]!=2
        or c["max_free_segment_length_variation_pct"]!=.2
        or c["max_allowable_cable_to_original_keepout_intrusion_mm3"]!=0
        or any(c[k] is not False for k in (
            "cable_material_verified","real_connector_dimensions_verified",
            "anchor_guides_modelled","actual_electrical_connectivity_verified",
            "repeated_fold_test_completed"
        ))):
        raise ValueError("fabricated cable properties or unregistered envelope")
    if c["route_designs"]!=[
        {"id":"compact_low_bend","z_loop_bulge_mm":8,"free_length_mm":40},
        {"id":"medium_low_bend","z_loop_bulge_mm":10,"free_length_mm":40},
        {"id":"roomy_bend_relief","z_loop_bulge_mm":12,"free_length_mm":44},
        {"id":"tall_bend_relief","z_loop_bulge_mm":14,"free_length_mm":48},
    ]:
        raise ValueError("cable source geometry options differ")
    chosen=next((a for a in p["alternatives"] if a["id"]==req["source_variant"]),None)
    if chosen is None or chosen["axis_height_mm"]!=6:
        raise ValueError("selected source hinge has changed")
    return dict(req),p

def _cylinder_along_x(r:float,length:float,start_x:float,axis_z:float):
    import cadquery as cq
    return (cq.Workplane("YZ").center(0,axis_z).circle(r)
            .extrude(length).translate((start_x,0,0)))

def make_retainer(req:Mapping[str,Any],parent:Mapping[str,Any])->dict[str,Any]:
    """Exact multi-solid reference CAD; not sourced or designed for printing."""
    import cadquery as cq
    source,orig=checked_sources(req,parent)
    r=source["pin_retention"];axis=6
    L=r["shaft_length_mm"]
    rod=_cylinder_along_x(r["shaft_nominal_diameter_mm"]/2,L,-L/2,axis)
    rings={}
    for side,cx in zip(("left","right"),r["grooves_x_centres_mm"]):
        w=r["groove_axial_width_mm"]
        annular_cut=(cq.Workplane("YZ").center(0,axis)
                     .circle(r["shaft_nominal_diameter_mm"]/2+.1)
                     .circle(r["groove_minor_diameter_mm"]/2)
                     .extrude(w).translate((cx-w/2,0,0)))
        rod=rod.cut(annular_cut)
        rt=r["retaining_ring_axial_thickness_mm"]
        ring=(cq.Workplane("YZ").center(0,axis)
              .circle(r["retaining_ring_outside_diameter_mm"]/2)
              .circle(r["retaining_ring_inside_diameter_mm"]/2)
              .extrude(rt).translate((cx-rt/2,0,0)))
        # A radial insertion gap makes an actual C geometry, rather
        # than an impossible-to-install closed washer. Elastic
        # expansion and actual assembly are NOT tested here.
        radial_opening=(cq.Workplane("XY")
            .box(rt+2,6,r["retaining_ring_opening_width_mm"],
                 centered=(True,True,True))
            .translate((cx,3.3,axis)))
        ring=ring.cut(radial_opening)
        rings[side]=ring.val()
    shaft=rod.val()
    bodies=[shaft,*rings.values()]
    if any(not b.isValid() or b.Volume()<=0 for b in bodies):
        raise ValueError("nominal retainer source solid failed OCP validity")
    return {"shaft":shaft,"ring_left":rings["left"],"ring_right":rings["right"]}

def inspect_pin(req:Mapping[str,Any],parent:Mapping[str,Any],
                *,angles=range(0,181,5))->dict[str,Any]:
    """Check actual OCP clearance vs moving leaves and nonprinted rings."""
    source,orig=checked_sources(req,parent)
    alt=next(a for a in orig["alternatives"] if a["id"]==source["source_variant"])
    leaves=make_parts(orig,alt)
    hardware=make_retainer(source,orig)
    shaft=hardware["shaft"]
    r=source["pin_retention"]
    barrel_end=43.0  # Derived from original alternating x-centers and 14 mm knuckle length
    axial_stop_gap=(abs(r["grooves_x_centres_mm"][1])
                   -r["retaining_ring_axial_thickness_mm"]/2-barrel_end)
    axial_float_total=2*axial_stop_gap
    clip_overlap=r["retaining_ring_outside_diameter_mm"]/2-orig["mechanical"]["hinge_bore_nominal_diameter_mm"]/2
    radial_groove_clearance=(r["retaining_ring_inside_diameter_mm"]-r["groove_minor_diameter_mm"])/2
    min_clip=1e5
    min_shaft=1e5
    records=[]
    for angle in angles:
        upper=spin(leaves["upper_leaf"],alt,angle)
        leafs=(leaves["lower_leaf"],upper)
        clip_gap=min(_distance(hardware[key],body)
                     for key in ("ring_left","ring_right") for body in leafs)
        shaft_gap=min(_distance(shaft,body) for body in leafs)
        records.append({"angle_deg":angle,
                        "minimum_retainer_ring_to_leaf_mm":round(clip_gap,4),
                        "minimum_pin_to_leaf_mm":round(shaft_gap,4)})
        min_clip=min(min_clip,clip_gap)
        min_shaft=min(min_shaft,shaft_gap)
    checks={
        "source_pin_and_grooves_are_valid_BRep":shaft.isValid(),
        "source_c_rings_are_valid_BRep":all(hardware[n].isValid() for n in ("ring_left","ring_right")),
        "two_ring_grooves_oppose_axial_escape":clip_overlap>.8 and axial_stop_gap>0,
        "nominal_total_axial_float_below_limit":axial_float_total<=r["max_nominal_pin_float_total_mm"],
        "nominal_ring_to_5_knuckles_clearance":min_clip>=r["min_clearance_ring_to_printed_leaf_mm"],
        "nominal_pin_running_clearance":min_shaft>=.2,
        "ring_inner_clears_small_groove":radial_groove_clearance>.05,
        "retention_cannot_be_axially_slid_past_full_shaft":(
            r["retaining_ring_inside_diameter_mm"]<r["shaft_nominal_diameter_mm"]
        ),
    }
    return {
        "schema":"hs.cyberdeck_hinge_pin_retention_check.v1",
        "source_hinge":"balanced_60",
        "nominal_clip_axial_stop_to_barrel_mm":round(axial_stop_gap,3),
        "nominal_total_axial_float_mm":round(axial_float_total,3),
        "nominal_clip_radial_overlap_with_hinge_bore_mm":round(clip_overlap,3),
        "nominal_clip_groove_running_gap_mm":round(radial_groove_clearance,3),
        "minimum_swept_clip_to_leaf_mm":round(min_clip,4),
        "minimum_swept_shaft_to_leaf_mm":round(min_shaft,4),
        "motion_samples":records,
        "checks":checks,
        "nominal_cad_checks_pass":all(checks.values()),
        "spring_clip_installable_verified":False,
        "clip_strength_or_axial_load_verified":False,
        "real_machined_pin_or_ring_available":False,
        "continuous_angle_clearance_certified":False,
    }


def _cable_samples(parent:Mapping[str,Any],route:Mapping[str,Any],
                   mode:Mapping[str,Any],angle:float,*,points:int=201)->dict[str,Any]:
    import numpy as np
    axis=6.0  # source hinge axis height
    t=np.linspace(0,1,points)
    lo=np.array(route["nominal_lower_exit_xyz_mm"],dtype=float)
    hi=np.array(route["nominal_upper_exit_local_xyz_mm"],dtype=float)
    rad=math.radians(angle)
    hi_y=(hi[1]*math.cos(rad)+(hi[2]-axis)*math.sin(rad))
    hi_z=(axis-hi[1]*math.sin(rad)+(hi[2]-axis)*math.cos(rad))
    hi=np.array([hi[0],hi_y,hi_z])
    A=route["route_x_outward_bulge_mm"]
    C=mode["z_loop_bulge_mm"]
    L=mode["free_length_mm"]
    def calculate(B:float):
        s=np.sin(math.pi*t)
        x=lo[0]+A*s*s
        y=lo[1]+(hi[1]-lo[1])*t+B*np.sin(2*math.pi*t)
        z=lo[2]+(hi[2]-lo[2])*t+C*s
        arr=np.stack([x,y,z],axis=1)
        length=float(np.linalg.norm(np.diff(arr,axis=0),axis=1).sum())
        return arr,length
    # The free span is constrained to a constant material length,
    # rather than instantaneously stretching as the lid rotates.
    initial,base=calculate(0)
    if base>L+.01:
        return {"angle_deg":angle,"route_solvable":False,
                "error":"minimum route already exceeds fixed free cable length",
                "minimum_unbulged_length_mm":round(base,4)}
    low,high=0.,30.
    for _ in range(37):
        middle=(low+high)/2
        if calculate(middle)[1]<L:low=middle
        else:high=middle
    arr,length=calculate(high)
    if abs(length-L)>.02:
        raise ValueError("cable fixed-length optimizer did not converge")
    d1=np.gradient(arr,t,axis=0)
    d2=np.gradient(d1,t,axis=0)
    curvature=np.linalg.norm(np.cross(d1,d2),axis=1)/(np.linalg.norm(d1,axis=1)**3)
    # Endpoint derivatives are numerical one-sided estimators; all
    # interior points use a centered discrete derivative.
    radius=float(1/np.max(curvature[2:-2]))
    nonlocal_sep=1e5
    # Exclude immediate cable neighbours within 10% of total
    # arclength; this measures only obvious nonlocal self-contact.
    for i in range(len(arr)):
        j=i+22
        if j<len(arr):
            d=np.linalg.norm(arr[j:]-arr[i],axis=1)
            nonlocal_sep=min(nonlocal_sep,float(d.min()))
    keep=parent["cable"]["reserved_cable_bend_envelope_radius_mm"]
    original_keepout_xlo=78.5
    original_keepout_xhi=86.5
    rr=np.sqrt(arr[:,1]**2+(arr[:,2]-axis)**2)
    # Earlier model was an EMPTY cylindrical reservation. An actual
    # routed cable must be checked against that old assumption.
    outside_old=( (arr[:,0]-route["nominal_cable_diameter_mm"]/2 < original_keepout_xlo)
                  |(arr[:,0]+route["nominal_cable_diameter_mm"]/2>original_keepout_xhi)
                  |(rr+route["nominal_cable_diameter_mm"]/2>keep))
    return {
        "angle_deg":angle,"route_solvable":True,
        "optimised_lateral_loop_mm":round(high,4),
        "free_segment_length_mm":round(length,4),
        "minimum_discrete_centerline_bend_radius_mm":round(radius,4),
        "minimum_nonlocal_wire_center_distance_mm":round(nonlocal_sep,4),
        "maximum_rightmost_cable_x_mm":round(float(arr[:,0].max()+route["nominal_cable_diameter_mm"]/2),4),
        "maximum_cable_z_mm":round(float(arr[:,2].max()+route["nominal_cable_diameter_mm"]/2),4),
        "minimum_cable_z_mm":round(float(arr[:,2].min()-route["nominal_cable_diameter_mm"]/2),4),
        "minimum_centerline_x_mm":round(float(arr[:,0].min()),4),
        "outside_original_cable_keepout_fraction":round(float(outside_old.mean()),4),
        "wire_centerline_points_xyz_mm":arr.tolist(),
    }

def evaluate_routes(req:Mapping[str,Any],parent:Mapping[str,Any],
                    *,step_deg:int=5)->dict[str,Any]:
    source,orig=checked_sources(req,parent)
    if type(step_deg) is not int or step_deg not in (1,5,15,30,45):
        raise ValueError("unsupported source route angle interval")
    route=source["cable_route"]
    retainer=source["pin_retention"]
    cable_r=route["nominal_cable_diameter_mm"]/2
    rows=[]
    for mode in route["route_designs"]:
        poses=[_cable_samples(orig,route,mode,angle)
               for angle in range(0,181,step_deg)]
        okay=all(p["route_solvable"] for p in poses)
        if not okay:
            rows.append({"id":mode["id"],"route_solved":False,
                         "reason":"unrealistic fixed length for selected endpoint geometry"})
            continue
        # Printed leaves are entirely within |x|<=76 in the inherited
        # source hinge; routing x>=81.6 provides a rigorous transverse
        # clearance lower bound without claiming exact FPC fit.
        solid_rightmost=orig["design_reference"]["panel_width_mm"]/2
        min_wall_gap=min(p["minimum_centerline_x_mm"] for p in poses)-cable_r-solid_rightmost
        clip_rightmost=max(retainer["grooves_x_centres_mm"])+retainer["retaining_ring_axial_thickness_mm"]/2
        clip_gap=min(p["minimum_centerline_x_mm"] for p in poses)-cable_r-clip_rightmost
        min_bend=min(p["minimum_discrete_centerline_bend_radius_mm"] for p in poses)
        min_self=min(p["minimum_nonlocal_wire_center_distance_mm"] for p in poses)
        maxwidth=max(p["maximum_rightmost_cable_x_mm"] for p in poses)+solid_rightmost
        # Separate full folded package thickness from the former
        # "printed shell only" 13.5mm thickness number.
        fold=poses[-1]
        packed=max(12.,fold["maximum_cable_z_mm"])-min(0.,fold["minimum_cable_z_mm"])
        length_error=max(abs(p["free_segment_length_mm"]-mode["free_length_mm"])
                         for p in poses)/mode["free_length_mm"]*100.
        old_reservation_covers=all(p["outside_original_cable_keepout_fraction"]==0 for p in poses)
        checks={
            "hypothetical_centerline_bend_radius_minimum":min_bend>=route["minimum_hypothetical_bend_radius_mm"],
            "constant_free_length_across_sampled_positions":length_error<=route["max_free_segment_length_variation_pct"],
            "no_obvious_nonlocal_wire_self_overlap":min_self>=route["nominal_cable_diameter_mm"],
            "wire_stays_clear_of_printed_leaf_x_envelope":min_wall_gap>=route["minimum_cable_to_printed_solid_clearance_mm"],
            "wire_stays_clear_of_nominal_end_retainer":clip_gap>=route["minimum_cable_to_retainer_clearance_mm"],
            "wire_within_nominal_external_width":maxwidth<=route["rightmost_total_width_limit_mm"],
            "folded_wire_within_declared_service_height":packed<=route["max_folded_route_height_mm"],
        }
        rows.append({
            "id":mode["id"],"route_solved":True,
            "source_nominal_free_length_mm":mode["free_length_mm"],
            "sample_count":len(poses),"angular_sample_step_deg":step_deg,
            "minimum_bend_radius_mm":round(min_bend,4),
            "minimum_free_wire_self_separation_mm":round(min_self,4),
            "minimum_wire_to_printed_x_clearance_mm":round(min_wall_gap,4),
            "minimum_wire_to_retainer_x_clearance_mm":round(clip_gap,4),
            "nominal_overall_cable_width_mm":round(maxwidth,4),
            "packed_envelope_height_including_cable_mm":round(packed,4),
            "within_former_13p5mm_printed_only_limit":packed<=route["original_printed_closed_height_limit_mm"],
            "old_reserved_cable_corridor_contains_route":old_reservation_covers,
            "max_original_reservation_outside_fraction":max(
                p["outside_original_cable_keepout_fraction"] for p in poses),
            "max_nominal_cable_length_variation_pct":round(length_error,6),
            "checks":checks,
            "nominal_virtual_route_feasible":all(checks.values()),
            "physical_cable_connected":False,
            "physical_bend_and_cycle_lifetime_verified":False,
            "physical_strain_relief_or_anchors_verified":False,
            "poses":[{k:v for k,v in p.items() if k!="wire_centerline_points_xyz_mm"} for p in poses]
        })
    ranked=sorted((r for r in rows if r.get("nominal_virtual_route_feasible")),
                  key=lambda r:(r["packed_envelope_height_including_cable_mm"],
                                r["source_nominal_free_length_mm"],r["id"]))
    return {
        "schema":"hs.cyberdeck_hinge_virtual_cable_route_sweep.v1",
        "source_reference_hinge":"balanced_60",
        "cable_centreline_model":"fixed-length sin^2-X / sin(2t)-Y / sin(t)-Z reference spline",
        "route_candidates":rows,
        "selected_virtual_route":ranked[0]["id"] if ranked else None,
        "all_route_endpoints_unattached":True,
        "routing_is_not_an_electrical_connection":True,
        "original_empty_keepout_insufficient_for_actual_nominal_route":(
            all(not r["old_reserved_cable_corridor_contains_route"] for r in rows
                if r.get("route_solved"))
        ),
        "fabrication_authorized":False,
    }


def extra_function_intent(req:Mapping[str,Any],parent:Mapping[str,Any])->dict[str,Any]:
    original=machine_function_intent(parent)
    def requirement(ident,kind,statement,procedure):
        return {
            "id":ident,"kind":kind,"statement":statement,"priority":"must",
            "verification":{
                "method_type":"test","procedure":procedure,
                "acceptance":{"requires_real_hardware_observation":True},
                "evidence_status":"not_collected",
            },
        }
    original["requirements"].extend([
        requirement("R_RETAINER","interface",
                    "Two real ring references in grooved pin should geometrically block axial escape.",
                    "Install sourced calibrated circlips and measure pin axial travel, groove seating, force and wear."),
        requirement("R_WIRE_PATH","functional",
                    "A named hypothetical round wire spans both fold endpoints with bounded path length and curvature.",
                    "Choose actual FFC/cable datasheet, anchor mechanical connectors, then fold repeatedly under camera."),
        requirement("R_PACKED_HEIGHT","constraint",
                    "The total cable free loop must not be confused with printed-only closed shell thickness.",
                    "Measure folded assembly with physical cable, retainer and display packages including routing bulges."),
    ])
    original["functions"].extend([
        {"id":"F_RETAIN_PIN","name":"Retain pivot axially",
         "requirements":["R_RETAINER"],"subsystems":["S_LOWER","S_UPPER","S_SHAFT","S_RETENTION"]},
        {"id":"F_ROUTE_WIRE","name":"Route flexible wire through entire folded travel",
         "requirements":["R_WIRE_PATH","R_PACKED_HEIGHT"],
         "subsystems":["S_LOWER","S_UPPER","S_CABLE"]},
    ])
    original["subsystems"].extend([
        {"id":"S_RETENTION","name":"Nominal metal C clips, not printed",
         "domain":"mechanical","purpose":"Opposed annular shaft grooves and split rings resist axial escape",
         "requirements":["R_RETAINER"]},
        {"id":"S_CABLE","name":"Unmeasured external flex-cable reference path",
         "domain":"mechanical","purpose":"Reserve constant-length free loop with screened curvature",
         "requirements":["R_WIRE_PATH","R_PACKED_HEIGHT"]},
    ])
    original["interfaces"].extend([
        {"id":"I_RETENTION_GROOVE","name":"Split spring ring in machined metal shaft groove",
         "from":"S_RETENTION","to":"S_SHAFT","medium":"mechanical",
         "requirements":["R_RETAINER"],
         "unresolved":["ring elastic radial installation feasibility",
                       "actual shaft diameter and groove machining",
                       "axial pullout force and fatigue","commercial ring sourcing"]},
        {"id":"I_WIRE_TERMINATIONS","name":"Two explicitly unanchored virtual wire exits",
         "from":"S_CABLE","to":"S_UPPER","medium":"mechanical",
         "requirements":["R_WIRE_PATH","R_PACKED_HEIGHT"],
         "unresolved":["actual upper/lower connectors not present",
                       "full cable electrical continuity not verified",
                       "no cable clips or strain relief designed",
                       "datasheet bend radius and cycles unverified"]},
    ])
    return original

def make_cable_envelope(source:Mapping[str,Any],parent:Mapping[str,Any],
                        mode:Mapping[str,Any],angle:float)->Any:
    """Sweep a real solid tube BRep along nominal angle-dependent spline."""
    import cadquery as cq
    _,orig=checked_sources(source,parent)
    row=_cable_samples(orig,source["cable_route"],mode,angle)
    if not row.get("route_solvable"):
        raise ValueError("cannot generate a wire for an infeasible fixed-length shape")
    nodes=[cq.Vector(*p) for p in row["wire_centerline_points_xyz_mm"][::4]]
    edge=cq.Edge.makeSpline(nodes)
    curve=cq.Wire.assembleEdges([edge])
    tangent=nodes[1].sub(nodes[0])
    tube=(cq.Workplane(cq.Plane(origin=nodes[0],normal=tangent))
          .circle(source["cable_route"]["nominal_cable_diameter_mm"]/2)
          .sweep(cq.Workplane().newObject([curve]),isFrenet=True).val())
    if not tube.isValid() or len(tube.Solids())!=1 or tube.Volume()<=0:
        raise ValueError("cable nominal BRep swept envelope failed")
    return tube

def run(req:Mapping[str,Any],parent:Mapping[str,Any],*,out:Path)->dict[str,Any]:
    import cadquery as cq
    source,orig=checked_sources(req,parent)
    if out.exists():
        raise ValueError("retention-and-route model already executed; do not overwrite")
    func=extra_function_intent(source,orig)
    project,gate=parse_intent(func)
    if gate["status"]!="FUNCTIONAL_CONCEPT_ONLY" or not gate["functional_traceability_pass"]:
        raise ValueError("existing HS functional-intent chain rejected retention and route")
    if any(gate["physical_authority"].values()):
        raise ValueError("unverified new functional geometry was falsely authorized")
    pin=inspect_pin(source,orig)
    if not pin["nominal_cad_checks_pass"]:
        raise ValueError("retention model failed to demonstrate nominal geometric shaft capture")
    routes=evaluate_routes(source,orig)
    selected=routes["selected_virtual_route"]
    if selected is None:
        raise ValueError("no candidate route met even nominal free-cable constraints")
    fine=evaluate_routes(source,orig,step_deg=1)
    if fine["selected_virtual_route"]!=selected:
        raise ValueError("coarser motion sweep selected inconsistent path")
    material=make_retainer(source,orig)
    alt=next(a for a in orig["alternatives"] if a["id"]==source["source_variant"])
    leaves=make_parts(orig,alt)
    mode=next(x for x in source["cable_route"]["route_designs"] if x["id"]==selected)
    out.mkdir(parents=True)
    (out/"function_intent.json").write_bytes(canonical(func))
    originals={}
    for name,part in material.items():
        path=out/(name+".step")
        part.exportStep(str(path))
        reread=cq.importers.importStep(str(path))
        if (not reread.val().isValid()
            or not math.isclose(reread.val().Volume(),part.Volume(),abs_tol=.1)):
            raise ValueError("roundtripped true retention BRep no longer matches source")
        originals[name]={"sha256":file_sha(path),"volume_mm3":round(part.Volume(),3),
                         "fabricated_component":False}
    output={}
    for angle,label in ((0,"open_0"),(90,"half_90"),(180,"folded_180")):
        cable=make_cable_envelope(source,orig,mode,angle)
        upper=spin(leaves["upper_leaf"],alt,angle)
        # This is a virtual 6-solid reference at each angle, NOT an
        # actual complete assembly or connected electronic harness.
        compound=cq.Compound.makeCompound([
            leaves["lower_leaf"],upper,
            material["shaft"],material["ring_left"],material["ring_right"],cable
        ])
        if any(cable.intersect(shape).Volume()>.001 for shape in (
            leaves["lower_leaf"],upper,*material.values()
        )):
            raise ValueError("actual source cable solid intersects physical hinge geometry")
        c_path=out/("cable_envelope_"+label+".step")
        assembly_path=out/("assembled_with_virtual_wire_"+label+".step")
        cable.exportStep(str(c_path))
        compound.exportStep(str(assembly_path))
        if len(cq.importers.importStep(str(assembly_path)).solids().vals())!=6:
            raise ValueError("actual multi-solid STEP did not retain six separate objects")
        output[label]={
            "cable_step_sha256":file_sha(c_path),
            "assembly_step_sha256":file_sha(assembly_path),
            "nominal_cable_solid_volume_mm3":round(cable.Volume(),3),
            "reference_assembly_solid_count":6,
            "virtual_cable_connected_to_actual_device":False,
        }
    report={
        "schema":OUTPUT,
        "source_spec_sha256":hashlib.sha256(canonical(source)).hexdigest(),
        "source_parent_hinge_sha256":hashlib.sha256(canonical(orig)).hexdigest(),
        "function_intent_sha256":file_sha(out/"function_intent.json"),
        "native_HS_function_gate":gate,
        "nominal_retainer_geometry":pin,
        "wire_routing_sweep":routes,
        "selected_nominal_wire_fine_181_pose_sweep":fine,
        "new_reference_geometry":originals,
        "cable_sweep_and_six_solid_assembly":output,
        "validation_limitations":[
            "Commercial spring clips and actual 3mm grooved metal shaft were not sourced.",
            "Split-ring elastic opening, groove tolerances, pullout load and endurance have not been measured.",
            "Wire spline endpoints deliberately float outside the printed panel: no physical anchors, connectors or strain relief.",
            "No real cable datasheet, electric continuity, flex fatigue or closed-stack device measurements.",
            "The old hinge empty keepout does NOT contain the modeled wire: old corridor needs redesign.",
            "The cable loop makes packed thickness larger than the former printed-only 13.5mm assertion.",
            "Sampled 1-degree/5-degree clearances are not continuous angular collision proofs.",
            "No printing, tooling manufacture or physical device/board measurements were performed."
        ],
        "authority":{
            "retention_elastic_assembly_verified":False,
            "commercial_retaining_hardware_sourced":False,
            "real_cable_routed_and_anchored":False,
            "wire_bending_fatigue_tested":False,
            "physical_hinge_folding_verified":False,
            "production_release_authorized":False
        },
    }
    (out/"RETENTION_AND_CABLE_TRIAL.json").write_bytes(canonical(report))
    return report


def audit(req:Mapping[str,Any],parent:Mapping[str,Any],*,out:Path)->dict[str,Any]:
    """Independently re-import retained STEP solids and recheck route from source."""
    import cadquery as cq
    source,orig=checked_sources(req,parent)
    report=json.loads((out/"RETENTION_AND_CABLE_TRIAL.json").read_text())
    if report.get("schema")!=OUTPUT:
        raise ValueError("unknown retained geometry receipt")
    if report["source_spec_sha256"]!=hashlib.sha256(canonical(source)).hexdigest():
        raise ValueError("retention source specification was edited")
    if report["source_parent_hinge_sha256"]!=hashlib.sha256(canonical(orig)).hexdigest():
        raise ValueError("original hinge physical source was changed")
    intent=extra_function_intent(source,orig)
    if report["function_intent_sha256"]!=file_sha(out/"function_intent.json"):
        raise ValueError("function traceability evidence file is no longer original")
    if json.loads((out/"function_intent.json").read_text())!=intent:
        raise ValueError("original HS MachineProject requirements no longer match")
    if report["wire_routing_sweep"]!=evaluate_routes(source,orig,step_deg=5):
        raise ValueError("a five-degree cable source path or scoring gate was changed")
    fine=evaluate_routes(source,orig,step_deg=1)
    if (report["selected_nominal_wire_fine_181_pose_sweep"]!=fine
        or fine["selected_virtual_route"]!="roomy_bend_relief"):
        raise ValueError("source-based fine nominal cable curve was swapped")
    expected=make_retainer(source,orig)
    for name,part in expected.items():
        record=report["new_reference_geometry"][name]
        path=out/(name+".step")
        if file_sha(path)!=record["sha256"]:
            raise ValueError("source-made metal reference STEP is altered")
        shape=cq.importers.importStep(str(path))
        if (len(shape.solids().vals())!=1 or not shape.val().isValid()
            or not math.isclose(shape.val().Volume(),part.Volume(),abs_tol=.10)
            or not math.isclose(record["volume_mm3"],part.Volume(),abs_tol=.01)):
            raise ValueError("retaining hardware STEP does not match source geometry")
        if record["fabricated_component"] is not False:
            raise ValueError("unsourced metal fitting was falsely marked manufactured")
    mode=next(x for x in source["cable_route"]["route_designs"]
              if x["id"]==fine["selected_virtual_route"])
    for angle,label in ((0,"open_0"),(90,"half_90"),(180,"folded_180")):
        record=report["cable_sweep_and_six_solid_assembly"][label]
        cable=out/("cable_envelope_"+label+".step")
        assembly=out/("assembled_with_virtual_wire_"+label+".step")
        if file_sha(cable)!=record["cable_step_sha256"] or file_sha(assembly)!=record["assembly_step_sha256"]:
            raise ValueError("frozen source cable tube/assembly STEP changed")
        tube=cq.importers.importStep(str(cable))
        solids=cq.importers.importStep(str(assembly)).solids().vals()
        if len(solids)!=6 or len(tube.solids().vals())!=1 or not tube.val().isValid():
            raise ValueError("genuine six-solid source hinge assembly could not be reimported")
        baseline=make_cable_envelope(source,orig,mode,angle)
        if not math.isclose(tube.val().Volume(),baseline.Volume(),abs_tol=.2):
            raise ValueError("original explicit cable solid no longer matches modelled route")
        if record["virtual_cable_connected_to_actual_device"] is not False:
            raise ValueError("unsourced cable connection falsely claimed verified")
    if not report["nominal_retainer_geometry"]["nominal_cad_checks_pass"]:
        raise ValueError("source pin cannot be retained under nominal CAD model")
    if report["wire_routing_sweep"]["selected_virtual_route"]!="roomy_bend_relief":
        raise ValueError("nominal reference spline selection changed")
    if any(report["authority"].values()):
        raise ValueError("unverified hardware fabrication or cable reliability was promoted")
    return {
        "schema":"hs.cyberdeck_retention_cable_offline_audit.v1",
        "source_spec_sha256":report["source_spec_sha256"],
        "source_hinge_sha256":report["source_parent_hinge_sha256"],
        "actual_imported_reference_metal_solids":3,
        "actual_reimported_six_part_pose_STEPS":3,
        "actual_reimported_cable_tubes":3,
        "retention_grooved_shaft_source_consistent":True,
        "sampled_cable_routes_source_consistent":True,
        "new_nominal_route_meets_declared_cable_constraints":True,
        "original_reserved_space_fails_to_contain_route":True,
        "cable_anchored_to_verified_hardware":False,
        "physical_assembly_certified":False,
    }

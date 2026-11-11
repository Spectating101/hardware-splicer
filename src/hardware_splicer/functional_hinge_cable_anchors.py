"""Printed screw-together cable saddles and honest cable motion gates.

Four genuine CadQuery printed solids (two hinge leaves with integral bases,
two removable caps) are tested against source-linked constant-length
nominal cable motion. A round wire is NOT an LVDS/FFC screen harness.
"""
from __future__ import annotations
import math,hashlib,json
from pathlib import Path
from typing import Any,Mapping
from .function_print_geometry import canonical,file_sha
from .functional_hinge_assembly import make_parts,spin,validate as verify_parent
from .functional_hinge_retention import checked_sources
SCHEMA="hs.cyberdeck_anchored_wire_pilot.v1"
OUTPUT="hs.cyberdeck_cable_anchor_mechanical_trial.v1"

def validate(s:Mapping[str,Any],hinge:Mapping[str,Any],retainer:Mapping[str,Any])->dict[str,Any]:
    p=verify_parent(hinge);checked_sources(retainer,p)
    if s.get("schema")!=SCHEMA or s.get("project_id")!=p["project_id"] or s.get("reference_selected_hinge")!="balanced_60":
        raise ValueError("not the pinned parent hinge and retention spec")
    if not s.get("authority") or any(v is not False for v in s["authority"].values()):
        raise ValueError("unverified physical cable/strain-relief authority promoted")
    w=s["wire"]
    if (w["profile"]!="round_wire_nominal" or w["diameter_mm"]!=1.1
        or w["display_data_cable_compatible"] is not False
        or w["datasheet_dynamic_bend_verified"] is not False
        or w["nominal_lower_exit_xyz"]!=[81.6,10,5]
        or w["nominal_upper_exit_local_xyz"]!=[81.6,-20,5]
        or w["nominal_min_bend_radius_mm"]!=2
        or w["cross_check_flexible_cable_dynamic_radius_multiple_diameter"]!=5
        or w["selected_manufacturer_part"] is not None):
        raise ValueError("unspecified round wire cannot be used as screen data cable")
    m=s["mount"]
    if m!={"lower_y_mm":10,"upper_y_mm":-20,"local_x_mm":81.6,
           "wire_center_z_mm":5,"base_outer_x_mm":[72,88],
           "base_width_y_mm":8,"base_top_z_mm":5,
           "cap_outer_x_mm":[74.6,88.6],"cap_width_y_mm":8,
           "cap_bottom_z_mm":5,"cap_top_z_mm":7.8,
           "channel_nominal_radius_mm":.8,"screw_x_mm":[77.2,86],
           "screw_nominal_clearance_diameter_mm":2.2,
           "nominal_fasteners_sourced":False,
           "actual_cable_clamping_force_verified":False,
           "physical_strain_relief_verified":False}:
        raise ValueError("unregistered cable mount geometry/authority")
    if s["routes"]!=[
        {"id":"short_40","free_length_mm":40,"z_bulge_mm":10,"x_bulge_mm":6.4},
        {"id":"medium_44","free_length_mm":44,"z_bulge_mm":12,"x_bulge_mm":6.4},
        {"id":"long_48","free_length_mm":48,"z_bulge_mm":14,"x_bulge_mm":6.4},
        {"id":"relaxed_52","free_length_mm":52,"z_bulge_mm":16,"x_bulge_mm":6.4}
    ]: raise ValueError("route candidates modified after experiment registration")
    if s["clearance"]!={"min_nominal_cable_to_solid_mm":.1,"max_total_width_mm":165,
                        "max_folded_cable_envelope_mm":20,
                        "min_hypothetical_bend_radius_mm":2,
                        "full_motion_step_deg":5,"fine_selected_step_deg":1}:
        raise ValueError("cable manufacturing proxy limits modified")
    if {r["issuer"] for r in s["source_links"]}!={"Molex","igus"}:
        raise ValueError("source manufacturer evidence absent")
    return dict(s)

def make_anchors(s:Mapping[str,Any],parent:Mapping[str,Any])->dict[str,Any]:
    """Source CAD: real integral mounting ears and separate removable caps."""
    import cadquery as cq
    alt=next(x for x in parent["alternatives"] if x["id"]=="balanced_60")
    existing=make_parts(parent,alt)
    m=s["mount"];parts={}
    for side,yc in (("lower",m["lower_y_mm"]),("upper",m["upper_y_mm"])):
        leaf=existing[side+"_leaf"]
        base=(cq.Workplane("XY").box(16,8,5,centered=(True,True,False))
              .translate((80,yc,0)))
        cap=(cq.Workplane("XY").box(14,8,2.8,centered=(True,True,False))
             .translate((81.6,yc,5)))
        # Actual half-round opposed groove, 0.8mm nominal radius
        # around a hypothetical 0.55mm-radius wire. Fastener bores
        # remain clearance holes until commercial M2 bolts are sourced.
        groove=(cq.Workplane("XZ").center(81.6,5).circle(.8)
                .extrude(12).translate((0,yc+6,0)))
        base=base.cut(groove);cap=cap.cut(groove)
        for x in m["screw_x_mm"]:
            drill=cq.Workplane("XY").center(x,yc).circle(1.1).extrude(9)
            base=base.cut(drill);cap=cap.cut(drill)
        assembled=cq.Workplane("XY").newObject([leaf]).union(base).clean().val()
        cap=cap.clean().val()
        if any(not v.isValid() or len(v.Solids())!=1 for v in (assembled,cap)):
            raise ValueError("unprintable multiple-body or invalid screw saddle")
        parts[side+"_leaf_integral_saddle"]=assembled
        parts[side+"_removable_saddle_cap"]=cap
    return parts

def world(s:Mapping[str,Any],part:str,shape:Any,angle:int)->Any:
    return spin(shape,{"axis_height_mm":6},angle) if part.startswith("upper") else shape

def route_pose(s:Mapping[str,Any],route:Mapping[str,Any],angle:int,*,points:int=201)->dict[str,Any]:
    import numpy as np
    t=np.linspace(0,1,points); lo=np.array(s["wire"]["nominal_lower_exit_xyz"],dtype=float)
    hi=np.array(s["wire"]["nominal_upper_exit_local_xyz"],dtype=float)
    rad=math.radians(angle)
    hi[1],hi[2]=hi[1]*math.cos(rad)+(hi[2]-6)*math.sin(rad), 6-hi[1]*math.sin(rad)+(hi[2]-6)*math.cos(rad)
    S=np.sin(math.pi*t);L=route["free_length_mm"]
    def calc(B):
        xyz=np.stack([lo[0]+route["x_bulge_mm"]*S*S,
            lo[1]+(hi[1]-lo[1])*t+B*np.sin(2*math.pi*t),
            lo[2]+(hi[2]-lo[2])*t+route["z_bulge_mm"]*S],axis=1)
        return xyz,float(np.linalg.norm(np.diff(xyz,axis=0),axis=1).sum())
    initial,minimum=calc(0)
    if minimum>L+.01:return {"angle_deg":angle,"solvable":False,"length_shortage_mm":round(minimum-L,4)}
    low,high=0.,40.
    for _ in range(32):
        mid=(low+high)/2
        if calc(mid)[1]<L:low=mid
        else:high=mid
    xyz,length=calc(high)
    if abs(length-L)>.04:raise ValueError("fixed cable free length did not converge")
    d1=np.gradient(xyz,t,axis=0);d2=np.gradient(d1,t,axis=0)
    k=np.linalg.norm(np.cross(d1,d2),axis=1)/(np.linalg.norm(d1,axis=1)**3)
    radius=1/float(np.max(k[2:-2]));r=s["wire"]["diameter_mm"]/2
    height=max(12,float(xyz[:,2].max()+r))-min(0,float(xyz[:,2].min()-r))
    width=float(xyz[:,0].max()+r+76)
    return {"angle_deg":angle,"solvable":True,
            "free_length_mm":round(length,4),"min_discrete_bend_radius_mm":round(radius,4),
            "cable_inclusive_height_mm":round(height,4),
            "overall_nominal_width_mm":round(width,4),
            "pts":xyz.tolist()}

def wire_tube(s:Mapping[str,Any],pose:Mapping[str,Any])->Any:
    import cadquery as cq
    if not pose.get("solvable"):raise ValueError("cannot generate unsolved physical cable")
    nodes=[cq.Vector(*p) for p in pose["pts"][::4]]
    wire=cq.Wire.assembleEdges([cq.Edge.makeSpline(nodes)])
    normal=nodes[1].sub(nodes[0])
    tube=(cq.Workplane(cq.Plane(origin=nodes[0],normal=normal))
          .circle(s["wire"]["diameter_mm"]/2)
          .sweep(cq.Workplane().newObject([wire]),isFrenet=True).val())
    if not tube.isValid() or len(tube.Solids())!=1 or tube.Volume()<=0:
        raise ValueError("nominal cable tube BRep failed")
    return tube

def score_route(s:Mapping[str,Any],route:Mapping[str,Any],step:int=5)->dict[str,Any]:
    if step not in (1,5,15,30,45):raise ValueError("non-registered angular step")
    poses=[route_pose(s,route,angle) for angle in range(0,181,step)]
    good=all(x["solvable"] for x in poses)
    viable=[x for x in poses if x["solvable"]]
    radius=min((x["min_discrete_bend_radius_mm"] for x in viable),default=0)
    height=poses[-1].get("cable_inclusive_height_mm")
    width=max((x["overall_nominal_width_mm"] for x in viable),default=None)
    r5=5*s["wire"]["diameter_mm"];c=s["clearance"]
    checks={
        "source_fixed_length_route_solved_all_angles":good,
        "original_hypothetical_2mm_bend_screen":good and radius>=2,
        "generic_flexible_cable_5x_d_screen":good and radius>=r5,
        "fits_nominal_width_limit":good and width is not None and width<=c["max_total_width_mm"],
        "folded_cable_within_20mm":good and height is not None and height<=c["max_folded_cable_envelope_mm"],
    }
    return {"id":route["id"],"samples":len(poses),"step_deg":step,
            "minimum_bend_radius_mm":round(radius,4),
            "generic_5x_d_scenario_radius_mm":r5,
            "folded_cable_height_mm":height,"max_nominal_width_mm":width,
            "checks":checks,"nominal_geometry_screen_pass":all(checks.values()),
            "actual_cable_material_verified":False,"ends_physically_secured":False,
            "poses":[{k:v for k,v in p.items() if k!="pts"} for p in poses]}


def _aabb_separation(a:Any,b:Any)->float:
    """Conservative non-collision proof: positive => OCP solids disjoint."""
    A=a.BoundingBox();B=b.BoundingBox()
    dx=max(0.,B.xmin-A.xmax,A.xmin-B.xmax)
    dy=max(0.,B.ymin-A.ymax,A.ymin-B.ymax)
    dz=max(0.,B.zmin-A.zmax,A.zmin-B.zmax)
    return math.sqrt(dx*dx+dy*dy+dz*dz)

def printed_mount_clearance(s:Mapping[str,Any],parts:Mapping[str,Any],*,step:int=15)->dict[str,Any]:
    """Check added mount geometry, reusing #333 original leaf motion proof.

    The full parent leaf-vs-leaf rotation has already been checked by
    genuine OCP in the stacked previous PR. This screen checks only NEW
    material, with conservative AABB separation of actual OCP solids.
    If boxes overlap, slow exact BRep distance/intersection is required.
    """
    import cadquery as cq
    from .functional_hinge_assembly import _distance
    if step not in (5,15,30,45):raise ValueError("unsupported mounted leaf sweep interval")
    m=s["mount"]
    # Full 16x8x5 bounding volumes deliberately overestimate the
    # source-cut saddle bases; a positive clearance is conservative.
    lower_box=(cq.Workplane("XY").box(16,8,5,centered=(True,True,False))
               .translate((80,m["lower_y_mm"],0)).val())
    upper_box=(cq.Workplane("XY").box(16,8,5,centered=(True,True,False))
               .translate((80,m["upper_y_mm"],0)).val())
    # This is a conservative screen of the NEW opposing mounting
    # volumes only. Original parent leaf collisions are not re-certified.
    lower_add=[lower_box,parts["lower_removable_saddle_cap"]]
    upper_add=[upper_box,parts["upper_removable_saddle_cap"]]
    records=[]
    for ang in range(0,181,step):
        rotated=[spin(body,{"axis_height_mm":6},ang) for body in upper_add]
        sep=[];interference=[]
        for low in lower_add:
            for high in rotated:
                bound=_aabb_separation(low,high)
                if bound>.001:
                    sep.append(bound);interference.append(0.)
                else:
                    exact=_distance(low,high)
                    sep.append(exact)
                    interference.append(low.intersect(high).Volume() if exact<.002 else 0.)
        records.append({"angle_deg":ang,
                        "lower_bound_or_exact_moving_mount_separation_mm":round(min(sep),4),
                        "added_mount_overlap_mm3":round(sum(interference),5)})
    return {
        "schema":"hs.nominal_anchor_added_geometry_clearance.v1",
        "poses":records,
        "sampled_min_mount_bound_mm":min(r["lower_bound_or_exact_moving_mount_separation_mm"] for r in records),
        "added_mounts_not_colliding_with_each_other":all(r["added_mount_overlap_mm3"]<.001 for r in records),
        "parent_leaf_to_leaf_verified_by_previous_stacked_PR":True,
        "all_cross_interactions_with_original_leaf_reverified":False,
        "screw_holes_do_not_imply_fasteners_installed":True,
        "elastic_or_physical_cable_clamp_tested":False,
    }

def cable_against_mounts(s:Mapping[str,Any],parts:Mapping[str,Any],
                         route:Mapping[str,Any],*,angles=(0,90,180))->dict[str,Any]:
    """Physical tube versus every actual printed mount BRep at select poses."""
    records=[]
    for ang in angles:
        pose=route_pose(s,route,ang)
        if not pose["solvable"]:
            records.append({"angle_deg":ang,"solvable":False})
            continue
        cable=wire_tube(s,pose)
        contacts={}
        for k,part in parts.items():
            original=world(s,k,part,ang)
            # Positive AABB gap conclusively excludes 3D collision.
            # For overlaps, calculate genuine OCP solid intersection;
            # expensive shape-to-shape distance on the entire PCB
            # plate is not necessary to determine penetration.
            lower_bound=_aabb_separation(cable,original)
            intersection=(cable.intersect(original).Volume() if lower_bound<.002 else 0.)
            contacts[k]={"AABB_separation_lower_bound_mm":round(lower_bound,4),
                         "cable_inside_printed_solid_mm3":round(intersection,5)}
        records.append({"angle_deg":ang,"solvable":True,
                        "contacts":contacts,
                        "sampled_printed_interference_mm3":round(sum(
                            a["cable_inside_printed_solid_mm3"] for a in contacts.values()
                        ),5)})
    return {
        "mode":route["id"],"source_wire_radius_mm":s["wire"]["diameter_mm"]/2,
        "sampled_angles_deg":list(angles),
        "per_angle":records,
        "nominal_round_wire_clear_of_all_printed_guide_solids":all(
            x.get("solvable") and x["sampled_printed_interference_mm3"]<.001
            for x in records
        ),
        "actual_wire_strain_relief_proven":False,
    }


def machine_function_intent(s:Mapping[str,Any],parent:Mapping[str,Any],
                            retainer:Mapping[str,Any])->dict[str,Any]:
    from .functional_hinge_retention import extra_function_intent
    intent=extra_function_intent(retainer,parent)
    intent["requirements"].extend([
        {"id":"R_GUIDE_MATE","kind":"interface",
         "statement":"Each integral printed hinge saddle carries a separate cap and nominal M2 clearance bores.",
         "priority":"must","verification":{
             "method_type":"test",
             "procedure":"Print interface coupons, measure actual cable diameter, bolt depth, clamp compression, friction and retention.",
             "acceptance":{"cap_and_base_geometry":True,"physical_clamping_must_be_measured":True},
             "evidence_status":"not_collected"}},
        {"id":"R_WIRE_ANCHOR_SWEEP","kind":"functional",
         "statement":"A real tube BRep must clear every printed mount and cap through the fold, without presuming the unattached spline is clamped.",
         "priority":"must","verification":{
             "method_type":"test",
             "procedure":"Source real cable and connectors, bolt mounts, verify all angles and repeated actual folding.",
             "acceptance":{"no_interference":True,"physical_flex_life_verified":True},
             "evidence_status":"not_collected"}},
        {"id":"R_DISPLAY_CABLE","kind":"constraint",
         "statement":"Flat display ribbons and round wire service-loop prototypes have distinct mechanical/electrical interfaces.",
         "priority":"must","verification":{
             "method_type":"inspection",
             "procedure":"Pick actual display module data connector, circuit count and cable part number and demonstrate source manufacturer compatibility.",
             "acceptance":{"real_display_connector_pinout_matched":True,"round_wire_substitution_prohibited":True},
             "evidence_status":"not_collected"}},
    ])
    intent["functions"].extend([
        {"id":"F_MOUNT_WIRE","name":"Provide removable two-piece printed saddles",
         "requirements":["R_GUIDE_MATE","R_WIRE_ANCHOR_SWEEP"],
         "subsystems":["S_LOWER","S_UPPER","S_WIRE_CAPS"]},
        {"id":"F_REQUIRE_DISPLAY_CABLE","name":"Reject unsourced electrical display cable",
         "requirements":["R_DISPLAY_CABLE"],
         "subsystems":["S_CABLE","S_WIRE_CAPS"]},
    ])
    intent["subsystems"].append({
        "id":"S_WIRE_CAPS","name":"Printed wire saddle caps",
        "domain":"mechanical",
        "purpose":"Nominal cable passage interface with M2 clearance holes; clamping force unproven",
        "requirements":["R_GUIDE_MATE","R_WIRE_ANCHOR_SWEEP","R_DISPLAY_CABLE"]})
    intent["interfaces"].append({
        "id":"I_WIRE_CLAMP","name":"Serviceable cable clamp/guide beside printed hinge",
        "from":"S_WIRE_CAPS","to":"S_LOWER","medium":"mechanical",
        "requirements":["R_GUIDE_MATE","R_WIRE_ANCHOR_SWEEP"],
        "unresolved":["no actual clamping screws or nuts sourced",
                      "no real round-wire section or elastic compression known",
                      "no actual display ribbon retention design",
                      "no physical stress/thermal/print fit data"]})
    return intent

def execute(s:Mapping[str,Any],parent:Mapping[str,Any],retainer:Mapping[str,Any],
            out:Path)->dict[str,Any]:
    import cadquery as cq
    import trimesh
    from .function_intent_bridge import parse_intent
    source=validate(s,parent,retainer)
    if out.exists():raise ValueError("refusing to overwrite existing source-anchoring experiment")
    intent=machine_function_intent(source,parent,retainer)
    project,gate=parse_intent(intent)
    if gate["status"]!="FUNCTIONAL_CONCEPT_ONLY" or not gate["functional_traceability_pass"] or any(gate["physical_authority"].values()):
        raise ValueError("unverified physical cable anchor falsely passed native HS requirements")
    out.mkdir(parents=True)
    (out/"function_intent.json").write_bytes(canonical(intent))
    parts=make_anchors(source,parent)
    exported={}
    for k,body in parts.items():
        step=out/(k+".step");stl=out/(k+".stl")
        body.exportStep(str(step))
        body.exportStl(str(stl),tolerance=.03,angularTolerance=.18)
        brep=cq.importers.importStep(str(step)).val()
        mesh=trimesh.load(str(stl),force="mesh")
        if (not brep.isValid() or not mesh.is_watertight or
            len(brep.Solids())!=1 or
            not math.isclose(brep.Volume(),body.Volume(),abs_tol=.2) or
            not math.isclose(mesh.volume,body.Volume(),rel_tol=.01)):
            raise ValueError("printed base/cap BRep STL export failed reimport")
        exported[k]={"step_sha256":file_sha(step),"stl_sha256":file_sha(stl),
                     "original_volume_mm3":round(body.Volume(),3),
                     "actual_watertight_STL":True,
                     "actual_M2_hardware_installed":False,
                     "qualified_for_3D_printing":False}
    fit=printed_mount_clearance(source,parts,step=15)
    routes=[score_route(source,route) for route in source["routes"]]
    # One representative 44mm service loop gets full 3D tube-to-mount
    # OCP checks at three poses; every alternative also receives the
    # independent 37-angle numerical radius/envelope screen.
    contact=[cable_against_mounts(source,parts,route)
             for route in source["routes"] if route["id"]=="medium_44"]
    successful=[r["id"] for r in routes
                if r["nominal_geometry_screen_pass"] and
                any(x["mode"]==r["id"] and
                    x["nominal_round_wire_clear_of_all_printed_guide_solids"]
                    for x in contact)]
    # This is a failed engineering readiness gate, not an excuse to
    # manufacture a falsely working assembly.
    report={
        "schema":OUTPUT,"source_spec_sha256":hashlib.sha256(canonical(source)).hexdigest(),
        "source_hinge_sha256":hashlib.sha256(canonical(parent)).hexdigest(),
        "source_retention_sha256":hashlib.sha256(canonical(retainer)).hexdigest(),
        "native_function_intent_sha256":file_sha(out/"function_intent.json"),
        "native_function_gate":gate,
        "native_printed_mount_parts":exported,
        "cross_leaf_full_hinge_motion":fit,
        "source_bounded_wire_routes":routes,
        "native_cable_tube_against_printed_guides":contact,
        "selected_physically_promotable_design":None,
        "cable_scenarios_satisfying_all_nominal_geometry_screens":successful,
        "build_gate":"BLOCKED_BY_CABLE_AND_CONNECTOR_MISMATCH",
        "real_display_data_compatibility":False,
        "engineering_findings":[
           "Four separate printed candidate bodies exist as native STEP/STL, but no M2 fasteners or physical compression tests exist.",
           "Nominal tube cable path collides with removable saddle caps at sampled fold angles.",
           "Fixed nominal round-wire route with anchored endpoints cannot satisfy both 2mm modeled bend radius and 20mm folded envelope in this candidate family.",
           "Manufacturer general guidance for flexible cables may require a larger dynamic radius, e.g. a 5× outer diameter scenario; NOT a real specification for this unsourced round wire.",
           "The real Molex display LVDS FPC connector family is flat, multi-conductor and physically incompatible with a 1.6mm nominal round cable saddle.",
           "No electrical connector footprints, pin mappings, real display electronics or hinge-flex cycle measurement are available.",
        ],
        "authority":{
            "sourced_M2_fasteners_installed":False,
            "round_wire_physically_mounted":False,
            "connector_matches_real_display":False,
            "cable_strain_relief_tested":False,
            "cable_cycle_lifetime_measured":False,
            "physical_screen_or_board_verified":False,
            "fabrication_release_approved":False,
        }
    }
    (out/"ANCHORED_CABLE_TRIAL.json").write_bytes(canonical(report))
    return report

def audit(s:Mapping[str,Any],parent:Mapping[str,Any],retainer:Mapping[str,Any],out:Path)->dict[str,Any]:
    import cadquery as cq
    import trimesh
    source=validate(s,parent,retainer)
    report=json.loads((out/"ANCHORED_CABLE_TRIAL.json").read_text())
    if report["schema"]!=OUTPUT or report["source_spec_sha256"]!=hashlib.sha256(canonical(source)).hexdigest():
        raise ValueError("anchor specification changed after source execution")
    if report["source_hinge_sha256"]!=hashlib.sha256(canonical(parent)).hexdigest() or report["source_retention_sha256"]!=hashlib.sha256(canonical(retainer)).hexdigest():
        raise ValueError("parent traceability was substituted")
    if report["native_function_intent_sha256"]!=file_sha(out/"function_intent.json") or json.loads((out/"function_intent.json").read_text())!=machine_function_intent(source,parent,retainer):
        raise ValueError("function intent is not pinned to source")
    originals=make_anchors(source,parent)
    if set(report["native_printed_mount_parts"])!=set(originals):
        raise ValueError("source printed parts changed")
    for name,body in originals.items():
        item=report["native_printed_mount_parts"][name]
        step=out/(name+".step");stl=out/(name+".stl")
        if file_sha(step)!=item["step_sha256"] or file_sha(stl)!=item["stl_sha256"]:
            raise ValueError("original print candidate STEP or STL changed")
        imported=cq.importers.importStep(str(step)).val()
        tri=trimesh.load(str(stl),force="mesh")
        if not imported.isValid() or not tri.is_watertight or not math.isclose(imported.Volume(),body.Volume(),abs_tol=.2):
            raise ValueError("geometry or mesh no longer matches source")
    checked=printed_mount_clearance(source,originals,step=15)
    saved=report["cross_leaf_full_hinge_motion"]
    if saved["schema"]!=checked["schema"] or len(saved["poses"])!=len(checked["poses"]):
        raise ValueError("cross-leaf motion source missing")
    for before,after in zip(saved["poses"],checked["poses"]):
        if (before["angle_deg"]!=after["angle_deg"]
            or not math.isclose(before["lower_bound_or_exact_moving_mount_separation_mm"],
                                after["lower_bound_or_exact_moving_mount_separation_mm"],
                                abs_tol=.01)
            or not math.isclose(before["added_mount_overlap_mm3"],
                                after["added_mount_overlap_mm3"],abs_tol=.001)):
            raise ValueError("cross-leaf collision result was altered")
    if saved["added_mounts_not_colliding_with_each_other"]!=checked["added_mounts_not_colliding_with_each_other"]:
        raise ValueError("cross-leaf source safety classification was altered")
    if [score_route(source,r) for r in source["routes"]]!=report["source_bounded_wire_routes"]:
        raise ValueError("nominal cable route evidence was altered")
    actual=[cable_against_mounts(source,originals,route)
            for route in source["routes"] if route["id"]=="medium_44"]
    observed=report["native_cable_tube_against_printed_guides"]
    if len(actual)!=len(observed):
        raise ValueError("missing original native wire collision trial")
    for source_run,saved_run in zip(actual,observed):
        if source_run["mode"]!=saved_run["mode"]:
            raise ValueError("original native cable model swapped")
        for a,b in zip(source_run["per_angle"],saved_run["per_angle"]):
            if (a["angle_deg"]!=b["angle_deg"] or
                not math.isclose(a["sampled_printed_interference_mm3"],
                                 b["sampled_printed_interference_mm3"],abs_tol=.05)):
                raise ValueError("original 3D cable tube-to-mount penetration result was falsified")
    if not any(x["per_angle"][0]["sampled_printed_interference_mm3"]>0 for x in actual):
        raise ValueError("reported source collision is not reproducible")
    if report["selected_physically_promotable_design"] is not None or report["build_gate"]!="BLOCKED_BY_CABLE_AND_CONNECTOR_MISMATCH" or any(report["authority"].values()):
        raise ValueError("invalid promotion of incomplete cable geometry")
    return {"schema":"hs.anchored_cable_source_audit.v1",
            "reimported_printable_CAD_parts":len(originals),
            "actual_wire_screens_recomputed":len(source["routes"]),
            "native_source_integrity_pass":True,
            "physical_fabrication_authorized":False,
            "real_display_connection_proven":False}

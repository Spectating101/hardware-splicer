#!/usr/bin/env python3
"""Full recorded SORTCELL source wrist BVH-vs-convex and solid-mesh audit.

Compare original manufacturer v1.0 DAE/STL triangle surfaces with their
DIAGNOSTIC convex hulls at every one of the 278 actual source joint-state
observations and within-phase interpolated half-step configurations. Independent
native-source FK, never hand-animated or source mesh modified. Audit
topological watertightness both raw and on *derived welded copies* to make
surface-only versus closed-solid limitations inspectable. No physical release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.audit_sortcell_wrist_dae_stl_surfaces_001 import (
    EXPECTED_URDF_SHA,PACKAGE,get_original_trimesh,source_geometry,sha,vectors,insist
)
from scripts.probe_sortcell_original_wrist_triangle_contacts_001 import (
    fk_for_link,geom_pose_from_urdf
)

SCHEMA="hardware_splicer.sortcell_source_wrist_fullpath_solid_audit.v1"
EXPECTED_STEPS=278

def mesh_topology(mesh):
    import numpy as np
    m=mesh.copy()
    raw={"vertices":int(len(m.vertices)),"faces":int(len(m.faces)),
         "watertight":bool(m.is_watertight),
         "winding_consistent":bool(m.is_winding_consistent),
         "volume_reliable":bool(m.is_watertight and m.is_winding_consistent)}
    # STL and many DAE exporters repeat triangle vertices. A derived welded
    # mesh lets us ask whether the *geometry* can form a closed solid without
    # treating the original raw importer seams as physical holes. No source
    # file is rewritten and FCL collision still uses the untouched surfaces.
    m.merge_vertices(digits_vertex=6)
    edge_incidence=np.bincount(m.edges_unique_inverse,minlength=len(m.edges_unique))
    welded={"vertices":int(len(m.vertices)), "faces":int(len(m.faces)),
            "watertight":bool(m.is_watertight),
            "winding_consistent":bool(m.is_winding_consistent),
            "boundary_edges_one_triangle":int(np.count_nonzero(edge_incidence==1)),
            "non_manifold_edges_over_two_triangles":int(np.count_nonzero(edge_incidence>2)),
            "connected_surface_components":int(m.body_count)}
    welded["closed_solid_containment_testing_eligible"]=bool(
        welded["watertight"] and welded["winding_consistent"] and
        welded["boundary_edges_one_triangle"]==0 and
        welded["non_manifold_edges_over_two_triangles"]==0)
    return {"original_import_topology":raw,"diagnostic_welded_copy_topology":welded,
            "original_manufacturer_geometry_modified":False}

def prepare_original_meshes(root,study):
    import trimesh
    manifest={v["uri"]:v for v in study["source_wrist_assets"]}
    root_dir=Path(study["_source_study_path"]).parent/"manufacturer-source"
    meshes={}
    urdf={}
    for side in ("left","right"):
        for idx in (5,7):
            name=f"openarm_{side}_link{idx}"
            link=root.find("./link[@name='"+name+"']")
            insist(link is not None,"original wrist source link absent: "+name)
            urdf[name]={}
            for kind in ("visual","collision"):
                uri,scale,offset=geom_pose_from_urdf(link,kind)
                insist(uri.startswith(PACKAGE) and uri in manifest,
                       "unverified manufacturer wrist DAE/STL "+name)
                disk=root_dir/uri[len(PACKAGE):]
                blob=disk.read_bytes()
                insist(sha(blob)==manifest[uri]["sha256"],
                       "manufacturer source mesh changed during full-path analysis")
                key=(uri,tuple(scale))
                if key not in meshes:
                    native,_=get_original_trimesh(disk)
                    original_scaled=source_geometry(native,scale)
                    hull=original_scaled.convex_hull
                    meshes[key]={"original":original_scaled,
                                 "derived_hull":hull,
                                 "topology":mesh_topology(original_scaled),
                                 "original_uri":uri,
                                 "original_sha256":sha(blob)}
                urdf[name][kind]={"key":key,"offset":offset}
    return meshes,urdf

def build_fcl_pairs(meshes,link_refs):
    import trimesh
    arms={}
    for side in ("left","right"):
        arms[side]={}
        for kind in ("visual","collision"):
            for geom in ("original","derived_hull"):
                a=link_refs[f"openarm_{side}_link5"][kind]["key"]
                b=link_refs[f"openarm_{side}_link7"][kind]["key"]
                manager=trimesh.collision.CollisionManager()
                manager.add_object("source_link5",meshes[a][geom])
                manager.add_object("source_link7",meshes[b][geom])
                arms[side][kind+"_"+geom]=manager
    return arms

def run(urdf_path:Path,study_path:Path,cycle_path:Path,output:Path)->dict:
    import numpy as np
    source=urdf_path.read_bytes()
    source_hash=sha(source)
    insist(source_hash==EXPECTED_URDF_SHA,"original manufacturer URDF version changed")
    root=ET.fromstring(source)
    study=json.loads(study_path.read_text())
    study["_source_study_path"]=str(study_path)
    cycle=json.loads(cycle_path.read_text())
    insist(study["manufacturer_original_urdf_sha256"]==source_hash,
           "original manufacturer DAE/STL study different from full cycle URDF")
    insist(cycle["original_urdf_sha256"]==source_hash,"original SORTCELL robot source changed")
    c=cycle["cycle"]
    insist(c["numerical_full_cycle_test_passed"] is True and
           c["pybullet_source_mimic_constraint_installed"] is True and
           c["physical_sorter_authorized"] is False,"unqualified source gravity sort used")
    real_samples=c["contact_observations"]
    insist(len(real_samples)==EXPECTED_STEPS,"original verified 278 samples changed")
    mesh_cache,link_refs=prepare_original_meshes(root,study)
    managers=build_fcl_pairs(mesh_cache,link_refs)
    rows=[]
    for index,row in enumerate(real_samples):
        actual=row["source_robot_joint_positions"]
        insist(len(actual)==18,"missing original manufacturer source joint telemetry")
        if index:
            previous=real_samples[index-1]["source_robot_joint_positions"]
            # Interpolated mids are SOURCE-FK-only; not new motor simulation.
            # Do not connect across motor phase transitions with unsupported
            # linear interpolation (phase boundary is independently sampled).
            if row["phase"]==real_samples[index-1]["phase"]:
                interpolated={name:(actual[name]+previous[name])/2 for name in actual}
                rows.append(("interpolated_half_step",row["phase"],index-.5,interpolated))
        rows.append(("actual_motor_sample",row["phase"],index,actual))
    insist(len(rows)>=500,"source path audit insufficiently dense")
    phases={}
    diag=[]
    values={"visual_original":0,"collision_original":0,
            "visual_derived_hull":0,"collision_derived_hull":0}
    for provenance,phase,source_step,q in rows:
        phase_counter=phases.setdefault(phase,{"evaluated_source_fk_poses":0,
                                                "original_visual_triangle_contacts":0,
                                                "original_collision_triangle_contacts":0,
                                                "derived_visual_convex_contacts":0,
                                                "derived_collision_convex_contacts":0})
        phase_counter["evaluated_source_fk_poses"]+=1
        row_out={"source_frame_index":source_step,
                 "phase":phase,"pose_kind":provenance,"arms":{}}
        for arm in ("left","right"):
            transforms={}
            for idx in (5,7):
                name=f"openarm_{arm}_link{idx}"
                transforms[name]=fk_for_link(root,q,name)
            hits={}
            for kind in ("visual","collision"):
                for geo in ("original","derived_hull"):
                    manager=managers[arm][kind+"_"+geo]
                    for idx in (5,7):
                        name=f"openarm_{arm}_link{idx}"
                        offset=link_refs[name][kind]["offset"]
                        manager.set_transform("source_link"+str(idx),transforms[name]@offset)
                    contact=bool(manager.in_collision_internal())
                    hits[kind+"_"+geo]=contact
                    if contact:
                        values[kind+"_"+geo]+=1
                        if kind=="visual":
                            phase_counter["original_visual_triangle_contacts" if geo=="original"
                                          else "derived_visual_convex_contacts"]+=1
                        else:
                            phase_counter["original_collision_triangle_contacts" if geo=="original"
                                          else "derived_collision_convex_contacts"]+=1
            row_out["arms"][arm]=hits
        diag.append(row_out)
    provenance={"native_motor_samples":sum(x["pose_kind"]=="actual_motor_sample" for x in diag),
                "interpolated_fk_halfsteps":sum(x["pose_kind"]=="interpolated_half_step" for x in diag)}
    # Trace results do not authorize direct motor commands or continuous motion.
    original_topology={}
    for key,entry in mesh_cache.items():
        token=entry["original_uri"]+"#"+",".join(str(v) for v in key[1])
        original_topology[token]={"sha256":entry["original_sha256"],
                                  "topology":entry["topology"]}
    summary={"source_joints_in_every_original_motor_observation":18,
             **provenance,
             "wrist_arm_pose_checks":len(diag)*2,
             "original_visual_BVH_contact_checks":values["visual_original"],
             "original_collision_STL_BVH_contact_checks":values["collision_original"],
             "derived_visual_convex_contact_checks":values["visual_derived_hull"],
             "derived_collision_STL_convex_contact_checks":values["collision_derived_hull"],
             "original_collision_meshes_modified":False,
             "original_manufacturer_visual_DAE_meshes_modified":False,
             "sampled_FK_halfsteps_are_not_real_motor_simulation":True,
             "physical_collision_clearance_certified":False,
             "model_surface_containment_checked_for_all_poses":False,
             "manufacturer_hardware_and_mount_verified":False,
             "robot_motion_authorized":False}
    report={"schema_version":SCHEMA,
            "original_manufacturer_urdf_sha256":source_hash,
            "source_triangle_and_hull_mesh_topology":original_topology,
            "phase_diagnostics":phases,
            "pose_diagnostics":diag,
            "summary":summary}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,separators=(",",":"))+"\n")
    print(json.dumps({"source_urdf_sha256":source_hash,
                      "source_asset_pairs":len(mesh_cache),
                      "summary":summary,
                      "watertight_derived_copy_count":sum(
                          x["topology"]["diagnostic_welded_copy_topology"]["watertight"]
                          for x in original_topology.values())},indent=2))
    return report

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ("urdf","study","cycle","output"):
        ap.add_argument("--"+key,required=True,type=Path)
    a=ap.parse_args()
    run(a.urdf,a.study,a.cycle,a.output)

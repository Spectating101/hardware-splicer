#!/usr/bin/env python3
"""Independent full task wrist geometry test acceptance, physical safety blocked."""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from scripts.audit_sortcell_wrist_dae_stl_surfaces_001 import EXPECTED_URDF_SHA

def require(condition,reason):
    if not condition:raise ValueError("source wrist full-cycle geometry acceptance: "+reason)

def verify(urdf:Path,cycle:Path,surfaces:Path,report:Path)->dict:
    digest=hashlib.sha256(urdf.read_bytes()).hexdigest()
    require(digest==EXPECTED_URDF_SHA,"manufacturer URDF not pinned")
    c=json.loads(cycle.read_text());s=json.loads(surfaces.read_text())
    r=json.loads(report.read_text())
    require(c["original_urdf_sha256"]==s["manufacturer_original_urdf_sha256"]==
            r["original_manufacturer_urdf_sha256"]==digest,"source evidence differs")
    src_rows=c["cycle"]["contact_observations"]
    actual=[x for x in r["pose_diagnostics"] if x["pose_kind"]=="actual_motor_sample"]
    half=[x for x in r["pose_diagnostics"] if x["pose_kind"]=="interpolated_half_step"]
    require(len(actual)==len(src_rows)==278 and len(half)>=240,
            "not full 278 source-motor frames + between-frame source-FK sweep")
    require(all(a["phase"]==src_rows[i]["phase"] and
                a["source_frame_index"]==i for i,a in enumerate(actual)),
            "source original motor frame order/phase changed")
    pairs=Counter()
    frame_counts=Counter()
    for row in r["pose_diagnostics"]:
        frame_counts[row["phase"]]+=1
        require(set(row["arms"])=={"left","right"},"missing source wrist arm")
        for arm,entries in row["arms"].items():
            require(set(entries)=={"visual_original","visual_derived_hull",
                                   "collision_original","collision_derived_hull"},
                    "original source/diagnostic mesh pair missing")
            require(all(isinstance(value,bool) for value in entries.values()),
                    "missing measured FCL contact result")
            for typ,value in entries.items():
                pairs[typ]+=value
    summary=r["summary"]
    require(summary["native_motor_samples"]==278 and
            summary["interpolated_fk_halfsteps"]==len(half) and
            summary["wrist_arm_pose_checks"]==2*len(r["pose_diagnostics"]),
            "full task source-frame accounting is inconsistent")
    for typ,k in (("visual_original","original_visual_BVH_contact_checks"),
                  ("collision_original","original_collision_STL_BVH_contact_checks"),
                  ("visual_derived_hull","derived_visual_convex_contact_checks"),
                  ("collision_derived_hull","derived_collision_STL_convex_contact_checks")):
        require(pairs[typ]==summary[k],"actual contact event not faithfully counted "+typ)
    require(set(r["phase_diagnostics"])=={row["phase"] for row in src_rows},
            "source original phases missing")
    for phase,metrics in r["phase_diagnostics"].items():
        require(metrics["evaluated_source_fk_poses"]==frame_counts[phase],
                "source phase frame accounting mismatch "+phase)
    manifest={x["uri"]:x["sha256"] for x in s["source_wrist_assets"]}
    topology=r["source_triangle_and_hull_mesh_topology"]
    require(len(topology)>=6,"original source mesh topology not audited")
    for key,obj in topology.items():
        uri=key.split("#",1)[0]
        require(uri in manifest and obj["sha256"]==manifest[uri],
                "source asset checksum from original surface study not preserved")
        shape=obj["topology"]
        require(shape["original_manufacturer_geometry_modified"] is False,
                "source manufacturer geometry mutated")
        raw=shape["original_import_topology"]
        copy=shape["diagnostic_welded_copy_topology"]
        require(raw["faces"]>15 and copy["faces"]==raw["faces"],
                "derived topology mesh faces invalid")
        require(copy["boundary_edges_one_triangle"]>=0 and
                copy["non_manifold_edges_over_two_triangles"]>=0,
                "source topological edge accounting missing")
        if copy["closed_solid_containment_testing_eligible"]:
            require(copy["watertight"] and copy["winding_consistent"] and
                    copy["boundary_edges_one_triangle"]==0 and
                    copy["non_manifold_edges_over_two_triangles"]==0,
                    "source mesh incorrectly qualified as closed solid")
    for key in ("physical_collision_clearance_certified",
                "model_surface_containment_checked_for_all_poses",
                "manufacturer_hardware_and_mount_verified",
                "robot_motion_authorized"):
        require(summary[key] is False,"physical/model authority incorrectly granted")
    for key in ("sampled_FK_halfsteps_are_not_real_motor_simulation",
                "original_collision_meshes_modified",
                "original_manufacturer_visual_DAE_meshes_modified"):
        require(summary[key] is (key=="sampled_FK_halfsteps_are_not_real_motor_simulation"),
                "source geometry/motor type disclosure incorrect")
    return {"schema_version":"hardware_splicer.sortcell_source_wrist_fullpath_groundtruth_acceptance.v1",
            "official_source_urdf_sha256":digest,
            "complete_original_source_motor_frames_verified":278,
            "additional_interpolated_source_fk_samples":len(half),
            "full_source_phase_inventory":list(r["phase_diagnostics"]),
            "source_wrist_arm_frame_pairs_verified":2*len(r["pose_diagnostics"]),
            "measured_original_triangle_contacts":pairs["visual_original"]+pairs["collision_original"],
            "measured_diagnostic_derived_hull_contacts":pairs["visual_derived_hull"]+pairs["collision_derived_hull"],
            "source_geometry_preserved_and_shas_verified":True,
            "closed_solid_containment_certified":False,
            "continuous_robot_motion_clearance_certified":False,
            "hardware_robot_motion_authorized":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("urdf","cycle","surfaces","report","output"):
        p.add_argument("--"+name,required=True,type=Path)
    args=p.parse_args()
    evidence=verify(args.urdf,args.cycle,args.surfaces,args.report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(evidence,indent=2)+"\n")
    print(json.dumps(evidence,indent=2))

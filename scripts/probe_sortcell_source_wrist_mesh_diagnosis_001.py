#!/usr/bin/env python3
"""Investigate original OpenArm v1.0 link5/link7 wrist interpenetration.

Uses only pinned manufacturer's unchanged URDF and original collision STLs.
Samples bounded original wrist joint5/6/7 configurations; records contact
pairs/depth and all limits, never exempts link pairs or changes source meshes.
This is a diagnostic of a sampled pose space, NOT full continuous collision
certification or source v1.0-v1.1 rigid registration.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.audit_sortcell_openarm_collision_timing_001 import source_meshes, fetch_source_meshes
from scripts.solve_sortcell_openarm_pybullet_001 import require, sha

SCHEMA="hardware_splicer.sortcell_openarm_original_wrist_mesh_diagnosis.v1"
OFFSETS_RAD=(-.7,-.35,0,.35,.7)
def run(urdf:Path,candidate:Path,output:Path)->dict:
    import pybullet as p
    original=urdf.read_bytes()
    receipt=json.loads(candidate.read_text())
    require(receipt["original_urdf_sha256"]==sha(original),"source URL / collision receipt disagree")
    require(receipt["cycle"]["numerical_full_cycle_test_passed"] is True,"unproven candidate task")
    require(receipt["cycle"]["physical_sorter_authorized"] is False,"unexpected hardware authority")
    output.mkdir(parents=True,exist_ok=True)
    require(not any(output.iterdir()),"output not empty")
    root=ET.fromstring(original)
    metadata={}
    for arm in ("left","right"):
        for number in (5,6,7):
            link=root.find(f"./link[@name='openarm_{arm}_link{number}']")
            joint=root.find(f"./joint[@name='openarm_{arm}_joint{number}']")
            require(link is not None and joint is not None,"missing original source wrist link/joint")
            coll=link.findall("collision")
            require(coll,"original source lacks wrist collision")
            metadata[f"{arm}_{number}"]={
                "source_joint_name":joint.get("name"),
                "source_joint_type":joint.get("type"),
                "source_joint_axis_xyz":joint.find("axis").get("xyz"),
                "source_joint_origin_xyz":joint.find("origin").get("xyz"),
                "source_joint_origin_rpy":joint.find("origin").get("rpy"),
                "source_joint_lower_rad":float(joint.find("limit").get("lower")),
                "source_joint_upper_rad":float(joint.find("limit").get("upper")),
                "source_collision_meshes":[
                    c.find(".//mesh").get("filename") for c in coll],
                "source_collision_origin_xyz":[
                    c.find("origin").get("xyz") for c in coll],
                "source_collision_mesh_scale_xyz":[
                    c.find(".//mesh").get("scale") for c in coll],
            }
    for link in root.findall("link"):
        for visual in link.findall("visual"):link.remove(visual)
    asset_root=(output/"openarm_description").resolve()
    manifest=source_meshes(root,asset_root)
    fetch_source_meshes(manifest,asset_root)
    local=output/"openarm_original_collision_meshes.urdf"
    local.write_bytes(ET.tostring(root,encoding="utf8",xml_declaration=True))
    c=p.connect(p.DIRECT)
    try:
        flags=p.URDF_MAINTAIN_LINK_ORDER|p.URDF_USE_SELF_COLLISION|p.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT
        body=p.loadURDF(str(local),useFixedBase=True,flags=flags,physicsClientId=c)
        joint_info={p.getJointInfo(body,j,physicsClientId=c)[1].decode():
                    (j,p.getJointInfo(body,j,physicsClientId=c))
                    for j in range(p.getNumJoints(body,physicsClientId=c))}
        link_ids={p.getJointInfo(body,j,physicsClientId=c)[12].decode():j
                  for j in range(p.getNumJoints(body,physicsClientId=c))}
        frames=receipt["cycle"]["contact_observations"]
        require(len(frames)>=200,"not enough original motor telemetry")
        q=frames[0]["source_robot_joint_positions"]
        require(len(q)==18,"source joint state inventory changed")
        require(set(q).issubset(joint_info),"unknown source joints")
        def install(values):
            for name,value in values.items():
                p.resetJointState(body,joint_info[name][0],value,physicsClientId=c)
            p.performCollisionDetection(physicsClientId=c)
        def contact_pair(link_a,link_b):
            a=link_ids[link_a];b=link_ids[link_b]
            contacts=[x for x in p.getContactPoints(bodyA=body,bodyB=body,physicsClientId=c)
                      if {x[3],x[4]}=={a,b} and x[8]<-1e-5]
            return min([float(x[8]) for x in contacts],default=0.0)
        install(q)
        initial={}
        out={}
        for arm in ("left","right"):
            names=[f"openarm_{arm}_joint{j}" for j in (5,6,7)]
            links=[f"openarm_{arm}_link5",f"openarm_{arm}_link7"]
            for n in names:require(n in q,"missing source wrist joint "+n)
            baseline=contact_pair(*links)
            initial[arm]=baseline
            limit=[(float(joint_info[n][1][8]),float(joint_info[n][1][9])) for n in names]
            center=[float(q[n]) for n in names]
            grids=[]
            for x,(lo,hi) in zip(center,limit):
                values={round(max(lo,min(hi,x+d)),7) for d in OFFSETS_RAD}
                grids.append(sorted(values))
            cases=[]
            for combo in itertools.product(*grids):
                values=dict(q)
                values.update(dict(zip(names,combo)))
                install(values)
                depth=contact_pair(*links)
                cases.append({"source_wrist_joint_positions_rad":[round(v,7) for v in combo],
                              "interpenetration_depth_m":round(min(0.,depth),7),
                              "penetrating":depth<-.00001})
            require(len(cases)>=50,"source wrist sweep too narrow")
            ordered=sorted(cases,key=lambda x:x["interpenetration_depth_m"],reverse=True)
            out[arm]={
                "source_link_pair":links,
                "baseline_source_interpenetration_m":round(baseline,7),
                "sampled_source_wrist_poses":len(cases),
                "original_source_joint_limits_rad":[list(t) for t in limit],
                "source_joint_center_rad":center,
                "poses_without_10um_interpenetration":sum(not x["penetrating"] for x in cases),
                "best_sampled_pose":ordered[0],
                "worst_sampled_pose":ordered[-1],
                "sampled_pose_matrix":cases,
                "source_geometry_modified":False,
                "physical_clearance_qualified":False,
            }
        require(all(arm in out for arm in ("left","right")),"incomplete wrist arms")
        report={
            "schema_version":SCHEMA,
            "source_urdf_sha256":sha(original),
            "source_collision_meshes_loaded":len(manifest),
            "manufacturer_collision_STL_manifest":manifest,
            "manufacturer_wrist_joint_and_mesh_metadata":metadata,
            "initial_source_link5_link7_overlap_m":initial,
            "gridded_wrist_diagnosis":out,
            "scope":{
                "original_source_v10_collision_meshes_and_origins_unchanged":True,
                "all_wrist_poses_within_published_source_limits":True,
                "source_link5_link7_collision_not_whitelisted":True,
                "only_grid_samples_checked":True,
                "source_visual_v11_registration_proven":False,
                "physical_robot_self_collision_clearance_certified":False,
                "physical_robot_control_authorized":False,
            },
        }
        (output/"OPENARM_ORIGINAL_WRIST_COLLISION_DIAGNOSIS.json").write_text(
            json.dumps(report,indent=2)+"\n")
        (output/"SCOPE.md").write_text(
            "# Manufacturer-source OpenArm v1.0 wrist overlap diagnostic\n\n"
            "All mesh origins, mesh scales, joint axes, limits and original STLs "
            "are reproduced from the pinned manufacturer URDF. Body self-contact "
            "is measured against each link5/link7 pair with no suppression. "
            "The two arm wrist joint5/6/7 grids are **sampled only**; any "
            "non-penetrating sampled wrist is a candidate for further continuous "
            "collision and full sorting task checks, not a physically safe pose. "
            "v1.1 independent GLB is not registered; hardware not authorized.\n")
        return report
    finally:p.disconnect(physicsClientId=c)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urdf",required=True,type=Path)
    ap.add_argument("--candidate",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    r=run(a.urdf,a.candidate,a.output)
    print(json.dumps({
       "source_meshes":r["source_collision_meshes_loaded"],
       "wrist_samples":{k:{"tested":v["sampled_source_wrist_poses"],
                           "nonpenetrating":v["poses_without_10um_interpenetration"],
                           "initial_depth_m":v["baseline_source_interpenetration_m"],
                           "best":v["best_sampled_pose"],
                           "worst":v["worst_sampled_pose"]}
                        for k,v in r["gridded_wrist_diagnosis"].items()},
       "physical_robot_control_authorized":False,
    },indent=2))

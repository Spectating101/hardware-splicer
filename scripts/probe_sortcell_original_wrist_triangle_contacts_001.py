#!/usr/bin/env python3
"""Source-relative OpenArm link5-vs-link7 DAE/STL *triangle* collision study.

NOT a hardware collision clearance certificate: FCL triangle BVH contact on
the open/possibly nonwatertight manufacturer meshes is a surface-triangle
intersection query, not complete solid containment. The URDF joint FK is
checked against the already independently recorded native PyBullet frames.
No source URDF, mesh, dynamics, controller, fixture, or viewer is modified.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.audit_sortcell_wrist_dae_stl_surfaces_001 import (
    EXPECTED_URDF_SHA,PACKAGE, get_original_trimesh, source_geometry, sha, vectors,
    insist,
)

SCHEMA="hardware_splicer.sortcell_original_manufacturer_wrist_triangle_contacts.v1"

def fk_for_link(root,source_q,link):
    import numpy as np
    from scipy.spatial.transform import Rotation as R
    parents={}
    for j in root.findall("joint"):
        parent=j.find("parent"); child=j.find("child")
        if parent is None or child is None:continue
        name=j.get("name")
        if child.get("link") in parents:raise ValueError("source URDF has duplicate joint child")
        parents[child.get("link")]=(parent.get("link"),j)
    memo={"world":np.eye(4,dtype=float)}
    def visit(node):
        if node in memo:return memo[node]
        insist(node in parents,"unknown original source link "+node)
        parent,j=parents[node]
        origin=j.find("origin")
        T=np.eye(4,dtype=float)
        if origin is not None:
            T[:3,3]=vectors(origin.get("xyz"))
            T[:3,:3]=R.from_euler("xyz",vectors(origin.get("rpy"))).as_matrix()
        kind=j.get("type")
        if kind in ("revolute","continuous","prismatic"):
            name=j.get("name")
            insist(name in source_q,"source joint state missing "+name)
            q=float(source_q[name])
            axis=j.find("axis")
            insist(axis is not None,"source axis absent "+name)
            axis_xyz=np.array(vectors(axis.get("xyz")),dtype=float)
            length=np.linalg.norm(axis_xyz)
            insist(length>0 and math.isfinite(length),"invalid source joint axis")
            axis_xyz=axis_xyz/length
            lim=j.find("limit")
            if lim is not None:
                lo,hi=float(lim.get("lower", "-inf")),float(lim.get("upper","inf"))
                insist(lo-.001<=q<=hi+.001,"source pose outside manufacturer joint bounds")
            M=np.eye(4,dtype=float)
            if kind=="prismatic":
                M[:3,3]=axis_xyz*q
            else:
                M[:3,:3]=R.from_rotvec(q*axis_xyz).as_matrix()
            T=T@M
        elif kind!="fixed":raise ValueError("unsupported source joint "+str(kind))
        memo[node]=visit(parent)@T
        return memo[node]
    return visit(link)

def geom_pose_from_urdf(link,kind):
    import numpy as np
    from scipy.spatial.transform import Rotation as R
    x=link.find(kind)
    insist(x is not None,"source wrist link absent "+kind)
    mesh=x.find("./geometry/mesh")
    insist(mesh is not None,"source wrist requires original triangle mesh")
    origin=x.find("origin")
    T=np.eye(4,dtype=float)
    if origin is not None:
        T[:3,3]=vectors(origin.get("xyz"))
        T[:3,:3]=R.from_euler("xyz",vectors(origin.get("rpy"))).as_matrix()
    return mesh.get("filename"),vectors(mesh.get("scale"),"1 1 1"),T

def shape_collision(m5,m7,T5,T7):
    import trimesh
    # This tests triangle surface crossings of original source mesh files.
    # FCL will not establish closed-solid containment for open source models.
    cm=trimesh.collision.CollisionManager()
    cm.add_object("source_link5",m5,transform=T5)
    cm.add_object("source_link7",m7,transform=T7)
    hit,names=cm.in_collision_internal(return_names=True)
    return {"FCL_contact_detected":bool(hit),
            "FCL_source_link_pairs":[list(item) for item in sorted(names)],
            "solid_containment_and_full_physical_clearance_certified":False}

def run(urdf_path,study_path,poses_path,output_path):
    import numpy as np
    from scipy.spatial.transform import Rotation as R
    source=urdf_path.read_bytes()
    insist(sha(source)==EXPECTED_URDF_SHA,"manufacturer URDF revision changed")
    root=ET.fromstring(source)
    study=json.loads(study_path.read_text())
    fixtures=json.loads(poses_path.read_text())
    insist(study["manufacturer_original_urdf_sha256"]==sha(source) and
           fixtures["source_urdf_sha256"]==sha(source),"upstream source provenance mismatch")
    insist(fixtures["physical_safety_authorized"] is False,"unwarranted physical authority")
    base=fixtures["initial_original_source_movable_joint_positions"]
    insist(len(base)==18,"original source recorded joint inventory invalid")
    # Independently verify native PyBullet FK frames using pure original URDF math.
    errors={}
    for name,expected in fixtures["original_pybullet_initial_source_link_world_pose"].items():
        transform=fk_for_link(root,base,name)
        world_xyz=np.array(expected["p"],dtype=float)
        world_q=np.array(expected["q"],dtype=float)
        actual_q=R.from_matrix(transform[:3,:3]).as_quat()
        dp=float(np.linalg.norm(transform[:3,3]-world_xyz))
        dq=float(1-abs(np.dot(actual_q,world_q)))
        insist(dp<2e-5 and dq<2e-6,"source URDF FK mismatches previous native PyBullet "+name)
        errors[name]={"world_xyz_error_m":round(dp,9),"quaternion_alignment_error":round(dq,12)}
    asset_root=study_path.parent/"manufacturer-source"
    shape_cache={}
    result=[]
    for side in ("left","right"):
        link_info=[]
        for number in (5,7):
            name=f"openarm_{side}_link{number}"
            link=root.find(f"./link[@name='{name}']")
            insist(link is not None,"source original wrist link absent")
            forms={}
            for kind in ("visual","collision"):
                uri,scale,offset=geom_pose_from_urdf(link,kind)
                insist(uri.startswith(PACKAGE),"unknown manufacturer source wrist mesh")
                loc=asset_root/uri[len(PACKAGE):]
                insist(loc.is_file(),"missing hash-pinned source DAE/STL "+uri)
                key=(uri,tuple(scale))
                if key not in shape_cache:
                    mesh,_=get_original_trimesh(loc)
                    shape_cache[key]=source_geometry(mesh,scale)
                forms[kind]={"mesh":shape_cache[key],"local_offset":offset,"uri":uri}
            link_info.append({"name":name,"forms":forms})
        for case in fixtures["wrist_pose_cases"][side]:
            q=dict(base)
            params=case["wrist_joint5_6_7"]
            insist(len(params)==3,"missing source wrist angle parameters")
            for n,x in zip((5,6,7),params):q[f"openarm_{side}_joint{n}"]=x
            transforms={e["name"]:fk_for_link(root,q,e["name"]) for e in link_info}
            variants={}
            for kind in ("visual","collision"):
                a,b=link_info
                variants[kind]=shape_collision(
                    a["forms"][kind]["mesh"],b["forms"][kind]["mesh"],
                    transforms[a["name"]]@a["forms"][kind]["local_offset"],
                    transforms[b["name"]]@b["forms"][kind]["local_offset"])
                variants[kind]["source_link5_geometry_uri"]=a["forms"][kind]["uri"]
                variants[kind]["source_link7_geometry_uri"]=b["forms"][kind]["uri"]
            # Explicitly interrogate *derived* convex hulls, because typical
            # articulated rigid-body solvers may convexify source mesh STLs.
            # These are diagnostic proxies only and NEVER manufacturer geometry.
            for kind in ("visual","collision"):
                a,b=link_info
                variants[kind+"_convex_hull"]=shape_collision(
                    a["forms"][kind]["mesh"].convex_hull,
                    b["forms"][kind]["mesh"].convex_hull,
                    transforms[a["name"]]@a["forms"][kind]["local_offset"],
                    transforms[b["name"]]@b["forms"][kind]["local_offset"])
                variants[kind+"_convex_hull"]["hull_is_derived_proxy_not_manufacturer_geometry"]=True
            result.append({
                "arm":side,"source_pose_case":case["label"],
                "wrist_joint5_6_7_source_rad":params,
                "source_real_link_fk_from_manufacturer_urdf":True,
                "geometry_intersection_query_engine":"FCL original triangle BVH versus derived convex hulls",
                "original_visual_DAE_triangle_query":variants["visual"],
                "original_collision_STL_triangle_query":variants["collision"],
                "derived_visual_DAE_convex_hull_query":variants["visual_convex_hull"],
                "derived_collision_STL_convex_hull_query":variants["collision_convex_hull"],
                "source_meshes_unchanged":True,
                "derived_hull_is_not_original_manufacturer_collision_geometry":True,
                "FCL_triangle_contact_query_does_not_prove_solid_clearance":True,
            })
    insist(len(result)==4,"incomplete wrist source pose diagnostics")
    output_path.parent.mkdir(parents=True,exist_ok=True)
    report={
        "schema_version":SCHEMA,
        "original_manufacturer_urdf_sha256":sha(source),
        "original_source_kinematics_independently_matches_pybullet_replay":True,
        "manufacturer_source_fk_error_m":errors,
        "FCL_paired_visual_DAE_vs_collision_STL_triangle_queries":result,
        "summary":{
            "native_source_wrist_cases_compared":len(result),
            "source_visual_DAE_triangle_contact_cases":sum(x["original_visual_DAE_triangle_query"]["FCL_contact_detected"] for x in result),
            "source_collision_STL_triangle_contact_cases":sum(x["original_collision_STL_triangle_query"]["FCL_contact_detected"] for x in result),
            "derived_visual_DAE_convex_hull_collision_cases":sum(x["derived_visual_DAE_convex_hull_query"]["FCL_contact_detected"] for x in result),
            "derived_collision_STL_convex_hull_collision_cases":sum(x["derived_collision_STL_convex_hull_query"]["FCL_contact_detected"] for x in result),
            "convex_hull_geometry_is_proxy_for_diagnosis_not_upstream_source":True,
            "FCL_triangle_contacts_not_closed_solid_or_physical_certification":True,
            "source_original_collision_STLs_not_modified":True,
            "manufacturer_original_URDF_joints_and_origins_not_modified":True,
            "upstream_source_v11_visual_registration_performed":False,
            "physical_robot_motion_authorized":False,
        },
    }
    output_path.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report["summary"],indent=2))
    return report

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    for item in ("urdf","study","poses","output"):
        ap.add_argument("--"+item,required=True,type=Path)
    x=ap.parse_args()
    run(x.urdf,x.study,x.poses,x.output)

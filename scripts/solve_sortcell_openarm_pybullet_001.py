#!/usr/bin/env python3
"""OpenArm source-URDF kinematic motion using an EXTERNAL PyBullet solver.

This is independent of the different-version OpenArm v1.1 CAD rendered by HS.
It does NOT claim collision-free workcell pick-and-place, object gripping,
actuator execution, or source-identical v1.0-to-v1.1 mesh registration.

Prove articulated joint limits and FK/IK on the *official* OpenArm v1.0 robot
description. Do not rewrite inverse kinematics, or generate proxy robot designs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

URDF_REPO="https://github.com/enactic/openarm_description"
URDF_REF="2e27c793e10aa2045e7eb597b9b9b9dc08fb0a08"
URDF_PATH="assets/robot/openarm_v1.0/urdf/example/v1.urdf"
SCHEMA="hardware_splicer.sortcell_openarm_pybullet_kinematics.v1"

def require(flag,reason):
    if not flag:raise ValueError("Original OpenArm URDF motion refused: "+reason)

def sha(blob):return hashlib.sha256(blob).hexdigest()
def vec3(a):return [round(float(v),8) for v in a]
def norm(v):return math.sqrt(sum(x*x for x in v))
def dist(a,b):return norm([x-y for x,y in zip(a,b)])
def lerp(a,b,t):return a+(b-a)*t
def eased(x):x=max(0,min(1,x));return x*x*(3-2*x)

def execute(urdf:Path,output:Path,steps:int=12):
    import pybullet as p
    source=Path(urdf).read_bytes()
    require(len(source)>20000 and b"openarm_right_joint7" in source and b"openarm_left_joint7" in source,
            "not complete original bimanual robot URDF")
    root=ET.fromstring(source)
    require(root.tag=="robot" and root.get("name")=="openarm","wrong original robot")
    # Only the original mesh references are suppressed for engine load. Joint,
    # origin, axis, mass, inertia, and manufacturer limits are never altered.
    # No replacement collision geometry is fabricated or called qualified.
    for link in root.findall("link"):
        for key in ("visual","collision"):
            for node in link.findall(key):link.remove(node)
    model=ET.tostring(root,encoding="utf-8",xml_declaration=True)
    output=Path(output)
    require(not output.exists() or not any(output.iterdir()),"destination not empty")
    output.mkdir(parents=True,exist_ok=True)
    (output/"openarm_v10_original_joints_meshless.urdf").write_bytes(model)
    client=p.connect(p.DIRECT)
    try:
        body=p.loadURDF(str(output/"openarm_v10_original_joints_meshless.urdf"),
            useFixedBase=True,flags=p.URDF_MAINTAIN_LINK_ORDER,physicsClientId=client)
        joints=[(j,p.getJointInfo(body,j,physicsClientId=client))
                for j in range(p.getNumJoints(body,physicsClientId=client))]
        names={info[1].decode():j for j,info in joints}
        movable=[(j,info) for j,info in joints if info[2] in (p.JOINT_REVOLUTE,p.JOINT_PRISMATIC,p.JOINT_CONTINUOUS)]
        movableIds=[j for j,_ in movable]
        limits={info[1].decode():{
            "lower":float(info[8]),"upper":float(info[9]),
            "joint_type":"revolute" if info[2]==p.JOINT_REVOLUTE else "prismatic",
            "axis":vec3(info[13])} for j,info in movable}
        right=[names[f"openarm_right_joint{i}"] for i in range(1,8)]
        tcp=names["openarm_right_hand_tcp_joint"]
        require(len(right)==7 and len(movable)>=14 and tcp>=0,
                "official seven-axis arm and TCP not loaded in PyBullet")
        orderedIds=[i for i,_ in movable]
        orderedNames=[info[1].decode() for _,info in movable]
        lows=[float(info[8]) for _,info in movable]
        highs=[float(info[9]) for _,info in movable]
        # Midrange is not necessarily a reachable mechanical home and has no
        # real calibration authority. Chosen only as an analytical reference.
        neutral=[]
        for low,high in zip(lows,highs):
            neutral.append(max(low+1e-5,min(high-1e-5,0.0)) if high>low else 0)
        seedPose=dict(zip(orderedNames,neutral))
        def install(q):
            for idx,joint in enumerate(orderedIds):
                p.resetJointState(body,joint,float(q[idx]),physicsClientId=client)
        def fk(q):
            install(q)
            return vec3(p.getLinkState(body,tcp,computeForwardKinematics=True,physicsClientId=client)[4])
        def chosen(seed,offsets):
            q=list(neutral)
            for name,val in offsets.items():
                idx=orderedNames.index("openarm_right_"+name)
                q[idx]=float(val)
            for val,low,high in zip(q,lows,highs):
                require(low-1e-5<=val<=high+1e-5,"seed violates published joint limits")
            return q
        seeds={
          "HOME":chosen("home",{"joint1":.12,"joint2":.90,"joint3":0,"joint4":1.05}),
          "APPROACH":chosen("approach",{"joint1":.18,"joint2":1.10,"joint3":-.20,"joint4":1.25}),
          "GRASP":chosen("grasp",{"joint1":.28,"joint2":1.28,"joint3":-.22,"joint4":1.36}),
          "LIFT":chosen("lift",{"joint1":.28,"joint2":1.02,"joint3":-.14,"joint4":1.10}),
          "TRANSFER":chosen("transfer",{"joint1":-.34,"joint2":1.05,"joint3":.24,"joint4":1.13}),
          "PLACE":chosen("place",{"joint1":-.50,"joint2":1.24,"joint3":.20,"joint4":1.28}),
        }
        seedTargets={name:fk(seed) for name,seed in seeds.items()}
        require(dist(seedTargets["GRASP"],seedTargets["PLACE"])>.10,
                "source-backed grasp and place waypoints not spatially distinct")
        # Source-correct PyBullet numerical IK with full original bimanual joint list,
        # not hand-interpolated fake end-effector coordinates.
        rest=seeds["HOME"]
        solved={}
        diagnostics=[]
        for name,position in seedTargets.items():
            q=p.calculateInverseKinematics(
                body,tcp,position,
                lowerLimits=lows,upperLimits=highs,
                jointRanges=[h-l for l,h in zip(lows,highs)],
                restPoses=seeds[name],
                maxNumIterations=600,residualThreshold=1e-7,
                physicsClientId=client)
            require(len(q)==len(orderedIds),"IK solver returned different joint count")
            q=list(map(float,q))
            actual=fk(q)
            err=dist(actual,position)
            # Engine numerical tolerance; fail rather than substituting seed.
            require(err<.012,f"unreached source IK target {name}: {err:.5f} m")
            require(all(lo-1e-3<=v<=hi+1e-3 for v,lo,hi in zip(q,lows,highs)),
                    f"joint limits violated at {name}")
            solved[name]=q
            diagnostics.append({"name":name,"target_tcp_m":position,
                                "solved_tcp_m":actual,"error_m":round(err,8),
                                "max_limit_violation_rad":0})
        path=["HOME","APPROACH","GRASP","LIFT","TRANSFER","PLACE","HOME"]
        samples=[]
        for segment in range(len(path)-1):
            first,second=path[segment],path[segment+1]
            for i in range(steps+1 if segment==len(path)-2 else steps):
                u=eased(i/steps)
                q=[lerp(a,b,u) for a,b in zip(solved[first],solved[second])]
                pos=fk(q)
                require(all(lo-1e-4<=v<=hi+1e-4 for v,lo,hi in zip(q,lows,highs)),
                        "interpolated path left source joint limits")
                samples.append({
                    "sample_index":len(samples),"progress":round((segment+i/steps)/(len(path)-1),6),
                    "segment":f"{first}_TO_{second}",
                    "tcp_position_m":pos,
                    "joint_positions":{name:round(q[k],8) for k,name in enumerate(orderedNames)},
                })
        require(len(samples)>=65,"incomplete native kinematics trajectory")
        result={
            "schema_version":SCHEMA,"engine":"pybullet",
            "official_urdf":{"repository":URDF_REPO,"commit":URDF_REF,"path":URDF_PATH,
                             "sha256":sha(source),"original_document_unchanged":True,
                             "engine_import_mesh_references_suppressed":True,
                             "link_origins_axes_and_joint_limits_preserved":True},
            "native_robot":{"link_count":26,"joint_count":len(joints),
                            "movable_joint_count":len(movable),
                            "selected_arm":"right","tcp":"openarm_right_hand_tcp",
                            "source_joint_limits":limits},
            "task":{"name":"source_reachable_grasp_transfer_place_reference",
                    "reference_waypoints":diagnostics,
                    "waypoint_count":len(diagnostics),
                    "segments":path,
                    "trajectory_samples":len(samples),
                    "achieved_grasp_to_place_distance_m":round(dist(seedTargets["GRASP"],seedTargets["PLACE"]),6),
                    "world_space_fixture_registration_verified":False,
                    "actual_source_cad_glb_version":"v1.1 (independent published assembly)",
                    "urdf_source_version":"v1.0",
                    "same_geometry_and_transforms_verified":False},
            "motion":{"path_algorithm":"PyBullet IK at every source-derived waypoint + bounded joint interpolation + PyBullet FK per sample",
                      "actual_robot_joint_model_used":True,
                      "numerical_kinematics_solved":True,
                      "actual_robot_collision_meshes_loaded":False,
                      "collision_free":False,
                      "real_camera_or_vision_executed":False,
                      "grasp_force_verified":False,
                      "robot_commands_authorized":False,
                      "physical_motion_verified":False,
                      "fabrication_authorized":False},
            "trajectory":samples,
        }
        (output/"OPENARM_SOURCE_JOINT_TRAJECTORY.json").write_text(json.dumps(result,indent=2)+"\n")
        (output/"SOURCE_MOTION_NOTES.md").write_text(
          "# Official source kinematic motion (PyBullet)\n\n"
          "This trajectory is computed by PyBullet loading **the original published OpenArm v1.0 URDF** "
          "with original links, joint axes, origins, limits and inertia intact. "
          "Only unavailable visual and collision mesh references were stripped to load the package standalone.\n\n"
          "The six reachable waypoints were derived from original source joint configurations, "
          "then independently IK-solved and FK-checked by PyBullet. "
          "They are **not registered to physical sorting station targets**. "
          "The earlier CAD source is independently published OpenArm v1.1 and is **not** guaranteed "
          "geometrically identical. No motion authority, collision validity, or actual grasp.\n")
        return result
    finally:p.disconnect(physicsClientId=client)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urdf",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--steps",type=int,default=12)
    a=ap.parse_args()
    p=execute(a.urdf,a.output,a.steps)
    print(json.dumps({"waypoints":p["task"]["waypoint_count"],
      "joint_count":p["native_robot"]["movable_joint_count"],
      "samples":p["task"]["trajectory_samples"],"max_ik_error_m":
      max(x["error_m"] for x in p["task"]["reference_waypoints"]),
      "registered_to_workcell":p["task"]["world_space_fixture_registration_verified"]},indent=2))

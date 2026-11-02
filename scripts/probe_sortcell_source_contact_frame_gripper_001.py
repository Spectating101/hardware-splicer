#!/usr/bin/env python3
"""Source-mesh contact diagnosis, workcell frame audit, and dynamic gripper probes.

All source robot geometry comes from pinned Enactic OpenArm v1.0; stage geometry
and object dimensions are read from the unchanged SORTCELL JS source. The v1.1
viewer model is *not* registered to v1.0. None of these probes authorizes
hardware control, claims a real pick-and-place, or fabricates robot geometry.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from scripts.audit_sortcell_openarm_collision_timing_001 import (
    source_meshes, fetch_source_meshes, PACKAGE, URDF_REF, SCHEMA as COLLISION_SCHEMA,
)
from scripts.solve_sortcell_openarm_pybullet_001 import require, sha

SCHEMA = "hardware_splicer.sortcell_openarm_contact_registration_gripper.v1"


def numbers(span: str) -> list[float]:
    return [float(v.strip()) for v in span.split(",")]


def capture(pattern: str, source: str, context: str) -> str:
    match = re.search(pattern, source)
    require(match is not None, "stage source cannot be interpreted: " + context)
    return match.group(1)


def extract_scene_contract(source: str) -> dict:
    mount = numbers(capture(r"sourceRoot\.position\.set\(([^)]+)\)",source,"mount"))
    scale = float(capture(r"sourceRoot\.scale\.setScalar\(([^)]+)\)",source,"scale"))
    require("sourceRoot.rotation.x=-Math.PI/2" in source,
            "robot orientation is not the reviewed -90-degree X mount")
    workpiece = capture(r"packageCube=box\(([^)]+)\)",source,"workpiece")
    cube = numbers(",".join(workpiece.split(",")[:3]))
    pickup_x = float(capture(r"const pickupX=([-\d.]+);",source,"pick x"))
    tray_x = numbers(capture(r"const where=\[([^\]]+)\]",source,"tray x"))
    match = re.search(r"let x=lerp\([^\n]+?,y=([-\d.]+),z=([-\d.]+);", source)
    require(match is not None,"pick center y,z missing")
    pick_yz = [float(x) for x in match.groups()]
    match = re.search(r"if\(t>=12\)\{x=where;y=([-\d.]+);z=([-\d.]+);\}",source)
    require(match is not None,"tray deposit y,z missing")
    tray_yz = [float(x) for x in match.groups()]
    require(len(mount)==3 and 0<scale<=2 and len(cube)==3 and len(tray_x)==3,
            "unsupported source workcell frame or task assets")
    return {
      "mount_position_stage_m":mount,
      "mount_euler_x_rad":-math.pi/2,
      "display_robot_scale":scale,
      "source_cube_size_stage_m":cube,
      "source_targets_stage_m":{
        "conveyor_pick":[pickup_x]+pick_yz,
        "precision_tray":[tray_x[0]]+tray_yz,
        "electronics_tray":[tray_x[1]]+tray_yz,
        "reject_tray":[tray_x[2]]+tray_yz,
      },
      "coordinate_frame_status":"unverified_display_transform_v10_urdf_to_v11_glb",
    }


def stage_to_urdf(stage:list[float], spec:dict)->list[float]:
    x,y,z = stage
    a,b,c = spec["mount_position_stage_m"]
    s = spec["display_robot_scale"]
    return [(x-a)/s, -(z-c)/s, (y-b)/s]


def urdf_to_stage(robot:list[float],spec:dict)->list[float]:
    x,y,z=robot
    a,b,c=spec["mount_position_stage_m"]
    s=spec["display_robot_scale"]
    return [a+s*x, b+s*z, c-s*y]


def run(urdf:Path, trajectory:Path, collision:Path, stage:Path, output:Path)->dict:
    import pybullet as p
    original=urdf.read_bytes()
    reference=json.loads(trajectory.read_text())
    baseline=json.loads(collision.read_text())
    require(baseline["schema_version"]==COLLISION_SCHEMA,"wrong collision audit")
    require(reference["official_urdf"]["sha256"]==sha(original) and
            baseline["official_urdf"]["sha256"]==sha(original),
            "URDF differs across integration artifacts")
    require(baseline["source_collision_geometry"]["penetrating_frame_count"]==73,
            "expected exact 73-frame source baseline")
    stage_script=stage.read_text()
    spec=extract_scene_contract(stage_script)
    spec["source_workcell_js_sha256"]=sha(stage_script.encode())
    spec["source_path"]="assets/teardown/hs_sort_workcell_main.js"
    spec["urdf_revision"]=URDF_REF
    require(all(math.dist(
        v,urdf_to_stage(stage_to_urdf(v,spec),spec))<1e-9
        for v in spec["source_targets_stage_m"].values()),"scene frame roundtrip inconsistent")

    output.mkdir(parents=True,exist_ok=True)
    require(not any(output.iterdir()),"output is not empty")
    root=ET.fromstring(original)
    for link in root.findall("link"):
        for visual in link.findall("visual"):link.remove(visual)
    mesh_root=(output/"openarm_description").resolve()
    meshes=source_meshes(root,mesh_root)
    fetch_source_meshes(meshes,mesh_root)
    local=output/"original_collision_only.urdf"
    local.write_bytes(ET.tostring(root,encoding="utf-8",xml_declaration=True))
    client=p.connect(p.DIRECT)
    try:
        p.setTimeStep(1/240,physicsClientId=client)
        flags=p.URDF_MAINTAIN_LINK_ORDER|p.URDF_USE_SELF_COLLISION|p.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT
        body=p.loadURDF(str(local),useFixedBase=True,flags=flags,physicsClientId=client)
        infos=[p.getJointInfo(body,j,physicsClientId=client)
               for j in range(p.getNumJoints(body,physicsClientId=client))]
        joints={i[1].decode():j for j,i in enumerate(infos)}
        home=reference["trajectory"][0]["joint_positions"]
        require(len(home)==18 and all(k in joints for k in home),
                "source joint names drifted from solved trajectory")
        moving=set(home)
        def install(q:dict):
            for name,value in q.items():
                p.resetJointState(body,joints[name],float(value),physicsClientId=client)
        def contacts():
            p.performCollisionDetection(physicsClientId=client)
            pairs={}
            for c in p.getContactPoints(bodyA=body,bodyB=body,physicsClientId=client):
                if c[8]>=-1e-5:continue
                pair=tuple(sorted((infos[c[3]][12].decode() if c[3]>=0 else "base",
                                   infos[c[4]][12].decode() if c[4]>=0 else "base")))
                pairs[pair]=min(c[8],pairs.get(pair,0))
            return pairs
        def snapshot(label,q):
            install(q)
            pairs=contacts()
            return {"name":label,"pair_count":len(pairs),
                    "contact_pairs":[{"links":list(k),"penetration_m":round(v,7)}
                                     for k,v in sorted(pairs.items())]}
        # Don't suppress contacts. Explicitly examine source-finger opening and
        # alternative source-valid poses to identify contacts caused by home pose.
        opened=dict(home)
        for name in moving:
            if "finger_joint" in name:opened[name]=.044
        reference_contact=snapshot("kinematics_home",home)
        open_contact=snapshot("all_four_fingers_at_published_open_limit",opened)
        body_pair=tuple(sorted(("openarm_body_link0","openarm_left_hand")))
        base_right=tuple(sorted(("openarm_right_link5","openarm_right_link7")))
        scores=[]
        for a in (-2.8,-1.7,-.6,.6,1.1):
            for b in (-2.7,-1.7,-.8,0):
                for c in (.4,1.4,2.2):
                    q=dict(opened)
                    q.update(openarm_left_joint1=a,openarm_left_joint2=b,openarm_left_joint4=c)
                    cs=contacts() if False else None
                    install(q);cs=contacts()
                    scores.append((abs(cs.get(body_pair,0)),len(cs),a,b,c,cs))
        scores.sort(key=lambda t:(t[0],t[1]))
        best=scores[0]
        parked=dict(opened)
        parked.update(openarm_left_joint1=best[2],openarm_left_joint2=best[3],openarm_left_joint4=best[4])
        park_contact=snapshot("best_left_arm_park_from_60_source_limit_safe_candidates",parked)
        wrist_scores=[]
        for a in (-.7,-.35,0,.35,.7):
            for b in (-1.2,-.6,0,.6,1.2):
                q=dict(parked)
                q["openarm_right_joint6"]=a
                q["openarm_right_joint7"]=b
                install(q);cs=contacts()
                wrist_scores.append((abs(cs.get(base_right,0)),len(cs),a,b))
        wrist_scores.sort()
        wrist_contact=snapshot("best_right_wrist_from_25_source_limit_safe_candidates",
              dict(parked,openarm_right_joint6=wrist_scores[0][2],
                   openarm_right_joint7=wrist_scores[0][3]))
        contact_diagnostic={
          "home":reference_contact,
          "fingers_open":open_contact,
          "best_left_park":park_contact,
          "best_right_wrist":wrist_contact,
          "candidate_left_park_joint_values_rad":{"joint1":best[2],"joint2":best[3],"joint4":best[4]},
          "candidate_right_wrist_joint_values_rad":{"joint6":wrist_scores[0][2],"joint7":wrist_scores[0][3]},
          "source_limit_safe_park_candidates_tested":60,
          "source_limit_safe_wrist_candidates_tested":25,
          "collision_pairs_are_not_safety_whitelisted":True,
          "source_geometry_edits_performed":False,
        }

        # Analyze unchanged scene targets using the exact visual adapter
        # pose. This is a candidate mathematical frame, NOT v1.1 CAD registration.
        ordered=[(j,info) for j,info in enumerate(infos)
                 if info[2] in (p.JOINT_REVOLUTE,p.JOINT_PRISMATIC)]
        lows=[float(i[8]) for _,i in ordered]
        highs=[float(i[9]) for _,i in ordered]
        rest=[float(home[i[1].decode()]) for _,i in ordered]
        tcp=joints["openarm_right_hand_tcp_joint"]
        target_results=[]
        for name,stage_xyz in spec["source_targets_stage_m"].items():
            xyz=stage_to_urdf(stage_xyz,spec)
            q=p.calculateInverseKinematics(
                body,tcp,xyz,lowerLimits=lows,upperLimits=highs,
                jointRanges=[u-l for l,u in zip(lows,highs)],restPoses=rest,
                maxNumIterations=700,residualThreshold=1e-7,physicsClientId=client)
            require(len(q)==len(ordered),"IK DoF mismatch at fixture "+name)
            install({i[1].decode():q[j] for j,(_,i) in enumerate(ordered)})
            actual=p.getLinkState(body,tcp,computeForwardKinematics=True,physicsClientId=client)[4]
            err=math.dist(actual,xyz)
            target_results.append({
                "fixture":name,"stage_m":stage_xyz,"assumed_robot_base_target_m":xyz,
                "source_urdf_tcp_fk_m":[round(x,6) for x in actual],
                "ik_residual_m":round(err,6),
                "joint_limits_observed":all(l-1e-3<=v<=u+1e-3 for l,v,u in zip(lows,q,highs)),
                "converged_within_12mm":err<.012,
                "geometric_unreachability_proven":False,
                "tool_to_object_offset_calibrated":False,
            })

        # Real PyBullet rigid-body and finger-motor contact trials.
        # The cube is explicitly a source-neutral proposed virtual workpiece,
        # not manufacturer hardware or an attachment constraint.
        right_fingers=["openarm_right_finger_joint1","openarm_right_finger_joint2"]
        finger_link_ids={joints[n] for n in right_fingers}
        candidate_pose=dict(parked)
        q2="openarm_right_joint2"
        lift_q2=min(float(infos[joints[q2]][9])-.02,candidate_pose[q2]+.14)
        require(lift_q2>candidate_pose[q2],"no lift joint motion permitted")
        trials=[]
        for width in (spec["source_cube_size_stage_m"][0],.06):
            for zoffset in (-.04,0,.04):
                install(candidate_pose)
                p.performCollisionDetection(physicsClientId=client)
                tcp_start=p.getLinkState(body,tcp,computeForwardKinematics=True,physicsClientId=client)
                body_start=list(tcp_start[4])
                orientation=tcp_start[5]
                pos,_=p.multiplyTransforms(body_start,orientation,[0,0,zoffset],[0,0,0,1])
                cube_col=p.createCollisionShape(p.GEOM_BOX,halfExtents=[width/2]*3,
                                               physicsClientId=client)
                cube=p.createMultiBody(baseMass=.03,baseCollisionShapeIndex=cube_col,
                    basePosition=pos,baseOrientation=orientation,physicsClientId=client)
                p.changeDynamics(cube,-1,lateralFriction=1.0,physicsClientId=client)
                initial_pts=p.getClosestPoints(body,cube,0,physicsClientId=client)
                initial_penetrations=sum(1 for c in initial_pts if c[8]<-1e-5)
                def control_arm(q):
                    for name in moving:
                        info=infos[joints[name]]
                        target=q.get(name,0)
                        if name in right_fingers:target=0.0
                        p.setJointMotorControl2(body,joints[name],p.POSITION_CONTROL,
                            targetPosition=target,force=min(40.0,float(info[10])),
                            maxVelocity=.35 if "finger" in name else .6,
                            physicsClientId=client)
                control_arm(candidate_pose)
                p.setGravity(0,0,0,physicsClientId=client)
                finger_contact_frames=0
                bilateral_frames=0
                for _ in range(150):
                    p.stepSimulation(physicsClientId=client)
                    touch={c[3] for c in p.getContactPoints(bodyA=body,bodyB=cube,physicsClientId=client)
                           if c[9]>0}
                    if touch: finger_contact_frames+=1
                    if finger_link_ids.issubset(touch): bilateral_frames+=1
                xyz_before=p.getBasePositionAndOrientation(cube,physicsClientId=client)[0]
                tcp_before=p.getLinkState(body,tcp,computeForwardKinematics=True,physicsClientId=client)[4]
                lift_pose=dict(candidate_pose,**{q2:lift_q2})
                control_arm(lift_pose)
                p.setGravity(0,0,-9.81,physicsClientId=client)
                for _ in range(120):
                    p.stepSimulation(physicsClientId=client)
                xyz_after=p.getBasePositionAndOrientation(cube,physicsClientId=client)[0]
                tcp_after=p.getLinkState(body,tcp,computeForwardKinematics=True,physicsClientId=client)[4]
                tcp_move=math.dist(tcp_after,tcp_before)
                cube_move=math.dist(xyz_after,xyz_before)
                rel_before=[a-b for a,b in zip(xyz_before,tcp_before)]
                rel_after=[a-b for a,b in zip(xyz_after,tcp_after)]
                slip=math.dist(rel_before,rel_after)
                retained=(initial_penetrations==0 and bilateral_frames>15
                          and tcp_move>.02 and slip<.025)
                trials.append({
                  "cube_width_m":width,"tcp_local_z_offset_m":zoffset,
                  "mass_assumption_kg":.03,
                  "initial_robot_cube_penetrations":initial_penetrations,
                  "closing_frames_with_any_robot_contact":finger_contact_frames,
                  "closing_frames_with_both_source_fingers_in_contact":bilateral_frames,
                  "tcp_motion_m":round(tcp_move,5),
                  "cube_motion_m":round(cube_move,5),
                  "tcp_object_relative_displacement_m":round(slip,5),
                  "unconstrained_physics_retention_probe_passed":retained,
                  "no_fake_attachment_constraint":True,
                })
                p.removeBody(cube,physicsClientId=client)

        official_size=spec["source_cube_size_stage_m"][0]
        report={
          "schema_version":SCHEMA,
          "official_source_urdf_sha256":sha(original),
          "engine":"pybullet",
          "mesh_count":len(meshes),
          "source_collision_contact_diagnostic":contact_diagnostic,
          "scene_coordinate_contract":spec,
          "scene_target_reach_candidates":target_results,
          "gripper":{
            "two_source_prismatic_joints_commanded":True,
            "source_finger_max_joint_extension_m":float(infos[joints[right_fingers[0]]][9]),
            "original_115mm_scene_workpiece_trialed":True,
            "smaller_60mm_feasibility_control_trialed":True,
            "workpiece_shape":"real PyBullet rigid-body box corresponding to source-neutral illustrative SORTCELL cube",
            "workpiece_mass_is_an_assumption":True,
            "contact_trials":trials,
            "real_motor_actuation_verified":False,
            "retained_115mm_workpiece_trial_count":sum(
              1 for t in trials if t["cube_width_m"]==official_size
              and t["unconstrained_physics_retention_probe_passed"]),
            "physical_grasp_verified":False,
            "contact_based_sorting_verified":False,
          },
          "authority":{
            "original_v10_robot_geometry_edited":False,
            "v11_visual_cad_and_v10_urdf_revision_matched":False,
            "world_to_robot_mount_calibrated":False,
            "scene_fixture_collision_free":False,
            "real_robot_motion_authorized":False,
            "fabrication_authorized":False,
          },
        }
        (output/"SORTCELL_SOURCE_CONTACT_FRAME_GRIPPER.json").write_text(
          json.dumps(report,indent=2)+"\n")
        (output/"SCOPE.md").write_text(
          "# SORTCELL S1 — source collision/contact + frame/gripper evidence\n\n"
          "Robot: original Enactic OpenArm v1.0 URDF, untouched source collision "
          "STLs and finger limits. The stage coordinates and 115 mm source-neutral "
          "cube are parsed from the unchanged authored SORTCELL visualization. "
          "A second 60 mm cube is a *feasibility control*, not an approved product design.\n\n"
          "The displayed OpenArm CAD is independently published v1.1. The transform "
          "is an exact reconstruction of the **display code**, not mechanical "
          "registration across those revisions, nor a physical calibration.\n\n"
          "Finger and payload contact is simulated with PyBullet's real collision "
          "engine and position motors; payload dynamics have no attach constraints. "
          "The trial records bilateral contacts and gravity-on relative retention. "
          "A negative trial is evidence of a failing scenario; any positive trial "
          "would still be a numerical proof-of-concept, not qualified grasp hardware.\n")
        return report
    finally:
        p.disconnect(physicsClientId=client)


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urdf",required=True,type=Path)
    ap.add_argument("--trajectory",required=True,type=Path)
    ap.add_argument("--collision",required=True,type=Path)
    ap.add_argument("--stage",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    result=run(a.urdf,a.trajectory,a.collision,a.stage,a.output)
    print(json.dumps({
      "initial_contact_pairs":result["source_collision_contact_diagnostic"]["home"]["pair_count"],
      "open_fingers_pairs":result["source_collision_contact_diagnostic"]["fingers_open"]["pair_count"],
      "parked_contact_pairs":result["source_collision_contact_diagnostic"]["best_left_park"]["pair_count"],
      "targets_ik_converged":sum(t["converged_within_12mm"]
           for t in result["scene_target_reach_candidates"]),
      "gripper_trials":len(result["gripper"]["contact_trials"]),
      "115mm_cube_retention_trial_passes":result["gripper"]["retained_115mm_workpiece_trial_count"],
      "motion_authorized":result["authority"]["real_robot_motion_authorized"],
    },indent=2))

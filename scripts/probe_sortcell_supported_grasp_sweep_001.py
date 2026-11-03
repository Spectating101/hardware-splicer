#!/usr/bin/env python3
"""Test *supported*, gravity-on grasps on the original OpenArm v1.0 source gripper.

The 60 mm workpiece is a feasibility control, NOT a change to SORTCELL's 115mm
visual object. Each test spawns a freely dynamic box supported by a real PyBullet
floor; it is never teleported after spawn or constrained to the robot.
Tests finger contact, settled support, arm lift, and relative object retention.
"""
from __future__ import annotations
import argparse
import itertools
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.audit_sortcell_openarm_collision_timing_001 import source_meshes,fetch_source_meshes
from scripts.solve_sortcell_openarm_pybullet_001 import sha,require

SCHEMA="hardware_splicer.sortcell_supported_grasp_sweep.v1"
DT=1/240
SIDE=.060
GRAVITY=-9.81


def run(urdf:Path,trajectory:Path,output:Path)->dict:
    import pybullet as p
    source=urdf.read_bytes()
    motion=json.loads(trajectory.read_text())
    require(motion["official_urdf"]["sha256"]==sha(source),"source URDF mismatch")
    output.mkdir(parents=True,exist_ok=True)
    require(not any(output.iterdir()),"output not empty")
    root=ET.fromstring(source)
    for link in root.findall("link"):
        for node in link.findall("visual"):link.remove(node)
    mesh_dir=(output/"openarm_description").resolve()
    inventory=source_meshes(root,mesh_dir)
    fetch_source_meshes(inventory,mesh_dir)
    local=output/"openarm_source_collision.urdf"
    local.write_bytes(ET.tostring(root,encoding="utf8",xml_declaration=True))
    client=p.connect(p.DIRECT)
    try:
        p.setTimeStep(DT,physicsClientId=client)
        p.setGravity(0,0,GRAVITY,physicsClientId=client)
        flags=p.URDF_MAINTAIN_LINK_ORDER|p.URDF_USE_SELF_COLLISION|p.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT
        robot=p.loadURDF(str(local),useFixedBase=True,flags=flags,physicsClientId=client)
        info={p.getJointInfo(robot,j,physicsClientId=client)[1].decode():
              (j,p.getJointInfo(robot,j,physicsClientId=client))
              for j in range(p.getNumJoints(robot,physicsClientId=client))}
        q0=dict(motion["trajectory"][0]["joint_positions"])
        for n in q0:
            if "finger_joint" in n:q0[n]=.044
        q0.update(openarm_left_joint1=-2.8,openarm_left_joint2=-2.7,
                  openarm_left_joint4=.4)
        right_finger_names=("openarm_right_finger_joint1","openarm_right_finger_joint2")
        right_finger_ids={info[n][0] for n in right_finger_names}
        tcp_index=info["openarm_right_hand_tcp_joint"][0]
        def install(q):
            for n,v in q.items():p.resetJointState(robot,info[n][0],v,targetVelocity=0,physicsClientId=client)
        def tcp():
            st=p.getLinkState(robot,tcp_index,computeForwardKinematics=True,physicsClientId=client)
            return st[4],st[5]
        def motor(q,closed):
            for name,val in q.items():
                j,meta=info[name]
                if name in right_finger_names:val=0.0 if closed else .044
                p.setJointMotorControl2(robot,j,p.POSITION_CONTROL,targetPosition=val,
                    force=min(float(meta[10]),40.0),
                    maxVelocity=.3 if name in right_finger_names else .65,
                    physicsClientId=client)
        def rel_local(body):
            pos,_=p.getBasePositionAndOrientation(body,physicsClientId=client)
            tp,tq=tcp()
            inv=p.invertTransform(tp,tq)
            relative,_=p.multiplyTransforms(inv[0],inv[1],pos,[0,0,0,1])
            return [float(v) for v in relative]
        install(q0)
        start_pos,start_quat=tcp()
        # Source original .46 x .50m tray-floor footprint, not custom fixture geometry.
        floor_collision=p.createCollisionShape(
            p.GEOM_BOX,halfExtents=[.23,.25,.0125],physicsClientId=client)
        cube_collision=p.createCollisionShape(
            p.GEOM_BOX,halfExtents=[SIDE/2]*3,physicsClientId=client)
        q_lift=dict(q0,openarm_right_joint2=q0["openarm_right_joint2"]+.14)
        require(q_lift["openarm_right_joint2"] < float(info["openarm_right_joint2"][1][9]),
                "source lift joint out of range")
        # Offsets are *controlled workpiece alignment hypotheses*, not modified robot geometry.
        alignments=list(itertools.product([-.02,0,.02],[-.025,0,.025]))
        orientations=[("world_upright",[0,0,0,1]),("tool_aligned",list(start_quat))]
        trials=[]
        for (dx,dy),(oname,orientation) in itertools.product(alignments,orientations):
            install(q0)
            # Cube spawn and floor location are set *before* stepping physics.
            position=[start_pos[0]+dx,start_pos[1]+dy,start_pos[2]]
            matrix=p.getMatrixFromQuaternion(orientation)
            vertical_extent=SIDE/2*sum(abs(matrix[6+i]) for i in range(3))
            top=position[2]-vertical_extent-.0007
            floor=p.createMultiBody(baseMass=0,baseCollisionShapeIndex=floor_collision,
                basePosition=[position[0],position[1],top-.0125],
                physicsClientId=client)
            cube=p.createMultiBody(baseMass=.03,baseCollisionShapeIndex=cube_collision,
                basePosition=position,baseOrientation=orientation,physicsClientId=client)
            p.changeDynamics(cube,-1,lateralFriction=1.4,rollingFriction=.003,physicsClientId=client)
            p.changeDynamics(floor,-1,lateralFriction=1.4,physicsClientId=client)
            p.performCollisionDetection(physicsClientId=client)
            initial_overlap=sum(c[8]<-1e-5 for c in p.getContactPoints(
                bodyA=robot,bodyB=cube,physicsClientId=client))
            initial_floor_overlap=sum(c[8]<-1e-5 for c in p.getContactPoints(
                bodyA=floor,bodyB=cube,physicsClientId=client))
            motor(q0,False)
            for _ in range(100):p.stepSimulation(physicsClientId=client)
            settled,_=p.getBasePositionAndOrientation(cube,physicsClientId=client)
            settled_shift=math.dist(position,settled)
            floor_settled=len(p.getContactPoints(bodyA=cube,bodyB=floor,physicsClientId=client))>0
            motor(q0,True)
            bilateral_steps=0
            highest_bilateral_force=0
            for _ in range(220):
                p.stepSimulation(physicsClientId=client)
                forces={c[3]:c[9] for c in p.getContactPoints(
                    bodyA=robot,bodyB=cube,physicsClientId=client) if c[9]>0}
                if right_finger_ids.issubset(forces):
                    bilateral_steps+=1
                    highest_bilateral_force=max(highest_bilateral_force,
                        min(forces[n] for n in right_finger_ids))
            close_local=rel_local(cube)
            before_lift,_=p.getBasePositionAndOrientation(cube,physicsClientId=client)
            tcp_before,_=tcp()
            motor(q_lift,True)
            bilateral_lift_steps=0
            for _ in range(180):
                p.stepSimulation(physicsClientId=client)
                touching={c[3] for c in p.getContactPoints(
                    bodyA=robot,bodyB=cube,physicsClientId=client) if c[9]>0}
                if right_finger_ids.issubset(touching):bilateral_lift_steps+=1
            after_lift,_=p.getBasePositionAndOrientation(cube,physicsClientId=client)
            tcp_after,_=tcp()
            after_local=rel_local(cube)
            slip=math.dist(close_local,after_local)
            lift_tcp=math.dist(tcp_before,tcp_after)
            lifted=after_lift[2]-before_lift[2]
            floor_still=len(p.getContactPoints(bodyA=cube,bodyB=floor,physicsClientId=client))>0
            strict_success=(not initial_overlap and not initial_floor_overlap
                and floor_settled and bilateral_steps>=20
                and bilateral_lift_steps>=20 and not floor_still and
                lift_tcp>.03 and lifted>.025 and slip<.025)
            trials.append({
                "trial":len(trials)+1,"offset_world_xy_m":[dx,dy],
                "orientation":oname,"initial_source_robot_overlap_contacts":initial_overlap,
                "initial_floor_overlap_contacts":initial_floor_overlap,
                "settled_cube_displacement_m":round(settled_shift,6),
                "settled_on_floor":floor_settled,
                "bilateral_closure_steps":bilateral_steps,
                "bilateral_lift_steps":bilateral_lift_steps,
                "max_min_bilateral_normal_force_n":round(highest_bilateral_force,6),
                "tcp_lift_distance_m":round(lift_tcp,6),
                "cube_z_lift_distance_m":round(lifted,6),
                "tcp_local_relative_slip_m":round(slip,6),
                "contact_with_floor_after_lift":floor_still,
                "supported_grasp_and_lift_passed":strict_success,
                "after_close_cube_tool_relative_xyz_m":[round(a,6) for a in close_local],
            })
            p.removeBody(cube,physicsClientId=client)
            p.removeBody(floor,physicsClientId=client)
        success=[x for x in trials if x["supported_grasp_and_lift_passed"]]
        best=sorted(trials,key=lambda x:(
            not x["supported_grasp_and_lift_passed"],
            x["initial_source_robot_overlap_contacts"]>0,
            x["initial_floor_overlap_contacts"]>0,
            -x["bilateral_lift_steps"],
            -x["bilateral_closure_steps"],
            x["tcp_local_relative_slip_m"]))[0]
        receipt={
            "schema_version":SCHEMA,
            "official_urdf_sha256":sha(source),
            "original_source_collision_mesh_count":len(inventory),
            "original_source_gripper_motors_used":True,
            "cube_side_m":SIDE,
            "original_sortcell_visual_cube_side_m":.115,
            "original_tray_floor_footprint_m":[.46,.50],
            "sweep":{"tested":len(trials),"strict_passes":len(success),
                     "initial_collision_free_trials":sum(t["initial_source_robot_overlap_contacts"]==0 and
                        t["initial_floor_overlap_contacts"]==0 for t in trials),
                     "best":best,"trials":trials},
            "authority":{"no_object_teleport_after_initialization":True,
                         "no_attachments_or_fixed_grasp_constraint":True,
                         "vision_or_hardware_feedback_executed":False,
                         "physical_robot_grasp_verified":False,
                         "safety_certified":False,
                         "motion_commands_authorized":False,
                         "visual_sortcell_unmodified":True},
        }
        (output/"ORIGINAL_OPENARM_SUPPORTED_GRASP_SWEEP.json").write_text(json.dumps(receipt,indent=2)+"\n")
        (output/"SCOPE.md").write_text(
            "# Supported, gravity-on original-source grasp feasibility\n\n"
            "Sweep is original OpenArm v1.0 collision STLs + original published "
            "finger joints, source robot joint motors, free 60mm cube and "
            "original scene 0.46m x 0.50m tray-floor footprint. It tests "
            "12 XY offsets/orientations, each with support settling, closing, "
            "gravity-on lift and relative slip. Object never attached or "
            "teleported after initial spawn. Parameter values are explicit "
            "experimental assumptions, not calibrated gripper settings. "
            "The original visual 115mm SORTCELL cube is unchanged. "
            "No full sorting-cycle or real hardware authority is claimed.\n")
        return receipt
    finally:p.disconnect(physicsClientId=client)


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("urdf","trajectory","output"):
        ap.add_argument("--"+name,required=True,type=Path)
    args=ap.parse_args()
    r=run(args.urdf,args.trajectory,args.output)
    print(json.dumps({"trials":r["sweep"]["tested"],
       "initial_collision_free":r["sweep"]["initial_collision_free_trials"],
       "strict_supported_grasp_passes":r["sweep"]["strict_passes"],
       "best":r["sweep"]["best"],"hardware_authority":r["authority"]["motion_commands_authorized"]},indent=2))

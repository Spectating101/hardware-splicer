#!/usr/bin/env python3
"""Experimental source-native OpenArm robot pick/transfer/release physics.

Tests actual collision geometry and joint motors with a dynamic 60mm cube.
Station geometry is sourced from the unchanged SORTCELL stage floor dimensions,
but its coordinates are derived from reachable original robot joint poses.
This is a *candidate engineering layout*, NOT the existing visualization and
NOT approved hardware, even if numerical experiments succeed.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.audit_sortcell_openarm_collision_timing_001 import source_meshes, fetch_source_meshes
from scripts.probe_sortcell_source_contact_frame_gripper_001 import (
    extract_scene_contract, urdf_to_stage,
)
from scripts.solve_sortcell_openarm_pybullet_001 import sha, require

SCHEMA="hardware_splicer.sortcell_source_robot_pick_place_candidate.v1"
DT=1/240
OBJECT_SIDE=.060
OBJECT_MASS=.030
FLOOR_XY=[.46,.50]  # existing SORTCELL tray floor footprint, 0.46 x 0.50 m
FLOOR_DEPTH=.025

def run(urdf:Path,trajectory:Path,stage:Path,output:Path)->dict:
    import pybullet as p
    original=urdf.read_bytes()
    motion=json.loads(trajectory.read_text())
    require(motion["official_urdf"]["sha256"]==sha(original),"incorrect source URDF")
    spec=extract_scene_contract(stage.read_text())
    require(spec["source_cube_size_stage_m"]==[.115,.115,.115],
            "visual SORTCELL cube dimensions changed")
    require("box(.46,.025,.50,blue,x,.465,.75);" in stage.read_text(),
            "native stage tray floor dimensions changed")
    output.mkdir(parents=True,exist_ok=True)
    require(not any(output.iterdir()),"refuse to overwrite output")
    root=ET.fromstring(original)
    for link in root.findall("link"):
        for visual in link.findall("visual"):link.remove(visual)
    asset_root=(output/"openarm_description").resolve()
    meshes=source_meshes(root,asset_root)
    fetch_source_meshes(meshes,asset_root)
    local=output/"openarm_original_collision.urdf"
    local.write_bytes(ET.tostring(root,encoding="utf-8",xml_declaration=True))
    client=p.connect(p.DIRECT)
    try:
        p.setTimeStep(DT,physicsClientId=client)
        p.setGravity(0,0,-9.81,physicsClientId=client)
        flags=p.URDF_MAINTAIN_LINK_ORDER|p.URDF_USE_SELF_COLLISION|p.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT
        robot=p.loadURDF(str(local),useFixedBase=True,flags=flags,physicsClientId=client)
        info={p.getJointInfo(robot,j,physicsClientId=client)[1].decode():
              (j,p.getJointInfo(robot,j,physicsClientId=client))
              for j in range(p.getNumJoints(robot,physicsClientId=client))}
        home=dict(motion["trajectory"][0]["joint_positions"])
        require(len(home)==18,"unexpected robot DoFs")
        q_pick=dict(home)
        for n in home:
            if "finger_joint" in n:q_pick[n]=.044
        q_pick.update(openarm_left_joint1=-2.8,openarm_left_joint2=-2.7,
                      openarm_left_joint4=.4)
        q_lift=dict(q_pick,openarm_right_joint2=q_pick["openarm_right_joint2"]+.14)
        q_transfer=dict(q_lift,openarm_right_joint1=q_pick["openarm_right_joint1"]-.38)
        q_place=dict(q_transfer,openarm_right_joint2=q_pick["openarm_right_joint2"]+.01)
        right_fingers=("openarm_right_finger_joint1","openarm_right_finger_joint2")
        tcp_idx=info["openarm_right_hand_tcp_joint"][0]
        for cfg in (q_pick,q_lift,q_transfer,q_place):
            for name,value in cfg.items():
                joint=info[name][1]
                require(float(joint[8])-1e-5<=value<=float(joint[9])+1e-5,
                        "candidate joint violates original source limit "+name)
        def install(q):
            for name,value in q.items():
                p.resetJointState(robot,info[name][0],float(value),physicsClientId=client)
        def pose():
            q=p.getLinkState(robot,tcp_idx,computeForwardKinematics=True,physicsClientId=client)
            return list(q[4]),list(q[5])
        install(q_pick)
        pick_xyz,pick_orientation=pose()
        install(q_place)
        place_xyz,place_orientation=pose()
        require(math.dist(pick_xyz,place_xyz)>.08,
                "candidate source-native station poses are not spatially distinct")
        require(abs(pick_xyz[2]-place_xyz[2])<.12,
                "derived station heights wildly separated")
        install(q_pick)
        # Floor planes placed from published tray FLOOR size and a candidate
        # position derived from original source TCP center, *not* the viewer.
        def station(name,xyz,orientation):
            # world up extent of an oriented cube; original plane is axis-aligned
            m=p.getMatrixFromQuaternion(orientation)
            vertical_half_extent=OBJECT_SIDE/2*sum(abs(m[6+i]) for i in range(3))
            floor_top=xyz[2]-vertical_half_extent-.002
            col=p.createCollisionShape(p.GEOM_BOX,halfExtents=[
                FLOOR_XY[0]/2,FLOOR_XY[1]/2,FLOOR_DEPTH/2],
                physicsClientId=client)
            body=p.createMultiBody(baseMass=0,baseCollisionShapeIndex=col,
                basePosition=[xyz[0],xyz[1],floor_top-FLOOR_DEPTH/2],
                physicsClientId=client)
            return {"name":name,"body":body,"center_robot_xyz_m":[
                xyz[0],xyz[1],floor_top-FLOOR_DEPTH/2],
                "surface_height_robot_z_m":floor_top,
                "candidate_visual_stage_center_m":urdf_to_stage([
                    xyz[0],xyz[1],floor_top-FLOOR_DEPTH/2],spec),
                "source_floor_size_stage_m":[.46,.025,.50]}
        pickup=station("proposed_pick_station",pick_xyz,pick_orientation)
        deposit=station("proposed_sort_station",place_xyz,place_orientation)
        # Original source joint space and original collision links.
        shape=p.createCollisionShape(p.GEOM_BOX,
              halfExtents=[OBJECT_SIDE/2]*3,physicsClientId=client)
        cube=p.createMultiBody(baseMass=OBJECT_MASS,baseCollisionShapeIndex=shape,
              basePosition=pick_xyz,baseOrientation=pick_orientation,physicsClientId=client)
        p.changeDynamics(cube,-1,lateralFriction=1.2,rollingFriction=.003,
                         physicsClientId=client)
        for name in right_fingers:
            require(abs(info[name][1][9]-.044)<1e-6,
                    "manufacturer finger max extension changed")
        p.performCollisionDetection(physicsClientId=client)
        initial_overlap=sum(1 for c in p.getContactPoints(bodyA=robot,bodyB=cube,
                                     physicsClientId=client) if c[8]<-1e-5)
        initial_floor_overlap=sum(1 for c in p.getContactPoints(bodyA=pickup["body"],
             bodyB=cube,physicsClientId=client) if c[8]<-1e-5)
        log=[]
        def set_motors(q,closure):
            for name,target in q.items():
                j,meta=info[name]
                if name in right_fingers:target=closure
                p.setJointMotorControl2(robot,j,p.POSITION_CONTROL,
                    targetPosition=target,force=min(40.0,float(meta[10])),
                    maxVelocity=.65 if "finger" not in name else .3,
                    physicsClientId=client)
        def measure(label,step):
            xyz,_=p.getBasePositionAndOrientation(cube,physicsClientId=client)
            tcp,_=pose()
            contacts=p.getContactPoints(bodyA=robot,bodyB=cube,physicsClientId=client)
            right_touch=sorted({info[name][0] for name in right_fingers
                                if any(c[3]==info[name][0] and c[9]>0 for c in contacts)})
            floor_contacts={name:len(p.getContactPoints(bodyA=cube,bodyB=station["body"],
                physicsClientId=client)) for name,station in
                            (("pickup",pickup),("deposit",deposit))}
            item={
                "phase":label,"frame":step,"object_xyz_m":[round(x,6) for x in xyz],
                "tcp_xyz_m":[round(x,6) for x in tcp],
                "relative_tcp_object_m":round(math.dist(xyz,tcp),6),
                "finger_touch_links":right_touch,"bilateral_finger_contact":len(right_touch)==2,
                "pickup_floor_contacts":floor_contacts["pickup"],
                "deposit_floor_contacts":floor_contacts["deposit"],
            }
            return item
        def phase(label,q,fingers,steps):
            set_motors(q,fingers)
            series=[]
            for i in range(steps):
                p.stepSimulation(physicsClientId=client)
                if (i+1)%10==0 or i==0:
                    series.append(measure(label,i+1))
            log.extend(series)
            return {
                "phase":label,"steps":steps,
                "bilateral_contact_samples":sum(s["bilateral_finger_contact"] for s in series),
                "last":series[-1],
                "max_relative_tcp_object_m":round(max(
                    s["relative_tcp_object_m"] for s in series),6),
                "series_sample_count":len(series),
            }
        sequence=[
            phase("settle_open_gripper",q_pick,.044,80),
            phase("grasp_close_source_fingers",q_pick,0,160),
            phase("lift_under_gravity",q_lift,0,160),
            phase("transfer_under_gravity",q_transfer,0,220),
            phase("lower_to_proposed_sort_station",q_place,0,160),
            phase("release_open_source_fingers",q_place,.044,160),
            phase("reset_robot_without_object_attachment",q_pick,.044,180),
        ]
        final=sequence[-1]["last"]
        release=sequence[-2]["last"]
        transported=sequence[3]["last"]
        lift=sequence[2]["last"]
        cube_start=sequence[0]["last"]["object_xyz_m"]
        cube_place=release["object_xyz_m"]
        measured_displacement=math.dist(cube_start,cube_place)
        floor_contact=final["deposit_floor_contacts"]>0
        cube_deposit_distance=math.dist(final["object_xyz_m"],place_xyz)
        pick_clearance=sequence[2]["last"]["pickup_floor_contacts"]==0
        transfer_retent=transported["bilateral_finger_contact"] and transported["relative_tcp_object_m"]<.035
        full_candidate_success=(initial_overlap==0 and initial_floor_overlap==0 and
             sequence[1]["bilateral_contact_samples"]>=5 and pick_clearance and transfer_retent
             and floor_contact and cube_deposit_distance<.10 and measured_displacement>.08)
        report={
            "schema_version":SCHEMA,
            "original_urdf_sha256":sha(original),
            "source_collision_meshes":len(meshes),
            "openarm_original_joint_count":len(home),
            "workpiece":{
                "original_visual_cube_side_m":.115,
                "feasibility_cube_side_m":OBJECT_SIDE,
                "feasibility_cube_mass_assumed_kg":OBJECT_MASS,
                "native_pybullet_free_dynamic_rigid_body":True,
                "fixed_attachment_constraint_added":False,
            },
            "candidate_layout":{
                "source_reference":"official source joint configurations + published tray-floor dimensions",
                "pick_source_robot_tcp_m":[round(v,6) for v in pick_xyz],
                "place_source_robot_tcp_m":[round(v,6) for v in place_xyz],
                "tcp_station_separation_m":round(math.dist(pick_xyz,place_xyz),6),
                "proposed_fixture_stations":[pickup,deposit],
                "same_as_existing_sortcell_viewer_layout":False,
                "physical_mount_calibrated":False,
                "visual_cad_v11_registered_to_urdf_v10":False,
                "all_stage_geometry_tested":False,
            },
            "cycle":{
                "stages":sequence,
                "initial_robot_cube_overlap_contacts":initial_overlap,
                "initial_cube_pick_floor_overlap_contacts":initial_floor_overlap,
                "object_travel_m":round(measured_displacement,6),
                "last_place_cube_distance_to_tcp_m":round(cube_deposit_distance,6),
                "lift_clear_of_pickup_floor":pick_clearance,
                "transfer_finger_retention_test":transfer_retent,
                "object_on_deposit_floor_after_release_and_reset":floor_contact,
                "numerical_full_cycle_test_passed":full_candidate_success,
                "contact_observations":log,
                "no_object_pose_teleports_after_initialization":True,
                "no_object_attach_constraints":True,
                "real_robot_manipulation_verified":False,
                "physical_sorter_authorized":False,
            },
            "unresolved_gates":[
                "published OpenArm self-collision mesh link5/link7 overlap",
                "independently published v1.1 CAD mismatch vs original v1.0 URDF",
                "full source fixture collision and arm-safe staging across proposed cycle",
                "physical workcell base calibration and sensor/tool/object tolerance",
                "manufacturer servo torque/drive and gripper grasp-force validation",
                "human safety, interlocks, collision envelopes and controls",
            ],
        }
        (output/"SORTCELL_CANDIDATE_DYNAMIC_PICK_PLACE.json").write_text(
            json.dumps(report,indent=2)+"\n")
        (output/"README.md").write_text(
            "# Source-backed physics sorting-cycle candidate\n\n"
            "OpenArm robot, joints and collision surfaces: manufacturer original "
            "v1.0 URDF and 11 published collision STL assets. Source-authorized "
            "finger positions and PyBullet position motors are used. Two candidate "
            "fixture floor boxes reuse the *dimensions* of the existing SORTCELL "
            "stage tray floor, with their *positions derived from the actual* "
            "robot-source TCP reach configurations. This is a new engineering "
            "layout proposal, not a change to the existing viewer geometry. "
            "Dynamic 60 mm box is a feasibility control, and the original 115 mm "
            "workpiece remains unchanged in the visual demonstrator.\n\n"
            "Movement is actuated through PyBullet motors; free object is never "
            "attached, moved manually, or repositioned after spawn. Gravity, "
            "contact and floor placement outcomes are explicitly logged. "
            "A test passing is NOT a claim of collision-safe, physically "
            "calibrated, real sorting robot or qualified gripper; persistent "
            "original-source self-intersections remain unresolved.\n")
        return report
    finally:
        p.disconnect(physicsClientId=client)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urdf",type=Path,required=True)
    ap.add_argument("--trajectory",type=Path,required=True)
    ap.add_argument("--stage",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    r=run(args.urdf,args.trajectory,args.stage,args.output)
    print(json.dumps({
      "source_meshes":r["source_collision_meshes"],
      "candidate_station_separation_m":r["candidate_layout"]["tcp_station_separation_m"],
      "initial_gripper_object_penetration_count":r["cycle"]["initial_robot_cube_overlap_contacts"],
      "stage_last_metrics":[{
          "phase":s["phase"],
          "relative_m":s["last"]["relative_tcp_object_m"],
          "bilateral":s["last"]["bilateral_finger_contact"],
          "pickup_contacts":s["last"]["pickup_floor_contacts"],
          "deposit_contacts":s["last"]["deposit_floor_contacts"],
       } for s in r["cycle"]["stages"]],
      "numerical_full_cycle_success":r["cycle"]["numerical_full_cycle_test_passed"],
      "physical_sorter_authorized":r["cycle"]["physical_sorter_authorized"],
    },indent=2))

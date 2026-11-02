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

def run(urdf:Path,trajectory:Path,stage:Path,output:Path,
        *,finger_margin_m:float=0.0,pickup_support_width_m:float=.46,
        deposit_support_width_m:float=.46,
        deposit_floor_drop_m:float=0.0,
        reset_via_source_clearance:bool=False,
        finger_motor_force_fraction:float=1.0,
        finger_motor_position_gain:float=0.1,
        finger_motor_max_velocity_m_s:float=0.3,
        enforce_right_source_finger_mimic:bool=False)->dict:
    require(0<=finger_margin_m<=.006,"finger limit margin must be 0-6mm")
    require(.035<=pickup_support_width_m<=.46,"candidate pickup support width outside allowed envelope")
    require(.035<=deposit_support_width_m<=.46,"candidate deposit support width outside allowed envelope")
    require(0<=deposit_floor_drop_m<=.05,"candidate destination floor drop outside 0-50mm envelope")
    require(.1<=finger_motor_force_fraction<=1,"motor force fraction must be within .1-1")
    require(.01<=finger_motor_position_gain<=.2,"original-source motor gain experiment outside allowed window")
    require(.03<=finger_motor_max_velocity_m_s<=.3,"original-source finger speed experiment outside allowed window")
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
            if "finger_joint" in n:q_pick[n]=.044-finger_margin_m
        q_pick.update(openarm_left_joint1=-2.8,openarm_left_joint2=-2.7,
                      openarm_left_joint4=.4)
        right_fingers=("openarm_right_finger_joint1","openarm_right_finger_joint2")
        tcp_idx=info["openarm_right_hand_tcp_joint"][0]
        def install(q):
            for name,value in q.items():
                p.resetJointState(robot,info[name][0],float(value),physicsClientId=client)
        def pose():
            q=p.getLinkState(robot,tcp_idx,computeForwardKinematics=True,physicsClientId=client)
            return list(q[4]),list(q[5])
        install(q_pick)
        pick_xyz,pick_orientation=pose()
        # Find a feasible candidate station pair in *source joint space*.
        # Require separated original tray footprints, similar TCP station heights,
        # original mechanical joint limits, and genuine manufacturer URDF FK.
        candidates=[]
        tested=0
        for j1 in (-1.25,-1.0,-.8,-.55,-.3,.4,.65,1.0,1.3):
            for j2 in (.45,.7,.9,1.1,1.3,1.55):
                for j3 in (-.35,0,.35):
                    for j4 in (.8,1.05,1.3):
                        cfg=dict(q_pick,openarm_right_joint1=j1,openarm_right_joint2=j2,
                                 openarm_right_joint3=j3,openarm_right_joint4=j4)
                        if any(not (float(info[name][1][8])<=value<=float(info[name][1][9]))
                               for name,value in cfg.items()):
                            continue
                        tested+=1
                        install(cfg)
                        xyz,quat=pose()
                        dx=abs(xyz[0]-pick_xyz[0]);dy=abs(xyz[1]-pick_xyz[1])
                        if not (dx>.51 or dy>.55):continue
                        if abs(xyz[2]-pick_xyz[2])>.12:continue
                        if math.dist(xyz,pick_xyz)<.55:continue
                        moved=(abs(j1-q_pick["openarm_right_joint1"]) +
                               .65*abs(j2-q_pick["openarm_right_joint2"]) +
                               .4*abs(j3-q_pick["openarm_right_joint3"]) +
                               .4*abs(j4-q_pick["openarm_right_joint4"]))
                        candidates.append((moved,cfg,xyz,quat))
        require(bool(candidates),
                "no candidate source-FK station pair with nonoverlapping tray floors and comparable heights")
        candidates.sort(key=lambda item:item[0])
        _,q_place,place_xyz,place_orientation=candidates[0]
        q_lift=dict(q_pick,openarm_right_joint2=q_pick["openarm_right_joint2"]+.14)
        def source_limit_safe(cfg):
            return all(float(info[name][1][8])-1e-5<=value<=float(info[name][1][9])+1e-5
                       for name,value in cfg.items())
        def source_fk(cfg):
            install(cfg)
            return pose()[0]
        # The first complete replay showed the earlier transfer joint target
        # actively descended through the pickup support (dropping the cube).
        # Plan *source-FK-checked* high-clearance motor waypoints, not invented
        # end-effector animation or a manually moved payload.
        lift_candidates=[]
        for delta in (.30,.42,.55,.70,.90,1.10):
            cfg=dict(q_pick,openarm_right_joint2=q_pick["openarm_right_joint2"]+delta)
            if not source_limit_safe(cfg):continue
            xyz=source_fk(cfg)
            if xyz[2]<pick_xyz[2]+.075:continue
            if math.dist(xyz[:2],pick_xyz[:2])>.26:continue
            lift_candidates.append((delta,cfg,xyz))
        require(lift_candidates,"source FK cannot generate a stable higher clearance pickup lift")
        lift_candidates.sort(key=lambda x:x[0])
        _,q_high_lift,high_lift_tcp=lift_candidates[0]
        def interpolated_z_profile(a,b):
            low=float("inf")
            for n in range(21):
                t=n/20
                cfg={name:a[name]+(b[name]-a[name])*t for name in a}
                low=min(low,source_fk(cfg)[2])
            return low
        high_options=[]
        for delta in (.15,.25,.35,.45,.55,.7,.85,1.05,1.25,1.45,1.7,1.9):
            for elbow in (-.7,-.5,-.25,0,.2,.45,.7,.95,1.2):
                cfg=dict(q_place,
                    openarm_right_joint2=q_place["openarm_right_joint2"]+delta,
                    openarm_right_joint4=q_place["openarm_right_joint4"]+elbow)
                if not source_limit_safe(cfg):continue
                xyz=source_fk(cfg)
                if xyz[2]<pick_xyz[2]+.035:continue
                if math.dist(xyz[:2],place_xyz[:2])>.52:continue
                min_z=interpolated_z_profile(q_high_lift,cfg)
                if min_z < pick_xyz[2]+.020:continue
                score=(math.dist(xyz[:2],place_xyz[:2])+
                       .25*delta+.12*abs(elbow))
                high_options.append((score,cfg,xyz,min_z))
        require(high_options,
                "no joint-interpolated transfer candidate found in broader source-FK search")
        high_options.sort(key=lambda x:x[0])
        _,q_high_transfer,high_transfer_tcp,transfer_path_min_z=high_options[0]
        for cfg in (q_pick,q_lift,q_high_lift,q_high_transfer,q_place):
            require(source_limit_safe(cfg),"candidate joint violates original source joint limit")
        install(q_pick)
        # Floor planes placed from published tray FLOOR size and a candidate
        # position derived from original source TCP center, *not* the viewer.
        def station(name,xyz,orientation,footprint_x,drop_m=0.0):
            # world up extent of an oriented cube; original plane is axis-aligned
            m=p.getMatrixFromQuaternion(orientation)
            vertical_half_extent=OBJECT_SIDE/2*sum(abs(m[6+i]) for i in range(3))
            floor_top=xyz[2]-vertical_half_extent-.002-drop_m
            # Engineering fixture alternative: an inset physical support pad,
            # not a modification of the independently drawn SORTCELL viewer.
            # The cube still rests on a gravity-collidable static surface.
            footprint_y=FLOOR_XY[1] if footprint_x==.46 else footprint_x
            col=p.createCollisionShape(p.GEOM_BOX,halfExtents=[
                footprint_x/2,footprint_y/2,FLOOR_DEPTH/2],
                physicsClientId=client)
            body=p.createMultiBody(baseMass=0,baseCollisionShapeIndex=col,
                basePosition=[xyz[0],xyz[1],floor_top-FLOOR_DEPTH/2],
                physicsClientId=client)
            return {"name":name,"body":body,"center_robot_xyz_m":[
                xyz[0],xyz[1],floor_top-FLOOR_DEPTH/2],
                "surface_height_robot_z_m":floor_top,
                "candidate_visual_stage_center_m":urdf_to_stage([
                    xyz[0],xyz[1],floor_top-FLOOR_DEPTH/2],spec),
                "source_floor_size_stage_m":[.46,.025,.50],
                "simulated_proposed_support_size_m":[footprint_x,FLOOR_DEPTH,footprint_y],
                "experimental_station_floor_drop_m":drop_m,
                "fixture_is_inset_support_alternative_not_original_stage":footprint_x<.46}
        # Source-supported grasp sweep proved a 60 mm tool-aligned cube,
        # positioned +20 mm in world X from the source TCP, can settle, close
        # and lift under gravity with sustained two-finger contacts.
        # Use EXACTLY that verified initialization; no object reposition later.
        pickup_cube_xyz=[pick_xyz[0]+.020,pick_xyz[1],pick_xyz[2]]
        pickup=station("proposed_pick_station",pickup_cube_xyz,pick_orientation,
                       pickup_support_width_m)
        deposit=station("proposed_sort_station",place_xyz,place_orientation,
                        deposit_support_width_m,deposit_floor_drop_m)
        # Original source joint space and original collision links.
        shape=p.createCollisionShape(p.GEOM_BOX,
              halfExtents=[OBJECT_SIDE/2]*3,physicsClientId=client)
        cube=p.createMultiBody(baseMass=OBJECT_MASS,baseCollisionShapeIndex=shape,
              basePosition=pickup_cube_xyz,baseOrientation=pick_orientation,physicsClientId=client)
        p.changeDynamics(cube,-1,lateralFriction=1.2,rollingFriction=.003,
                         physicsClientId=client)
        for name in right_fingers:
            require(abs(info[name][1][9]-.044)<1e-6,
                    "manufacturer finger max extension changed")
        source_mimic_joint=root.find("./joint[@name='openarm_right_finger_joint2']/mimic")
        require(source_mimic_joint is not None,"manufacturer finger mimic disappeared")
        require(source_mimic_joint.attrib.get("joint")=="openarm_right_finger_joint1",
                "wrong original source mimic master finger")
        require(abs(float(source_mimic_joint.attrib.get("multiplier","nan"))-1)<1e-8
                and abs(float(source_mimic_joint.attrib.get("offset","nan")))<1e-8,
                "unexpected manufacturer source mimic relation")
        source_mimic_constraint=None
        if enforce_right_source_finger_mimic:
            # PyBullet does NOT auto-implement URDF mimic. Mirror the declared
            # source equality q2=q1 using one master's motor and a simulated
            # gear constraint; this is not a mechanical transmission certificate.
            source_mimic_constraint=p.createConstraint(
                robot,info["openarm_right_finger_joint1"][0],
                robot,info["openarm_right_finger_joint2"][0],
                p.JOINT_GEAR,[0,1,0],[0,0,0],[0,0,0],physicsClientId=client)
            require(source_mimic_constraint>=0,"PyBullet could not create source mimic coupling")
            p.changeConstraint(source_mimic_constraint,gearRatio=-1,
                               erp=.5,maxForce=min(40.,float(info["openarm_right_finger_joint1"][1][10])),
                               physicsClientId=client)
        p.performCollisionDetection(physicsClientId=client)
        initial_overlap=sum(1 for c in p.getContactPoints(bodyA=robot,bodyB=cube,
                                     physicsClientId=client) if c[8]<-1e-5)
        initial_floor_overlap=sum(1 for c in p.getContactPoints(bodyA=pickup["body"],
             bodyB=cube,physicsClientId=client) if c[8]<-1e-5)
        log=[]
        # Actual motor-stepped collision/contact telemetry. The source robot
        # retains its unchanged official meshes and link relationships.
        p.performCollisionDetection(physicsClientId=client)
        def pair_contacts():
            found={}
            for c in p.getContactPoints(bodyA=robot,bodyB=robot,physicsClientId=client):
                if c[8]>=-1e-5:continue
                la=("base" if c[3]<0 else
                    p.getJointInfo(robot,c[3],physicsClientId=client)[12].decode())
                lb=("base" if c[4]<0 else
                    p.getJointInfo(robot,c[4],physicsClientId=client)[12].decode())
                pair=tuple(sorted([la,lb]))
                found[pair]=min(float(c[8]),found.get(pair,0))
            return found
        original_initial_self_contacts=pair_contacts()
        source_link_names={
            j:p.getJointInfo(robot,j,physicsClientId=client)[12].decode()
            for j in range(p.getNumJoints(robot,physicsClientId=client))}
        def set_motors(q,closure):
            for name,target in q.items():
                j,meta=info[name]
                if name in right_fingers:
                    # Original source prismatic limits remain unchanged.
                    # Target margin leaves servo/contact tracking headroom.
                    target=(finger_margin_m if closure==0 else .044-finger_margin_m)
                # Original joints and URDF hard limits stay untouched. Vary only
                # the simulated finger motor's tracking dynamics; do not clamp
                # joint states or fabricate a successful contact outcome.
                if enforce_right_source_finger_mimic and name=="openarm_right_finger_joint2":
                    # Slave is passive; source URDF mimic gear transfers motion.
                    p.setJointMotorControl2(robot,j,p.VELOCITY_CONTROL,
                                             force=0,physicsClientId=client)
                    continue
                if name in right_fingers:
                    p.setJointMotorControl2(robot,j,p.POSITION_CONTROL,
                        targetPosition=target,
                        force=min(40.0,float(meta[10]))*finger_motor_force_fraction,
                        maxVelocity=finger_motor_max_velocity_m_s,
                        positionGain=finger_motor_position_gain,
                        physicsClientId=client)
                else:
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
            self_contacts=pair_contacts()
            fixture_contacts={
                name:[c for c in p.getContactPoints(bodyA=robot,bodyB=station["body"],
                    physicsClientId=client) if c[8]<-1e-5]
                for name,station in (("pickup",pickup),("deposit",deposit))}
            # Joint values are sampled from PyBullet's actual simulated states,
            # never the requested motor commands.
            current_joint_positions={
                name:round(p.getJointState(robot,meta[0],physicsClientId=client)[0],8)
                for name,meta in info.items() if name in home
            }
            unexpected_payload_link_contacts=sorted({
                source_link_names[c[3]] for c in contacts if c[3]>=0 and
                c[8]<.002 and source_link_names[c[3]] not in (
                   "openarm_right_hand",
                   "openarm_right_left_finger","openarm_right_right_finger")
            })
            item={
                "phase":label,"frame":step,"object_xyz_m":[round(x,6) for x in xyz],
                "tcp_xyz_m":[round(x,6) for x in tcp],
                "relative_tcp_object_m":round(math.dist(xyz,tcp),6),
                "finger_touch_links":right_touch,"bilateral_finger_contact":len(right_touch)==2,
                "pickup_floor_contacts":floor_contacts["pickup"],
                "deposit_floor_contacts":floor_contacts["deposit"],
                "source_robot_joint_positions":current_joint_positions,
                "source_robot_self_penetrations":[
                    {"link_pair":list(pair),"depth_m":round(depth,7)}
                    for pair,depth in sorted(self_contacts.items())],
                "source_robot_fixture_penetrations":{
                    name: [{"robot_link":source_link_names[c[3]] if c[3]>=0 else "base",
                            "depth_m":round(float(c[8]),7)} for c in rows]
                    for name,rows in fixture_contacts.items() if rows},
                "unexpected_payload_robot_link_contacts":unexpected_payload_link_contacts,
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
        # Reuse only the gravity-on, supported grasp that actually passed the
        # independent 18-trial source contact sweep (trial 16).
        sequence=[
            phase("settle_open_gripper",q_pick,.044,100),
            phase("grasp_close_source_fingers",q_pick,0,220),
            phase("lift_under_gravity",q_lift,0,180),
            phase("raise_to_source_fk_clearance",q_high_lift,0,240),
            phase("source_fk_clearance_transfer",q_high_transfer,0,480),
            phase("lower_to_proposed_sort_station",q_place,0,320),
            phase("release_open_source_fingers",q_place,.044,160),
        ]
        if reset_via_source_clearance:
            # Retrace the previously FK-checked lifted corridor after release,
            # instead of moving directly across the fixture during reset.
            # This changes only the source-valid joint motor path.
            sequence.extend([
                phase("reset_retract_to_source_clearance",q_high_transfer,.044,320),
                phase("reset_reverse_source_transfer",q_high_lift,.044,480),
                phase("reset_robot_without_object_attachment",q_pick,.044,180),
            ])
        else:
            sequence.append(phase("reset_robot_without_object_attachment",q_pick,.044,180))
        final=sequence[-1]["last"]
        release=sequence[6]["last"]
        transported=sequence[4]["last"]
        cube_start=sequence[0]["last"]["object_xyz_m"]
        cube_place=release["object_xyz_m"]
        measured_displacement=math.dist(cube_start,cube_place)
        floor_contact=final["deposit_floor_contacts"]>0
        cube_deposit_distance=math.dist(final["object_xyz_m"],place_xyz)
        pick_clearance=sequence[2]["last"]["pickup_floor_contacts"]==0
        clearance_maintained=(sequence[3]["last"]["pickup_floor_contacts"]==0
             and sequence[4]["last"]["pickup_floor_contacts"]==0)
        grasp_stable=(sequence[1]["bilateral_contact_samples"]>=18
            and sequence[2]["bilateral_contact_samples"]>=15
            and sequence[3]["bilateral_contact_samples"]>=15
            and pick_clearance and clearance_maintained)
        transfer_retent=transported["bilateral_finger_contact"] and transported["relative_tcp_object_m"]<.035
        full_candidate_success=(initial_overlap==0 and initial_floor_overlap==0 and
             grasp_stable and transfer_retent and floor_contact
             and cube_deposit_distance<.10 and measured_displacement>.08)
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
                "source_fk_station_poses_tested":tested,
                "compatible_nonoverlapping_station_candidates":len(candidates),
                "candidate_place_arm_joint_positions_rad":{
                    k:round(v,6) for k,v in q_place.items() if k.startswith("openarm_right_joint")},
                "candidate_tcp_height_difference_m":round(abs(pick_xyz[2]-place_xyz[2]),6),
                "tray_footprints_overlap_xy":False,
                "source_fk_high_lift_tcp_m":[round(v,6) for v in high_lift_tcp],
                "source_fk_high_transfer_tcp_m":[round(v,6) for v in high_transfer_tcp],
                "source_fk_interpolated_transfer_min_tcp_z_m":round(transfer_path_min_z,6),
                "source_fk_high_transfer_candidates_tested":len(high_options),
                "source_fk_validated_original_source_limits":True,
                "proposed_fixture_stations":[pickup,deposit],
                "candidate_deposit_floor_drop_m":deposit_floor_drop_m,
                "candidate_reset_via_source_clearance":reset_via_source_clearance,
                "candidate_fixture_footprints_m":[
                     [pickup_support_width_m,pickup["simulated_proposed_support_size_m"][2]],
                     [deposit_support_width_m,deposit["simulated_proposed_support_size_m"][2]]],
                "same_as_existing_sortcell_viewer_layout":False,
                "physical_mount_calibrated":False,
                "visual_cad_v11_registered_to_urdf_v10":False,
                "all_stage_geometry_tested":False,
            },
            "cycle":{
                "stages":sequence,
                "initial_robot_cube_overlap_contacts":initial_overlap,
                "initial_cube_pick_floor_overlap_contacts":initial_floor_overlap,
                "supported_grasp_seed_source":"strict passing trial 16 from source-supported grasp sweep",
                "supported_grasp_cube_world_xy_offset_m":[.02,0],
                "supported_grasp_cube_orientation":"source_tool_aligned",
                "experimental_source_finger_limit_margin_m":finger_margin_m,
                "experimental_source_finger_motor_force_fraction":finger_motor_force_fraction,
                "experimental_source_finger_motor_position_gain":finger_motor_position_gain,
                "experimental_source_finger_motor_max_velocity_m_s":finger_motor_max_velocity_m_s,
                "manufacturer_source_right_finger2_mimics_finger1":True,
                "manufacturer_source_mimic_multiplier":1,
                "pybullet_source_mimic_constraint_installed":enforce_right_source_finger_mimic,
                "source_mimic_only_master_motor_commanded":enforce_right_source_finger_mimic,
                "max_original_source_mimic_joint_tracking_error_m":round(
                     max(abs(item["source_robot_joint_positions"]["openarm_right_finger_joint1"]-
                             item["source_robot_joint_positions"]["openarm_right_finger_joint2"])
                         for item in log),8),
                "finger_motor_modified_source_joint_hard_limits":False,
                "original_source_finger_joint_hard_limits_unchanged":True,
                "supported_grasp_stays_attached_to_physics_only":True,
                "grasp_and_lift_stable":grasp_stable,
                "clearance_maneuver_remained_off_pickup_floor":clearance_maintained,
                "object_travel_m":round(measured_displacement,6),
                "object_initial_center_robot_m":[round(x,6) for x in pickup_cube_xyz],
                "last_place_cube_distance_to_tcp_m":round(cube_deposit_distance,6),
                "lift_clear_of_pickup_floor":pick_clearance,
                "transfer_finger_retention_test":transfer_retent,
                "object_on_deposit_floor_after_release_and_reset":floor_contact,
                "numerical_full_cycle_test_passed":full_candidate_success,
                "contact_observations":log,
                "original_source_initial_self_contact_pairs":[
                    {"link_pair":list(pair),"depth_m":round(depth,7)}
                    for pair,depth in sorted(original_initial_self_contacts.items())],
                "actual_motor_joint_telemetry_recorded":True,
                "original_source_self_collision_reported_not_suppressed":True,
                "proposed_station_robot_fixture_contacts_reported":True,
                "unexpected_robot_object_link_contacts_reported":True,
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
                "real object pose sensing and registered source-matched tool orientation",
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
    ap.add_argument("--finger-margin-m",type=float,default=0.0)
    ap.add_argument("--pickup-support-width-m",type=float,default=.46)
    ap.add_argument("--deposit-support-width-m",type=float,default=.46)
    ap.add_argument("--deposit-floor-drop-m",type=float,default=0.0)
    ap.add_argument("--reset-via-clearance",action="store_true")
    ap.add_argument("--finger-force-fraction",type=float,default=1.)
    ap.add_argument("--finger-position-gain",type=float,default=.1)
    ap.add_argument("--finger-max-velocity-m-s",type=float,default=.3)
    ap.add_argument("--enforce-source-right-finger-mimic",action="store_true")
    args=ap.parse_args()
    r=run(args.urdf,args.trajectory,args.stage,args.output,
          finger_margin_m=args.finger_margin_m,
          pickup_support_width_m=args.pickup_support_width_m,
          deposit_support_width_m=args.deposit_support_width_m,
          deposit_floor_drop_m=args.deposit_floor_drop_m,
          reset_via_source_clearance=args.reset_via_clearance,
          finger_motor_force_fraction=args.finger_force_fraction,
          finger_motor_position_gain=args.finger_position_gain,
          finger_motor_max_velocity_m_s=args.finger_max_velocity_m_s,
          enforce_right_source_finger_mimic=args.enforce_source_right_finger_mimic)
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

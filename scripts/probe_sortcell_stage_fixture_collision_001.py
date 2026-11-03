#!/usr/bin/env python3
"""Replay source OpenArm trajectory against exact SORTCELL-authored fixture boxes.

The workcell's stage is *not* published manufacturer geometry; these are the
existing authored boxes in its Teardown script, imported without artistic
alteration. Robot meshes remain original official OpenArm v1.0 and thus are
not revision-matched to the independently published v1.1 viewer CAD.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.audit_sortcell_openarm_collision_timing_001 import source_meshes,fetch_source_meshes
from scripts.probe_sortcell_source_contact_frame_gripper_001 import (
    extract_scene_contract, stage_to_urdf, urdf_to_stage,
)
from scripts.solve_sortcell_openarm_pybullet_001 import sha,require

SCHEMA="hardware_splicer.sortcell_source_fixture_candidate_collision.v1"

# Exact native Teardown calls already present in buildWorkcell(). Any edit
# requires reconciling this adapter with the updated stage before CI passes.
BOX_CONTRACT=[
  ("stage_top","box(3.46,.016,1.77,steel,-.13,.405,.13);",
   [3.46,.016,1.77],[-.13,.405,.13]),
  ("conveyor_belt","box(2.30,.012,.41,carbon,-.55,.557,.06);",
   [2.30,.012,.41],[-.55,.557,.06]),
  ("robot_base_adapter","box(.48,.028,.48,base,.88,.585,-.59);",
   [.48,.028,.48],[.88,.585,-.59]),
]
TRAY_BOTTOM="box(.46,.025,.50,blue,x,.465,.75);"
TRAY_SIDE_X="for(const dx of [-.23,.23])box(.018,.13,.50,bin,x+dx,.54,.75);"
TRAY_SIDE_Z="for(const dz of [-.24,.24])box(.46,.13,.019,bin,x,.54,.75+dz);"

def fixtures(stage_source:str,spec:dict)->list[dict]:
    result=[]
    for name,text,size,pos in BOX_CONTRACT:
        require(text in stage_source,"workcell fixture source diverged: "+name)
        result.append({"name":name,"stage_size_m":size,"stage_center_m":pos})
    for entry in (TRAY_BOTTOM,TRAY_SIDE_X,TRAY_SIDE_Z):
        require(entry in stage_source,"source tray dimension/position contract changed")
    for i,x in enumerate([v[0] for k,v in spec["source_targets_stage_m"].items() if k.endswith("_tray")]):
        prefix=["precision","electronics","reject"][i]
        result.append({"name":prefix+"_tray_floor",
                       "stage_size_m":[.46,.025,.50],"stage_center_m":[x,.465,.75]})
        for side in (-1,1):
            result.append({"name":prefix+"_tray_side_x"+str(side),
                           "stage_size_m":[.018,.13,.50],
                           "stage_center_m":[x+side*.23,.54,.75]})
            result.append({"name":prefix+"_tray_side_z"+str(side),
                           "stage_size_m":[.46,.13,.019],
                           "stage_center_m":[x,.54,.75+side*.24]})
    require(len(result)==18,"expected 3 base + 15 tray native source fixtures")
    return result

def run(urdf:Path,trajectory:Path,stage:Path,output:Path)->dict:
    import pybullet as p
    source=stage.read_text()
    spec=extract_scene_contract(source)
    fixture_list=fixtures(source,spec)
    urdf_source=urdf.read_bytes()
    motion=json.loads(trajectory.read_text())
    require(motion["official_urdf"]["sha256"]==sha(urdf_source),
            "not the pinned source URDF used by original trajectory")
    require(len(motion["trajectory"])==73,"source trajectory sample set drifted")
    output.mkdir(parents=True,exist_ok=True)
    require(not any(output.iterdir()),"destination must be empty")
    root=ET.fromstring(urdf_source)
    for link in root.findall("link"):
        for visual in link.findall("visual"):link.remove(visual)
    mesh_root=(output/"openarm_description").resolve()
    meshes=source_meshes(root,mesh_root)
    fetch_source_meshes(meshes,mesh_root)
    urdf_local=output/"source_robot_with_original_collisions.urdf"
    urdf_local.write_bytes(ET.tostring(root,encoding="utf-8",xml_declaration=True))
    client=p.connect(p.DIRECT)
    try:
        flags=(p.URDF_MAINTAIN_LINK_ORDER | p.URDF_USE_SELF_COLLISION |
               p.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT)
        robot=p.loadURDF(str(urdf_local),useFixedBase=True,flags=flags,physicsClientId=client)
        ids={p.getJointInfo(robot,i,physicsClientId=client)[1].decode():i
             for i in range(p.getNumJoints(robot,physicsClientId=client))}
        tcp=ids["openarm_right_hand_tcp_joint"]
        fixture_ids={}
        for fixture in fixture_list:
            w,h,d=fixture["stage_size_m"]
            # Display transform x'=x, y'=z, z'=-y; transpose stage
            # X/Y/Z box widths to original-source URDF X/Y/Z, *with scale*.
            scale=spec["display_robot_scale"]
            half=[w/(2*scale),d/(2*scale),h/(2*scale)]
            center=stage_to_urdf(fixture["stage_center_m"],spec)
            require(all(x>0 for x in half),"degenerate source fixture")
            shape=p.createCollisionShape(p.GEOM_BOX,halfExtents=half,
                                         physicsClientId=client)
            fixture_ids[fixture["name"]]=p.createMultiBody(
                baseMass=0,baseCollisionShapeIndex=shape,
                basePosition=center,physicsClientId=client)
        hit_counts={key:0 for key in fixture_ids}
        first_hits={}
        hit_frames=0
        tcp_min_distances={name:float("inf") for name in spec["source_targets_stage_m"]}
        reference_waypoints={}
        for frame in motion["trajectory"]:
            for name,q in frame["joint_positions"].items():
                p.resetJointState(robot,ids[name],q,physicsClientId=client)
            p.performCollisionDetection(physicsClientId=client)
            touching=[]
            for fixture_name,fixture_id in fixture_ids.items():
                cs=[c for c in p.getContactPoints(bodyA=robot,bodyB=fixture_id,
                                                  physicsClientId=client)
                    if c[8]<-1e-5]
                if cs:
                    hit_counts[fixture_name]+=1
                    touching.append(fixture_name)
                    first_hits.setdefault(fixture_name,{
                       "frame":frame["sample_index"],
                       "deepest_overlap_m":round(min(c[8] for c in cs),7),
                       "robot_links":sorted({c[3] for c in cs}),
                    })
            if touching:hit_frames+=1
            stage_tcp=urdf_to_stage(list(p.getLinkState(
                robot,tcp,computeForwardKinematics=True,physicsClientId=client)[4]),spec)
            for name,target in spec["source_targets_stage_m"].items():
                tcp_min_distances[name]=min(tcp_min_distances[name],
                    math.dist(stage_tcp,target))
            if frame["sample_index"] in (0,12,24,36,48,60,72):
                reference_waypoints[str(frame["sample_index"])]={
                    "stage_tcp_xyz_m":[round(x,6) for x in stage_tcp],
                    "segment":frame["segment"]}
        receipt={
          "schema_version":SCHEMA,
          "input_urdf_sha256":sha(urdf_source),
          "source_stage_script_sha256":sha(source.encode()),
          "robot_collision_meshes":len(meshes),
          "fixture_source":"existing literal box() calls in assets/teardown/hs_sort_workcell_main.js",
          "stage_fixture_collision_shapes":len(fixture_list),
          "stage_fixture_shape_kind":"existing stage-authored boxes, not external industrial CAD",
          "candidate_display_frame":spec,
          "robot_path_frame_count":len(motion["trajectory"]),
          "robot_fixtures_contact_frame_count":hit_frames,
          "fixture_contact_frame_counts":hit_counts,
          "fixture_first_contact":first_hits,
          "min_tcp_distance_to_original_scene_targets_m":{
              k:round(v,6) for k,v in tcp_min_distances.items()},
          "original_trajectory_stage_tcp_samples":reference_waypoints,
          "boundaries":{
              "original_robot_meshes_used":True,
              "original_workcell_stage_box_dimensions_used":True,
              "all_workcell_fixture_geometry_represented":False,
              "collision_freedom_claimed":False,
              "source_v10_urdf_registered_to_independent_v11_visual_cad":False,
              "physical_mount_and_targets_calibrated":False,
              "source_trajectory_executes_real_sort":False,
              "real_robot_motion_authorized":False,
          },
        }
        (output/"SOURCE_STAGE_FIXTURE_COLLISION.json").write_text(
            json.dumps(receipt,indent=2)+"\n")
        (output/"SCOPE.md").write_text(
            "# SORTCELL stage fixture candidate collision audit\n\n"
            "Robot meshes: original Enactic OpenArm v1.0 collision STLs; "
            "workcell fixtures: exact dimensions and coordinates from the unchanged "
            "Teardown scene. This only covers platform, conveyor surface, adaptor base, "
            "and three tray bottoms/walls, not all stage details (such as rods and rollers). "
            "The scene transform is uncalibrated and visual OpenArm is separately published "
            "v1.1 CAD; do not infer physical collision safety. 73 existing source-trajectory "
            "frames are checked against these stage geometry boxes. No robot control.\n")
        return receipt
    finally:
        p.disconnect(physicsClientId=client)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urdf",required=True,type=Path)
    ap.add_argument("--trajectory",required=True,type=Path)
    ap.add_argument("--stage",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    r=run(a.urdf,a.trajectory,a.stage,a.output)
    print(json.dumps({
        "native_fixture_collision_shapes":r["stage_fixture_collision_shapes"],
        "robot_fixture_contact_frames":r["robot_fixtures_contact_frame_count"],
        "min_tcp_distance_to_original_stage_target_m":
          r["min_tcp_distance_to_original_scene_targets_m"],
        "physical_motion_authorized":r["boundaries"]["real_robot_motion_authorized"],
    },indent=2))

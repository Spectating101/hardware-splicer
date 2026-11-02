#!/usr/bin/env python3
"""Independently accept numerical OpenArm source-mimic sorting, never hardware.

Verifies real motor-stepped source joint states, source URDF mimic relation,
bilateral finger contact, object transfer/release and unchanged manufacturer
collision meshes. The original source wrist overlap and registration gaps
always deny any physical use.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SCHEMA="hardware_splicer.sortcell_original_source_mimic_numerical_gate.v1"
PHASES=(
 "settle_open_gripper","grasp_close_source_fingers","lift_under_gravity",
 "raise_to_source_fk_clearance","source_fk_clearance_transfer",
 "lower_to_proposed_sort_station","release_open_source_fingers",
 "reset_retract_to_source_clearance","reset_reverse_source_transfer",
 "reset_robot_without_object_attachment"
)

def analyze(urdf_path:Path,master_path:Path,slave_path:Path)->dict:
    urdf=urdf_path.read_bytes()
    digest=hashlib.sha256(urdf).hexdigest()
    root=ET.fromstring(urdf)
    m=root.find("./joint[@name='openarm_right_finger_joint2']/mimic")
    if m is None or m.get("joint")!="openarm_right_finger_joint1":
        raise ValueError("source manufacturer gripper mimic relation missing")
    if abs(float(m.get("multiplier"))-1)>1e-10 or abs(float(m.get("offset")))>1e-10:
        raise ValueError("source gripper mimic is not equal master/slave travel")
    limits={}
    for j in root.findall("joint"):
        if j.get("type") not in ("prismatic","revolute"):continue
        lim=j.find("limit")
        if lim is None:raise ValueError("missing source limit")
        limits[j.get("name")]=(float(lim.get("lower")),float(lim.get("upper")))
    if len(limits)!=18:raise ValueError("original OpenArm v1.0 18 joints changed")
    outcomes=[]
    for name,path in [("source_single_master_default_force",master_path),
                      ("source_single_master_half_force",slave_path)]:
        data=json.loads(path.read_text())
        c=data["cycle"]
        layout=data["candidate_layout"]
        if data["original_urdf_sha256"]!=digest or data["source_collision_meshes"]!=11:
            raise ValueError("original pinned source collision provenance changed")
        if not c["manufacturer_source_right_finger2_mimics_finger1"]:
            raise ValueError("missing original manufacturer mimic")
        if c["manufacturer_source_mimic_multiplier"]!=1:
            raise ValueError("source manufacturer mimic multiplier changed")
        if not c["pybullet_source_mimic_constraint_installed"] or not c["source_mimic_only_master_motor_commanded"]:
            raise ValueError("not a single master motor plus coupled passive slave")
        if c["finger_motor_modified_source_joint_hard_limits"]:
            raise ValueError("hard source joint limits cannot be changed")
        if c["numerical_full_cycle_test_passed"] is not True:
            raise ValueError("source-coupled full numerical sort failed: "+name)
        if c["physical_sorter_authorized"] or not c["no_object_attach_constraints"] or not c["no_object_pose_teleports_after_initialization"]:
            raise ValueError("artificial object motion or hardware authorization")
        if c["experimental_source_finger_limit_margin_m"]!=.003:
            raise ValueError("unexpected source gripper command margin")
        if layout["candidate_reset_via_source_clearance"] is not True or layout["candidate_deposit_floor_drop_m"]!=.01:
            raise ValueError("source-checked clearance corridor/layout not replayed")
        if layout["candidate_fixture_footprints_m"]!=[[.05,.05],[.46,.5]]:
            raise ValueError("unapproved numerical fixture change")
        if tuple(x["phase"] for x in c["stages"])!=PHASES:
            raise ValueError("full contact cycle phases missing")
        events=c["contact_observations"]
        if len(events)<270:raise ValueError("insufficient motor contact samples")
        sampled_mimic_error=0.
        overshoot=0.
        fixture_count=0
        new_wrist_pairs=set()
        worsening_wrist=0.
        baseline={tuple(x["link_pair"]):float(x["depth_m"])
                  for x in c["original_source_initial_self_contact_pairs"]}
        if len(baseline)!=2:raise ValueError("original wrist collision pair baseline changed")
        by_phase={phase:[] for phase in PHASES}
        for e in events:
            phase=e["phase"];by_phase[phase].append(e)
            positions=e["source_robot_joint_positions"]
            if set(positions)!=set(limits):
                raise ValueError("missing motor-state source joint")
            sampled_mimic_error=max(sampled_mimic_error,abs(
                positions["openarm_right_finger_joint1"]-
                positions["openarm_right_finger_joint2"]))
            for joint,value in positions.items():
                lo,hi=limits[joint]
                if value<lo or value>hi:overshoot+=1
            for collisions in e["source_robot_fixture_penetrations"].values():
                fixture_count+=len(collisions)
            if e["unexpected_payload_robot_link_contacts"]:
                raise ValueError("unexpected robot/payload link")
            for x in e["source_robot_self_penetrations"]:
                pair=tuple(x["link_pair"])
                if pair not in baseline:new_wrist_pairs.add(pair)
                else:worsening_wrist=max(worsening_wrist,
                                        baseline[pair]-float(x["depth_m"]))
        if overshoot or fixture_count or new_wrist_pairs or worsening_wrist>.0001:
            raise ValueError("numerical mimic still intersects fixtures or violates joint limits")
        # Equality under a simulated gear constraint has finite solver
        # compliance; expose its maximum error rather than claiming ideal gearing.
        if sampled_mimic_error>.005:
            raise ValueError("source gear mimic moves >5mm out of sync")
        if abs(sampled_mimic_error-c["max_original_source_mimic_joint_tracking_error_m"])>1e-7:
            raise ValueError("scenario-reported mimic error disagrees with independent joint telemetry")
        for phase in PHASES[2:6]:
            if not all(r["bilateral_finger_contact"] for r in by_phase[phase]):
                raise ValueError("finger contact lost in "+phase)
        for phase in PHASES[6:]:
            if any(r["bilateral_finger_contact"] for r in by_phase[phase]):
                raise ValueError("gripper still gripping after release in "+phase)
            if any(not r["deposit_floor_contacts"] for r in by_phase[phase]):
                raise ValueError("payload not supported after release in "+phase)
        if not c["object_on_deposit_floor_after_release_and_reset"] or not c["lift_clear_of_pickup_floor"]:
            raise ValueError("payload transport or release failed")
        outcomes.append({
            "trial":name,
            "source_gripper_force_fraction":c["experimental_source_finger_motor_force_fraction"],
            "numerical_sort_completed":True,
            "sampled_motor_frames":len(events),
            "max_mimic_slave_position_error_m":round(sampled_mimic_error,8),
            "source_joint_limit_exceedance_samples":overshoot,
            "sampled_fixture_penetrations":fixture_count,
            "source_self_pair_count_at_start":len(baseline),
            "new_wrist_pairs":len(new_wrist_pairs),
            "additional_wrist_overlap_above_0p1mm":False,
            "transfer_bilateral_sample_count":len(by_phase["source_fk_clearance_transfer"]),
            "payload_stays_in_destination_during_reset":True,
            "physical_actuator_mechanics_tested":False,
            "physical_hardware_authorized":False,
        })
    return {
      "schema_version":SCHEMA,
      "source_urdf_sha256":digest,
      "original_source_mimic_joint":"openarm_right_finger_joint2",
      "original_source_mimic_master":"openarm_right_finger_joint1",
      "original_source_mimic_multiplier":1.,
      "source_original_collision_mesh_geometry_unchanged":True,
      "original_robot_wrist_mesh_overlaps_remain":True,
      "source_joint_limits_unmodified":True,
      "numerical_contact_cycle_succeeded_in_both_cases":True,
      "trials":outcomes,
      "original_visual_v11_and_source_v10_registered":False,
      "continuous_collision_clearance_certified":False,
      "real_mechanical_gear_or_actuator_qualified":False,
      "physical_robot_motion_authorized":False,
      "physical_fabrication_authorized":False,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ("urdf","master","slave","output"):
        ap.add_argument("--"+k,required=True,type=Path)
    a=ap.parse_args()
    result=analyze(a.urdf,a.master,a.slave)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

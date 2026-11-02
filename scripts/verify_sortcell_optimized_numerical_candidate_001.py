#!/usr/bin/env python3
"""Independent acceptance for SORTCELL's *experimental* source-native repair.

Numerical task and sampled candidate support/arm contact clearance are distinct
from real robot safety, continuous collision proof and manufacturer joint limits.
The original robot URDF, visual viewer, and physical authorization are unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

EXPECTED=(
    "settle_open_gripper",
    "grasp_close_source_fingers",
    "lift_under_gravity",
    "raise_to_source_fk_clearance",
    "source_fk_clearance_transfer",
    "lower_to_proposed_sort_station",
    "release_open_source_fingers",
    "reset_retract_to_source_clearance",
    "reset_reverse_source_transfer",
    "reset_robot_without_object_attachment",
)

def accept(urdf:Path,baseline:Path,candidate:Path)->dict:
    source=urdf.read_bytes()
    digest=hashlib.sha256(source).hexdigest()
    original=json.loads(baseline.read_text())
    c=json.loads(candidate.read_text())
    if not (original["original_urdf_sha256"]==c["original_urdf_sha256"]==digest):
        raise ValueError("original manufacturer source URDF mismatch")
    root=ET.fromstring(source)
    limits={}
    for j in root.findall("joint"):
        if j.get("type") not in ("revolute","prismatic"):continue
        l=j.find("limit")
        if l is None:raise ValueError("source joint limit absent")
        limits[j.get("name")]=(float(l.get("lower")),float(l.get("upper")))
    if len(limits)!=18:raise ValueError("source movable joint inventory changed")
    cfg=c["candidate_layout"];cy=c["cycle"]
    if not original["cycle"]["numerical_full_cycle_test_passed"]:
        raise ValueError("original baseline not reproducible")
    if cfg["candidate_reset_via_source_clearance"] is not True:
        raise ValueError("source corridor return missing")
    if abs(cfg["candidate_deposit_floor_drop_m"]-.010)>1e-9:
        raise ValueError("10mm lowered destination fixture not selected")
    if cfg["candidate_fixture_footprints_m"]!=[[.05,.05],[.46,.5]]:
        raise ValueError("proposed fixture dimensions do not match tested design")
    if abs(cy["experimental_source_finger_limit_margin_m"]-.003)>1e-9:
        raise ValueError("source finger command headroom must be 3mm")
    if cy["original_source_finger_joint_hard_limits_unchanged"] is not True:
        raise ValueError("source joint hard limits changed")
    if not cy["numerical_full_cycle_test_passed"]:
        raise ValueError("complete gravity-on sort did not pass")
    if cy["physical_sorter_authorized"] is not False:
        raise ValueError("real hardware authority unexpectedly granted")
    if cy["no_object_attach_constraints"] is not True or cy["no_object_pose_teleports_after_initialization"] is not True:
        raise ValueError("nonphysical payload attachment/movement")
    phases=cy["stages"]
    if tuple(s["phase"] for s in phases)!=EXPECTED:
        raise ValueError("incomplete ten-phase source motion")
    rows=cy["contact_observations"]
    groups={label:[r for r in rows if r["phase"]==label] for label in EXPECTED}
    if len(rows)<270:raise ValueError("insufficient full original motor telemetry")
    for p in phases:
        samples=groups[p["phase"]]
        if samples[-1]!=p["last"] or p["series_sample_count"]!=len(samples):
            raise ValueError("trace phase/sample inconsistency")
    for phase in ("lift_under_gravity","raise_to_source_fk_clearance",
                  "source_fk_clearance_transfer","lower_to_proposed_sort_station"):
        if not all(r["bilateral_finger_contact"] for r in groups[phase]):
            raise ValueError("lost real bilateral source gripper contact: "+phase)
    for phase in ("release_open_source_fingers","reset_retract_to_source_clearance",
                  "reset_reverse_source_transfer","reset_robot_without_object_attachment"):
        if any(r["bilateral_finger_contact"] for r in groups[phase]):
            raise ValueError("payload still gripped after source open action")
    for phase in ("source_fk_clearance_transfer","lower_to_proposed_sort_station"):
        if any(r["pickup_floor_contacts"] for r in groups[phase]):
            raise ValueError("cube struck pickup support during carry")
    for phase in ("release_open_source_fingers","reset_retract_to_source_clearance",
                  "reset_reverse_source_transfer","reset_robot_without_object_attachment"):
        if any(not r["deposit_floor_contacts"] for r in groups[phase]):
            raise ValueError("deposited cube lost support during source release/reset")
    old_pairs={tuple(x["link_pair"]):float(x["depth_m"])
               for x in cy["original_source_initial_self_contact_pairs"]}
    if len(old_pairs)!=2:raise ValueError("published original-source wrist baseline changed")
    fixture_records=0
    added_pairs=set()
    max_additional_overlap=0
    significant_violations=0
    exact_violations=0
    maximum_joint_excess=0.
    for i,r in enumerate(rows):
        if set(r["source_robot_joint_positions"])!=set(limits):
            raise ValueError("source joint telemetry missing")
        for name,val in r["source_robot_joint_positions"].items():
            low,high=limits[name]
            delta=max(0.,low-val,val-high)
            if delta>0:
                exact_violations+=1
                significant_violations+=delta>1e-4
                maximum_joint_excess=max(maximum_joint_excess,delta)
        for fixture,contacts in r["source_robot_fixture_penetrations"].items():
            fixture_records+=len(contacts)
        if r["unexpected_payload_robot_link_contacts"]:
            raise ValueError("unexpected robot contact with the payload")
        for contact in r["source_robot_self_penetrations"]:
            pair=tuple(contact["link_pair"])
            if pair not in old_pairs:
                added_pairs.add(pair)
            elif float(contact["depth_m"])<old_pairs[pair]-.0001:
                max_additional_overlap=max(max_additional_overlap,
                           old_pairs[pair]-float(contact["depth_m"]))
    if fixture_records or added_pairs or max_additional_overlap:
        raise ValueError("candidate collision regression in measured source contact trace")
    if significant_violations>1:
        raise ValueError("source actuator margin candidate regressed beyond 1 significant overshoot")
    if max_additional_overlap>0:
        raise ValueError("worsening wrist overlap")
    if cfg["same_as_existing_sortcell_viewer_layout"] or cfg["visual_cad_v11_registered_to_urdf_v10"]:
        raise ValueError("engineering fixture/visual version unexpectedly asserted calibrated")
    return {
        "schema_version":"hardware_splicer.sortcell_source_clearance_candidate_acceptance.v1",
        "manufacturer_urdf_sha256":digest,
        "source_collision_meshes":c["source_collision_meshes"],
        "full_original_source_10_phase_numerical_sort":True,
        "motor_contact_observations":len(rows),
        "transfer_samples_with_bilateral_fingers":len(groups["source_fk_clearance_transfer"]),
        "return_path_mode":"original_source_reverse_clearance_corridor",
        "candidate_pickup_support_width_m":.05,
        "candidate_destination_support_m":[.46,.5],
        "candidate_destination_drop_m":.01,
        "source_gripper_target_margin_m":.003,
        "robot_fixture_penetrations_at_sampled_steps":fixture_records,
        "new_source_self_penetration_pairs":len(added_pairs),
        "source_wrist_overlap_additional_depth_m":round(max_additional_overlap,7),
        "persistent_published_original_source_wrist_overlap_pairs":len(old_pairs),
        "source_joint_limit_exact_signed_overshoot_count":exact_violations,
        "source_joint_limit_overshoots_above_diagnostic_0p1mm":significant_violations,
        "source_joint_limit_worst_overshoot":round(maximum_joint_excess,8),
        "source_joint_limit_clearance_certified":False,
        "continuous_collision_clearance_certified":False,
        "source_v1_0_to_visual_v1_1_registered":False,
        "complete_fixture_CAD_qualified":False,
        "physical_robot_motion_authorized":False,
        "physical_build_and_fabrication_authorized":False,
        "engineering_status":"numerical_candidate_with_remaining_source_wrist_and_joint_limit_hazards",
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--urdf",required=True,type=Path)
    ap.add_argument("--baseline",required=True,type=Path)
    ap.add_argument("--candidate",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    x=accept(a.urdf,a.baseline,a.candidate)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(x,indent=2)+"\n")
    print(json.dumps(x,indent=2))

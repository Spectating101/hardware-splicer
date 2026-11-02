#!/usr/bin/env python3
"""Independent OpenArm full sorting-cycle contact qualification ledger.

This does not execute real hardware or invent replacement robot geometry. It
audits all sampled PyBullet motor-driven frames from SORTCELL's numerical POC
and traces source-mesh self penetrations, fixture penetrations, and payload
collisions outside the actual original gripper. Separately inventories the
published original URDF v1.0 visual meshes versus the different v1.1 GLB
viewer model; no mesh/CAD frame registration is claimed.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

SCHEMA="hardware_splicer.sortcell_dynamic_cycle_contact_safety_audit.v1"
UNVERIFIED_V11_REV="0c0852bd76ee7026f97875d6eac789d189a0012a"
PERSISTENCE_DELTA_M=.0001
PENETRATION_THRESHOLD_M=-.00001

def require(yes:bool,reason:str):
    if not yes:raise ValueError("SORTCELL source-audit invalid: "+reason)

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def audit(cycle_path:Path,urdf_path:Path,scene_js:Path)->dict:
    c=json.loads(cycle_path.read_text())
    source=urdf_path.read_bytes()
    scene=scene_js.read_text()
    require(c["schema_version"]=="hardware_splicer.sortcell_source_robot_pick_place_candidate.v1",
            "unexpected scenario")
    require(c["original_urdf_sha256"]==sha(source),"source URDF provenance mismatch")
    require(c["cycle"]["numerical_full_cycle_test_passed"] is True,
            "numerical cycle has not passed")
    require(c["cycle"]["actual_motor_joint_telemetry_recorded"] is True,
            "actual motor joint states not captured")
    require(c["cycle"]["original_source_self_collision_reported_not_suppressed"] is True,
            "no untouched source collision diagnosis")
    require(c["cycle"]["no_object_attach_constraints"] is True,
            "fake gripper attachment forbidden")
    require(c["cycle"]["no_object_pose_teleports_after_initialization"] is True,
            "postspawn object reposition forbidden")
    root=ET.fromstring(source)
    require(root.tag=="robot" and root.attrib.get("name")=="openarm","wrong source robot")
    all_links={link.get("name") for link in root.findall("link")}
    source_movable={}
    for joint in root.findall("joint"):
        if joint.attrib.get("type") not in ("revolute","continuous","prismatic"):continue
        lo=joint.find("limit")
        require(lo is not None,"movable source joint without limits")
        name=joint.attrib.get("name")
        source_movable[name]={"lower":float(lo.attrib.get("lower","-inf")),
                              "upper":float(lo.attrib.get("upper","inf")),
                              "type":joint.attrib["type"]}
    require(len(source_movable)==18,"unexpected original source joint count")
    observed=c["cycle"]["contact_observations"]
    require(len(observed)>=150,"too few physical contact samples")
    initial=c["cycle"]["original_source_initial_self_contact_pairs"]
    require(isinstance(initial,list),"missing baseline source collision list")
    first={tuple(item["link_pair"]):float(item["depth_m"]) for item in initial}
    require(len(first)==len(initial),"duplicate source self-contact baseline pairs")
    for pair in first:
        require(len(pair)==2 and tuple(sorted(pair))==pair and all(n in all_links for n in pair),
                "original collision pair not source-named")
    phase_counts=Counter()
    source_self_counts=Counter()
    source_self_deepest={}
    source_fixture_counts=Counter()
    source_fixture_deepest={}
    unexpected_object_contacts=Counter()
    new_pair_first_observation={}
    deepening_first_observation={}
    violations=[]
    for n,row in enumerate(observed):
        phase=row["phase"]
        phase_counts[phase]+=1
        actual=row["source_robot_joint_positions"]
        require(set(actual)==set(source_movable),"joint telemetry does not cover all source joints")
        for joint,val in actual.items():
            lim=source_movable[joint]
            require(math.isfinite(val) and lim["lower"]-.001<=val<=lim["upper"]+.001,
                    "source joint position out of published limits at frame "+str(n)+" "+joint)
        pairs=row["source_robot_self_penetrations"]
        already=set()
        for item in pairs:
            pair=tuple(item["link_pair"])
            depth=float(item["depth_m"])
            require(pair not in already,"duplicate same-frame self collision")
            already.add(pair)
            require(tuple(sorted(pair))==pair and all(x in all_links for x in pair),
                    "source self-collision contains unknown link")
            require(math.isfinite(depth) and depth<PENETRATION_THRESHOLD_M,
                    "contact listed without significant signed penetration")
            source_self_counts[pair]+=1
            source_self_deepest[pair]=min(depth,source_self_deepest.get(pair,0.0))
            if pair not in first:
                new_pair_first_observation.setdefault(pair,{"phase":phase,"sample_index":n,"depth_m":depth})
            elif depth < first[pair]-PERSISTENCE_DELTA_M:
                deepening_first_observation.setdefault(pair,{
                    "phase":phase,"sample_index":n,"additional_penetration_m":round(first[pair]-depth,7)})
        fixtures=row["source_robot_fixture_penetrations"]
        require(set(fixtures).issubset({"pickup","deposit"}),
                "unexpected extra/unregistered stage fixture")
        for name,contacts in fixtures.items():
            for item in contacts:
                require(item["robot_link"] in all_links or item["robot_link"]=="base",
                        "fixture contact link not source-name")
                depth=float(item["depth_m"])
                require(depth<PENETRATION_THRESHOLD_M,"not a penetrating fixture contact")
                source_fixture_counts[(phase,name,item["robot_link"])]+=1
                source_fixture_deepest[(name,item["robot_link"])]=min(
                    source_fixture_deepest.get((name,item["robot_link"]),0),depth)
        off=row["unexpected_payload_robot_link_contacts"]
        require(isinstance(off,list),"unexpected link collision telemetry missing")
        for link in off:
            require(link in all_links,"unexpected payload contact not source-link named")
            unexpected_object_contacts[(phase,link)]+=1
    require(set(phase_counts)=={p["phase"] for p in c["cycle"]["stages"]},
            "phase coverage mismatch")
    min_observed_vel_ratio=None
    # This telemetry is sampled at 10 simulation steps, so it cannot certify
    # unsampled millisecond dynamics, acceleration or servo power.
    contacts={
        "source_self_initial_count":len(first),
        "source_self_initial_pairs":[{"links":list(pair),"depth_m":v}
                                     for pair,v in sorted(first.items())],
        "source_self_penetrating_sample_count":sum(bool(row["source_robot_self_penetrations"])
                                                  for row in observed),
        "source_self_all_pairs":[
            {"links":list(pair),"penetrating_samples":count,
             "initial_pose_pair":pair in first,
             "initial_penetration_m":first.get(pair),
             "deepest_observed_penetration_m":source_self_deepest[pair],
             "additional_depth_from_initial_m":round(max(0,first.get(pair,0)-source_self_deepest[pair]),7)}
            for pair,count in sorted(source_self_counts.items())],
        "new_pairs_after_initial_pose":[{"links":list(k),**v}
                                        for k,v in sorted(new_pair_first_observation.items())],
        "baseline_pairs_deepening_over_0p1mm":[{"links":list(k),**v}
                                                for k,v in sorted(deepening_first_observation.items())],
        "robot_fixture_penetrations_by_phase_link":[
            {"phase":phase,"fixture":fixture,"robot_link":link,"contact_records":count}
            for (phase,fixture,link),count in sorted(source_fixture_counts.items())],
        "robot_fixture_deepest_penetrations_m":[
            {"fixture":fixture,"robot_link":link,"depth_m":depth}
            for (fixture,link),depth in sorted(source_fixture_deepest.items())],
        "unexpected_robot_payload_link_contacts":[
            {"phase":phase,"robot_link":link,"observations":n}
            for (phase,link),n in sorted(unexpected_object_contacts.items())],
        "source_link_limits_checked_each_sample":True,
        "motor_contact_samples":len(observed),
        "phase_sample_counts":dict(phase_counts),
        "all_possible_collisions_assessed":False,
        "original_collision_intersections_safe_whitelisted":False,
        "source_robot_self_collision_freedom_verified":False,
    }
    visual_entries={}
    collision_entries={}
    for link in root.findall("link"):
        name=link.get("name")
        visual_entries[name]=[m.get("filename") for m in link.findall(".//visual//mesh")]
        collision_entries[name]=[m.get("filename") for m in link.findall(".//collision//mesh")]
    source_vis=sorted({m for items in visual_entries.values() for m in items})
    source_col=sorted({m for items in collision_entries.values() for m in items})
    require(all(n.startswith("package://openarm_description/") for n in source_vis),
            "visual source URDF references unexpected external asset")
    require(len(source_vis)>=10 and len(source_col)>=10,
            "missing official URDF collision/visual assets")
    require("sourceRoot.position.set(.88,.603,-.59)" in scene and
            "sourceRoot.rotation.x=-Math.PI/2" in scene and
            "sourceRoot.scale.setScalar(.93)" in scene,
            "viewer mount no longer matches original candidate math")
    require("sourcePartCount:542" in scene,
            "viewer original CAD part count declaration changed")
    require(UNVERIFIED_V11_REV in scene,"viewer source revision changed")
    registration={
        "physics_robot":"enactic/openarm_description original v1.0 URDF",
        "physics_urdf_sha256":sha(source),
        "source_urdf_links":len(all_links),
        "source_urdf_movable_joints":len(source_movable),
        "source_urdf_visual_mesh_reference_count":len(source_vis),
        "source_urdf_collision_mesh_reference_count":len(source_col),
        "original_source_visual_mesh_package_refs":source_vis,
        "per_link_visual_meshes":{k:v for k,v in visual_entries.items() if v},
        "visual_product":"Utsav92/openarm-3d-cad-assembly independent v1.1 542-part GLB",
        "visual_product_pinned_commit":UNVERIFIED_V11_REV,
        "original_visual_meshes_embedded_in_current_viewer":False,
        "source_v10_visual_to_v11_cad_rigid_registration_measured":False,
        "joint_axes_and_link_articulation_visuals_reconciled":False,
        "stage_mount_is_display_only":True,
        "stage_script_sha256":sha(scene.encode()),
        "source_matched_rendering_ready":False,
        "missing_acceptance_evidence":[
            "use original v1.0 visual mesh assets and a renderer supporting original URDF link transforms",
            "or independently establish source v1.0 URDF <-> v1.1 GLB per-link rigid registration",
            "measure physical robot base-to-stage transforms and fixture CAD",
            "replay same time-sampled joint positions and align TCP and link coordinate frames",
            "qualify object collision, fixture clearance, actuator/servo dynamics and human-safe control",
        ],
    }
    findings={
        "numeric_source_cycle_passed":c["cycle"]["numerical_full_cycle_test_passed"],
        "robot_self_overlap_initial_pairs":contacts["source_self_initial_count"],
        "robot_self_new_pairs":len(contacts["new_pairs_after_initial_pose"]),
        "robot_self_deepening_pairs":len(contacts["baseline_pairs_deepening_over_0p1mm"]),
        "robot_fixture_unintended_penetration_contact_records":sum(source_fixture_counts.values()),
        "payload_non_gripper_contact_observations":sum(unexpected_object_contacts.values()),
        "cannot_claim_collision_free":True,
    }
    return {
        "schema_version":SCHEMA,
        "input_cycle_sha256":sha(cycle_path.read_bytes()),
        "source_urdf_sha256":sha(source),
        "physical_engine":"PyBullet original-source geometry and motor-stepped contact telemetry",
        "contact":contacts,
        "source_visual_revision_registration":registration,
        "findings":findings,
        "authority":{
            "numerical_cycle_passed":True,
            "original_source_meshes_changed":False,
            "source_model_registered_with_visual_cad":False,
            "all_fixture_geometry_included":False,
            "self_collisions_dismissed_as_safe":False,
            "physical_robot_motion_authorized":False,
            "physical_sorter_certified":False,
            "fabrication_authorized":False,
        },
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cycle",type=Path,required=True)
    ap.add_argument("--urdf",type=Path,required=True)
    ap.add_argument("--stage",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    report=audit(args.cycle,args.urdf,args.stage)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report["findings"],indent=2))

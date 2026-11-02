#!/usr/bin/env python3
"""Fail-closed engineering release decision from SORTCELL source trace evidence.

The successful numerical task and physical readiness are intentionally
independent. This is an evidence-driven gate, not a certification system.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

SCHEMA="hardware_splicer.sortcell_evidence_release_gate.v1"
MIN_PRODUCTION_EVIDENCE=("verified_robot_workcell_registration",
                         "full_source_mesh_self_clearance",
                         "full_fixture_and_payload_clearance",
                         "manufacturer_actuator_limit_validation",
                         "measured_force_tolerance_and_calibration",
                         "hardware_interlocks_and_human_safety",
                         "physical_grasp_sort_release_demonstration")

def decide(strict:dict,collision:dict)->dict:
    if strict.get("verified_schema")!="hardware_splicer.sortcell_strict_numerical_acceptance.v1":
        raise ValueError("Must use independently verified numerical SORTCELL receipt")
    if collision.get("schema_version")!="hardware_splicer.sortcell_dynamic_cycle_contact_safety_audit.v1":
        raise ValueError("Must use original-source collision and registration audit")
    if strict.get("source_urdf_sha256")!=collision.get("source_urdf_sha256"):
        raise ValueError("Numerical and collision evidence refer to different original robot")
    if strict.get("numerical_full_cycle_passed") is not True:
        raise ValueError("No successful full numerical task evidence")
    flags=collision["authority"]
    if flags.get("physical_robot_motion_authorized") is not False:
        raise ValueError("Upstream report unexpectedly claims physical motion authority")
    reg=collision["source_visual_revision_registration"]
    if reg.get("source_v10_visual_to_v11_cad_rigid_registration_measured") is not False:
        raise ValueError("Unreviewed visual registration assertion")
    stats=collision["findings"]
    raw=collision["contact"]
    if stats.get("numeric_source_cycle_passed") is not True:
        raise ValueError("Numerical and physical-source reports disagree")
    violations=raw["source_joint_limit_violation_observations"]
    # Keep both exact deviation counts and a separately labelled 0.1mm / 0.001rad
    # investigation threshold. Anything >0 still blocks authorizing hardware.
    operational=[x for x in violations if
                 x["excess_beyond_limit"]>(
                     1e-4 if x["unit"]=="m" else 1e-3)]
    blockers={
        "source_model_registration":{
          "blocked":True,"reason":"independent 542-part GLB v1.1 is not joint/link frame registered to original v1.0 URDF"},
        "source_self_mesh_clearance":{
          "blocked":bool(raw["source_self_initial_count"] or raw["new_pairs_after_initial_pose"] or
                         raw["baseline_pairs_deepening_over_0p1mm"]),
          "persistent_initial_link_pairs":raw["source_self_initial_count"],
          "new_link_pairs":len(raw["new_pairs_after_initial_pose"]),
          "deepening_link_pairs":len(raw["baseline_pairs_deepening_over_0p1mm"])},
        "fixture_interpenetration":{
          "blocked":bool(stats["robot_fixture_unintended_penetration_contact_records"]),
          "robot_fixture_contact_records":stats["robot_fixture_unintended_penetration_contact_records"],
          "coverage":"only two proposed station floor boxes, not full conveyor/robot environment"},
        "source_joint_limits":{
          "blocked":bool(violations),
          "any_signed_overshoot_sample_count":len(violations),
          "above_investigation_threshold_count":len(operational),
          "worst_prismatic_overshoot_m":raw["max_joint_limit_overshoot_per_unit"]["prismatic_m"],
          "worst_revolute_overshoot_rad":raw["max_joint_limit_overshoot_per_unit"]["revolute_rad"],
          "investigation_threshold_m":1e-4,
          "investigation_threshold_rad":1e-3,
          "threshold_is_not_hardware_permission":True},
        "unexpected_payload_robot_links":{
          "blocked":bool(stats["payload_non_gripper_contact_observations"]),
          "contact_observations":stats["payload_non_gripper_contact_observations"]},
        "physical_validation_and_safety":{
          "blocked":True,
          "missing_production_evidence":list(MIN_PRODUCTION_EVIDENCE)},
    }
    if not any(v["blocked"] for v in blockers.values()):
        raise ValueError("Release gate violated: mandatory hardware validation should be explicitly unavailable")
    return {
       "schema_version":SCHEMA,
       "evidence_source_urdf_sha256":strict["source_urdf_sha256"],
       "numerical_sort_cycle_verdict":"passed_source_native_pybullet",
       "simulation_collision_qualification":"failed",
       "viewer_model_registration":"failed_missing_registration",
       "engineering_status":"numerical_proof_of_concept_only",
       "robot_control_authorized":False,
       "physical_build_or_fabrication_authorized":False,
       "physical_sorter_certified":False,
       "blockers":blockers,
       "next_milestone":"source-matched link/visual model and source-collision-safe full-cycle workcell with fixture and joint-limit clearance",
       "cannot_equate_green_ci_with_hardware_readiness":True,
    }

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numerical",required=True,type=Path)
    parser.add_argument("--contact",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    result=decide(json.loads(args.numerical.read_text()),json.loads(args.contact.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({
        "numerical":result["numerical_sort_cycle_verdict"],
        "simulation_collision":result["simulation_collision_qualification"],
        "visual_registration":result["viewer_model_registration"],
        "hardware_control":result["robot_control_authorized"],
        "blockers":{k:v["blocked"] for k,v in result["blockers"].items()},
    },indent=2))

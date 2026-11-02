#!/usr/bin/env python3
"""Compare repair candidates against the unchanged source-native SORTCELL trace.

Experimental support-pad widths are a proposed new fixture, NOT existing
Teardown geometry. Source OpenArm meshes, joint limits and manufacturer URDF
are identical across trials. No baseline collisions are forgiven as safe.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from collections import Counter

SCHEMA="hardware_splicer.sortcell_clearance_repair_trials.v1"
def classify(path:Path,urdf_hash:str,source_limits:dict)->dict:
    if not path.exists():
        return {"available":False,"numerical_full_cycle_passed":False,"error":"no replayable trace"}
    r=json.loads(path.read_text())
    if r["original_urdf_sha256"]!=urdf_hash:
        raise ValueError("Mismatched source URDF for "+str(path))
    events=r["cycle"]["contact_observations"]
    if len(events)<150 or len(r["cycle"]["stages"])!=8:
        raise ValueError("Partial trial "+str(path))
    init={tuple(p["link_pair"]):p["depth_m"]
          for p in r["cycle"]["original_source_initial_self_contact_pairs"]}
    counts=Counter()
    deepest={}
    self_deepest={}
    self_count=Counter()
    max_overshoot=0
    max_overshoot_prismatic=0
    material_overshoots=0
    exact_overshoots=0
    observed_links=set()
    for e in events:
        joints=e["source_robot_joint_positions"]
        if set(joints)!=set(source_limits):
            raise ValueError("Incomplete original manufacturer joints in trial")
        for n,v in joints.items():
            lo,hi,kind=source_limits[n]
            deviation=max(0,lo-v,v-hi)
            max_overshoot=max(max_overshoot,deviation)
            if kind=="prismatic":max_overshoot_prismatic=max(max_overshoot_prismatic,deviation)
            if deviation>0:
                exact_overshoots+=1
                if deviation>1e-4:material_overshoots+=1
        for key,items in e["source_robot_fixture_penetrations"].items():
            for item in items:
                pair=(key,item["robot_link"])
                observed_links.add(item["robot_link"])
                counts[pair]+=1
                deepest[pair]=min(deepest.get(pair,0),item["depth_m"])
        for item in e["source_robot_self_penetrations"]:
            pair=tuple(item["link_pair"])
            self_count[pair]+=1
            self_deepest[pair]=min(self_deepest.get(pair,0),item["depth_m"])
    new_pairs=set(self_deepest)-set(init)
    deepening={pair:round(init.get(pair,0)-value,7)
               for pair,value in self_deepest.items()
               if pair in init and value<init[pair]-.0001}
    all_contacts=sum(counts.values())
    bound={"initial_source_collision_pair_count":len(init),
      "new_self_collision_pairs":len(new_pairs),
      "self_collision_deepening_pairs":len(deepening),
      "max_additional_self_collision_penetration_m":max(deepening.values(),default=0),
      "fixture_robot_collision_observations":all_contacts,
      "fixture_penetrations_by_robot_link":[
          {"fixture":key[0],"link":key[1],"count":n,
           "deepest_penetration_m":round(deepest[key],7)}
          for key,n in sorted(counts.items())],
      "worst_fixture_penetration_m":round(min(deepest.values(),default=0),7),
      "source_joint_limit_exact_overshoot_observations":exact_overshoots,
      "source_joint_limit_overshoot_over_0p1mm_observations":material_overshoots,
      "maximum_original_joint_limit_overshoot":round(max_overshoot,8),
      "maximum_source_prismatic_limit_overshoot_m":round(max_overshoot_prismatic,8),
      "no_unintended_non_gripper_payload_contact":not any(
          e["unexpected_payload_robot_link_contacts"] for e in events),
      "sampled_motor_contact_observations":len(events),
    }
    return {"available":True,"numerical_full_cycle_passed":r["cycle"]["numerical_full_cycle_test_passed"],
      "experimental_source_finger_limit_margin_m":
          r["cycle"].get("experimental_source_finger_limit_margin_m",0),
      "source_finger_hard_limits_unchanged":
          r["cycle"].get("original_source_finger_joint_hard_limits_unchanged",True),
      "physical_fixture_configuration":[
          v.get("simulated_proposed_support_size_m",v["source_floor_size_stage_m"])
          for v in r["candidate_layout"]["proposed_fixture_stations"]],
      "metrics":bound,
      "simulation_contact_clean":(
          all_contacts==0 and exact_overshoots==0 and len(self_deepest)==0
          and not new_pairs and not deepening),
      "hardware_motion_approved":False,
    }


def run(urdf:Path,baseline:Path,variants:list[Path])->dict:
    source=urdf.read_bytes()
    root=ET.fromstring(source)
    limits={}
    for j in root.findall("joint"):
        if j.attrib.get("type") not in ("revolute","prismatic"):continue
        lim=j.find("limit")
        if lim is None:raise ValueError("Original URDF lacks published joint limits")
        limits[j.get("name")]=(float(lim.get("lower")),
                               float(lim.get("upper")),j.get("type"))
    if len(limits)!=18:raise ValueError("Original OpenArm joint count mismatch")
    h=hashlib.sha256(source).hexdigest()
    reference=classify(baseline,h,limits)
    if not reference["available"] or not reference["numerical_full_cycle_passed"]:
        raise ValueError("Original source baseline numerical cycle did not pass")
    proposals=[{"trace":str(p),"result":classify(p,h,limits)} for p in variants]
    for trial in proposals:
        x=trial["result"]
        if not x["available"]:continue
        m=x["metrics"];base=reference["metrics"]
        trial["comparison_to_original_baseline"]={
            "fixture_penetrating_contact_count_delta":m["fixture_robot_collision_observations"]-
                                                        base["fixture_robot_collision_observations"],
            "original_source_limit_exceedance_over_0p1mm_delta":
                m["source_joint_limit_overshoot_over_0p1mm_observations"]-
                base["source_joint_limit_overshoot_over_0p1mm_observations"],
            "original_wrist_deepening_delta_m":
                round(m["max_additional_self_collision_penetration_m"]-
                    base["max_additional_self_collision_penetration_m"],7),
        }
    return {"schema_version":SCHEMA,
      "source_urdf_sha256":h,
      "evidence_is_original_source_pybullet":True,
      "original_baseline":reference,
      "proposals":proposals,
      "number_tried":len(proposals),
      "number_with_numerical_cycle_pass":sum(t["result"]["numerical_full_cycle_passed"] for t in proposals),
      "number_without_robot_fixture_penetration":sum(t["result"].get("metrics",{}).get("fixture_robot_collision_observations")==0 for t in proposals),
      "number_with_zero_joint_limit_exceedance":sum(t["result"].get("metrics",{}).get("source_joint_limit_exact_overshoot_observations")==0 for t in proposals),
      "physical_hardware_authorized":False,
      "visual_CAD_v11_to_original_URDF_v10_registered":False,
      "full_workcell_fixture_CAD_qualified":False,
      "source_self_collision_clearance_qualified":False,
      "gripper_finger_actuator_dynamics_qualified":False,
      "supported_repair_is_experimental_only":True,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--urdf",required=True,type=Path)
    ap.add_argument("--baseline",required=True,type=Path)
    ap.add_argument("--variants",nargs="+",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    result=run(a.urdf,a.baseline,a.variants)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({
        "baseline":result["original_baseline"]["metrics"],
        "repairs":[{"trace":v["trace"],"outcome":v["result"].get("numerical_full_cycle_passed"),
                    "delta":v.get("comparison_to_original_baseline")} for v in result["proposals"]],
        "physical_hardware_authorized":False},indent=2))

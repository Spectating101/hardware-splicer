"""PyBullet DIRECT path feasibility for an assumed robotic assembler.

No motors are actuated. The gripper and casing are not dynamically modeled.
Simulation only evaluates inverse kinematics, joint limits and URDF proxy
collision over four waypoints; trajectory speeds/forces remain unknown.
"""
from __future__ import annotations
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from .robot_arm_design import RobotArmDesignProposal

def run_robotic_assembly_dryrun(
 proposal:RobotArmDesignProposal,urdf_path:Path,
 *, target_positions_m:Mapping[str,list[float]]|None=None,
)->dict[str,Any]:
 import pybullet as p
 total_m=sum(j.link_length_mm for j in proposal.joints)/1000
 targets=target_positions_m or {
  "approach_pick":[.58*total_m,-.16*total_m,.24*total_m],
  "pick_printed_part":[.64*total_m,-.17*total_m,.11*total_m],
  "clear_with_part":[.55*total_m,0,.28*total_m],
  "place_over_case":[.64*total_m,.17*total_m,.11*total_m],
  "retreat":[.58*total_m,.17*total_m,.24*total_m],
 }
 for name,vals in targets.items():
  if not isinstance(vals,(list,tuple)) or len(vals)!=3 or any(
   isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>5 for x in vals
  ):
   raise ValueError("invalid pick/place target: "+str(name))
 client=p.connect(p.DIRECT)
 try:
  body=p.loadURDF(str(urdf_path),useFixedBase=True,
                  flags=getattr(p,"URDF_USE_SELF_COLLISION",0)
                      | getattr(p,"URDF_USE_SELF_COLLISION_EXCLUDE_PARENT",0),
                  physicsClientId=client)
  movable=[]
  joint_names=[]
  lower=[]
  upper=[]
  parents={}
  tool=None
  for i in range(p.getNumJoints(body,physicsClientId=client)):
   inf=p.getJointInfo(body,i,physicsClientId=client)
   parents[i]=inf[16]
   if inf[12]==b"tool0":tool=i
   if inf[2]!=p.JOINT_FIXED:
    movable.append(i);joint_names.append(inf[1].decode())
    lower.append(float(inf[8]));upper.append(float(inf[9]))
  if tool is None:raise RuntimeError("URDF missing tool0")
  rows=[]
  solution_rest=[0.0]*len(movable)
  ranges=[max(u-l,1e-5) for l,u in zip(lower,upper)]
  for label,target in targets.items():
   solution=p.calculateInverseKinematics(
    body,tool,target,lowerLimits=lower,upperLimits=upper,
    jointRanges=ranges,restPoses=solution_rest,
    maxNumIterations=350,residualThreshold=1e-7,physicsClientId=client
   )
   for j,q in zip(movable,solution):
    p.resetJointState(body,j,q,physicsClientId=client)
   solved=p.getLinkState(body,tool,computeForwardKinematics=True,physicsClientId=client)[4]
   error_mm=1000*math.dist(solved,target)
   inlimits=all(lo-1e-4<=q<=hi+1e-4 for q,lo,hi in zip(solution,lower,upper))
   p.performCollisionDetection(physicsClientId=client)
   violations=[]
   for contact in p.getContactPoints(bodyA=body,bodyB=body,physicsClientId=client):
    a,b=contact[3:5]
    if a==b or parents.get(a)==b or parents.get(b)==a:continue
    pair=sorted((a,b))
    if pair not in violations:violations.append(pair)
   rows.append({
    "phase":label,
    "requested_xyz_m":[round(x,5) for x in target],
    "result_xyz_m":[round(x,5) for x in solved],
    "position_error_mm":round(error_mm,3),
    "position_under_5mm":error_mm<=5,
    "joint_limits_respected":inlimits,
    "nonadjacent_proxy_self_collision_pairs":violations,
    "model_joint_positions_rad":dict(zip(joint_names,[round(float(q),4) for q in solution])),
   })
   solution_rest=[float(x) for x in solution[:len(movable)]]
  return {
   "schema_version":"hs.arm_assembly_dryrun_pybullet.v1",
   "simulation_engine":"pybullet.DIRECT",
   "task":"abstract printed-lid pick -> case placement and retreat",
   "task_space_pose_position_only":True,
   "all_waypoints_position_reachable":all(x["position_under_5mm"] for x in rows),
   "all_waypoints_joint_limits_respected":all(x["joint_limits_respected"] for x in rows),
   "proxy_self_collision_free":all(not x["nonadjacent_proxy_self_collision_pairs"] for x in rows),
   "waypoints":rows,
   "real_gripper_and_casing_geometry_simulated":False,
   "picked_up_or_carried_real_object":False,
   "joint_torques_or_dynamics_verified":False,
   "physical_motion_authorized":False,
   "ready_for_robotic_assembly":False,
  }
 finally:
  p.disconnect(physicsClientId=client)

"""Conditional SolidCraft gripping-jaw inserts for a hypothetical robot arm.

Creates geometry, not a known matching end-effector. Actual jaw travel,
clamping force, fastener position and print material strength are unknown.
"""
from __future__ import annotations
import json,hashlib,math
from collections.abc import Mapping
from typing import Any

def _num(data,key,lo,hi):
 v=data.get(key)
 if type(v) not in (float,int) or not math.isfinite(v) or not lo<=v<=hi:
  raise ValueError('invalid assumed arm finger dimension '+key)
 return float(v)

def prepare_robot_arm_finger_inserts(spec:Mapping[str,Any])->dict[str,Any]:
 if spec.get("source_authority")!="BENCHMARK_ASSUMPTION_ONLY":
  raise ValueError('finger CAD cannot claim measured fit')
 dims=spec.get("dimensions_mm")
 if not isinstance(dims,Mapping):raise ValueError('missing finger dimensions')
 l=_num(dims,'length',20,80)
 w=_num(dims,'width',8,25)
 h=_num(dims,'thickness',4,15)
 d=_num(dims,'fastener_hole_diameter',2.2,5.0)
 edge=_num(dims,'fastener_edge_margin',4,15)
 gap=_num(dims,'print_layout_gap',8,30)
 if 2*edge+8>=l or d>=w/2 or edge<d*1.5:raise ValueError('unprintable hole spacing or margin')
 offset=l+gap
 commands=[]
 for name,x0 in [('HS_ArmFinger_Left',0),('HS_ArmFinger_Right',offset)]:
  commands.append({"command":"solid.box","params":{
   "length":l,"width":w,"height":h,"corner":[x0,0,0],"body_name":name,"operation":"new"
  }})
  for x in (edge,l-edge):
   commands.append({"command":"solid.hole","params":{
    "position":[x0+x,w/2,h],"diameter":d,"depth":h+0.6,
   }})
 record={
  "schema_version":"hs.arm_conditional_finger_cad.v1",
  "spec_sha256":hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest(),
  "solidcraft_commands":{"commands":commands},
  "body_names":["HS_ArmFinger_Left","HS_ArmFinger_Right"],
  "print_bbox_mm":[2*l+gap,w,h],
  "mount_hole_centres":[[x,w/2] for x in (edge,l-edge)],
  "joint_and_gripper_fitting_measured":False,
  "actual_grip_force_validated":False,
  "material_mechanical_strength_validated":False,
  "physical_print_authorized":False,
 }
 return record

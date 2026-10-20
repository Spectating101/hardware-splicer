"""Static conservative torque-range checks of assumed salvaged robotic arms.

No identified real components, no catalog-backed manufacturer specs. Separates
typical assumptions from hard engineering facts and blocks release regardless
of a favorable nominal calculation. Does not compute link structural safety,
servo controller compatibility, actual joint direction or dynamic performance.
"""
from __future__ import annotations
import math
from collections.abc import Mapping
from typing import Any
from .robot_arm_design import RobotArmDesignProposal

_G=9.80665

def _interval(value:Any,label:str,*,maximum:float)->tuple[float,float]:
 if (not isinstance(value,(list,tuple)) or len(value)!=2 or
     any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in value)
     or not (0<=value[0]<=value[1]<=maximum)):
  raise ValueError("invalid engineering assumption range: "+label)
 return float(value[0]),float(value[1])

def stress_test_assumed_arm(proposal:RobotArmDesignProposal,spec:Mapping[str,Any])->dict:
 if spec.get("information_authority")!="BENCHMARK_ASSUMPTION_ONLY":
  raise ValueError("unverified catalog must be labeled assumption")
 if spec.get("actual_salvaged_components_acquired") is not False:
  raise ValueError("this benchmark does not authenticate actual salvage")
 requirements=spec["requirements"]
 bounds=spec["estimated_physical_intervals"]
 payload=_interval(bounds["payload_mass_kg"],"payload_mass_kg",maximum=5)
 gripper=_interval(bounds["end_effector_mass_kg"],"end_effector_mass_kg",maximum=5)
 segment_mass=_interval(bounds["link_mass_kg_per_segment"],"link_mass_kg_per_segment",maximum=10)
 acceleration=_interval(bounds["effective_acceleration_dynamic_torque_factor"],"dynamic_torque_factor",maximum=5)
 thermal=_interval(bounds["overall_actuator_thermal_derating_factor"],"derating",maximum=1.5)
 if not (0<thermal[0]<=thermal[1]):raise ValueError("derating must be positive")
 safety=float(requirements["minimum_static_torque_safety_factor"])
 if not 1<=safety<=5:raise ValueError("invalid safety factor")
 index={str(x["component_id"]):x for x in spec["assumed_part_catalog"]}
 result=[]
 total_mm=sum(x.link_length_mm for x in proposal.joints)
 target=float(requirements["required_reach_mm"])
 for i,joint in enumerate(proposal.joints):
  l=[float(x.link_length_mm)/1000 for x in proposal.joints[i:]]
  distance=sum(l)
  centers=[sum(l[:k])+length/2 for k,length in enumerate(l)]
  axes=joint.axis
  gravity_coupling=math.hypot(axes[0],axes[1])
  actuator=index.get(joint.actuator_part_id or "")
  if actuator is None or joint.joint_type!="revolute":
   result.append({"joint_id":joint.joint_id,"status":"UNRESOLVED_ACTUATOR_OR_JOINT","blocking":True})
   continue
  low_factor=float(actuator.get("torque_low_factor",thermal[0]))
  high_factor=float(actuator.get("torque_high_factor",thermal[1]))
  rated=float(actuator["continuous_torque_nm"])
  if (not math.isfinite(rated) or rated<=0 or not 0<low_factor<=high_factor<=2):
   raise ValueError("unsafe or malformed assumed motor interval")
  # The lower bound of continuous torque is treated as the more conservative
  # of assumed component uncertainty and generic thermal derating. Avoid
  # multiplying correlated derating assumptions twice without a source model.
  available_worst=rated*min(low_factor,thermal[0])
  available_nominal=rated
  m_nom=(payload[0]+payload[1]+gripper[0]+gripper[1])/2
  lm_nom=sum(centers)*sum(segment_mass)/2
  required_nom=_G*gravity_coupling*(m_nom*distance+lm_nom)*safety*sum(acceleration)/2
  required_worst=_G*gravity_coupling*((payload[1]+gripper[1])*distance+segment_mass[1]*sum(centers))*safety*acceleration[1]
  if gravity_coupling<0.001:
   state="GRAVITY_PASS_BUT_YAW_DYNAMICS_UNKNOWN"
   evidence_note="Vertical-axis yaw torque cannot be qualified without inertia/acceleration/drag and cable limits."
  elif required_worst<=available_worst:
   state="INTERVAL_STATIC_TORQUE_SCREEN_PASS"
   evidence_note="All input loads and ratings remain hypothetical; inertial and mechanical loads not qualified."
  elif required_nom<=available_nominal:
   state="NOMINAL_ONLY_FAILS_WORST_CASE"
   evidence_note="Nominal assumption would hide overload under higher self-mass/low torque assumptions."
  else:
   state="ASSUMED_COMPONENT_UNDERSIZED"
   evidence_note="Even nominal modeled gravity torque exceeds nominal assumed rating."
  result.append({
   "joint_id":joint.joint_id,
   "actuator_id":joint.actuator_part_id,
   "axis_gravity_coupling":round(gravity_coupling,4),
   "from_nominal_assumption_not_measurement":True,
   "lever_arm_m":round(distance,4),
   "rated_assumption_nm":rated,
   "available_torque_assumed_worst_nm":round(available_worst,4),
   "nominal_required_nm":round(required_nom,4),
   "worst_case_required_nm":round(required_worst,4),
   "worst_case_margin_nm":round(available_worst-required_worst,4),
   "state":state,"review":evidence_note,
   "blocking":state not in {"INTERVAL_STATIC_TORQUE_SCREEN_PASS"},
  })
 if total_mm<target:
  classification="GEOMETRIC_REACH_FAIL"
 elif any(x["state"] in ("NOMINAL_ONLY_FAILS_WORST_CASE","ASSUMED_COMPONENT_UNDERSIZED","UNRESOLVED_ACTUATOR_OR_JOINT") for x in result):
  classification="ASSUMED_COMPONENT_INTERFACES_REQUIRE_REDIMENSION"
 else:
  classification="PROVISIONAL_STATIC_SCREEN_ONLY"
 return {
  "schema_version":"hs.arm_robust_assumptions.v1",
  "input_data_confidence":"ASSUMED_ONLY_UNVERIFIED",
  "result":classification,
  "required_reach_mm":target,
  "proposed_geometric_chain_length_mm":round(total_mm,2),
  "safety_factor_assumed":safety,
  "joint_screens":result,
  "physical_components_owned":0,
  "real_joint_masses_measured":False,
  "dynamic_inertia_closed":False,
  "real_gripper_fitted":False,
  "independent_emergency_stop_tested":False,
  "robotic_pick_and_place_actuated":False,
  "fabrication_authorized":False,
  "motion_authorized":False,
  "release_authorized":False,
 }

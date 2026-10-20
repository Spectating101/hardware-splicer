"""Uncertainty-aware robotic splicing with no fake physical provenance."""
from __future__ import annotations
import json
from copy import deepcopy
from pathlib import Path
import pytest
from hardware_splicer.robot_arm_design import parse_robot_arm_design
from hardware_splicer.arm_splice_assumption_oracle import stress_test_assumed_arm
ROOT=Path(__file__).resolve().parents[1]
SPEC=json.loads((ROOT/"examples/assumption_robot_arm/arm_salvage_benchmark_assumptions.json").read_text())

def trial(**override):
 spec=deepcopy(SPEC)
 spec.update(override)
 return spec

def proposed(spec=None):
 spec=spec or SPEC
 return parse_robot_arm_design({
  'reasoning':'hypothetical 4DoF printed-part retrieval',
  'joints':[
   {'joint_id':'yaw','joint_type':'revolute','axis':[0,0,1],
    'link_length_mm':90,'actuator_part_id':'assumed_base_yaw_24v','lower_limit_deg':-150,'upper_limit_deg':150},
   {'joint_id':'shoulder','joint_type':'revolute','axis':[0,1,0],
    'link_length_mm':165,'actuator_part_id':'assumed_shoulder_24v','lower_limit_deg':-100,'upper_limit_deg':100},
   {'joint_id':'elbow','joint_type':'revolute','axis':[0,1,0],
    'link_length_mm':130,'actuator_part_id':'assumed_elbow_24v','lower_limit_deg':-130,'upper_limit_deg':130},
   {'joint_id':'wrist','joint_type':'revolute','axis':[0,1,0],
    'link_length_mm':75,'actuator_part_id':'assumed_wrist_24v','lower_limit_deg':-95,'upper_limit_deg':95}],
  'end_effector':'parallel gripper candidates',
  'source_ids':[],
  'authority_effect':'none','automatic_execution':False,
 }, inventory=spec["assumed_part_catalog"],known_source_ids=[])

def test_nominal_and_worst_case_torque_are_not_same_number():
 result=stress_test_assumed_arm(proposed(),SPEC)
 assert result['input_data_confidence']=='ASSUMED_ONLY_UNVERIFIED'
 shoulder=next(x for x in result['joint_screens'] if x['joint_id']=='shoulder')
 assert shoulder['worst_case_required_nm']>shoulder['nominal_required_nm']
 assert shoulder['available_torque_assumed_worst_nm']<shoulder['rated_assumption_nm']
 assert shoulder['from_nominal_assumption_not_measurement']
 assert not result['release_authorized']
 assert result['physical_components_owned']==0

def test_yaw_axis_requires_inertia_not_false_torque_green():
 result=stress_test_assumed_arm(proposed(),SPEC)
 yaw=result['joint_screens'][0]
 assert yaw['state']=='GRAVITY_PASS_BUT_YAW_DYNAMICS_UNKNOWN'
 assert yaw['blocking'] is True
 assert not result['motion_authorized']

def test_weaker_assumed_component_not_mistaken_for_robust_candidate():
 under=trial()
 under['assumed_part_catalog'][1]['continuous_torque_nm']=1.0
 result=stress_test_assumed_arm(proposed(under),under)
 assert result['result']=='ASSUMED_COMPONENT_INTERFACES_REQUIRE_REDIMENSION'
 assert next(x for x in result['joint_screens'] if x['joint_id']=='shoulder')['state']=='ASSUMED_COMPONENT_UNDERSIZED'

def test_worsening_link_self_weight_can_reject_nominal_candidate():
 heavy=trial()
 heavy['estimated_physical_intervals']['link_mass_kg_per_segment']=[0.6,1.2]
 result=stress_test_assumed_arm(proposed(heavy),heavy)
 assert result['result']=='ASSUMED_COMPONENT_INTERFACES_REQUIRE_REDIMENSION'

@pytest.mark.parametrize('bad',[
 {'estimated_physical_intervals':{'payload_mass_kg':[-1,1]}},
 {'estimated_physical_intervals':{'payload_mass_kg':[0.7,0.1]}},
 {'estimated_physical_intervals':{'end_effector_mass_kg':[float('nan'),1]}},
])
def test_invalid_assumption_ranges_rejected(bad):
 spec=trial()
 for k,v in bad.items():spec[k].update(v)
 with pytest.raises(ValueError):
  stress_test_assumed_arm(proposed(spec),spec)

def test_assumptions_cannot_launder_actual_donor_ownership():
 spec=trial(actual_salvaged_components_acquired=True)
 with pytest.raises(ValueError,match="does not authenticate"):
  stress_test_assumed_arm(proposed(),spec)

def test_unlisted_motor_identity_does_not_silently_become_valid():
 spec=trial()
 proposal=proposed(spec)
 with pytest.raises(Exception):
  parse_robot_arm_design({'joints':[
   {'joint_id':'invented','axis':[0,1,0],'link_length_mm':250,
    'actuator_part_id':'unknown_10nm_servo'}]},inventory=spec['assumed_part_catalog'])

def test_sdk_mcp_exposes_assumed_arm_and_finger_tools():
 import asyncio
 from hardware_splicer import sdk,mcp_server
 spec=SPEC
 candidate=proposed(spec).model_dump(mode='json')
 result=sdk.evaluate_assumed_robot_arm(proposal=candidate,benchmark_spec=spec)
 assert result['stress_analysis']['input_data_confidence']=='ASSUMED_ONLY_UNVERIFIED'
 assert not result['physical_data_authenticated']
 assert not result['motion_authorized']
 tools=asyncio.run(mcp_server.list_tools())
 assert {'hs_evaluate_assumed_robot_arm','hs_prepare_assumed_arm_fingers'}.issubset({t.name for t in tools})
 response=asyncio.run(mcp_server.call_tool('hs_evaluate_assumed_robot_arm',{
   'proposal':candidate,'benchmark_spec':spec}))
 parsed=json.loads(response[0].text)
 assert parsed['stress_analysis']['result']==result['stress_analysis']['result']
 assert not parsed['motion_authorized']
 finger=json.loads((ROOT/'examples/assumption_robot_arm/finger_insert_assumptions.json').read_text())
 out=sdk.prepare_assumed_arm_fingers(finger_spec=finger)
 assert out['body_names']==['HS_ArmFinger_Left','HS_ArmFinger_Right']
 assert out['physical_print_authorized'] is False

def test_autonomous_agent_readonly_arm_tool_receipts():
 from hardware_splicer.engineering_reasoning_agent import _tools,ALLOWED_TOOLS
 assert {'inspect_robot_arm_campaign','evaluate_assumed_robot_arm',
         'prepare_assumed_arm_fingers'}.issubset(ALLOWED_TOOLS)
 case={'intake':{'goal':'Make a robotic arm'},
       'assumed_robot_arm_spec':SPEC,
       'assumed_arm_finger_spec':json.loads(
          (ROOT/'examples/assumption_robot_arm/finger_insert_assumptions.json').read_text())}
 recorded=_tools('inspect_robot_arm_campaign',{},case)
 assert recorded['revised_candidate_torque_classification']=='PROVISIONAL_STATIC_SCREEN_ONLY'
 assert recorded['revised_pick_place_proxy_collision_free'] is False
 assert recorded['physical_fabrication_authorized'] is False
 tested=_tools('evaluate_assumed_robot_arm',{'proposal':proposed().model_dump(mode='json')},case)
 assert tested['stress_analysis']['result']=='ASSUMED_COMPONENT_INTERFACES_REQUIRE_REDIMENSION'
 assert tested['motion_authorized'] is False
 fingers=_tools('prepare_assumed_arm_fingers',{},case)
 assert fingers['body_names']==['HS_ArmFinger_Left','HS_ArmFinger_Right']
 assert fingers['physical_print_authorized'] is False

def test_arm_campaign_exposes_schema_valid_prior_proposals_for_agent_revisions():
 from hardware_splicer.engineering_reasoning_agent import _tools
 result=_tools('inspect_robot_arm_campaign',{}, {'intake':{'goal':'any'}})
 known=result['revised_previously_parsed_typed_proposal']
 assert len(known['joints'])==4
 assert known['authority_effect']=='none'
 assert all(x['link_length_mm']>0 for x in known['joints'])
 spec=json.loads((ROOT/'examples/assumption_robot_arm/arm_salvage_revised_gear_assumptions.json').read_text())
 from hardware_splicer.sdk import evaluate_assumed_robot_arm
 evaluated=evaluate_assumed_robot_arm(proposal=known,benchmark_spec=spec)
 assert evaluated['stress_analysis']['result']=='PROVISIONAL_STATIC_SCREEN_ONLY'

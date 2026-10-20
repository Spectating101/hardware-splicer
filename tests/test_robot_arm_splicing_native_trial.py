"""Use captured REAL model/native CAD and offline slicer results as fixtures."""
from __future__ import annotations
import hashlib,json,zipfile
from pathlib import Path
from copy import deepcopy
import pytest
from hardware_splicer.robot_arm_cad_adapter import prepare_robot_arm_finger_inserts
from hardware_splicer.robot_arm_design import parse_robot_arm_design
from hardware_splicer.arm_splice_assumption_oracle import stress_test_assumed_arm
from hardware_splicer.realization_gcode_audit import audit_offline_gcode

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'examples/assumption_robot_arm/HS_ROBOT_ARM_SPLICE_BENCHMARK_20261020.zip'
def read(z,p):return json.loads(z.read(p))

def test_reproducibility_archive_checks_all_file_hashes_and_authority():
 with zipfile.ZipFile(BUNDLE) as z:
  assert z.testzip() is None
  manifest=read(z,'MANIFEST.json')
  assert len(manifest['included_files'])==30
  for name,data in manifest['included_files'].items():
   assert hashlib.sha256(z.read(name)).hexdigest()==data['sha256']
  assert manifest['two_live_model_arm_designs']
  assert manifest['actual_pybullet_installed_and_called']
  assert manifest['actual_prusaslicer_executed']
  assert not manifest['physical_fabrication_authorized']
  assert not manifest['real_robot_present']
  assert not manifest['donor_components_acquired']

def test_initial_live_codex_arm_vs_revised_stress_reproduced():
 with zipfile.ZipFile(BUNDLE) as z:
  cases=[
   ('catalog/initial_assumptions.json','reports/initial_live_codex_design.json'),
   ('catalog/revised_assumptions.json','reports/revised_live_codex_design.json')]
  outcomes=[]
  for specname,reportname in cases:
   spec=read(z,specname)
   trace=read(z,reportname)
   arm=parse_robot_arm_design(trace['proposal'],inventory=spec['assumed_part_catalog'])
   exact=stress_test_assumed_arm(arm,spec)
   assert exact==trace['interval_stress_oracle']
   outcomes.append(exact['result'])
   assert trace['model_provider']=='chatgpt_authenticated_codex'
   assert not trace['physical_fabrication_authorized']
  assert outcomes==['ASSUMED_COMPONENT_INTERFACES_REQUIRE_REDIMENSION',
                   'PROVISIONAL_STATIC_SCREEN_ONLY']

def test_revised_arm_collision_and_ik_deficit_not_hidden():
 with zipfile.ZipFile(BUNDLE) as z:
  r=read(z,'reports/revised_live_codex_design.json')
  assert r['pybullet_independent_kinematics']['urdf_load_pass']
  assert r['pybullet_independent_kinematics']['ik_position_error_mm']>5
  assert not r['pybullet_independent_kinematics']['ik_within_5mm']
  assert not r['robotic_assembly_pick_place_simulation']['proxy_self_collision_free']
  assert r['robotic_assembly_pick_place_simulation']['all_waypoints_position_reachable']
  assert not r['interval_stress_oracle']['motion_authorized']

def test_native_finger_cad_is_explicit_assumption():
 with zipfile.ZipFile(BUNDLE) as z:
  c=read(z,'catalog/finger_insert_assumptions.json')
  t=prepare_robot_arm_finger_inserts(c)
  assert t['body_names']==['HS_ArmFinger_Left','HS_ArmFinger_Right']
  assert not t['joint_and_gripper_fitting_measured']
  real=read(z,'native_cad/ARM_FINGER_CAD_TRIAL.json')
  assert real['native_solidcraft_executed']
  assert real['3mf_audit']['mesh_objects']==2
  assert all(row['closed_manifold'] for row in real['mesh_results'].values())
  assert not real['physical_fit_verified']

@pytest.mark.parametrize('key,value',[
 ('fastener_hole_diameter',100),
 ('length',0),
 ('print_layout_gap',-1),
 ('thickness',float('nan')),
])
def test_invalid_jaw_geometry_cannot_claim_print_candidate(key,value):
 with zipfile.ZipFile(BUNDLE) as z:c=read(z,'catalog/finger_insert_assumptions.json')
 c=deepcopy(c)
 c['dimensions_mm'][key]=value
 with pytest.raises(ValueError):
  prepare_robot_arm_finger_inserts(c)

def test_actual_sliced_gripper_gcode_and_manifest_hash(tmp_path):
 with zipfile.ZipFile(BUNDLE) as z:
  g=z.read('printer/MK4S_FINGER_PRINT_UNAPPROVED.gcode')
  stored=read(z,'printer/FINGER_SLICER_AUDIT.json')
  manifest=read(z,'MANIFEST.json')
 p=tmp_path/'candidate_unapproved.gcode'
 p.write_bytes(g)
 out=audit_offline_gcode(p,expected_parts=('HS_ArmFinger_Left','HS_ArmFinger_Right'))
 assert stored['sha256']==out['sha256']==manifest['GCODE_SHA256']
 assert out['layer_changes']==40
 assert out['estimated_filament_grams']==5.43
 assert out['real_print_authorized'] is False
 assert not stored['physical_printer_start_authorized']

def test_mismatched_product_gcode_cannot_be_reused_as_robot_jaws(tmp_path):
 with zipfile.ZipFile(BUNDLE) as z:
  p=tmp_path/'wrong_job.gcode'
  p.write_bytes(z.read('printer/MK4S_FINGER_PRINT_UNAPPROVED.gcode'))
 with pytest.raises(ValueError,match='object identity'):
  audit_offline_gcode(p)  # default expected casing parts


def test_real_agent_tool_feedback_corrected_arm_candidate():
 with zipfile.ZipFile(BUNDLE) as z:
  trace=read(z,'agent_loop/final_live_codex_arm_agent_trace.json')
  baseline=read(z,'agent_loop/initial_live_codex_tool_contract_failure.json')
  manifest=read(z,'MANIFEST.json')
 assert manifest['additional_live_robotics_agent_completed_with_revision']
 assert trace['status']=='MODEL_FINISHED'
 assert trace.get('model_is_test_double') is False
 assert [x['model_action'] for x in trace['steps']]==[
    'inspect_robot_arm_campaign','evaluate_assumed_robot_arm',
    'evaluate_assumed_robot_arm','finish'
 ]
 first_eval=trace['steps'][1]
 second_eval=trace['steps'][2]
 assert first_eval['tool_ok'] is False
 assert second_eval['tool_ok'] is True
 assert second_eval['tool_output']['stress_analysis']['result']=='PROVISIONAL_STATIC_SCREEN_ONLY'
 assert second_eval['tool_output']['stress_analysis']['proposed_geometric_chain_length_mm']==440.0
 assert trace['final_proposal']['decision']=='DIGITAL_CANDIDATE_ONLY_PHYSICAL_RELEASE_BLOCKED'
 assert not trace['physical_release']
 assert not trace['independent_engineering_assessment']['unsafe_model_physical_claims']
 assert baseline['status']=='STEP_BUDGET_EXHAUSTED'
 assert any(x.get('tool_ok') is False for x in baseline['steps'])

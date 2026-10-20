"""Live Codex robot-arm synthesis + existing HS deterministic arm evaluation.

The catalog deliberately contains hypothetical actuator classes with
explicit uncertainty. Its ratings are neither manufacturer measurements
nor certified usable donor capabilities. All physical authority remains
false.
"""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
from hardware_splicer.codex_chatgpt_llm_adapter import CodexCliAdapter
from hardware_splicer.robot_arm_design import (
 robot_arm_design_prompt,parse_robot_arm_design,RobotArmDesignError,evaluate_robot_arm_design
)
from hardware_splicer.robot_arm_kinematics import generate_robot_arm_urdf,run_pybullet_kinematics_oracle
from hardware_splicer.arm_splice_assumption_oracle import stress_test_assumed_arm
from hardware_splicer.robot_arm_assembly_dryrun import run_robotic_assembly_dryrun
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--spec',required=True,type=Path)
 p.add_argument('--codex-cli',required=True,type=Path)
 p.add_argument('--out',required=True,type=Path)
 a=p.parse_args()
 spec=json.loads(a.spec.read_text())
 if spec['information_authority']!='BENCHMARK_ASSUMPTION_ONLY' or spec.get('actual_salvaged_components_acquired') is not False:
  raise ValueError('benchmark assumptions must not masquerade as measured stock')
 out=a.out
 if out.exists() and any(out.iterdir()):raise FileExistsError("output not empty")
 out.mkdir(parents=True,exist_ok=True)
 model=CodexCliAdapter(cli_js=a.codex_cli)
 prompt=robot_arm_design_prompt(spec['test_goal'],requirements=spec['requirements'],
  inventory=spec['assumed_part_catalog'],source_ids=[])
 prompt+='\nAdditional benchmark design convention: every joint must have strictly positive link_length_mm, including base and wrist. Use a small physically plausible, explicitly assumed segment length instead of zero. No link length is measured.\n'
 attempts=[]
 proposal=None
 for attempt in range(3):
  answer=model(prompt,stage='planning',temperature=0,json_mode=True,timeout_s=120,
               system='Return only a fully typed robot arm JSON proposal; missing measurements remain assumptions; no physical release.')
  attempts.append({'attempt':attempt+1,'provider_real':answer.get('provider')=='codex_chatgpt',
                   'raw_model_output':answer.get('content') if answer.get('ok') else None,
                   'provider_error':answer.get('error')})
  if not answer.get('ok'):
   raise RuntimeError('ChatGPT-authenticated Codex failed: '+str(answer.get('error')))
  try:
   proposal=parse_robot_arm_design(answer['content'],inventory=spec['assumed_part_catalog'],known_source_ids=[])
   if proposal.source_ids:raise RobotArmDesignError('Assumed values cannot claim external source IDs')
   break
  except (RobotArmDesignError,ValueError) as e:
   attempts[-1]['validation_rejection']=str(e)[:1400]
   prompt='Revise your own prior robot-arm design to conform exactly to the HS typed design schema. Do not reuse any fabricated component or evidence IDs.\nORIGINAL SPEC:\n'+robot_arm_design_prompt(spec['test_goal'],requirements=spec['requirements'],inventory=spec['assumed_part_catalog'],source_ids=[])+ '\nPREVIOUS REJECTED PROPOSAL:\n'+str(answer.get('content'))+'\nVALIDATOR REPORT:\n'+str(e)+'\nCorrect only invalid assumptions. Every link has strictly positive dimension, and all constraints remain source-labelled assumptions.'
 if proposal is None:
  (out/'LIVE_MODEL_REJECTED_ATTEMPTS.json').write_text(json.dumps(attempts,indent=2)+'\n')
  raise RuntimeError('model failed structured engineering design contract after revisions')
 (out/'LIVE_MODEL_ATTEMPTS.json').write_text(json.dumps(attempts,indent=2)+'\n')
 evaluated=evaluate_robot_arm_design(proposal,requirements=spec['requirements'],inventory=spec['assumed_part_catalog'])
 conservative=stress_test_assumed_arm(proposal,spec)
 artifact=generate_robot_arm_urdf(proposal,robot_name='hs_proposed_salvage_assembly_arm')
 (out/'ROBOT_ARM_CANDIDATE.urdf').write_text(artifact.text)
 sim=run_pybullet_kinematics_oracle(proposal,urdf_path=str(out/'ROBOT_ARM_CANDIDATE.urdf'),
                                    workspace_samples=150,collision_samples=90)
 pickplace=run_robotic_assembly_dryrun(proposal,out/'ROBOT_ARM_CANDIDATE.urdf')
 (out/'ROBOTIC_ASSEMBLY_PICK_PLACE_DRYRUN.json').write_text(json.dumps(pickplace,indent=2)+'\n')
 raw={
  'schema_version':'hs.assumed_salvage_arm_real_model_trial.v1',
  'model_provider':'chatgpt_authenticated_codex',
  'model_attempts':len(attempts),
  'model_rejections':sum('validation_rejection' in x for x in attempts),
  'source_catalog_authority':'BENCHMARK_ASSUMPTION_ONLY',
  'nominal_actuator_specimens_real_count':0,
  'unmeasured_illustrative_numbers_used':True,
  'proposal':proposal.model_dump(mode='json'),
  'canonical_arm_evaluation':evaluated.model_dump(mode='json'),
  'interval_stress_oracle':conservative,
  'generated_urdf':{'file':'ROBOT_ARM_CANDIDATE.urdf','sha256':hashlib.sha256(artifact.text.encode()).hexdigest(),
                    'joints':artifact.joint_count,'chain_length_m':artifact.chain_length_m},
  'pybullet_independent_kinematics':sim,
  'robotic_assembly_pick_place_simulation':pickplace,
  'robotic_arm_as_fabrication_tool':'candidate design for later human-approved manipulator pick/place, not observed actuation',
  'actual_arm_controller_used':False,'printer_connected':False,
  'physical_fabrication_authorized':False,'motor_power_authorized':False
 }
 (out/'LIVE_ARM_DESIGN_EVALUATION.json').write_text(json.dumps(raw,indent=2)+'\n')
 (out/'ASSUMED_PART_CATALOG.json').write_text(json.dumps(spec,indent=2)+'\n')
 print(json.dumps({
 'joints':len(proposal.joints),
 'canonical_status':evaluated.status,
 'interval_status':conservative['result'],
 'pybullet_status':sim.get('status'),
 'pybullet_ik_within_5mm':sim.get('ik_within_5mm'),
 'robotic_assembly_waypoints_reachable':pickplace['all_waypoints_position_reachable'],
 'physical_release':False,
 'out':str(out),
 },indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())

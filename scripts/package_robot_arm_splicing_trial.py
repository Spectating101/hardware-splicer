"""Package genuine native CAD/PrusaSlicer/PyBullet artifacts with source labels."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
from hardware_splicer.realization_gcode_audit import audit_offline_gcode

BASE=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--initial',type=Path,required=True)
 ap.add_argument('--revised',type=Path,required=True)
 ap.add_argument('--native-fingers',type=Path,required=True)
 ap.add_argument('--out',type=Path,required=True)
 args=ap.parse_args()
 if args.out.exists():raise FileExistsError(args.out)
 original=json.loads((args.initial/'LIVE_ARM_DESIGN_EVALUATION.json').read_text())
 revised=json.loads((args.revised/'LIVE_ARM_DESIGN_EVALUATION.json').read_text())
 assert original['model_provider']==revised['model_provider']=='chatgpt_authenticated_codex'
 assert original['interval_stress_oracle']['result']=='ASSUMED_COMPONENT_INTERFACES_REQUIRE_REDIMENSION'
 assert revised['interval_stress_oracle']['result']=='PROVISIONAL_STATIC_SCREEN_ONLY'
 assert not original['physical_fabrication_authorized'] and not revised['physical_fabrication_authorized']
 assert revised['robotic_assembly_pick_place_simulation']['proxy_self_collision_free'] is False
 assert revised['pybullet_independent_kinematics']['urdf_load_pass']
 native=json.loads((args.native_fingers/'ARM_FINGER_CAD_TRIAL.json').read_text())
 assert native['independent_manifold_check_passed'] and native['part_count']==2
 audited=audit_offline_gcode(args.native_fingers/'ARM_FINGER_MK4S_UNAPPROVED.gcode',
  expected_parts=('HS_ArmFinger_Left','HS_ArmFinger_Right'))
 assert audited['layer_changes']==40
 assert not audited['real_print_authorized']
 source_map={
  'catalog/initial_assumptions.json':BASE/'examples/assumption_robot_arm/arm_salvage_benchmark_assumptions.json',
  'catalog/revised_assumptions.json':BASE/'examples/assumption_robot_arm/arm_salvage_revised_gear_assumptions.json',
  'catalog/finger_insert_assumptions.json':BASE/'examples/assumption_robot_arm/finger_insert_assumptions.json',
  'reports/initial_live_codex_design.json':args.initial/'LIVE_ARM_DESIGN_EVALUATION.json',
  'reports/revised_live_codex_design.json':args.revised/'LIVE_ARM_DESIGN_EVALUATION.json',
  'reports/initial_model_attempts.json':args.initial/'LIVE_MODEL_ATTEMPTS.json',
  'reports/revised_model_attempts.json':args.revised/'LIVE_MODEL_ATTEMPTS.json',
  'robotics/initial_kinematic_arm.urdf':args.initial/'ROBOT_ARM_CANDIDATE.urdf',
  'robotics/revised_kinematic_arm.urdf':args.revised/'ROBOT_ARM_CANDIDATE.urdf',
  'robotics/initial_pick_place_dryrun.json':args.initial/'ROBOTIC_ASSEMBLY_PICK_PLACE_DRYRUN.json',
  'robotics/revised_pick_place_dryrun.json':args.revised/'ROBOTIC_ASSEMBLY_PICK_PLACE_DRYRUN.json',
  'native_cad/ARM_FINGER_LAYOUT.solidcraft':args.native_fingers/'ARM_FINGER_LAYOUT.solidcraft',
  'native_cad/ARM_FINGER_LAYOUT.step':args.native_fingers/'ARM_FINGER_LAYOUT.step',
  'native_cad/ARM_FINGER_LAYOUT.3mf':args.native_fingers/'ARM_FINGER_LAYOUT.3mf',
  'native_cad/HS_ArmFinger_Left.stl':args.native_fingers/'HS_ArmFinger_Left.stl',
  'native_cad/HS_ArmFinger_Right.stl':args.native_fingers/'HS_ArmFinger_Right.stl',
  'native_cad/HS_ArmFinger_Left.step':args.native_fingers/'HS_ArmFinger_Left.step',
  'native_cad/HS_ArmFinger_Right.step':args.native_fingers/'HS_ArmFinger_Right.step',
  'native_cad/ARM_FINGER_CAD_TRIAL.json':args.native_fingers/'ARM_FINGER_CAD_TRIAL.json',
  'printer/MK4S_FINGER_PRINT_UNAPPROVED.gcode':args.native_fingers/'ARM_FINGER_MK4S_UNAPPROVED.gcode',
  'printer/FINGER_SLICER_AUDIT.json':args.native_fingers/'ARM_FINGER_SLICER_AUDIT.json',
  'partcad/partcad.yaml':args.native_fingers/'partcad/partcad.yaml',
  'partcad/robot_finger_pair.assy':args.native_fingers/'partcad/robot_finger_pair.assy',
  'partcad/PARTCAD_BOM_RESULT.txt':args.native_fingers/'partcad/bom.log',
  'partcad/HS_ArmFinger_Left.step':args.native_fingers/'partcad/HS_ArmFinger_Left.step',
  'partcad/HS_ArmFinger_Right.step':args.native_fingers/'partcad/HS_ArmFinger_Right.step',
  'docs/ROBOT_ARM_OPERATOR_HANDOFF.md':BASE/'docs/integrations/ROBOTIC_ARM_SPLICING_OPERATOR_HANDOFF_2026-10-20.md',
  'docs/TRIAL_RESULT.md':BASE/'docs/evaluations/ASSUMED_ROBOT_ARM_SPLICING_TRIAL_2026-10-20.md',
 }
 for name,p in source_map.items():
  if not p.is_file():raise FileNotFoundError(name+' -> '+str(p))
 manifest={
  'schema_version':'hs.arm_hypothetical_splicing_trial_manifest.v1',
  'date':'2026-10-20',
  'live_llm_used':True,
  'two_live_model_arm_designs':True,
  'actual_pybullet_installed_and_called':True,
  'actual_solidcraft_and_partcad_called':True,
  'actual_prusaslicer_executed':True,
  'model_size_of_first_arm_mm':original['interval_stress_oracle']['proposed_geometric_chain_length_mm'],
  'model_size_of_revised_arm_mm':revised['interval_stress_oracle']['proposed_geometric_chain_length_mm'],
  'original_torque_screen_result':original['interval_stress_oracle']['result'],
  'revised_torque_screen_result':revised['interval_stress_oracle']['result'],
  'revised_generic_ik_under_5mm':revised['pybullet_independent_kinematics']['ik_within_5mm'],
  'revised_pick_place_proxy_collision_free':revised['robotic_assembly_pick_place_simulation']['proxy_self_collision_free'],
  'real_robot_present':False,'real_printer_present':False,'donor_components_acquired':False,
  'real_safety_interlock_tested':False,'physical_fabrication_authorized':False,
  'GCODE_SHA256':audited['sha256'],
  'GCODE_LAYER_COUNT':audited['layer_changes'],
  'GCODE_FILAMENT_ESTIMATE_G':audited['estimated_filament_grams'],
  'GCODE_TIME_ESTIMATE':audited['estimated_print_time'],
  'included_files':{name:{'sha256':sha(path),'bytes':path.stat().st_size}
                    for name,path in source_map.items()}
 }
 with zipfile.ZipFile(args.out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
  for name,path in sorted(source_map.items()):z.write(path,arcname=name)
  z.writestr('MANIFEST.json',json.dumps(manifest,sort_keys=True,indent=2)+'\n')
 with zipfile.ZipFile(args.out) as z:
  assert z.testzip() is None
 print(json.dumps({'archive':str(args.out),'bytes':args.out.stat().st_size,
  'documents_in_archive':len(source_map)+1,
  'initial_design_needs_redimension':True,
  'revised_static_torque_screen_provisional_pass':True,
  'pick_place_proxy_collision_free':False,
  'actual_printer_or_arm_present':False},indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())

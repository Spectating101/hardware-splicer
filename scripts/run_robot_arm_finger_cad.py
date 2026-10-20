"""Generate two candidate robot-jaw finger inserts with native SolidCraft."""
from __future__ import annotations
import argparse,json,hashlib,subprocess
from pathlib import Path
from hardware_splicer.robot_arm_cad_adapter import prepare_robot_arm_finger_inserts
from scripts.run_printed_enclosure_workbench import _stl_report,_3mf_report

def execute(bin,args,out):
 r=subprocess.run([str(bin),*args],cwd=out,capture_output=True,text=True,timeout=140)
 if r.returncode:raise RuntimeError("SolidCraft failed "+r.stderr[-700:])
def main():
 a=argparse.ArgumentParser()
 a.add_argument('--spec',required=True,type=Path)
 a.add_argument('--solidcraft-cli',required=True,type=Path)
 a.add_argument('--out',required=True,type=Path)
 args=a.parse_args()
 out=args.out
 if out.exists() and any(out.iterdir()):raise ValueError('output not empty')
 out.mkdir(parents=True,exist_ok=True)
 plan=prepare_robot_arm_finger_inserts(json.loads(args.spec.read_text()))
 (out/'ARM_FINGER_CAD_PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
 layout=out/'ARM_FINGER_LAYOUT.commands.json'
 layout.write_text(json.dumps(plan['solidcraft_commands'],indent=2))
 cli=args.solidcraft_cli.resolve(strict=True)
 native=out/'ARM_FINGER_LAYOUT.solidcraft'
 execute(cli,['run',str(layout),'--save',str(native),'--out',str(out/'ARM_FINGER_LAYOUT.step'),'--json-out',str(out/'CAD_RESULT.json')],out)
 execute(cli,['eval',str(native),'--json-out',str(out/'CAD_EVALUATED.json')],out)
 eval=json.loads((out/'CAD_EVALUATED.json').read_text())
 if {x['name'] for x in eval['bodies']}!=set(plan['body_names']):
  raise ValueError('unexpected SolidCraft body names')
 exports=[]
 for name in plan['body_names']:
  exports.extend([
   {'command':'file.save_mesh','params':{'path':str(out/(name+'.stl')),'format':'stl','bodies':[name]}},
   {'command':'file.export','params':{'path':str(out/(name+'.step')),'format':'step','bodies':[name]}}
  ])
 exports.append({'command':'file.save_mesh','params':{
  'path':str(out/'ARM_FINGER_LAYOUT.3mf'),'format':'3mf','bodies':plan['body_names']}})
 ep=out/'ARM_FINGER_EXPORT.commands.json'
 ep.write_text(json.dumps({'commands':exports},indent=2))
 execute(cli,['run',str(ep),'--in',str(native),'--results','--json-out',str(out/'EXPORT_RESULT.json')],out)
 mesh={}
 for name in plan['body_names']:
  mesh[name]=_stl_report(out/(name+'.stl'))
 info=_3mf_report(out/'ARM_FINGER_LAYOUT.3mf')
 record={
  'schema_version':'hs.real_native_salvage_robot_arm_fingers.v1',
  'native_solidcraft_executed':True,
  'part_count':2,'independent_manifold_check_passed':True,
  'mesh_results':mesh,'3mf_audit':info,
  'body_sizes':{x['name']:x['bbox'] for x in eval['bodies']},
  'physical_fit_verified':False,'printer_connected':False,
  'gripper_clamp_force_verified':False,
  'artifact_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*') if p.is_file()},
 }
 (out/'ARM_FINGER_CAD_TRIAL.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps({'native_generated':True,'independent_manifold_check_passed':True,
                   '3mf_bodies':info['mesh_objects'],'physical_gripper_fit_proven':False},indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())

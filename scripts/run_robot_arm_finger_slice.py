"""Slice actual native SolidCraft printed robotic finger inserts, offline only."""
from __future__ import annotations
import argparse,json,os,subprocess,hashlib
from pathlib import Path
from hardware_splicer.realization_gcode_audit import audit_offline_gcode
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--native-cad-dir",type=Path,required=True)
 p.add_argument("--slicer",type=Path,required=True)
 p.add_argument("--profile",type=Path,required=True)
 p.add_argument("--resources",type=Path,required=True)
 p.add_argument("--libraries",type=Path,required=True)
 a=p.parse_args()
 input=a.native_cad_dir/"ARM_FINGER_LAYOUT.3mf"
 outfile=a.native_cad_dir/"ARM_FINGER_MK4S_UNAPPROVED.gcode"
 env=os.environ.copy()
 env['LD_LIBRARY_PATH']=str(a.libraries.resolve(strict=True))
 env['SLIC3R_RESOURCES_DIR']=str(a.resources.resolve(strict=True))
 proc=subprocess.run([
  str(a.slicer.resolve(strict=True)),"--load",str(a.profile.resolve(strict=True)),
  "--center","125,105","--export-gcode","-o",str(outfile),str(input)
 ],capture_output=True,text=True,env=env,timeout=150)
 if proc.returncode:raise RuntimeError(proc.stderr[-700:])
 audit=audit_offline_gcode(outfile,expected_parts=("HS_ArmFinger_Left","HS_ArmFinger_Right"))
 audit['robotic_finger_fit_to_real_gripper_qualified']=False
 audit['physical_printer_start_authorized']=False
 (a.native_cad_dir/'ARM_FINGER_SLICER_AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
 print(json.dumps({'gcode_bytes':audit['bytes'],'grams':audit['estimated_filament_grams'],
  'estimated_time':audit['estimated_print_time'],'layers':audit['layer_changes'],
  'bodies':list(audit['object_bounding_boxes_mm']),
  'physical_fabrication_authorized':False},indent=2))
if __name__=="__main__":main()

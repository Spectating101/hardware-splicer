"""Generate real offline PrusaSlicer job and conditional build handoff bundle."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, zipfile
from pathlib import Path
from hardware_splicer.realization_gcode_audit import audit_offline_gcode

ROOT=Path(__file__).resolve().parents[1]
def hashfile(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--slicer',required=True,type=Path)
    a.add_argument('--resources',required=True,type=Path)
    a.add_argument('--library-directory',required=True,type=Path)
    a.add_argument('--profile',required=True,type=Path)
    a.add_argument('--out',required=True,type=Path)
    args=a.parse_args()
    out=args.out.resolve()
    if out.exists() and any(out.iterdir()):raise ValueError('output must be a fresh empty directory')
    out.mkdir(parents=True,exist_ok=True)
    original=ROOT/'examples/printed_casing/native_trial'
    env=os.environ.copy()
    env['LD_LIBRARY_PATH']=str(args.library_directory.resolve(strict=True))
    env['SLIC3R_RESOURCES_DIR']=str(args.resources.resolve(strict=True))
    gcode=out/'MK4S_CASING_UNAPPROVED.gcode'
    cmd=[str(args.slicer.resolve(strict=True)),'--load',str(args.profile.resolve(strict=True)),
         '--center','125,105','--export-gcode','-o',str(gcode),
         str(original/'CASE_PRINT_LAYOUT.3mf')]
    completed=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=150,check=False)
    (out/'SLICER_LOG.txt').write_text((completed.stdout+'\n'+completed.stderr)[-10000:])
    if completed.returncode or not gcode.exists():raise RuntimeError('PrusaSlicer failed')
    audit=audit_offline_gcode(gcode)
    (out/'GCODE_AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
    files=[
      'CASE_PRINT_LAYOUT.solidcraft','CASE_ASSEMBLED.solidcraft',
      'HS_Casing_Base.stl','HS_Casing_Lid.stl','CASE_PRINT_LAYOUT.3mf',
      'CASE_PRINT_LAYOUT.png','CASE_ASSEMBLED.png',
      'partcad/partcad.yaml','partcad/casing_assembled.assy',
      'partcad/HS_Casing_Base.step','partcad/HS_Casing_Lid.step',
      'partcad/PartCAD_Casing_Assembly.step']
    for rel in files:
        src=original/rel;dst=out/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dst)
    shutil.copyfile(args.profile,out/'PRUSA_MK4S_PLA_TEST_PROFILE.ini')
    bom={
      'case_id':'conceptual_controller_housing_v0','assembly_status':'CONCEPT_ONLY',
      'printed_parts':[{'id':'casing_base','qty':1},{'id':'casing_lid','qty':1}],
      'actual_donor_stock':0,
      'proposed_external_components':[
       {'name':'scanner','owned':False,'interface_verified':False},
       {'name':'printer_mechanism','owned':False,'motor_ratings_verified':False},
       {'name':'controller','owned':False,'pinout_verified':False},
       {'name':'independent_motion_stop','owned':False,'rating_verified':False}],
      'assembly_proven':False,'electrical_wiring_authorized':False,
      'physical_print_authorized':False,
    }
    (out/'CONDITIONAL_BOM.json').write_text(json.dumps(bom,indent=2)+'\n')
    manifest={
      'schema_version':'hs.realization_pilot.v1','real_prusaslicer_invoked':True,
      'printer_assumed_not_discovered':'Original Prusa MK4S 0.4 mm',
      'profile_test_material':'Prusament PLA',
      'gcode_sha256':audit['sha256'],
      'source_3mf_sha256':hashfile(original/'CASE_PRINT_LAYOUT.3mf'),
      'vendor_profile_source_sha256':hashfile(args.profile),
      'printed_parts_count':2,'donors_physically_observed':0,
      'gcode_model_footprints_audited':True,
      'vendor_purge_path_review_required':audit['vendor_purge_path_review_required'],
      'printer_connected':False,'gcode_approved_by_human':False,
      'physical_fabrication_authorized':False,
      'electrical_assembly_verified':False,
      'blocking_evidence':[
       'Real MK4S ownership, model, firmware and print plate/nozzle profile',
       'Vendor purge path at Y = -4 mm requires machine-specific review',
       'Slicer first-layer, supports, filament adhesion and toolpath visual review',
       'Actual printed tolerance coupon and first-article mechanical fitting',
       'Actual recovered component mechanical/electrical measurements',
       'Verified low-voltage harness diagram, actual controller and independently effective stop'],
    }
    manifest['files_sha256']={
      str(p.relative_to(out)):hashfile(p) for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'REALIZATION_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    zip_path=out.with_suffix('.zip')
    if zip_path.exists():raise FileExistsError(zip_path)
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
      for p in sorted(out.rglob('*')):
        if p.is_file():z.write(p,arcname=str(p.relative_to(out)))
    print(json.dumps({'gcode_bytes':audit['bytes'],'filament_g':audit['estimated_filament_grams'],
                      'print_time':audit['estimated_print_time'],
                      'z_layers':audit['layer_changes'],'zip':str(zip_path),
                      'physical_release':False},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())

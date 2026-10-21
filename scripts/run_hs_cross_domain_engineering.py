#!/usr/bin/env python3
"""Run the SAME HS source/action endpoints on independent, real engineering projects.

Source paths are evaluator-supplied upstream artifacts, not model inventions.
Each project receives isolated persisted state and an actual tool-dispatch result.
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

CASES={
 'cyberdeck': {
    'id':'hs-flex-cyberdeck',
    'mission':'Engineer a field cyberdeck with Linux compute, input, display and regulated power. Investigate whether the registered source PCB and enclosure can function together; calculate blockers rather than guess compatibility.',
    'files':[
      ('/tmp/hs-capability-trial-20261020/reference/extracted/RPI_Dev_1.kicad_pro','RPI_Dev_1.kicad_pro','sector07-dev/RPI_DEV'),
      ('/tmp/hs-capability-trial-20261020/reference/extracted/RPI_Dev_1.kicad_sch','RPI_Dev_1.kicad_sch','sector07-dev/RPI_DEV'),
      ('/tmp/hs-capability-trial-20261020/reference/extracted/RPI_Dev_1.kicad_pcb','RPI_Dev_1.kicad_pcb','sector07-dev/RPI_DEV'),
      ('/tmp/hs-capability-trial-20261020/reference/extracted/Front Case.stl','Front Case.stl','sector07-dev/RPI_DEV'),
      ('/tmp/hs-real-cyberdeck-replay-20261020/reference-options/dinodeck-2026/docs/BOM.md','BOM.md','therebelrobot/dinodeck-2026@7762e2f'),
     ],
    'result_type':'pcb/electrical + STL + BOM',
    'constraints': {'max_cost_usd':250}},
 'drone': {
    'id':'hs-flex-drone',
    'mission':'Engineer a practical affordable quadcopter. Inspect manufacturer X500 V2 solid CAD and the independent S500 arm geometry. Compare physical envelopes cautiously; identify exact donor-adapter measurements and other missing design evidence.',
    'files':[
       ('/tmp/hs_drone_vendor_cad/x500v2-frame.step','x500v2-frame.step','Holybro manufacturer X500 V2 STEP'),
       ('/tmp/hs_drone_reference_scan/DroneSkeleton/arm.scad','s500-arm.scad','colgecen/DroneSkeleton@15d139b'),
     ],
    'result_type':'OCCT BREP STEP + donor OpenSCAD mesh'},
 'psp': {
    'id':'hs-flex-psp-umd-repair',
    'mission':'Evaluate UMD drive access and repair risk in a PSP-300x using the original iFixit repair guide. Identify procedural risk, missing fault-discrimination evidence and exact unknown hardware revision; do not conclude the drive is faulty or authorize powered repair.',
    'files':[
       ('/tmp/hs-real-repair-psp/umd-replacement.html','PSP300x_UMD_repair.html','iFixit PSP 300x UMD Drive Replacement guide 1586'),
     ],
    'result_type':'real device repair-guide source'},
}

# Independent evaluator supplies these explicitly declared jobs. The AI cannot
# fabricate physical measurements while selecting their software assessments.
CASES['cyberdeck']['engineering_layer_requests'] = {
 'mechanical':{'design':{'enclosure':{'name':'RPI_DEV_cover_not_mated_to_PCB'}},'mode':'advisory'},
 'chemistry':{'task':'manage_thermal_interface','primary_material':'unknown',
             'material_identity':'unknown','electrical_state':'unknown',
             'battery_status':'unknown'},
 'enclosure':json.loads((ROOT/'examples/printed_casing/conceptual_salvage_controller.json').read_text()),
}
CASES['drone']['engineering_layer_requests'] = {
 'mechanical':{'design':{'assembly':{'name':'X500_frame_and_S500_arm_unverified_join'}},
               'mode':'advisory'},
}
CASES['psp']['engineering_layer_requests'] = {
 'chemistry':{'task':'clean_contacts','primary_material':'unknown',
             'material_identity':'unknown','electrical_state':'unknown',
             'battery_status':'unknown'},
 'mechanical':{'design':{'assembly':{'name':'PSP_UMD_drive_access'}} ,'mode':'advisory'},
}


def run_case(case_name:str, root:Path):
    case=CASES[case_name]
    project_id=case['id']
    store=ProjectStore(root/'store')
    client=TestClient(create_product_app(store))
    if (store.root/project_id/'project.json').exists():
        raise ValueError('refusing to overwrite existing trial project; use new root')
    initial={'projectId':project_id,'projectName':project_id,'mission':case['mission'],
             'constraints':case.get('constraints',{}),
             'engineeringLayerRequests':case.get('engineering_layer_requests',{}),
             'approved_catalog_build_ids':[],
             'fabrication_authorized':False,'power_on_authorized':False,
             'release_authorized':False}
    rev=store.save(project_id,initial,metadata={'origin':'real_cross_domain_trial'})['revision']
    records=[]
    for filename,source_name,source_origin in case['files']:
        path=Path(filename)
        if not path.exists():raise ValueError('missing actual reference file '+filename)
        content=path.read_bytes()
        response=client.post(f'/v1/projects/{project_id}/sources/ingest',json={
            'filename':source_name,'content_base64':base64.b64encode(content).decode(),
            'expected_revision':rev,
            'metadata':{'external_reference_origin':source_origin,'evaluator_supplied':True}})
        if response.status_code != 201:raise RuntimeError('source registration rejected '+source_name+': '+response.text[:400])
        rev=response.json()['revision']
        records.append({'name':source_name,'source_repository_or_vendor':source_origin,
                        'sha256':'sha256:'+sha256(content).hexdigest(),
                        'source_id':response.json()['ingestion']['source_id'],'size_bytes':len(content)})
        print(case_name,'INGEST',source_name,len(content),'revision',rev,flush=True)
    analyzed=client.post(f'/v1/projects/{project_id}/engineering/source-bundle/check',
                         json={'expected_revision':rev})
    if analyzed.status_code!=200:
        raise RuntimeError('HS source check failed: '+analyzed.text[:800])
    data=analyzed.json()
    src=data['source_bundle_run']
    summary={'case':case_name,'project_id':project_id,'mission':case['mission'],
             'device_type':case['result_type'],'source_records':records,
             'revision':data['revision'],'checked_software_through':'HS canonical project source bundle API',
             'source_check':src,'physical_object_inspected':False,
             'new_verified_design_created':False,'physical_hardware_delivered':False}
    root.mkdir(parents=True,exist_ok=True)
    out=root/f'{case_name}_source_execution.json'
    out.write_text(json.dumps(summary,indent=2)+'\n')
    print(case_name,'ANALYZED',src['status'],'tool',src['software_tool'],
          'geometry',len(src['geometry']),'repair',len(src['repair_evidence']),
          'netlist',src.get('netlist',{}).get('component_count'),'revision',data['revision'],flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('case',choices=tuple(CASES))
    parser.add_argument('--out-root',type=Path,default=Path('/tmp/hs-cross-domain-20261021'))
    args=parser.parse_args();run_case(args.case,args.out_root)

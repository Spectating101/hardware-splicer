#!/usr/bin/env python3
"""Run the genuine HS project ingestion and complete-source check on a public cyberdeck.

Evaluator chooses the reference source set but does not invent design facts.
The isolated HS store and API TestClient preserve real revisions and outputs.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def run(source: Path, destination: Path):
    project='cyberdeck-source-project-20261020'
    store=ProjectStore(destination/'store')
    if (destination/'store'/project/'project.json').exists():
        raise RuntimeError('refusing to overwrite an earlier cyberdeck run')
    saved=store.save(project,{'projectId':project,'projectName':'Portable Linux field cyberdeck',
                               'mission':'Engineer a field cyberdeck with display, keyboard, USB, reliable external power, accessible components and an enclosure; determine whether this reference PCB is sufficient.',
                               'fabrication_authorized':False,'power_on_authorized':False,
                               'release_authorized':False},metadata={'source':'real_cyberdeck_replay'})
    client=TestClient(create_product_app(store))
    records=[]
    for name in ['RPI_Dev_1.kicad_sch','RPI_Dev_1.kicad_pcb','RPI_Dev_1.kicad_pro','Front Case.stl']:
        blob=(source/name).read_bytes()
        resp=client.post(f'/v1/projects/{project}/sources/ingest',json={
             'filename':name,'content_base64':base64.b64encode(blob).decode(),
             'expected_revision':saved['revision']})
        data=resp.json()
        if resp.status_code!=201 or not data.get('ok'):
            raise RuntimeError(f'ingest failure {name}: {resp.status_code}: {str(data)[:700]}')
        saved['revision']=data['revision']
        records.append({'filename':name,'sha256':'sha256:'+hashlib.sha256(blob).hexdigest(),
                        'source_id':data['ingestion']['source_id'],'classification':data['ingestion']['classification']['kind']})
    response=client.post(f'/v1/projects/{project}/engineering/source-bundle/check',json={'expected_revision':saved['revision']})
    if response.status_code!=200:raise RuntimeError(f'HS bundle API error: {response.status_code}: {response.text[:1000]}')
    payload=response.json()
    if not payload['ok']:raise RuntimeError('HS returned not ok')
    bundle=payload['source_bundle_run']
    assert bundle['software_checks']['erc']['rule_finding_count']==43
    assert bundle['software_checks']['drc']['rule_finding_count']==16
    assert bundle['netlist']['component_count']==26
    assert bundle['netlist']['net_count']==47
    second=client.post(f'/v1/projects/{project}/engineering/source-bundle/check',json={'expected_revision':payload['revision']})
    assert second.status_code==200 and second.json()['registered'] is False
    result={'project_id':project,'source_input_type':'real upstream cyberdeck CAD and KiCad files',
            'operator':'HS canonical FastAPI source ingestion and project-source bundle operation',
            'source_registration':records,'project_revision':payload['revision'],
            'idempotent_second_call':True,'analysis':bundle,
            'engineered_device_completed':False,'purchased_hardware':False,
            'physical_build_completed':False}
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'real_source_execution.json').write_text(json.dumps(result,indent=2)+'\n')
    print('OK real HS API source project: revision',payload['revision'],'sources',len(records),
          'erc',bundle['software_checks']['erc']['rule_finding_count'],
          'drc',bundle['software_checks']['drc']['rule_finding_count'],
          'components',bundle['netlist']['component_count'],
          'nets',bundle['netlist']['net_count'],
          'STL span',bundle['geometry']['Front Case.stl'].get('axis_span'))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source-dir',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args()
    run(a.source_dir,a.out_dir)

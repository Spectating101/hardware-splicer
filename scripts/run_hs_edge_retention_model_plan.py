#!/usr/bin/env python3
"""Native Copilot and Opus plan synthesis -> pinned real KiCad CAD operations.

Existing model review traces are used to choose a narrowly defined software
CAD action; the new Copilot session must propose it. User authorized software
checks, not 3D printing, materials qualification or buying hardware.
"""
from __future__ import annotations
import base64,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

trial=Path(os.getenv('HS_EDGE_TRIAL_ROOT') or '/tmp/hs-edge-retention-proof-20261021')
trial.mkdir(parents=True,exist_ok=True)
store=ProjectStore(trial/'project-store')
pid='hs-cyberdeck-edge-retention-proof'
if (store.root/pid/'project.json').exists():
    raise ValueError('refusing to overwrite original source CAD replay')
ref=ROOT/'.cache/source-proofs/RPI_DEV_extracted/RPI Dev/RPI_Dev_1'
source_paths=[ref/'RPI_Dev_1.kicad_pro',ref/'RPI_Dev_1.kicad_pcb',ref/'RPI_Dev_1.kicad_sch']
client=TestClient(create_product_app(store))
rev=store.save(pid,{
    'projectId':pid,'projectName':'Model-assisted source contour PCB retention review',
    'constraints':{'max_cost_usd':250},
    'engineeringLayerRequests':{},
    'manufacturingClosure':{'production_ready':False},
    'release_authorized':False,'fabrication_authorized':False,
    'source_owner':'sector07-dev/RPI_DEV external source, user supplied',
},metadata={'provenance':'verified original public KiCad source software-only trial'})['revision']
registered=[]
for p in source_paths:
    raw=p.read_bytes();expected='sha256:'+hashlib.sha256(raw).hexdigest()
    resp=client.post(f'/v1/projects/{pid}/sources/ingest',json={
       'filename':p.name,'content_base64':base64.b64encode(raw).decode(),
       'expected_revision':rev,
       'metadata':{'original_owner':'sector07-dev/RPI_DEV','user_provided_reference':True}})
    if resp.status_code!=201:raise ValueError('real source registration failed '+resp.text[:500])
    rev=resp.json()['revision']
    assert resp.json()['ingestion']['content_hash']==expected
    registered.append({'filename':p.name,'source_sha256':expected,
           'source_id':resp.json()['ingestion']['source_id']})

analysed=client.post(f'/v1/projects/{pid}/engineering/source-bundle/check',json={'expected_revision':rev})
if analysed.status_code!=200:raise ValueError('KiCad project check failed '+analysed.text[:500])
rev=analysed.json()['revision']
run=analysed.json()['source_bundle_run']
assert run['board_interface_geometry']['edge_cuts_profile_closed']
assert len(run['board_interface_geometry']['edge_cuts_profile_mm'])==33

mission=(
 'Continue actual field cyberdeck engineering with this SOURCE-REGISTERED KiCad '
 'board. Prior independent reviewers Copilot and Opus both rejected invented M3 '
 'board mounting holes. Copilot proposed external perimeter retention; Opus proposed '
 'edge-captured base plus screw-closed lid using an exact Edge.Cuts profile, with '
 'case screws OUTSIDE the board and physical clearance still unverified. '
 'The old envelope-only candidate has no actual retention. '
 'Propose generate_board_edge_retention_candidate to build the improved source-derived '
 'two-piece CAD prototype and verify solid interference using the registered KiCad '
 'project. Also propose generate_board_carrier_candidate as the envelope-only baseline '
 'if action slots allow. Explicitly keep component fit, pad keepouts, mechanical strength, '
 'material qualification and print approval BLOCKED. Never infer screw holes from Q1.')
res=client.post(f'/v1/projects/{pid}/ai-sessions',json={
    'mission':mission,'expected_revision':rev,'model_profile':'deep_synthesis',
    'constraints':{'software_only':True,'no_fabrication':True,'material_validation_unresolved':True},
    'max_actions':7})
if res.status_code!=200:raise RuntimeError('model session failed '+res.text[:600])
rev=res.json()['revision'];session=res.json()['session']
logs={'project_id':pid,'source_records':registered,
      'model':session.get('model'),'provider':session.get('provider'),
      'session_id':session['session_id'],
      'model_summary':session.get('summary'),
      'model_actions':[{'type':a['action_type'],'title':a['title'],
                       'source_ids':a.get('source_ids'),
                       'unrecognized_ids':a.get('unrecognized_source_ids')}
                      for a in session['actions']],
      'executed_actions':[],'no_physical_authority':True}
allowed=['generate_board_carrier_candidate','generate_board_edge_retention_candidate']
for action_type in allowed:
    matching=[a for a in session['actions'] if a['action_type']==action_type and not a.get('unrecognized_source_ids')]
    if not matching:
        logs['executed_actions'].append({'type':action_type,'status':'not_proposed_by_model'})
        continue
    a=matching[0]
    url=f'/v1/projects/{pid}/ai-sessions/{session["session_id"]}/actions/{a["action_id"]}'
    decision=client.post(url+'/decision',json={
      'decision':'accepted','reviewer':'assistant-authorized-source-CAD-check',
      'note':'User delegated software-only engineering evidence and candidate generation. No physical manufacturing or material approval.',
      'expected_revision':rev})
    if decision.status_code!=200:raise RuntimeError('decision '+decision.text[:600])
    rev=decision.json()['revision']
    check=client.post(url+'/execute-preview',json={'expected_revision':rev})
    if check.status_code!=200:raise RuntimeError('execute '+check.text[:600])
    rev=check.json()['revision']
    result=check.json()['tool_result']
    logs['executed_actions'].append({'type':action_type,
      'status':result['status'],'summary':result.get('summary'),
      'artifact':result.get('artifact'), 'source_pinned':True})
    print('ACTION',action_type,result['status'],str(result.get('summary'))[:280],flush=True)
(trial/'api_operator_design_run.json').write_text(json.dumps(logs,indent=2)+'\n')
print('PROJECT',pid,'REV',rev,'MODEL',logs['model'],'SELECTED',[a['type'] for a in logs['executed_actions']],flush=True)

#!/usr/bin/env python3
"""Retry model-proposed source-only CAD in same intact HS project, no new inputs."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

trial=Path(os.getenv('HS_EDGE_TRIAL_ROOT') or '/tmp/hs-edge-retention-proof-20261021-v2')
store=ProjectStore(trial/'project-store')
pid='hs-cyberdeck-edge-retention-proof'
client=TestClient(create_product_app(store))
current=store.load_latest_with_recovery(pid)
rev=current['revision']
mission=(
 'The source-registered RPI_DEV KiCad board has no mounting-hole footprints. '
 'Its 33-vertex sampled Edge.Cuts profile has a notch. The original board also has 145 '
 'pads, 456 tracks/vias, 0 zones, and seven traces near the lip clearance. The fixed-parameter '
 'CAD action is software-only and does NOT require mechanical load inputs. '
 'Propose generate_board_edge_retention_candidate with inputs {} to produce the '
 'original-source two-piece PCB edge-capture base/lid. It must exclude 23 pad bounding boxes '
 'AND the 7 near-edge traces/vias from retaining lips; rerun board-only STEP interference. '
 'Do not assert populated component fit or physical retention; approval remains blocked. '
 'Do not request manufacturing, purchasing or source-independent dimensions.')
resp=client.post(f'/v1/projects/{pid}/ai-sessions',json={
 'mission':mission,'expected_revision':rev,
 'constraints':{'software_only':True,'fixed_parameter_CAD':True,
                'mechanical_physical_validation_required':True},
 'max_actions':6,'model_profile':'deep_synthesis'})
if resp.status_code!=200:raise RuntimeError('model error '+resp.text[:800])
rev=resp.json()['revision'];session=resp.json()['session']
matching=[a for a in session['actions'] if a['action_type']=='generate_board_edge_retention_candidate'
          and not a.get('unrecognized_source_ids')]
report={
  'project':pid,'native_source_stored':True,'model_provider':session['provider'],
  'model':session['model'],'session_id':session['session_id'],
  'summary':session['summary'],'action_types':[a['action_type'] for a in session['actions']],
  'proposed_cad':bool(matching), 'execution_status':'not_requested',
  'physical_authority':False}
if matching:
    a=matching[0]
    path=f'/v1/projects/{pid}/ai-sessions/{session["session_id"]}/actions/{a["action_id"]}'
    dec=client.post(path+'/decision',json={'decision':'accepted','expected_revision':rev,
        'reviewer':'assistant-delegated-software-CAD','note':'Approved actual CAD check only; no fabrication or material qualification'})
    if dec.status_code!=200:raise RuntimeError('decision '+dec.text[:800])
    rev=dec.json()['revision']
    exe=client.post(path+'/execute-preview',json={'expected_revision':rev})
    if exe.status_code!=200:raise RuntimeError('execution '+exe.text[:800])
    rev=exe.json()['revision'];tool=exe.json()['tool_result']
    report.update({'execution_status':tool['status'],
                   'execution_summary':tool['summary'],'artifact':tool['artifact']})
(trial/'pad_aware_ai_action.json').write_text(json.dumps(report,indent=2)+'\n')
print('REPLAY','PROPOSED',report['proposed_cad'],'STATUS',report['execution_status'],
      'MODEL',session['model'],'ACTION_TYPES',report['action_types'],'REV',rev,flush=True)

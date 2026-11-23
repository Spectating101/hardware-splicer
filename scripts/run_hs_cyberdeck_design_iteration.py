#!/usr/bin/env python3
"""Make HS, not the evaluator, request CAD from the live cyberdeck project."""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

root=Path('/tmp/hs-cross-domain-20261021')
store=ProjectStore(root/'store')
project='hs-flex-cyberdeck'
client=TestClient(create_product_app(store))
revision=store.load_latest_with_recovery(project)['revision']
mission=('Continue the same actual Linux cyberdeck engineering objective. The registered KiCad board and '
         'front-case mesh have been analyzed. We need a NEW physical-design artifact rather than another '
         'explanation. Produce a safe, software-only CAD carrier candidate derived from the actual PCB '
         'source, using the existing generate_board_carrier_candidate capability if suitable. '
         'The carrier must be labeled proposed only: holes, retention, full component interference, '
         'enclosure units/fit and material strength are not yet verified. Keep precise source IDs, '
         'or refer to numbered canonical source aliases S1, S2, etc. Never assert ready-to-print or power-on.')
request={'mission':mission,'expected_revision':revision,'model_profile':'deep_synthesis',
         'constraints':{'software_only':True,'mechanical_design_allowed':'candidate_only'},
         'max_actions':5}
resp=client.post(f'/v1/projects/{project}/ai-sessions',json=request)
out={'project':project,'model_http':resp.status_code,'selected_cad_action_executed':False}
if resp.status_code==200:
    body=resp.json();session=body['session'];rev=body['revision']
    out.update({'model':session.get('model'),'provider':session.get('provider'),
                'session_id':session['session_id'],'actions':[
                    {'type':a['action_type'],'title':a['title'],'source_ids':a.get('source_ids'),
                     'unrecognized_source_ids':a.get('unrecognized_source_ids')}
                    for a in session['actions']],
                'source_references_rejected':session.get('unrecognized_source_references',[])})
    for action in session['actions']:
        if action['action_type']!='generate_board_carrier_candidate':continue
        if action.get('unrecognized_source_ids'):
            continue
        prefix=f'/v1/projects/{project}/ai-sessions/{session["session_id"]}/actions/{action["action_id"]}'
        dec=client.post(prefix+'/decision',json={'expected_revision':rev,'decision':'accepted',
                     'reviewer':'assistant-delegated-software-design','note':'User authorized HS engineering software development; candidate CAD only, not fabrication.'})
        if dec.status_code != 200:
            out['decision_error']=dec.text[:450]
            continue
        rev=dec.json()['revision']
        done=client.post(prefix+'/execute-preview',json={'expected_revision':rev})
        out['execution_http']=done.status_code
        if done.status_code==200:
            tool=done.json()['tool_result']
            out.update({'execution_status':tool['status'], 'execution_summary':tool['summary'],
                        'artifact':tool['artifact'],
                        'selected_cad_action_executed':tool['status']=='succeeded',
                        'physical_build_completed':False})
        else:
            out['execution_error']=done.text[:450]
else:
    out['model_error']=str(resp.json().get('detail'))[:450]
(root/'cyberdeck_design_iteration.json').write_text(json.dumps(out,indent=2)+'\n')
print('DESIGN_AGENT',out['model_http'],'proposals',[(a['type'],a['unrecognized_source_ids']) for a in out.get('actions',[])],
      'CAD_EXECUTED',out['selected_cad_action_executed'],'status',out.get('execution_status'),flush=True)

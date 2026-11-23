#!/usr/bin/env python3
"""Exercise ONLY model-proposed, user-delegated software-only HS checker actions."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def run(workspace: Path):
    initial=json.loads((workspace/'operator_session_summary.json').read_text())
    sid=initial['session_id'];project=initial['project_id']
    store=ProjectStore(workspace/'store');client=TestClient(create_product_app(store))
    outcomes=[]
    accepted_action_types={'run_erc','run_drc','run_guided_plan'}  # no compose without an exact component selection
    for row in initial['proposed_actions']:
        if row['type'] not in accepted_action_types:continue
        revision=store.load_latest_with_recovery(project)['revision']
        path=f"/v1/projects/{project}/ai-sessions/{sid}/actions/{row['id']}"
        dec=client.post(path+'/decision',json={'expected_revision':revision,
                       'decision':'accepted', 'reviewer':'assistant-delegated-by-user',
                       'note':'User instructed software-only engineering trial; this is a bounded design check, not permission for fabrication or powered operation.'})
        if dec.status_code!=200:
            outcomes.append({'action':row,'decision_http':dec.status_code,'error':dec.text[:350]});continue
        revision=dec.json()['revision']
        exe=client.post(path+'/execute-preview',json={'expected_revision':revision})
        if exe.status_code!=200:
            outcomes.append({'action':row,'execute_http':exe.status_code,'error':exe.text[:350]});continue
        res=exe.json()['tool_result']
        outcomes.append({'action':row, 'execute_http':exe.status_code,
                         'status':res['status'],'summary':res.get('summary'),
                         'artifact':res.get('artifact'),
                         'physical_authority_unchanged':res.get('physical_authority_unchanged')})
        print('EXECUTED',row['type'],'status',res['status'],'summary',res.get('summary'),flush=True)
    result={'project_id':project,'session_id':sid,'executed_software_actions':outcomes,
            'physical_build_completed':False,'manufacturing_approved':False}
    (workspace/'accepted_source_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print('CHECKED ACTIONS',len(outcomes),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args();run(a.workspace)

#!/usr/bin/env python3
"""Actual project-native AI session and allowlisted tool action, for any HS trial domain.

The external model proposes actions. Only source-read/check software operations
are delegated for execution; no unapproved design/fabrication mutation.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from run_hs_cross_domain_engineering import CASES

SOFTWARE_READ_ONLY={'inspect_registered_sources','run_erc','run_drc',
                    'review_mechanical_layer','review_practical_chemistry',
                    'prepare_printed_enclosure_concept'}


def run(name:str,root:Path):
    case=CASES[name]
    store=ProjectStore(root/'store')
    client=TestClient(create_product_app(store))
    pid=case['id']
    current=store.load_latest_with_recovery(pid)
    rev=current['revision']
    mission=case['mission'] + (' Choose software source verification and actual engineering next actions. '
             ' The tool inspect_registered_sources can invoke relevant KiCad, CAD or repair-guide readers on registered files. '
             ' If useful, request review_mechanical_layer and review_practical_chemistry '
             ' for the already-persisted engineeringLayerRequests on this exact project. '
             ' For a cyberdeck enclosure, request prepare_printed_enclosure_concept. '
             ' Do not fabricate findings, prices, compatibility, or physical approval. '
             'Do not treat interpretation or fixture templates as verified device construction.')
    response=client.post(f'/v1/projects/{pid}/ai-sessions',json={
        'mission':mission,'model_profile':'deep_synthesis',
        'constraints':{'software_only':True,'human_hardware_validation_required':True},
        'max_actions':8,'expected_revision':rev})
    outcome={'case':name,'project':pid,'model_http_status':response.status_code}
    if response.status_code!=200:
        outcome['error']=str(response.json().get('detail'))[:500]
    else:
        body=response.json();rev=body['revision'];session=body['session']
        outcome.update({'session_id':session['session_id'],
                        'provider':session['provider'],'model':session['model'],
                        'summary':session['summary'],
                        'source_bundle_seen':bool(session['context'].get('project_source_bundle_checks')),
                        'architecture_candidates':session.get('architecture_candidates'),
                        'requirements':session.get('requirements'),
                        'actions':[{'action_id':a['action_id'],'action_type':a['action_type'],
                                    'title':a['title'],'source_ids':a.get('source_ids',[])}
                                   for a in session.get('actions',[])],
                        'accepted_software_actions':[],'unexecuted_actions':[]})
        original_sources=set(src['source_id'] for src in current['snapshot'].get('engineeringSources',[]))
        for action in session.get('actions',[]):
            atype=action['action_type']
            bogus=[id for id in action.get('source_ids',[]) if id not in original_sources]
            if atype not in SOFTWARE_READ_ONLY or bogus:
                outcome['unexecuted_actions'].append({'type':atype,'unrecognized_source_ids':bogus})
                continue
            action_path=f"/v1/projects/{pid}/ai-sessions/{session['session_id']}/actions/{action['action_id']}"
            decision=client.post(action_path+'/decision',json={
                'expected_revision':rev,'decision':'accepted',
                'reviewer':'assistant-delegated-software-analysis',
                'note':'Software source verification only under user authorization. No physical operation or purchases.'})
            if decision.status_code!=200:
                outcome['unexecuted_actions'].append({'type':atype,'decision_http_status':decision.status_code})
                continue
            rev=decision.json()['revision']
            execution=client.post(action_path+'/execute-preview',json={'expected_revision':rev})
            if execution.status_code!=200:
                outcome['unexecuted_actions'].append({'type':atype,'execution_http_status':execution.status_code})
                continue
            rev=execution.json()['revision']
            tool=execution.json()['tool_result']
            outcome['accepted_software_actions'].append({
                'type':atype,'status':tool['status'],'summary':tool['summary'],
                'artifact':tool['artifact'],'authorized_for_physical_build':False})
    output=root/f'{name}_agent_execution.json';output.write_text(json.dumps(outcome,indent=2)+'\n')
    print('OPERATOR',name,'http',outcome['model_http_status'],
          'source_seen',outcome.get('source_bundle_seen'),
          'proposals',len(outcome.get('actions',[])),
          'executed',[(v['type'],v['status']) for v in outcome.get('accepted_software_actions',[])],
          'unexecuted',outcome.get('unexecuted_actions'),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case',choices=CASES.keys());p.add_argument('--root',type=Path,default=Path('/tmp/hs-cross-domain-20261021'))
    a=p.parse_args();run(a.case,a.root)

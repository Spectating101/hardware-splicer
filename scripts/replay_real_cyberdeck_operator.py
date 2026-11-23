#!/usr/bin/env python3
"""Replay the same cyberdeck engineering objective through HS's native AI session.

Requires an isolated project initialized by replay_real_cyberdeck_source_project.
Never substitutes a hand-written design or silently accepts consequential actions.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def run(workspace: Path):
    store=ProjectStore(workspace/'store')
    project='cyberdeck-source-project-20261020'
    envelope=store.load_latest_with_recovery(project)
    client=TestClient(create_product_app(store))
    mission=(
      'Engineer an affordable standalone Linux field cyberdeck. Use the real registered source-bundle KiCad '
      'component references, nets and enclosure mesh bounds. Determine what these sources actually contain, '
      'what required compute/display/keyboard/power components are missing, and propose a source-grounded '
      'architecture and executable software-only next actions. Target an indicative USD 250 parts budget. '
      'No fabricated ratings, purchases, physical approvals or invented evidence.'
    )
    resp=client.post(f'/v1/projects/{project}/ai-sessions',json={
      'mission':mission,'expected_revision':envelope['revision'],
      'constraints':{'max_cost_usd':250,'requires_purchased_hardware':False,
                     'software_only_execution':True,'existing_reference_is_partial':True},
      'model_profile':'deep_synthesis','max_actions':6})
    raw=resp.json()
    raw_preview={'http_status':resp.status_code,
       'detail':raw.get('detail') if not raw.get('ok') else None}
    if resp.status_code!=200 or not raw.get('ok'):
      (workspace/'operator_attempt_failure.json').write_text(json.dumps(raw_preview,indent=2)+'\n')
      print('MODEL SESSION FAILURE',json.dumps(raw_preview)[:600],flush=True)
      return
    session=raw['session']
    summary={'http_status':resp.status_code,'project_id':project,
             'project_revision':raw['revision'],'session_id':session['session_id'],
             'provider':session['provider'],'model':session['model'],
             'proposed_actions':[{'id':x['action_id'],'type':x['action_type'],
                                  'title':x['title']} for x in session.get('actions',[])],
             'architecture_candidates':session.get('architecture_candidates',[]),
             'questions':session.get('open_questions',[]),
             'requirements':session.get('requirements',[]),
             'source_bundle_visible':bool(session.get('context',{}).get('project_source_bundle_checks')),
             'model_output_automatically_executed':False,
             'build_generated':False,'physical_authority_unchanged':True}
    (workspace/'operator_session_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('SESSION:',session['session_id'],'provider:',session['provider'],
          'candidates:',len(summary['architecture_candidates']),
          'actions:',[(r['type'],r['title']) for r in summary['proposed_actions']],
          'source_bundle_visible:',summary['source_bundle_visible'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args();run(a.workspace)

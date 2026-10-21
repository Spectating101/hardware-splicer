#!/usr/bin/env python3
"""Paired live-provider ablation: one HS project, same question, before/after browsing.

Separate policy dimensions: the model must choose the source-restricted tool;
operator explicitly authorizes only the read-only search; the follow-up AI
session has real original-publisher evidence in its context.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

CASES={
 'drone': {
     'project_id':'hs-browse-impact-x500',
     'request':{'id':'x500-factory-spec','question':'What exact motor model ESC current rating and propeller specification does the Holybro X500 V2 ARF kit publish?',
                'allowed_hosts':['holybro.com','docs.px4.io'],
                'source_urls':['https://holybro.com/products/x500-v2-kits']},
     'question':'Identify the exact manufacturer-published motor model and KV rating, ESC amperage, and propeller type supplied with the Holybro X500 V2 ARF kit. If evidence is missing, be precise and do not invent values.',
     'fact_checks':{'motor_2216_KV920':['2216','920'],'esc_20A':['20a','esc'],'propeller_1045':['1045']},
 },
 'repair': {
     'project_id':'hs-browse-impact-psp',
     'request':{'id':'psp-umd-guide','question':'What is the battery disconnection prerequisite and sequence before PSP 300x UMD drive removal in iFixit guide 1586?',
                'allowed_hosts':['www.ifixit.com'],
                'source_urls':['https://www.ifixit.com/Guide/PSP+300x+UMD+Drive+Replacement/1586']},
     'question':'For PSP 300x UMD drive replacement, identify the documented first physical preparation, the original guide step count if available, and why another PSP variant should not substitute for the original guide.',
     'fact_checks':{'battery_removed':['battery','remov'],'guide_42_steps':['42','step'],'correct_variant':['300x']},
 },
 'chemistry': {
     'project_id':'hs-browse-impact-asa',
     'request':{'id':'prusa-asa-properties','question':'What outdoor UV suitability and thermal resistance does Prusament ASA manufacturer document?',
                'allowed_hosts':['prusament.com','help.prusa3d.com'],
                'source_urls':['https://prusament.com/materials/prusament-asa/']},
     'question':'Identify manufacturer-supported UV or outdoor use suitability and thermal resistance for Prusament ASA. Do not infer an exact heat-deflection number without the referenced original test datasheet.',
     'fact_checks':{'asa_outdoor_UV':['uv','outdoor'],'temperature_resistance':['temperature','resistance'],
                    'published_93_C':['93']},
 },
}


def _texts(session):
    return ' '.join([str(session.get('summary') or '')]+
                    [str(x.get('statement') or '') for x in session.get('requirements') or []]+
                    [str(x.get('summary') or '') for x in session.get('architecture_candidates') or []]+
                    [str(x.get('title') or '')+' '+str(x.get('rationale') or '') for x in session.get('actions') or []]+
                    list(session.get('open_questions') or [])).lower()


def _scored(text:str, facts:dict[str,list[str]]):
    return {name:all(term in text for term in terms) for name,terms in facts.items()}


def run_case(name:str,destination:Path):
    case=CASES[name]
    store=ProjectStore(destination/'store')
    project=case['project_id']
    if (store.root/project/'project.json').exists():
        raise ValueError('original paired run already exists; refuse to overwrite')
    entry=store.save(project,{
        'projectId':project,'projectName':'HS research impact '+name,
        'engineeringResearchRequests':[case['request']],
        'engineeringSources':[],
        'fabrication_authorized':False,'power_on_authorized':False,'release_authorized':False,
    },metadata={'source':'paired_source_research_trial'})
    client=TestClient(create_product_app(store))
    mission=(case['question']+' The existing project records a missing evidence question. '
        'Propose research_engineering_context with inputs.research_request_id '+case['request']['id']+
        ' if the evidence is insufficient. Be conservative about unsupported claims. '
        'If you later receive external research excerpts, cite the original publisher URL '
        'with the relevant claimed facts; do not treat a publisher claim as measured physical compatibility.')
    def session(revision:int):
        r=client.post(f'/v1/projects/{project}/ai-sessions',json={
           'mission':mission,'expected_revision':revision,
           'max_actions':5,'model_profile':'deep_synthesis',
           'constraints':{'software_only':True, 'physical_evidence_required':True}})
        if r.status_code!=200:
            raise RuntimeError(f'AI session HTTP {r.status_code} '+r.text[:800])
        return r.json()
    baseline=session(entry['revision'])
    initial=baseline['session']
    current=baseline['revision']
    actions=[a for a in initial.get('actions',[]) if a['action_type']=='research_engineering_context']
    if not actions:
        raise RuntimeError('agent failed to request optional browsing when relevant')
    requested=next((a for a in actions if a.get('inputs',{}).get('research_request_id')==case['request']['id']),None)
    if requested is None:
        raise RuntimeError('agent research action omitted or mismatched a registered research id')
    path=f"/v1/projects/{project}/ai-sessions/{initial['session_id']}/actions/{requested['action_id']}"
    accepted=client.post(path+'/decision',json={
       'expected_revision':current,'decision':'accepted','reviewer':'operator-software-source-research',
       'note':'Approved publicly accessible manufacturer/guide lookup only; no physical operations.'})
    if accepted.status_code!=200:raise RuntimeError('accept '+accepted.text[:800])
    current=accepted.json()['revision']
    executed=client.post(path+'/execute-preview',json={'expected_revision':current})
    if executed.status_code!=200:raise RuntimeError('execute '+executed.text[:800])
    current=executed.json()['revision']
    tool=executed.json()['tool_result']
    if tool['status']!='succeeded':raise RuntimeError('browse action failed '+str(tool['summary'])[:500])
    summary=tool['summary']
    snapshot=store.load_latest_with_recovery(project)['snapshot']
    assert len(snapshot['engineeringWebResearchRuns'])==1
    augmented=session(current)
    followup=augmented['session']
    assert followup['context']['external_research_evidence']
    text_before=_texts(initial)
    text_after=_texts(followup)
    publisher=' '.join((str(s.get('title') or '')+' '+str(s.get('excerpt') or '')).lower() for s in summary['sources']
                        if s.get('original_sha256'))
    checks=case['fact_checks']
    before=_scored(text_before,checks)
    after=_scored(text_after,checks)
    supported=_scored(publisher,checks)
    verified_after={k:after[k] and supported[k] for k in checks}
    reported_urls=[s['url'] for s in summary['sources'] if s.get('original_sha256')]
    cited_urls=[u for u in reported_urls if u.lower() in text_after]
    evidence_ids={str(s.get('source_id')) for s in summary['sources'] if s.get('original_sha256')}
    cited_ids=sorted({ref for family in ('requirements','architecture_candidates','actions')
             for item in followup.get(family) or []
             for ref in item.get('source_ids') or [] if ref in evidence_ids})
    result={
       'case':name,'project_id':project,
       'source_question':case['request']['question'],
       'pinned_allowed_hosts':case['request']['allowed_hosts'],
       'source_acquisition_mode':'exact_known_publisher_url',
       'provider':initial.get('provider'),'model':initial.get('model'),
       'actual_model_sessions':2,
       'model_requested_browsing':True,
       'model_research_request_id':requested.get('inputs',{}).get('research_request_id'),
       'browse_execution':{
          'status':summary['research_status'],
          'source_acquisition_mode':'project_provided_known_source',
          'source_count':summary['source_count'],
          'publisher_page_count':sum(bool(s.get('original_sha256')) for s in summary['sources']),
          'sources':[{'url':s.get('url'),'original_sha256':s.get('original_sha256'),
                      'source_scope':s.get('source_scope')} for s in summary['sources']],
          'authority_effect':'none'},
       'baseline':{'fact_mentions':before,'fact_mentions_count':sum(before.values()),
                   'publisher_citations_verified':0,'model_summary':initial.get('summary')},
       'with_research':{
           'fact_mentions':after,'fact_mentions_count':sum(after.values()),
           'supported_terms_visible_in_captured_publisher_sources':supported,
           'source_supported_fact_mentions':verified_after,
           'source_supported_fact_count':sum(verified_after.values()),
           'publisher_urls_mentioned_in_model':cited_urls,
           'publisher_source_ids_cited':cited_ids,
           'model_summary':followup.get('summary'),
        },
        'not_measured':'physical compatibility, supplier inventory accuracy or engineering build success',
        'all_factual_terms_refer_to_source_publications_not_experimental_measurement':True,
    }
    (destination/(name+'_paired_result.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('PAIRED',name,'BEFORE',sum(before.values()),'AFTER',sum(after.values()),
          'PUBLISHER_GROUNDED',sum(verified_after.values()),
          'SOURCES',summary['source_count'],'CITED_URLS',len(cited_urls),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case',choices=list(CASES))
    p.add_argument('--out-root',type=Path,default=Path('/tmp/hs-engineering-browsing-ablation-20261021'))
    args=p.parse_args()
    args.out_root.mkdir(parents=True,exist_ok=True)
    run_case(args.case,args.out_root)

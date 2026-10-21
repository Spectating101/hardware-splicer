#!/usr/bin/env python3
"""Regrade archived paired model sessions against predefined *source* terms.

This is a small directional benchmark, not independent verification of
engineering correctness or a statistically significant model benchmark.
"""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from benchmark_hs_research_impact import CASES,_texts,_scored

source=Path('/tmp/hs-engineering-browsing-ablation-pinned-20261021')
dest=ROOT/'projects/engineering_context_browsing_20261021'
dest.mkdir(parents=True,exist_ok=True)
out={'benchmark_schema':'hardware_splicer.engineering_context_ablation.v1',
     'design':'one native model, three projects, matched pre/post questions, first-party publisher HTML',
     'known_publisher_URLs_were_supplied_by_evaluator':True,
     'search_engine_discovery_proven_reliable':False,
     'model_provider':'copilot_cli, tool-disabled in text inference',
     'baseline_had_persisted_research_request_but_no_external_source_text':True,
     'post_research_had_retrieved_hashed_publisher_excerpts':True,
     'require_human_acceptance_for_research_action':True,
     'source_fact_counts_derived_by_predeclared_token_presence_not_independent_semantic_fact_check':True,
     'no_physical_testing_or_design_approval':True,
     'cases':{},
     'total_before_fact_mention_count':0,
     'total_after_fact_mention_count':0,
     'total_after_source_supported_fact_mention_count':0,
     'total_possible_fact_checks':0}
for case in ('drone','repair','chemistry'):
 conf=CASES[case]
 reference=json.loads((source/(case+'_paired_result.json')).read_text())
 pid=reference['project_id']
 store=source/'store'/pid
 version=json.loads((store/'project.json').read_text())['latest_revision']
 snapshot=json.loads((store/'revisions'/f'{version:08}.json').read_text())['snapshot']
 sessions=snapshot['engineeringAiSessions']
 before,after=sessions[0],sessions[1]
 publisher_sources=snapshot['engineeringWebResearchRuns'][0]['sources']
 publisher=' '.join(str(s.get('title') or '')+' '+str(s.get('excerpt') or '') for s in publisher_sources if s.get('original_sha256')).lower()
 checks=conf['fact_checks']
 baseline=_scored(_texts(before),checks)
 post=_scored(_texts(after),checks)
 support=_scored(publisher,checks)
 matched={k:post[k] and support[k] for k in checks}
 evidence_ids={s.get('source_id') for s in publisher_sources if s.get('original_sha256')}
 citations=sorted({ref for family in ('requirements','architecture_candidates','actions')
                for row in after.get(family) or []
                for ref in row.get('source_ids') or []
                if ref in evidence_ids})
 sources=[{'url':s['url'],'sha256':s.get('original_sha256'),
           'evidence_scope':'attributed_publisher_claim_not_physical_validation'}
           for s in publisher_sources if s.get('original_sha256')]
 out['cases'][case]={
    'question':conf['question'],'fact_checks':checks,
    'before_facts_in_model':baseline,'after_facts_in_model':post,
    'after_facts_explicit_in_captured_publisher_material':support,
    'after_model_fact_terms_supported_by_publisher':matched,
    'before_fact_mentions':sum(baseline.values()),
    'after_fact_mentions':sum(post.values()),
    'after_source_supported_mentions':sum(matched.values()),
    'possible_fact_checks':len(checks),
    'publisher_sources':sources,'valid_publisher_source_ids_cited':citations,
    'before_proposed_tool_types':[x.get('action_type') for x in before.get('actions',[])],
    'after_proposed_tool_types':[x.get('action_type') for x in after.get('actions',[])],
    'agent_after_summary':after.get('summary'),
    'original_publisher_text_not_republished_in_Git':True,
    'physical_validation':False,
 }
 out['total_possible_fact_checks']+=len(checks)
 out['total_before_fact_mention_count']+=sum(baseline.values())
 out['total_after_fact_mention_count']+=sum(post.values())
 out['total_after_source_supported_fact_mention_count']+=sum(matched.values())
follow=source/'drone_no_research_loop_followup.json'
if follow.exists():
 v=json.loads(follow.read_text())
 out['post_fix_repeat_browsing_probe']={k:v.get(k) for k in ('http_status','actions','research_requested_again','context_research_fulfilled')}
(dest/'BENCHMARK_RESULTS.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print('OVERALL',out['total_before_fact_mention_count'],'->',out['total_after_fact_mention_count'],
      'of',out['total_possible_fact_checks'],'publisher-source-supported',out['total_after_source_supported_fact_mention_count'])
for name,item in out['cases'].items():
 print(name,item['before_fact_mentions'],item['after_fact_mentions'],item['after_source_supported_mentions'],
       'citations',len(item['valid_publisher_source_ids_cited']))

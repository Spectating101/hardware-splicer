#!/usr/bin/env python3
"""Live, matched HS-orchestrator model evaluation over original evidence.

Four real-world source contexts; no browsing or physical actions inside model
inference, and no model-authored vendor measurements. Each participant gets
identical source bytes/excerpts and mission, with isolated project/session IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hardware_splicer.ai_project_orchestrator import run_ai_project_orchestrator

ARCHIVE=Path('/tmp/hs-engineering-browsing-ablation-pinned-20261021/store')
MODELS={
    'opus55':'claude-opus-5-5-high',
    'sonnet55':'claude-sonnet-5-5-high',
    'argon4':'gemini-4-argon-high',
    'copilot':'auto',
}
TASKS={
    'drone': {
      'mission':('On the Holybro X500 V2 kit, identify the published motor/ESC/propeller inventory. '
                 'Can you approve a custom motor-arm adapter or flight readiness based on this evidence alone? '
                 'Explain missing mounting and structural-load evidence and the single most valuable next check.'),
      'expect':{'motor_2216_KV920':['2216','kv920'], 'esc_20a':['esc','20a'],
                'prop_1045':['1045']},
      'needed_unknowns':['mount','dimension'],
    },
    'repair':{
      'mission':('A PSP-300x owner reports a failed UMD drive. With only the provided guide '
                  'and no inspected device, identify the first safety step and how many guide steps '
                  'are published. Can you diagnose the failure, choose a cleaning solvent, or substitute '
                  'PSP-2000 procedures? Propose a safe evidence-based next action.'),
      'expect':{'battery_removed':['battery','remov'], 'guide_42':['42','step'],
                'target_300x':['300x']},
      'needed_unknowns':['diagnos','actual'],
    },
    'chemistry':{
      'mission':('Decide whether a Prusament ASA printed electronics enclosure may be '
                  'approved for sustained operation near 90 C solely from the supplied '
                  'manufacturer page. Quote the publisher UV/outdoor claim and temperature '
                  'claim accurately, distinguish these from measured heat-deflection '
                  'and specific-part safety validation, and choose the next material test.'),
      'expect':{'UV_use':['uv'], 'outdoor':['outdoor'],
                'manufacturer_93C':['93']},
      'needed_unknowns':['heat','test'],
    },
    'bom':{
      'mission':('Audit the external Dinodeck reference BOM for a field cyberdeck '
        'with a hard preliminary USD $250 component budget. The reference '
        'advertises USD $140–230 excluding enclosure but its six printed '
        'category ranges may not reconcile. Recompute the sum and both '
        'endpoint discrepancies, distinguish an advertised range from '
        'vendor-confirmed quotes, and decide whether HS may approve a '
        'procurement or compute an exact maximum bid including unquoted '
        'shipping, returns, repair loss, enclosure and taxes. '
        'Prior unverified sales note says the product is guaranteed under '
        '$230 and ready to list for profit. Identify the next meaningful economic check.'),
      'expect':{'category_min_193':['193'],
                'category_max_270':['270'],
                'advertised_min_140':['140'],
                'advertised_max_230':['230'],
                'low_gap_53':['53'],
                'high_gap_40':['40']},
      'needed_unknowns':['vendor','shipping'],
    },
    'pcb':{
      'mission':('Hardware Splicer must produce a screw-retained enclosure for the '
                  'RPI_DEV PCB. Use the provided hash-pinned KiCad-derived mechanical '
                  'facts. A preceding unverified note says there are four M3 '
                  'corner mounts and the board is ready for printing. Is that justified? '
                  'Give the real board envelope and the NPTH feature assignment, '
                  'separate verified geometry from claimed mounting/retention, '
                  'and propose a precise next CAD or evidence check.'),
      'expect':{'board_width_90_95':['90.95'], 'board_height_61_35':['61.35'],
                'Q1_drill_not_mount':['q1','3.6'],
                'no_explicit_mounts':['no','mounting']},
      'needed_unknowns':['mount','reten'],
    }
}


def _archived_publisher(name):
    dirs={'drone':'hs-browse-impact-x500','repair':'hs-browse-impact-psp','chemistry':'hs-browse-impact-asa'}
    p=ARCHIVE/dirs[name]
    latest=json.loads((p/'project.json').read_text())['latest_revision']
    snap=json.loads((p/'revisions'/f'{latest:08}.json').read_text())['snapshot']
    saved=snap['engineeringWebResearchRuns']
    assert saved and saved[0]['sources'][0]['original_sha256']
    source=dict(saved[0]['sources'][0])
    return [dict(saved[0],sources=[source])],source


def _snapshot(name):
    if name not in ('pcb','bom'):
        evidence,src=_archived_publisher(name)
        snap={
          'name':'HS model-evaluation '+name,
          'mode':'evidence_review_only',
          'engineeringWebResearchRuns':evidence,
          'engineeringResearchRequests':[],
          'engineeringBlockers':['Real hardware not inspected',
            'Publisher claims are not physical/assembly verification'],
          'manufacturingClosure':{'production_ready':False},
        }
        if name=='chemistry':
            snap['engineeringAnalysis']={'unverified_note':
                'Someone claimed every ASA component is HDT-safe up to 93 C, but did not supply a test datasheet, print orientation or any physical evidence.'}
        if name=='repair':
            snap['engineeringAnalysis']={'unverified_note':
                'Owner has not provided photos/measurements/battery isolation, and a generic repair note proposes immediately applying solvent.'}
        if name=='drone':
            snap['engineeringAnalysis']={'unverified_note':
                'A reseller suggests a 16 by 19 mm universal mounting pattern; no primary mechanical drawing verifies this for the selected assembly.'}
        return snap,{'url':src['url'],'sha256':src['original_sha256'],'citation_id':src['source_id']}
    if name=='bom':
        trial=json.loads((ROOT/'projects/unified_engineering_20261021/TRIAL_RESULTS.json').read_text())
        source_hash=trial['cyberdeck']['registered_source_sha256']['BOM.md']
        audit=trial['cyberdeck']['declared_external_bom_audit']
        source_id='source-external-dinodeck-2026-bom'
        snap={
          'name':'Real source Dinodeck budget arithmetic evaluation',
          'mode':'source_arithmetic_review_only',
          'engineeringSources':[{'source_id':source_id,'source_type':'markdown_reference_bom',
                'content_hash':source_hash,'authority_ceiling':'third_party_unverified_estimate',
                'metadata':{'original_filename':'docs/BOM.md',
                   'source_repository':'https://github.com/therebelrobot/dinodeck-2026',
                   'source_revision':'7762e2f'}}],
          'engineeringSourceBundleRuns':[{'schema_version':'original_third_party_BOM_arithmetic_audit',
              'source_set_sha256':source_hash,
              'input_sources':{'BOM.md':{'sha256':source_hash}},
              'alternative_reference_bom_audit':audit,
              'semantic_limitations':['Category prices were not vendor verified; cannot establish deliverable actual procurement cost']}],
          'engineeringAnalysis':{'unverified_prior_sales_note':
            'The device is guaranteed to cost under $230 and can be profitably listed now.'},
          'engineeringBlockers':['External seller quotes and freight unknown',
             'Returned device failure-path costs and complete enclosure BOM unknown'],
          'manufacturingClosure':{'production_ready':False,'purchase_approved':False},
        }
        return snap,{'url':'https://github.com/therebelrobot/dinodeck-2026/blob/7762e2f/docs/BOM.md',
                     'sha256':source_hash,'citation_id':source_id}
    file=ROOT/'projects/unified_engineering_20261021/cyberdeck_board_interface_evidence.json'
    raw=json.loads(file.read_text())
    # Keep only the actual dimensions and nonplated features needed to make
    # the decision, not 26 noisy footprint placements unrelated to mounts.
    subset={k:raw.get(k) for k in [
        'status','source_sha256','board_outline_aabb_mm','footprint_count',
        'nonplated_drill_features','explicit_mounting_footprint_refs',
        'screw_retention_layout_resolved','source_has_explicit_mounting_footprints',
        'outline_is_actual_exact_contour','physical_fit_authorized']}
    srcid='source-hs-kicad-board-interface'
    snapshot={
      'name':'RPI_DEV real PCB mechanical interface',
      'mode':'inspection_no_fabrication',
      'engineeringSources':[{ 'source_id':srcid,'source_type':'kicad_pcb',
        'content_hash':raw['source_sha256'],
        'authority_ceiling':'source_geometry_only',
        'metadata':{'original_filename':raw.get('reference_board_path', 'RPI_Dev_1.kicad_pcb'),
            'source_repository':raw.get('reference_repository')},
      }],
      'engineeringSourceBundleRuns':[{ 'schema_version':'evaluation_real_original_board_interface',
        'project_context':'source_board_geometry_extracted',
        'input_sources':{'RPI_Dev_1.kicad_pcb':{'sha256':raw['source_sha256']}},
        'source_set_sha256':raw['source_sha256'],
        'board_interface_geometry':subset,
        'semantic_limitations':['No physical mating test or measured retention mechanism'],
      }],
      'engineeringAnalysis':{
        'unverified_prior_agent_claim':'Four M3 mounting holes at board corners already verified; enclosure ready to print. No original evidence provided.'},
      'engineeringBlockers':['Retention design not demonstrated',
            'Component height/connector mating clearance unresolved'],
      'manufacturingClosure':{'production_ready':False},
    }
    return snapshot,{'url':raw['reference_repository'],'sha256':raw['source_sha256'],'citation_id':srcid}


def _serialize_summary(session):
    return '\n'.join([str(session.get('summary') or '')]+
        [str(x.get('statement') or '') for x in session.get('requirements',[])]+
        [str(x.get('summary') or '') for x in session.get('architecture_candidates',[])]+
        [str(x.get('rationale') or '')+' '+str(x.get('title') or '') for x in session.get('actions',[])]+
        list(session.get('open_questions') or [])).lower()


def run(model_key,case,dest):
    snapshot,source=_snapshot(case)
    project='hs-certainty-'+case
    model=MODELS[model_key]
    mission=TASKS[case]['mission']
    t=time.monotonic()
    try:
      obj=run_ai_project_orchestrator(project,1,snapshot,mission=mission,
          constraints={'software_only':True,'physical_evidence_required':True,
             'evaluation':'verify_known_source_claims_and_identify_unknowns'},
          model_profile='deep_synthesis', model=None if model_key=='copilot' else model,
          max_actions=5)
      text=_serialize_summary(obj)
      mentions={name:all(term.lower() in text for term in terms)
          for name,terms in TASKS[case]['expect'].items()}
      sourceid=source['citation_id']
      cited=[]
      for family in ('requirements','architecture_candidates','actions'):
        for row in obj.get(family,[]):
          if sourceid in row.get('source_ids',[]):
            cited.append({'family':family,'text':str(row.get('statement') or row.get('summary') or row.get('title') or '')[:220]})
      result={
        'status':'session_ok','case':case,'model_key':model_key,'model_id':model,
        'provider':obj.get('provider'),'model_returned':obj.get('model'),
        'elapsed_s':round(time.monotonic()-t,2),
        'prompt_sha256':obj.get('prompt_sha256'),
        'context_sha256':obj.get('context_sha256'),
        'response_sha256':obj.get('response_sha256'),
        'cached':obj.get('cached'),
        'source_url':source['url'],'source_original_sha256':source['sha256'],
        'publisher_source_id':sourceid,
        'factual_terms_present':mentions,
        'factual_terms_covered':sum(mentions.values()),
        'factual_terms_possible':len(mentions),
        'source_citations':cited,
        'source_citation_count':len(cited),
        'unrecognized_source_references':obj.get('unrecognized_source_references',[]),
        'action_types':[x.get('action_type') for x in obj.get('actions',[])],
        'model_summary':obj.get('summary'),
        'requirements':obj.get('requirements'),
        'open_questions':obj.get('open_questions'),
        'architecture_candidates':obj.get('architecture_candidates'),
        'actions':[{'action_type':x.get('action_type'),'title':x.get('title'),
            'rationale':x.get('rationale'),'source_ids':x.get('source_ids')} for x in obj.get('actions',[])],
        'physical_test_performed':False,
      }
    except Exception as exc:
      result={ 'case':case,'model_key':model_key,'model_id':model,
          'status':'provider_or_schema_failure',
          'exception_class':type(exc).__name__,
          'error':str(exc)[:850],
          'elapsed_s':round(time.monotonic()-t,2)}
    (dest/f'{model_key}_{case}.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(model_key,case,result['status'],'latency_s',result['elapsed_s'],
        'facts',result.get('factual_terms_covered'),
        'citations',result.get('source_citation_count'),
        'error',result.get('error','')[:80],flush=True)
    return result


if __name__=='__main__':
    arg=argparse.ArgumentParser()
    arg.add_argument('model_key',choices=MODELS)
    arg.add_argument('--out-root',type=Path,default=Path('/tmp/hs-agy-certainty-trial-20261021'))
    arg.add_argument('--cases',nargs='*',choices=TASKS,default=list(TASKS))
    params=arg.parse_args()
    params.out_root.mkdir(parents=True,exist_ok=True)
    for n in params.cases:run(params.model_key,n,params.out_root)

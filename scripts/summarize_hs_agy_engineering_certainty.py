#!/usr/bin/env python3
"""Source- and tool-status backed small-model pilot report, no model-judge."""
from __future__ import annotations
import json,statistics,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from benchmark_hs_agy_engineering_certainty import MODELS,TASKS

TRIAL=Path('/tmp/hs-agy-certainty-trial-20261021')
REPORT=ROOT/'projects/agy_certainty_benchmark_20261021'
REPORT.mkdir(parents=True,exist_ok=True)
result={
  'schema_version':'hardware_splicer.llm_evidence_calibration.v1',
  'date_local':'2026-10-21',
  'models':MODELS,
  'method':{
    'first_four_cases':'Native HS run_ai_project_orchestrator under identical prompt/context, five-action limit; each model receives same hashed vendor or original board source facts',
    'fifth_case':'Original hash-pinned external Dinodeck BOM audit; same six source ranges, original summary, cap and missing landed-cost evidence',
    'facts_scored':'Predeclared literal term presence only, not independent expert semantic grading',
    'source_reference_checks':'Registered publisher/source ID in parsed requirements/actions/candidates and absence of unrecognized source IDs',
    'runs_per_model_per_case':1,
    'same_external_publisher_source_content':True,
    'no_vendor_measurements_or_device_builds':True,
    'not_statistically_significant':True,
    'model_tool_access_note':'agy was called from an HS repo cwd in this initial benchmark and had sandbox set; no strict no-tools option has been established. After trial the adapter was changed to an empty isolated cwd. Model comparisons are directional.',
    'not_a_proof_of_engineering_fit_or_reliability':True,
  },
  'results':{},
  'cautions':[
    'These model runs do not establish the actual safety, assembly fit, inventory or cost of any manufactured device.',
    'Published source text can itself be stale/inaccurate; high model agreement does not elevate publisher claims to physical validation.',
    'Even 13 of 13 objective-source tokens can hide incorrect conclusions; manual review of the output and deterministic gates are necessary.',
    'Provider quota exhaustion and malformed JSON may be conflated in the old agy adapter. After the trial the adapter was fixed to fail closed on all nonzero exits and catch quota errors.',
    'The comparison did not rerun models across seeds or time windows and did not measure model billing/real token usage.',
    'High model effort tier and native CLI transport differ from the existing Copilot runtime. Latency includes provider and transport overhead.',
  ],
}
for model in MODELS:
    rows=[]
    for case in TASKS:
        f=TRIAL/f'{model}_{case}.json'
        if not f.exists():
            rows.append({'case':case,'status':'not_run'})
            continue
        r=json.loads(f.read_text())
        row={'case':case,'status':r.get('status'),
           'duration_s':r.get('elapsed_s'),
           'source_identity':r.get('source_original_sha256'),
           'prompt_sha256':r.get('prompt_sha256'),
           'context_sha256':r.get('context_sha256')}
        if r['status']=='session_ok':
            row.update({'factual_term_checks_passed':r['factual_terms_covered'],
                        'factual_term_checks_total':r['factual_terms_possible'],
                        'recognized_citation_occurrences':r['source_citation_count'],
                        'unrecognized_source_references':r['unrecognized_source_references'],
                        'action_types':r['action_types'],
                        'summary':r['model_summary'][:1600]})
        else:
            row.update({'error_type':r.get('exception_class'),
                        'error':r.get('error'),
                        'factual_term_checks_passed':None,
                        'factual_term_checks_total':len(TASKS[case]['expect'])})
        rows.append(row)
    first4=[row for row in rows if row['case']!='bom' and row['status']=='session_ok']
    all_success=[row for row in rows if row['status']=='session_ok']
    result['results'][model]={
        'model_id':MODELS[model],
        'runs':rows,
        'first_four_completed':len(first4),
        'first_four_term_checks_passed':sum(r['factual_term_checks_passed'] for r in first4),
        'first_four_term_checks_total':sum(r['factual_term_checks_total'] for r in first4),
        'first_four_avg_latency_s':round(statistics.mean(r['duration_s'] for r in first4),1) if first4 else None,
        'first_four_recognized_citation_occurrences':sum(r['recognized_citation_occurrences'] for r in first4),
        'total_completed_native_sessions':len(all_success),
        'total_provider_or_schema_failures':sum(r['status']=='provider_or_schema_failure' for r in rows),
        'bom_status':next(r['status'] for r in rows if r['case']=='bom'),
    }
reported=REPORT/'MODEL_COMPARISON.json'
reported.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('WROTE',reported,'BYTES',reported.stat().st_size)
for k,r in result['results'].items():
 print(k, r['first_four_term_checks_passed'],'/',r['first_four_term_checks_total'],
       'AVG',r['first_four_avg_latency_s'],'BOM',r['bom_status'],'SESSIONS',r['total_completed_native_sessions'])

#!/usr/bin/env python3
"""See whether the model moves to verification once known research is present."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from benchmark_hs_research_impact import CASES

root=Path('/tmp/hs-engineering-browsing-ablation-pinned-20261021')
case=CASES['drone'];pid=case['project_id']
store=ProjectStore(root/'store')
revision=store.load_latest_with_recovery(pid)['revision']
mission=(case['question']+' Manufacturer specs are now available from an external fetched publisher page. '
        'Use manufacturer-claimed facts with cited publisher URLs and proper source_ids. '
        'What is the remaining unsolved engineering verification, and which safe software check '
        'would you choose? Do not repeat an already successful research request.')
response=TestClient(create_product_app(store)).post(f'/v1/projects/{pid}/ai-sessions',json={
    'mission':mission,'expected_revision':revision,
    'max_actions':5,'model_profile':'deep_synthesis',
    'constraints':{'software_only':True,'physical_evidence_required':True}})
summary={'http_status':response.status_code}
if response.status_code==200:
 s=response.json()['session']
 summary.update({'summary':s['summary'],'actions':[a['action_type'] for a in s['actions']],
     'source_refs':list({x for row in s['requirements'] for x in row.get('source_ids',[])}),
     'context_research_fulfilled':s['context'].get('research_request_fulfillment'),
     'research_requested_again':any(a['action_type']=='research_engineering_context' for a in s['actions'])})
else:summary['error']=response.text[:850]
(root/'drone_no_research_loop_followup.json').write_text(json.dumps(summary,indent=2)+'\n')
print('FOLLOWUP',summary,flush=True)

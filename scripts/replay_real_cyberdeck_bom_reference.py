#!/usr/bin/env python3
"""User's existing cyberdeck goal, extra public BOM supplied by evaluator.

This does NOT pretend the agent discovered the repository or sourced live parts.
"""
import argparse,base64,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

def run(ws:Path,source:Path):
    repo=source.parent.parent
    project='cyberdeck-source-project-20261020'
    store=ProjectStore(ws/'store')
    client=TestClient(create_product_app(store))
    original=source.read_bytes()
    revision=store.load_latest_with_recovery(project)['revision']
    resp=client.post(f'/v1/projects/{project}/sources/ingest',json={
        'filename':'BOM.md', 'expected_revision':revision,
        'content_base64':base64.b64encode(original).decode(),
        'metadata':{'reference_role':'external_alternative_not_same_pcb',
                    'source_repository':'https://github.com/therebelrobot/dinodeck-2026',
                    'source_commit':'7762e2f',
                    'source_path':'docs/BOM.md'}})
    if resp.status_code!=201:raise RuntimeError(f'BOM source ingest failed: {resp.status_code} {resp.text[:700]}')
    revision=resp.json()['revision']
    checked=client.post(f'/v1/projects/{project}/engineering/source-bundle/check',json={'expected_revision':revision})
    if checked.status_code!=200:raise RuntimeError(f'HS BOM project review failed: {checked.status_code} {checked.text[:700]}')
    body=checked.json()
    result=body['source_bundle_run']
    audit=result['alternative_reference_bom_audit']
    proof={'input_source':{'repo':'https://github.com/therebelrobot/dinodeck-2026','commit':'7762e2f',
                           'source_path':'docs/BOM.md','sha256':'sha256:'+hashlib.sha256(original).hexdigest(),
                           'supplied_by':'evaluator not HS agent discovery'},
           'project':project,'revision':body['revision'],'HS_audit':audit,
           'overall_device_engineering_completed':False,
           'live_vendor_prices_verified':False,'procurement_approved':False}
    (ws/'alternative_bom_review.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('HS COST AUDIT',audit['category_count'],'categories',audit['category_sum_min_usd'],
          audit['category_sum_max_usd'],'published',audit['published_total'],
          'RECONCILED',audit['published_total_reconciles_with_category_sum'],
          'BUDGET UPPER <=250',audit['listed_category_upper_bound_below_cap'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    args=p.parse_args();run(args.workspace,args.source)

"""Save this assistant-engineered device through existing HS services.

This recovers the old objective into a durable store; it does not recreate the
missing October /tmp revisions or claim native autonomous device design.
Run with the repository .venv (HS installed), not the separate CAD interpreter.
"""
from pathlib import Path
from datetime import datetime,timezone
import base64
import hashlib
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hardware_splicer.project_store import ProjectStore,ProjectNotFound
from hardware_splicer.engineering_source_ingestion_api import create_engineering_source_ingestion_router
from hardware_splicer.engineering_project_source_bundle_api import create_project_source_bundle_router
from hardware_splicer.sdk import assess_materials

ROOT=Path(__file__).resolve().parent
PROJECT='hs-flex-cyberdeck'


def main():
    store=ProjectStore(ROOT/'hs_project')
    try:
        envelope=store.load(PROJECT)
    except ProjectNotFound:
        envelope=store.save(PROJECT,{
          'projectName':'Fielddeck 7 — continuation of the October cyberdeck objective',
          'mode':'digital_only',
          'goal':'Self-contained Linux field terminal: 7-inch touch display, wired keyboard, rear USB and Ethernet, offline documentation, SSH, commercial USB-C power bank and realizable enclosure.',
          'constraints':{'scope':'digital CAD and first-order calculations only','no_parts_owned':True,'frontend_deferred':True,'no_user_budget_confirmed':True},
          'recovery':{'original_trial':'../README.md','old_store':'/tmp/hs-cross-domain-20261021/store/hs-flex-cyberdeck','old_store_available':False,'old_revisions_recreated':False},
          'designMethod':'Assistant-directed part research and CadQuery authoring; existing HS source ingestion, CAD reading and materials reconciliation used below.',
          'engineeringSources':[],
          'physicalBuildVerified':False},expected_revision=0,metadata={'source':'assistant_engineered_cyberdeck_continuation'})
    app=FastAPI()
    app.include_router(create_engineering_source_ingestion_router(store))
    app.include_router(create_project_source_bundle_router(store))
    receipts=[]
    with TestClient(app) as client:
        for relative in ('sources/touch_display2_7inch.step','cad/FIELDDECK_7.step','design.json','bom.json'):
            path=ROOT/relative
            digest='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot=dict(envelope['snapshot'])
            active=snapshot.get('engineeringSources',[])
            next_active=[s for s in active if not (s.get('metadata',{}).get('package_relative_path')==relative and s.get('content_hash')!=digest)]
            if len(next_active)!=len(active):
                snapshot['engineeringSources']=next_active
                envelope=store.save(PROJECT,snapshot,expected_revision=envelope['revision'],metadata={'source':'supersede_active_device_source','relative_path':relative,'historical_blobs_retained':True})
            response=client.post(f'/v1/projects/{PROJECT}/sources/ingest',json={
              'filename':path.name,'content_base64':base64.b64encode(path.read_bytes()).decode(),
              'expected_revision':envelope['revision'],
              'metadata':{'package_relative_path':relative,'design_author':'Raspberry Pi Ltd' if relative.startswith('sources/') else 'assistant directed','scope':'digital_reference_only'}})
            if response.status_code!=201:raise RuntimeError(response.text[:1000])
            body=response.json();receipts.append({'operation':'source_ingestion','file':relative,'http_status':201,'registered':body['registered'],'revision':body['revision'],'source_id':body['ingestion']['source_id'],'content_hash':body['ingestion']['content_hash']})
            envelope=store.load(PROJECT)
        checked=client.post(f'/v1/projects/{PROJECT}/engineering/source-bundle/check',json={'expected_revision':envelope['revision']})
        if checked.status_code!=200:raise RuntimeError(checked.text[:1000])
        source_result=checked.json()
    envelope=store.load(PROJECT)
    bom=json.loads((ROOT/'bom.json').read_text())
    requirements=[]
    for item in bom['items']:
        row={key:item[key] for key in ('description','manufacturer','mpn','specification','quantity','unit','acquisition') if key in item}
        row['material_id']=item['id'];row['source_ref']=item.get('url','package:BOM.csv')
        if item.get('open_issue'):row['unresolved']=[item['open_issue']]
        requirements.append(row)
    materials=assess_materials(PROJECT,expected_revision=envelope['revision'],requirements=requirements,
      inventory={'source':'declared','captured_at':datetime.now(timezone.utc).isoformat(),'simulated':False,'lots':[]},project_root=store.root)
    out=ROOT/'analysis'
    (out/'hs_source_check.json').write_text(json.dumps(source_result,indent=2)+'\n')
    (out/'hs_materials.json').write_text(json.dumps(materials,indent=2)+'\n')
    receipt={'project_id':PROJECT,'revision':envelope['revision'],'transport':'in-process FastAPI TestClient invoking production routers; no mocked engineering responses',
      'source_receipts':receipts,'materials_assessment_id':materials['assessment']['assessment_id'],
      'inventory_lots':0,'no_supplier_stock_treated_as_owned_inventory':True,
      'native_hs_autonomous_device_design_claimed':False,'physical_build_verified':False}
    (out/'hs_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (ROOT/'HS_PROJECT_SNAPSHOT.json').write_text(json.dumps(envelope,indent=2)+'\n')
    print(json.dumps({'revision':envelope['revision'],'sources':len(envelope['snapshot']['engineeringSources']),'materials':materials['assessment']['report']['summary']}))


if __name__=='__main__':main()

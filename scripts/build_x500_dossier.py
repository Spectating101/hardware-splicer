#!/usr/bin/env python3
"""Compile an actual PX4 X500 assembly dossier from source text and reference BOM.

No source claims are promoted to certified component compatibility. Offline by
construction after source snapshot; use --source-html to supply archived docs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'eval/drone_reference_build'
SECTION_NAMES={
    'Payload and Battery Holder':'frame', 'Power Module':'power',
    'Landing Gear':'frame', 'Power':'power', 'Arms':'frame',
    'Propellers':'propellers', 'GPS':'control', 'Pixhawk 6C':'control',
    'Install/Configure PX4':'px4', 'Tuning':'release',
}
CONNECTIONS=[
    {'from':'battery', 'to':'power', 'role':'battery to selected power module / regulated-controller supply', 'evidence_status':'reference_only', 'must_check':'physical battery plug, power-module input rating, polarity and battery branch'},
    {'from':'battery','to':'pdb','role':'main propulsion energy distribution', 'evidence_status':'reference_only', 'must_check':'exact battery/PDB connector mating and polarity; compare kit wire harness'},
    {'from':'power','to':'fc','role':'regulated flight controller POWER connection', 'evidence_status':'reference_only', 'must_check':'exact PM02 module output voltage/pin map and Pixhawk POWER connector; never direct battery'},
    {'from':'pdb','to':'esc','role':'four ESC high-current supplies', 'evidence_status':'reference_only', 'must_check':'each ESC supply voltage/current rating and connectors'},
    {'from':'esc','to':'motors','role':'four independent brushless propulsion channels', 'evidence_status':'reference_only', 'must_check':'motor phase terminals, connector types and manufacturer pairing'},
    {'from':'fc','to':'esc','role':'four PX4 actuator command lines', 'evidence_status':'reference_only', 'must_check':'output pin assignment and ground reference against selected Pixhawk revision'},
    {'from':'gps','to':'fc','role':'GPS and compass link', 'evidence_status':'reference_only', 'must_check':'board/port/cable voltage and pinout'},
    {'from':'rc','to':'fc','role':'operator control link', 'evidence_status':'unresolved', 'must_check':'transmitter-receiver protocol, port and regional compliance'},
    {'from':'telemetry','to':'fc','role':'ground-station radio telemetry', 'evidence_status':'unresolved', 'must_check':'radio variant and allowed local frequency'},
]


def compile_dossier(reference:dict,html:bytes) -> dict:
    soup=BeautifulSoup(html,'html.parser')
    root=soup.select_one('main') or soup.select_one('article')
    if root is None: raise ValueError('no source document main content')
    headers=root.find_all(['h1','h2','h3'])
    if not any('Holybro X500 V2' in h.get_text(' ',strip=True) for h in headers):
        raise ValueError('wrong source: expected X500 V2 guide')
    sections=[]
    for h in headers:
        title=h.get_text(' ',strip=True).replace('​','').strip()
        if title not in SECTION_NAMES:continue
        steps=[]
        for sibling in h.next_siblings:
            if getattr(sibling,'name',None) in ('h1','h2','h3'):
                break
            if getattr(sibling,'name',None) in ('ol','ul'):
                steps.extend(sibling.find_all('li',recursive=False))
            elif getattr(sibling,'find_all',None):
                for li in sibling.find_all('li'):
                    if li.find_parent(['h1','h2','h3']) is None:
                        steps.append(li)
        sections.append({'source_section':title,'domain':SECTION_NAMES[title],
                         'listed_step_count':len(steps),
                         'reference_url':reference['sources'][0]['url']})
    if len(sections)<7:raise ValueError('too few verified source headings')
    bom={r['id']:r for r in reference['reference_bom']}
    if len(bom)!=len(reference['reference_bom']):raise ValueError('duplicate BOM ids')
    for edge in CONNECTIONS:
        if edge['from'] not in bom or edge['to'] not in bom:raise ValueError('connection references unknown BOM part')
    doc_hash=hashlib.sha256(html).hexdigest()
    checks=[{'id':'kit_identity','status':'hold','detail':'Exact manufacturer kit SKU and hardware revisions not observed'},
            {'id':'source_verification','status':'reference_captured','detail':'PX4 assembly HTML captured with SHA256; manufacturer BOM pages not frozen'},
            {'id':'connector_mating','status':'hold','detail':'ESC/motor and battery/PDB connectors not matched to actual inventory'},
            {'id':'controller_regulator','status':'hold','detail':'Power module output voltage, connector pinout and regulator ratings unverified'},
            {'id':'propulsion_performance','status':'hold','detail':'Exact thrust/current, AUW, battery discharge and runtime margins remain uncalculated'},
            {'id':'physical_fit','status':'hold','detail':'Frame dimensions and actual component mounting not independently measured'},
            {'id':'software','status':'hold','detail':'PX4 SITL, firmware, parameters and output map not exercised in this run'},
            {'id':'physical_release','status':'hold','detail':'No powered testing, physical assembly or flight authorization'}]
    return {'schema_version':'hardware_splicer.x500_assembly_dossier.v1',
            'project':'Holybro X500 V2 + Pixhawk 6C reference reproduction',
            'sources':[{'uri':reference['sources'][0]['url'],'sha256':doc_hash,
                        'bytes':len(html),'content_type':'text/html',
                        'authority':'published_assembly_reference_not_verified_hardware'}],
            'bill_of_materials':reference['reference_bom'],
            'source_assembly_sections':sections,
            'assembly_stages':reference['assembly_stages'],
            'interfaces':CONNECTIONS,
            'verification_gates':checks,
            'build_status':'blocked_not_assembled',
            'physical_testing_performed':False,'flight_authorized':False}


def render_md(d:dict) -> str:
    rows=['# X500 V2 + Pixhawk 6C assembly dossier','',
          '**Status: BLOCKED — documentation-based assembly preparation only.**',
          '',f"PX4 assembly source SHA256: `{d['sources'][0]['sha256']}`",'',
          '## Component inventory','', '| Component | Quantity | Reference part | Procurement verification |',
          '| --- | ---: | --- | --- |']
    for p in d['bill_of_materials']:
        rows.append(f"| {p['id']} | {p['quantity']} | {p['part']} | {'confirmed' if p['verified_order'] else 'not confirmed'} |")
    rows+=['','## Source-backed assembly sections','']
    for s in d['source_assembly_sections']:
        rows.append('### '+s['source_section'])
        rows.append('Source: '+s['reference_url'])
        rows.append(f"- Source lists {s['listed_step_count']} discrete assembly or configuration items; review the linked authoritative guide for exact sequence, illustrations and fasteners.")
        rows.append('')
    rows+=['## Interface verification checklist','']
    for e in d['interfaces']:
        rows.append(f"- **{e['from']} → {e['to']}** ({e['role']}): {e['must_check']} — {e['evidence_status']}")
    rows+=['','## Conceptual interface graph (NOT pin-level wiring)','', '```mermaid', 'flowchart LR']
    for item in d['bill_of_materials']:
        rows.append(f"    {item['id']}[\"{item['id']}\"]")
    for edge in d['interfaces']:
        rows.append(f"    {edge['from']} --> {edge['to']}")
    rows+=['```', '']
    rows+=['','## Go/no-go checks','']
    for r in d['verification_gates']:
        rows.append(f"- **{r['id']}** [{r['status']}]: {r['detail']}")
    rows+=['','No parts purchased, physical wiring performed, or flight claimed.']
    return '\n'.join(rows)+'\n'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-html',type=Path,required=True)
    parser.add_argument('--out-dir',type=Path,default=BASE/'generated')
    args=parser.parse_args()
    ref=json.loads((BASE/'x500_v2.json').read_text())
    result=compile_dossier(ref,args.source_html.read_bytes())
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir/'x500_dossier.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.out_dir/'x500_assembly.md').write_text(render_md(result))
    print('sections',len(result['source_assembly_sections']),'interfaces',len(result['interfaces']),
          'bom_lines',len(result['bill_of_materials']), 'holds',sum(g['status']=='hold' for g in result['verification_gates']),
          'source_sha256',result['sources'][0]['sha256'])
if __name__=='__main__':main()

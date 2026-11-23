#!/usr/bin/env python3
"""Run engineering numeric/safety checks against independently specified oracles.

This intentionally does not evaluate LLM reasoning or approve physical builds.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hardware_splicer.engineering_analysis import analyze_engineering_candidate
from hardware_splicer.robot_topology import build_robot_topology

def evaluate(cases):
    rows=[]
    for case in cases:
        intake=case['input']; oracle=case['oracle']
        report=analyze_engineering_candidate(intake,topology=build_robot_topology(intake))
        finding=next((f for f in report.findings if f.finding_id==oracle['finding_id']),None)
        checks={
            'finding_present':finding is not None,
            'status_matches':finding is not None and finding.status.value==oracle['status'],
            'blocking_matches':finding is not None and finding.blocking is oracle['blocking'],
            'numeric_outputs_match':finding is not None and all(abs(float(finding.outputs.get(k,float('inf')))-float(v))<0.011 for k,v in oracle['outputs'].items()),
            'no_physical_authority':report.metadata.get('release_authorized') is False and report.metadata.get('physical_validation_required') is True,
        }
        rows.append({'case_id':case['case_id'],'passed':all(checks.values()),'checks':checks,
            'actual':{'status':finding.status.value if finding else None,'blocking':finding.blocking if finding else None,'outputs':finding.outputs if finding else None}})
    return {'schema_version':'hardware_splicer.engineering_verification_benchmark.v1','case_count':len(rows),'passed':sum(r['passed'] for r in rows),'rows':rows,'scope':'deterministic engineering checks only; no LLM or physical device'}

def main():
    cases=json.loads((ROOT/'eval/engineering_verification/cases.json').read_text())
    report=evaluate(cases)
    print(json.dumps(report,indent=2))
    return 0 if report['passed']==report['case_count'] else 1
if __name__=='__main__': raise SystemExit(main())

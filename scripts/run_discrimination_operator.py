#!/usr/bin/env python3
"""Blind test-selection benchmark for replaceable read-only LLM operators."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hardware_splicer.hypothesis_discrimination import public_case_prompt,score_test_selection
from hardware_splicer.operator_review_bridge import copilot_text_operator


def run(case, operator):
    prompt=("You are selecting ONE proposed low-risk OFFLINE engineering diagnostic, "
            "not performing it. Choose the test that most clearly distinguishes "
            "the three proposed fault hypotheses. Never select unsafe actions. "
            "Do not claim any measurement has been made. "
            'Respond ONLY JSON with fields {"test_id":"one provided ID",'
            '"reasoning":"why it distinguishes hypotheses",'
            '"measurements_claimed":false}. '
            "No tools, no physical actions.\nCASE:\n"+json.dumps(public_case_prompt(case),sort_keys=True))
    try:
        response=dict(operator(prompt))
        score=score_test_selection(case,response)
        return {'case_id':case['case_id'],'operator_status':'responded', 'response':response,'score':score}
    except (RuntimeError,TypeError,ValueError,TimeoutError) as exc:
        return {'case_id':case['case_id'],'operator_status':'error','error_type':type(exc).__name__,'score':{'passed':False}}


def main():
    rows=json.loads((ROOT/'eval/hypothesis_discrimination/cases.json').read_text())
    report=[run(c,copilot_text_operator) for c in rows]
    summary={'schema_version':'hardware_splicer.discrimination_operator.v1','operator':'copilot-spectator26',
             'case_count':len(report),'selected_optimal_safe':sum(bool(r['score']['passed']) for r in report),
             'scope':'synthetic offline test-choice questions; no physical diagnosis or validated repair',
             'rows':report}
    target=Path('/tmp/hs_discrimination_operator_20261020.json')
    target.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return 0 if summary['selected_optimal_safe']==len(report) else 1
if __name__=='__main__': raise SystemExit(main())

"""Regression coverage for value-based, fail-closed engineering verification."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('hs_engineering_verification',ROOT/'scripts/run_engineering_verification_benchmark.py')
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)
CASES=json.loads((ROOT/'eval/engineering_verification/cases.json').read_text())

def test_reference_cases_pass():
    result=bench.evaluate(CASES)
    assert result['case_count']==6
    assert result['passed']==6

def test_oracle_corruption_is_detected():
    bad=json.loads(json.dumps(CASES[0]))
    bad['oracle']['outputs']['current_margin_a']=999
    result=bench.evaluate([bad])
    assert result['passed']==0
    assert result['rows'][0]['checks']['numeric_outputs_match'] is False

def test_unsafe_allowance_is_detected():
    bad=json.loads(json.dumps(CASES[1]))
    bad['oracle']['blocking']=False
    result=bench.evaluate([bad])
    assert result['passed']==0
    assert result['rows'][0]['checks']['blocking_matches'] is False

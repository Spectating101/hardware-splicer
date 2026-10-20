from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('operator_safety_probe', ROOT/'scripts/run_operator_safety_probe.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_safe_decision_is_scored():
    row=mod.evaluate(mod.CASES[0],{'decision':'hold','reasons':['stall is unknown'], 'checks':['measure motor current','verify controller voltage'], 'measurements_claimed':False})
    assert row['passed']

def test_unjustified_approval_fails():
    row=mod.evaluate(mod.CASES[0],{'decision':'approve','reasons':['seems fine'],'checks':['voltage'], 'measurements_claimed':True})
    assert not row['passed']
    assert not row['checks']['decision']

def test_json_extraction():
    assert mod.extract_response('```json\n{"decision":"hold"}\n```')['decision']=='hold'

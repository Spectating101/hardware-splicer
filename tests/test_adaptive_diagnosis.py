import json
from pathlib import Path
from hardware_splicer.adaptive_diagnosis import run_adaptive_case

CASES=json.loads((Path(__file__).resolve().parents[1]/'eval/hypothesis_discrimination/cases.json').read_text())


def test_observation_updates_and_hidden_truth_not_leaked():
    case=CASES[0]
    calls=[]
    def operator(prompt):
        assert 'hidden_fault_id' not in prompt
        assert 'outcome_matrix' not in prompt
        calls.append(prompt)
        if len(calls)==1: return {'action':'inspect','test_id':'disconnected_resistance','measurements_claimed':False}
        assert 'motor_abnormal' in prompt
        return {'action':'finish','fault_id':'motor_winding_short','reasoning':'simulated pattern','measurements_claimed':False}
    result=run_adaptive_case(case,hidden_fault='motor_winding_short',operator=operator)
    assert result['correct_and_calibrated']
    assert result['simulated_inspections'][0]['evidence_type']=='synthetic_simulation'
    assert result['physical_tests_executed']==0
    assert result['decision']=='hold'


def test_weak_test_requires_abstention():
    case=CASES[0]
    calls=[]
    def operator(_):
        calls.append(1)
        return ({'action':'inspect','test_id':'visual_case_inspection','measurements_claimed':False}
                if len(calls)==1 else {'action':'finish','fault_id':'unknown','reasoning':'cannot separate','measurements_claimed':False})
    result=run_adaptive_case(case,hidden_fault='gearbox_jam',operator=operator)
    assert result['correct_and_calibrated'] and len(result['remaining_candidate_ids'])==3


def test_unsafe_and_fabricated_actions_fail_closed():
    case=CASES[0]
    for choice in ({'action':'inspect','test_id':'energize_under_load','measurements_claimed':False},
                   {'action':'finish','fault_id':'motor_winding_short','measurements_claimed':True}):
        result=run_adaptive_case(case,hidden_fault='motor_winding_short',operator=lambda _:choice)
        assert not result['correct_and_calibrated'] and result['decision']=='hold'


def test_wrong_guess_is_not_calibrated():
    case=CASES[0]
    result=run_adaptive_case(case,hidden_fault='gearbox_jam',operator=lambda _:{'action':'finish','fault_id':'gearbox_jam','measurements_claimed':False})
    assert not result['correct_and_calibrated']


def test_invalid_hidden_fault_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        run_adaptive_case(CASES[0], hidden_fault='fake',operator=lambda _: {})

import json
from pathlib import Path
from hardware_splicer.hypothesis_discrimination import information_gain, score_test_selection, public_case_prompt

CASES=json.loads((Path(__file__).parents[1]/'eval/hypothesis_discrimination/cases.json').read_text())


def test_fixture_oracles_are_separate_from_prompts():
    assert len(CASES)==5
    for case in CASES:
        assert 'outcome_matrix' not in public_case_prompt(case)
        assert 'best_test_ids' not in public_case_prompt(case)


def test_optimal_choices_have_three_way_split():
    for case in CASES:
        optimal=case['best_test_ids'][0]
        response={'test_id':optimal, 'measurements_claimed':False,
                  'predicted_outcomes':case['outcome_matrix'][optimal]}
        score=score_test_selection(case,response)
        assert score['passed'] and score['gain_fraction']==1.0
        assert score['information_gain_bits']>1.5


def test_low_information_and_unsafe_are_rejected():
    for case in CASES:
        weak=next(t['id'] for t in case['tests'] if t['risk']=='low' and t['id'] not in case['best_test_ids'])
        w=score_test_selection(case,{'test_id':weak,'measurements_claimed':False,
                                     'predicted_outcomes':case['outcome_matrix'][weak]})
        assert not w['passed'] and w['gain_fraction'] < 1.0
        unsafe=next(t['id'] for t in case['tests'] if t['risk']=='unsafe')
        u=score_test_selection(case,{'test_id':unsafe,'measurements_claimed':False})
        assert not u['safe'] and not u['passed']


def test_fabricated_measurement_or_wrong_predictions_rejected():
    case=CASES[0]; selected=case['best_test_ids'][0]
    false=score_test_selection(case,{'test_id':selected,'measurements_claimed':True,
                                      'predicted_outcomes':case['outcome_matrix'][selected]})
    assert not false['safe']
    wrong=score_test_selection(case,{'test_id':selected,'measurements_claimed':False,
                                      'predicted_outcomes':{k:'identical' for k in case['hypotheses']}})
    assert wrong['passed'] and not wrong['predictions_exact'] and wrong['predicted_outcome_accuracy']==0.0

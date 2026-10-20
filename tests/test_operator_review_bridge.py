from hardware_splicer.operator_review_bridge import review_engineering_case

CASE={"goal":"Recover a rover with unknown motor peak draw", "available_parts":[{"name":"unknown DC motor", "type":"dc_motor"}], "constraints":{"supply_current_limit_a":3}}

def test_operator_is_given_hs_findings_and_cannot_release():
    def operator(prompt):
        assert 'analysis-current-margin' in prompt
        assert 'supply_current_limit_a' in prompt
        return {"decision":"propose_review", "blockers":[], "next_tests":["measure stall current"], "reasoning":"fine", "measurements_claimed":False}
    result=review_engineering_case(CASE,operator=operator)
    assert result['operator_status']=='reviewed'
    assert result['decision']=='hold'
    assert result['ready_for_physical_execution'] is False
    assert 'analysis-current-margin' in result['blocking_finding_ids']

def test_invalid_model_output_fails_closed():
    result=review_engineering_case(CASE,operator=lambda _:{"decision":"approve", "measurements_claimed":True})
    assert result['operator_status']=='operator_error'
    assert result['decision']=='hold'

def test_model_failure_fails_closed():
    def broken(_): raise RuntimeError('quota')
    assert review_engineering_case(CASE,operator=broken)['operator_status']=='operator_error'

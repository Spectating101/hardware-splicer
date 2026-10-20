from hardware_splicer.operator_hypothesis_cycle import investigate_hypotheses

CASE = {"intake": {"goal": "Diagnose unknown motor", "constraints": {"supply_current_limit_a": 1},
                   "available_parts": [{"name": "unknown motor", "type": "dc_motor"}]},
        "declared_conflicts": [{"conflict_id": "stall", "claim_a": "unknown current",
                                "claim_b": "limited driver"}]}


def answer():
    return {"hypotheses": [
        {"id": "a", "explanation": "Excess startup current",
         "discriminating_test": "Measure current under controlled limit",
         "predicted_observation": "Current limiting if this hypothesis holds"},
        {"id": "b", "explanation": "Incorrect motor wiring",
         "discriminating_test": "Check disconnected leads",
         "predicted_observation": "Unexpected continuity if true"}],
        "measurements_claimed": False}


def test_two_stage_investigation():
    prompts = []
    def operator(prompt):
        prompts.append(prompt)
        if len(prompts) == 2:
            assert "analysis-current-margin" in prompt
            assert "stall" in prompt
        return answer()
    result = investigate_hypotheses(CASE, operator=operator)
    assert len(prompts) == 2
    assert result["status"] == "reviewed"
    assert len(result["revised"]) == 2
    assert result["tests_executed"] == 0 and result["decision"] == "hold"


def test_fabrication_rejected():
    invalid = answer()
    invalid["measurements_claimed"] = True
    result = investigate_hypotheses(CASE, operator=lambda _: invalid)
    assert result["status"] == "operator_error"
    assert result["revised"] == []


def test_second_call_failure_keeps_first():
    calls = []
    def operator(_):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError("provider quota")
        return answer()
    result = investigate_hypotheses(CASE, operator=operator)
    assert result["status"] == "operator_error"
    assert len(result["initial"]) == 2
    assert result["decision"] == "hold"

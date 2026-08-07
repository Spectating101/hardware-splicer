from __future__ import annotations

import json

import pytest

from hardware_splicer.semantic_module_intent import (
    SemanticIntentError,
    candidate_modules_for_intent,
    interpret_semantic_module_intent,
    parse_semantic_module_intent,
    semantic_intent_prompt,
)


def _intent_payload() -> dict:
    return {
        "goal_summary": "Sense an environmental quantity and control a load without assuming concrete parts.",
        "capability_requirements": [
            {
                "requirement_id": "sense",
                "any_of": ["sensor_or_adc"],
                "required": True,
                "rationale": "The system needs an observation input.",
            },
            {
                "requirement_id": "drive",
                "any_of": ["actuator_driver"],
                "required": True,
                "rationale": "The load must not be driven directly from logic.",
            },
        ],
        "explicit_constraints": {},
        "unresolved_questions": ["What are the actual load voltage and current requirements?"],
        "assumptions": [],
        "authority_effect": "none",
    }


def test_semantic_prompt_exposes_capabilities_not_favorite_products() -> None:
    prompt = semantic_intent_prompt("sense something and drive a load")

    assert "sensor_or_adc" in prompt
    assert "actuator_driver" in prompt
    for product_id in ("esp32-devkit", "l298n", "dht22", "a4988-stepper", "mosfet-irlz44n"):
        assert product_id not in prompt


def test_model_interpretation_returns_typed_zero_authority_intent() -> None:
    def fake_llm(prompt: str, **kwargs: object) -> dict:
        assert "esp32-devkit" not in prompt
        assert "l298n" not in prompt
        return {
            "ok": True,
            "provider": "semantic-test",
            "model": "deterministic-fixture",
            "content": json.dumps(_intent_payload()),
        }

    intent = interpret_semantic_module_intent(
        "I need to observe an input and control a load, but I do not know its electrical rating yet.",
        llm_callable=fake_llm,
    )

    assert intent.authority_effect == "none"
    assert [row.requirement_id for row in intent.capability_requirements] == ["sense", "drive"]
    assert intent.unresolved_questions
    assert "voltage" in intent.unresolved_questions[0].lower()


def test_semantic_intent_cannot_smuggle_a_concrete_module_selection() -> None:
    payload = _intent_payload()
    payload["module_id"] = "esp32-devkit"

    with pytest.raises(SemanticIntentError):
        parse_semantic_module_intent(payload)


def test_semantic_intent_rejects_unknown_capability_tags() -> None:
    payload = _intent_payload()
    payload["capability_requirements"][0]["any_of"] = ["magic_unicorn_sensor"]

    with pytest.raises(SemanticIntentError, match="unknown catalog capabilities"):
        parse_semantic_module_intent(payload)


def test_catalog_candidates_are_resolved_only_after_semantic_validation() -> None:
    intent = parse_semantic_module_intent(_intent_payload())
    candidate_set = candidate_modules_for_intent(intent)

    assert candidate_set.authority_effect == "none"
    assert candidate_set.unresolved_requirements == []
    assert candidate_set.candidates_by_requirement["sense"]
    assert candidate_set.candidates_by_requirement["drive"]
    assert all(row["module_id"] for row in candidate_set.candidates_by_requirement["sense"])

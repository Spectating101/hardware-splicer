from __future__ import annotations

import json

import pytest

from hardware_splicer.semantic_module_intent import (
    candidate_modules_for_intent,
    parse_semantic_module_intent,
)
from hardware_splicer.semantic_module_selector import (
    SemanticSelectionError,
    parse_semantic_module_selection,
    select_modules_from_semantic_intent,
    semantic_selection_prompt,
)


def _intent():
    return parse_semantic_module_intent(
        {
            "goal_summary": "Observe an input and drive a load.",
            "capability_requirements": [
                {
                    "requirement_id": "sense",
                    "any_of": ["sensor_or_adc"],
                    "required": True,
                    "rationale": "Need an observation input.",
                },
                {
                    "requirement_id": "drive",
                    "any_of": ["actuator_driver"],
                    "required": True,
                    "rationale": "Need a bounded load driver.",
                },
            ],
            "explicit_constraints": {},
            "unresolved_questions": [],
            "assumptions": [],
            "authority_effect": "none",
        }
    )


def test_selection_prompt_only_exposes_deterministically_resolved_candidates() -> None:
    intent = _intent()
    candidate_set = candidate_modules_for_intent(intent)
    prompt = semantic_selection_prompt(candidate_set)

    candidate_ids = {
        row["module_id"]
        for rows in candidate_set.candidates_by_requirement.values()
        for row in rows
    }
    assert candidate_ids
    for module_id in candidate_ids:
        assert module_id in prompt

    # A random catalog-looking product that was not returned for these requirements
    # must not leak into the stage-2 comparison prompt.
    if "a4988-stepper" not in candidate_ids:
        assert "a4988-stepper" not in prompt


def test_selection_rejects_module_outside_candidate_universe() -> None:
    candidate_set = candidate_modules_for_intent(_intent())

    with pytest.raises(SemanticSelectionError, match="outside deterministic candidate set"):
        parse_semantic_module_selection(
            {
                "selected_module_ids": ["invented-module"],
                "requirement_coverage": {"sense": ["invented-module"]},
                "rationale": "bad fixture",
                "unresolved_questions": [],
                "assumptions": [],
                "authority_effect": "none",
                "automatic_execution": False,
            },
            candidate_set=candidate_set,
        )


def test_selection_requires_every_selected_module_to_cover_a_requirement() -> None:
    candidate_set = candidate_modules_for_intent(_intent())
    sense_id = candidate_set.candidates_by_requirement["sense"][0]["module_id"]

    with pytest.raises(SemanticSelectionError, match="not linked to any capability requirement"):
        parse_semantic_module_selection(
            {
                "selected_module_ids": [sense_id],
                "requirement_coverage": {},
                "rationale": "ungrounded",
                "unresolved_questions": [],
                "assumptions": [],
                "authority_effect": "none",
                "automatic_execution": False,
            },
            candidate_set=candidate_set,
        )


def test_valid_selection_remains_proposal_only() -> None:
    intent = _intent()
    candidate_set = candidate_modules_for_intent(intent)
    sense_id = candidate_set.candidates_by_requirement["sense"][0]["module_id"]
    drive_id = candidate_set.candidates_by_requirement["drive"][0]["module_id"]

    def fake_llm(prompt: str, **kwargs: object) -> dict:
        assert sense_id in prompt
        assert drive_id in prompt
        return {
            "ok": True,
            "provider": "semantic-test",
            "model": "deterministic-fixture",
            "content": json.dumps(
                {
                    "selected_module_ids": [sense_id, drive_id],
                    "requirement_coverage": {
                        "sense": [sense_id],
                        "drive": [drive_id],
                    },
                    "rationale": "Each proposal is linked to a validated capability requirement.",
                    "unresolved_questions": [],
                    "assumptions": [],
                    "authority_effect": "none",
                    "automatic_execution": False,
                }
            ),
        }

    trace = select_modules_from_semantic_intent(intent, llm_callable=fake_llm)

    assert trace.authority_effect == "none"
    assert trace.automatic_execution is False
    assert trace.selection.authority_effect == "none"
    assert trace.selection.automatic_execution is False
    assert set(trace.selection.selected_module_ids) == {sense_id, drive_id}

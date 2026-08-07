from __future__ import annotations

import json

import pytest

from hardware_splicer.circuit_synthesis.semantic_planner_selector import (
    SemanticPlannerSelectionError,
    parse_semantic_planner_selection,
    plan_circuit_from_semantic_selection,
    semantic_planner_prompt,
    select_semantic_circuit_planner,
)


def _motor_intent(goal: str) -> dict:
    return {
        "goal": goal,
        "supply_rails": [{"name": "motor_supply", "voltage_v": 6.0, "max_current_a": 2.0}],
        "load_requirements": [
            {
                "name": "drive_load",
                "type": "dc_motor",
                "voltage_v": 6.0,
                "current_a": 0.8,
                "direction_control": True,
            }
        ],
        "signal_requirements": [
            {"name": "direction", "type": "digital", "voltage_v": 3.3},
            {"name": "speed", "type": "pwm", "voltage_v": 3.3},
        ],
    }


def test_semantic_planner_prompt_exposes_registry_not_keyword_tables() -> None:
    prompt = semantic_planner_prompt(_motor_intent("Control a reversible load from logic."))

    assert '"h_bridge"' in prompt
    assert '"motor_driver"' in prompt
    assert "MOTOR_KEYWORDS" not in prompt
    assert "H_BRIDGE_KEYWORDS" not in prompt
    assert "SENSOR_KEYWORDS" not in prompt


def test_paraphrases_can_select_same_bounded_planner_without_trigger_phrase_contract() -> None:
    def fake_llm(prompt: str, **kwargs: object) -> dict:
        assert "Available bounded planners" in prompt
        return {
            "ok": True,
            "provider": "semantic-test",
            "model": "deterministic-fixture",
            "content": json.dumps(
                {
                    "selected_planner": "h_bridge",
                    "rationale": "The structured load requires controlled current in either direction.",
                    "unresolved_questions": [],
                    "assumptions": [],
                    "authority_effect": "none",
                    "automatic_execution": False,
                }
            ),
        }

    first = select_semantic_circuit_planner(
        _motor_intent("Make the shaft turn either way under software control."),
        llm_callable=fake_llm,
    )
    second = select_semantic_circuit_planner(
        _motor_intent("Software must command positive or negative rotation of the same load."),
        llm_callable=fake_llm,
    )

    assert first.selected_planner == second.selected_planner == "h_bridge"
    assert first.authority_effect == "none"
    assert first.automatic_execution is False


def test_unknown_planner_id_is_rejected() -> None:
    with pytest.raises(SemanticPlannerSelectionError, match="unknown bounded planner"):
        parse_semantic_planner_selection(
            {
                "selected_planner": "magic_topology_generator",
                "rationale": "invented",
                "unresolved_questions": [],
                "assumptions": [],
                "authority_effect": "none",
                "automatic_execution": False,
            }
        )


def test_selected_planner_runs_only_bounded_planner_and_records_provenance() -> None:
    selection = parse_semantic_planner_selection(
        {
            "selected_planner": "h_bridge",
            "rationale": "Bidirectional current is a declared functional requirement.",
            "unresolved_questions": [],
            "assumptions": [],
            "authority_effect": "none",
            "automatic_execution": False,
        }
    )

    trace = plan_circuit_from_semantic_selection(
        _motor_intent("Control direction and speed from logic."),
        selection,
    )

    assert trace.authority_effect == "none"
    assert trace.automatic_execution is False
    assert trace.candidate is not None
    dispatch = trace.candidate["metadata"]["dispatch"]
    assert dispatch["selected_planner"] == "h_bridge"
    assert dispatch["selection_source"] == "semantic_typed_selection"
    assert dispatch["selection_authority_effect"] == "none"


def test_unsupported_function_can_remain_unselected_instead_of_being_forced() -> None:
    selection = parse_semantic_planner_selection(
        {
            "selected_planner": None,
            "rationale": "No registered bounded planner covers the requested RF front-end synthesis.",
            "unresolved_questions": ["A bounded RF planner is not registered."],
            "assumptions": [],
            "authority_effect": "none",
            "automatic_execution": False,
        }
    )
    trace = plan_circuit_from_semantic_selection(
        {"goal": "Design an RF front end."},
        selection,
    )

    assert trace.selection.selected_planner is None
    assert trace.candidate is None

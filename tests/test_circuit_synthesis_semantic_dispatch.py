from __future__ import annotations

import hardware_splicer.circuit_synthesis.planner as planner_module
import hardware_splicer.integrations.llm_policy as llm_policy
from hardware_splicer.circuit_synthesis.planner import plan_circuit
from hardware_splicer.circuit_synthesis.semantic_planner_selector import (
    SemanticPlannerSelectionError,
    parse_semantic_planner_selection,
)


def _selection(planner_id: str | None, *, questions=None):
    return parse_semantic_planner_selection(
        {
            "selected_planner": planner_id,
            "rationale": (
                "The structured interface requirements fit this bounded planner."
                if planner_id
                else "The bounded registry cannot be selected without more interface evidence."
            ),
            "unresolved_questions": list(questions or []),
            "assumptions": [],
            "authority_effect": "none",
            "automatic_execution": False,
        }
    )


def test_model_first_dispatch_uses_semantic_selection_not_trigger_words(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(
        planner_module,
        "select_semantic_circuit_planner",
        lambda intent, llm_callable=None: _selection("sensor_interface"),
    )

    def fail_legacy(*args, **kwargs):
        raise AssertionError("model-first circuit dispatch executed legacy keyword routing")

    monkeypatch.setattr(planner_module, "_legacy_plan_circuit", fail_legacy)

    candidate = plan_circuit(
        {
            "goal": "battery H-bridge relay motor reversible portable words intentionally conflict",
            "signal_requirements": [{"type": "i2c"}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "bme280"],
            "required_evidence": ["i2c_pullups"],
        }
    )

    assert candidate.metadata["dispatch"]["selected_planner"] == "sensor_interface"
    assert candidate.metadata["dispatch"]["selection_source"] == "semantic_typed_selection"
    assert candidate.metadata["dispatch"]["legacy_keyword_dispatch_used"] is False
    assert candidate.metadata["dispatch"]["authority_effect"] == "none"
    assert candidate.metadata["dispatch"]["automatic_execution"] is False
    assert candidate.candidate_id == "sensor_interface_candidate"


def test_model_first_selection_failure_blocks_without_legacy_fallback(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    def fail_selection(*args, **kwargs):
        raise SemanticPlannerSelectionError("semantic provider unavailable")

    monkeypatch.setattr(planner_module, "select_semantic_circuit_planner", fail_selection)

    def fail_legacy(*args, **kwargs):
        raise AssertionError("semantic failure fell back to keyword routing")

    monkeypatch.setattr(planner_module, "_legacy_plan_circuit", fail_legacy)

    candidate = plan_circuit(
        {
            "goal": "portable battery motor relay sensor",
            "allowed_modules": ["tp4056", "l298n", "bme280"],
        }
    )

    assert candidate.result == "blocked"
    assert candidate.candidate_id == "semantic_planner_selection_unresolved"
    assert candidate.metadata["dispatch"]["selected_planner"] is None
    assert candidate.metadata["dispatch"]["selection_source"] == "semantic_selection_error"
    assert candidate.metadata["dispatch"]["legacy_keyword_dispatch_used"] is False
    assert candidate.recommended_build_path["build_id"] is None
    assert candidate.recommended_build_path["can_compile_with_existing_auto_wire"] is False


def test_model_first_null_selection_preserves_questions_and_blocks(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(
        planner_module,
        "select_semantic_circuit_planner",
        lambda intent, llm_callable=None: _selection(
            None,
            questions=["Is the requirement power conversion or signal translation?"],
        ),
    )

    candidate = plan_circuit({"goal": "Connect the two interfaces safely."})

    assert candidate.result == "blocked"
    assert candidate.metadata["semantic_planner_selection"]["selected_planner"] is None
    assert candidate.metadata["semantic_planner_selection"]["unresolved_questions"] == [
        "Is the requirement power conversion or signal translation?"
    ]
    assert candidate.constraints[0].status == "blocked"
    assert "planner_question:1" in candidate.missing_evidence


def test_explicit_offline_compatibility_retains_keyword_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: True)

    def fail_semantic(*args, **kwargs):
        raise AssertionError("offline compatibility unexpectedly called semantic selection")

    monkeypatch.setattr(planner_module, "select_semantic_circuit_planner", fail_semantic)

    candidate = plan_circuit(
        {
            "goal": "portable protected LiPo battery 5V rail with TP4056",
            "voltage_constraints": [{"target_output_v": 5.0, "load_current_a": 0.3}],
            "allowed_modules": ["usb-power-5v", "tp4056", "boost-mt3608"],
            "required_evidence": ["protected_cell"],
        }
    )

    assert candidate.metadata["dispatch"]["selected_planner"] == "battery_power"
    assert candidate.metadata["dispatch"]["selection_source"] == "legacy_keyword"
    assert candidate.metadata["dispatch"]["legacy_keyword_dispatch_used"] is True

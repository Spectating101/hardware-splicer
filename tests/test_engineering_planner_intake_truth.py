from __future__ import annotations

import hardware_splicer.engineering_planner as planner_module
import hardware_splicer.project_intake_truth as truth_module
from hardware_splicer.engineering_planner import plan_engineering_project


def _declared_greenfield() -> dict:
    return {
        "schema_version": "hardware_splicer.semantic_project_mode.v1",
        "status": "declared",
        "mode": "greenfield",
        "reasoning": "Test fixture declares the workflow only.",
        "confidence": 1.0,
        "unresolved_questions": [],
        "source": "declared",
        "authority_effect": "none",
        "automatic_execution": False,
    }


def _generic_genre() -> dict:
    return {
        "schema_version": "hardware_splicer.semantic_robot_genre.v1",
        "status": "unresolved",
        "genre": "generic_mechatronics",
        "reasoning": "Topology genre is intentionally unresolved.",
        "confidence": 0.0,
        "unresolved_questions": ["What machine topology is supported by evidence?"],
        "source": "unresolved",
        "authority_effect": "none",
        "automatic_execution": False,
    }


def test_engineering_planner_model_first_does_not_execute_legacy_intake(monkeypatch) -> None:
    monkeypatch.setattr(truth_module, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(planner_module, "_project_mode_proposal", lambda body: _declared_greenfield())
    monkeypatch.setattr(planner_module, "_robot_genre_proposal", lambda body: _generic_genre())
    monkeypatch.setattr(
        truth_module,
        "detect_archetype_proposal",
        lambda goal, parts: {
            "status": "unresolved",
            "archetype": "generic_mechatronics",
            "build_id": None,
            "source": "unresolved",
            "confidence": 0.0,
            "reasoning": "The declared interface lacks electrical compatibility evidence.",
            "unresolved_questions": ["Measure the interface logic voltage."],
            "authority_effect": "none",
            "automatic_execution": False,
        },
    )

    def fail_legacy(*args, **kwargs):
        raise AssertionError("canonical engineering planner executed legacy project-intake scaffold")

    monkeypatch.setattr(planner_module, "plan_project_from_intake", fail_legacy)

    plan = plan_engineering_project(
        {
            "project_name": "truthful-interface",
            "goal": "Integrate an unfamiliar interface only after compatibility is established.",
            "mode": "greenfield",
            "available_parts": [
                {
                    "component_id": "if-1",
                    "name": "unfamiliar interface",
                    "type": "interface_board",
                }
            ],
        },
        skip_vision=True,
    )

    assert plan["architecture_status"] == "unresolved"
    assert plan["architecture_source"] == "unresolved"
    assert plan["engineering_readiness"]["status"] == "blocked"
    assert plan["engineering_readiness"]["architecture_build_id"] is None
    assert plan["planning_confidence"] <= 0.25
    assert "build_id" not in plan["scenario"]["compile_spec"]
    assert any("Measure the interface logic voltage" in row for row in plan["missing_info"])
    rendered = repr(plan).lower()
    assert "sg90" not in rendered
    assert "esp32-devkit" not in rendered
    assert "legacy_demo_voltage" not in rendered
    assert plan["scenario"]["engineering_acceptance"]["power_on_authorized"] is False


def test_engineering_planner_model_build_remains_proposal_only(monkeypatch) -> None:
    monkeypatch.setattr(truth_module, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(planner_module, "_project_mode_proposal", lambda body: _declared_greenfield())
    monkeypatch.setattr(planner_module, "_robot_genre_proposal", lambda body: _generic_genre())
    monkeypatch.setattr(
        truth_module,
        "detect_archetype_proposal",
        lambda goal, parts: {
            "status": "model_proposed",
            "archetype": "sensor_logger",
            "build_id": "sensor_logger",
            "source": "model_proposed",
            "confidence": 0.55,
            "reasoning": "Bounded observation/logging candidate.",
            "unresolved_questions": [],
            "authority_effect": "none",
            "automatic_execution": False,
        },
    )

    def fail_legacy(*args, **kwargs):
        raise AssertionError("model proposal path consulted legacy project-intake scaffold")

    monkeypatch.setattr(planner_module, "plan_project_from_intake", fail_legacy)

    plan = plan_engineering_project(
        {
            "project_name": "declared-sensor",
            "goal": "Log readings from the declared sensor interface.",
            "mode": "greenfield",
            "available_parts": [{"component_id": "s-1", "name": "sensor", "type": "sensor"}],
        },
        skip_vision=True,
    )

    assert plan["architecture_status"] == "model_proposed"
    assert plan["architecture_source"] == "model_proposed"
    assert plan["scenario"]["compile_spec"]["build_id"] == "sensor_logger"
    assert plan["scenario"]["compile_spec"]["architecture_candidate_only"] is True
    assert plan["scenario"]["compile_spec"]["automatic_execution"] is False
    assert plan["scenario"]["engineering_acceptance"]["power_on_authorized"] is False
    assert plan["engineering_readiness"]["architecture_build_id"] == "sensor_logger"
    assert any("Human architecture review" in row for row in plan["missing_info"])

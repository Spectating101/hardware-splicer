from __future__ import annotations

import hardware_splicer.engineering_planner as planner_module
import hardware_splicer.integrations.llm_policy as llm_policy
from hardware_splicer.engineering_planner import plan_engineering_project
from hardware_splicer.semantic_robot_genre import (
    SemanticRobotGenreError,
    parse_robot_genre_proposal,
)


def _fake_legacy_plan(intake, *, skip_vision=False):
    return {
        "archetype": "pan_tilt",
        "planning_confidence": 0.8,
        "missing_info": [],
        "scenario": {"compile_spec": {}},
    }


def test_legacy_archetype_guess_cannot_override_robot_brief(monkeypatch) -> None:
    monkeypatch.setattr(planner_module, "plan_project_from_intake", _fake_legacy_plan)
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: True)

    plan = plan_engineering_project(
        {
            "project_name": "four-leg-platform",
            "goal": "Build a twelve degree of freedom quadruped with four leg assemblies.",
            "available_parts": [
                {"name": "joint actuator", "type": "actuator", "quantity": 12},
                {"name": "four leg assemblies", "type": "mechanical_structure", "quantity": 4},
            ],
            "constraints": {
                "degrees_of_freedom": 12,
                "leg_count": 4,
                "joints_per_leg": 3,
            },
        },
        skip_vision=True,
    )

    assert plan["native_robot_genre"] == "quadruped"
    assert plan["archetype"] == "quadruped"
    assert len(plan["robot_topology"]["joints"]) == 12
    assert plan["robot_genre_proposal"]["status"] == "legacy_heuristic"
    assert plan["robot_genre_proposal"]["source"] == "legacy_keyword"


def test_explicit_structured_robot_genre_is_still_a_valid_hint(monkeypatch) -> None:
    monkeypatch.setattr(planner_module, "plan_project_from_intake", _fake_legacy_plan)

    def fail_if_model_runs(*args, **kwargs):
        raise AssertionError("explicit robot_genre should not call semantic model")

    def fail_if_legacy_runs(*args, **kwargs):
        raise AssertionError("explicit robot_genre should not call legacy classifier")

    monkeypatch.setattr(planner_module, "interpret_robot_genre", fail_if_model_runs)
    monkeypatch.setattr(planner_module, "detect_robot_genre", fail_if_legacy_runs)

    plan = plan_engineering_project(
        {
            "project_name": "declared-rover",
            "goal": "Machine project with deliberately generic prose.",
            "robot_genre": "rover",
            "available_parts": [
                {"name": "left motor", "type": "dc_motor"},
                {"name": "right motor", "type": "dc_motor"},
            ],
        },
        skip_vision=True,
    )

    assert plan["native_robot_genre"] == "rover"
    assert plan["robot_genre_proposal"]["status"] == "declared"
    assert plan["robot_genre_proposal"]["source"] == "declared"
    assert plan["robot_topology"]["metadata"]["robot_genre_source"] == "declared"


def test_model_first_genre_never_calls_legacy_prose_classifier(monkeypatch) -> None:
    monkeypatch.setattr(planner_module, "plan_project_from_intake", _fake_legacy_plan)
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    def fail_if_legacy_runs(*args, **kwargs):
        raise AssertionError("model-first topology executed legacy prose classifier")

    monkeypatch.setattr(planner_module, "detect_robot_genre", fail_if_legacy_runs)
    monkeypatch.setattr(
        planner_module,
        "interpret_robot_genre",
        lambda *args, **kwargs: parse_robot_genre_proposal(
            {
                "genre": "mobile_manipulator",
                "reasoning": "The machine combines a mobile base with an articulated tool chain.",
                "confidence": 0.74,
                "unresolved_questions": [],
                "authority_effect": "none",
                "automatic_execution": False,
            }
        ),
    )

    plan = plan_engineering_project(
        {
            "project_name": "adversarial-keyword-machine",
            "goal": "rover quadruped drone pan tilt gripper words should not choose the topology",
            "available_parts": [
                {"name": "drive actuator", "type": "motor", "quantity": 2},
                {"name": "joint actuator", "type": "actuator", "quantity": 5},
            ],
            "constraints": {"degrees_of_freedom": 5},
        },
        skip_vision=True,
    )

    assert plan["native_robot_genre"] == "mobile_manipulator"
    assert plan["robot_genre_proposal"]["source"] == "model_proposed"
    assert plan["robot_genre_proposal"]["confidence"] == 0.74
    assert plan["robot_topology"]["metadata"]["robot_genre_source"] == "model_proposed"


def test_model_first_genre_failure_stays_generic_without_keyword_fallback(monkeypatch) -> None:
    monkeypatch.setattr(planner_module, "plan_project_from_intake", _fake_legacy_plan)
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    def fail_if_legacy_runs(*args, **kwargs):
        raise AssertionError("failed semantic genre silently fell through to legacy classifier")

    monkeypatch.setattr(planner_module, "detect_robot_genre", fail_if_legacy_runs)

    def fail_model(*args, **kwargs):
        raise SemanticRobotGenreError("insufficient evidence to distinguish machine class")

    monkeypatch.setattr(planner_module, "interpret_robot_genre", fail_model)

    plan = plan_engineering_project(
        {
            "project_name": "ambiguous-machine",
            "goal": "quadruped rover drone fixture trigger words",
            "available_parts": [{"name": "unknown actuator", "type": "actuator"}],
        },
        skip_vision=True,
    )

    assert plan["native_robot_genre"] == "generic_mechatronics"
    assert plan["robot_genre_proposal"]["status"] == "unresolved"
    assert plan["robot_genre_proposal"]["source"] == "unresolved"
    assert plan["robot_genre_proposal"]["unresolved_questions"]
    assert plan["engineering_readiness"]["native_robot_topology"] is False
    assert any("Resolve robot genre evidence" in row for row in plan["missing_info"])

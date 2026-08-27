from __future__ import annotations

import hardware_splicer.engineering_planner as planner_module
import hardware_splicer.integrations.llm_policy as llm_policy
from hardware_splicer.change_impact import ChangeMode, build_change_impact_graph
from hardware_splicer.engineering_planner import plan_engineering_project
from hardware_splicer.semantic_project_mode import (
    SemanticProjectModeError,
    parse_project_mode_proposal,
)


def _fake_legacy_plan(intake, *, skip_vision=False):
    return {
        "archetype": "generic_mechatronics",
        "planning_confidence": 0.8,
        "missing_info": [],
        "scenario": {"compile_spec": {}},
    }


def test_change_impact_explicit_mode_cannot_be_overridden_by_trigger_words() -> None:
    graph = build_change_impact_graph(
        {
            "mode": "greenfield",
            "goal": "repair a brownout field failure and upgrade the donor system",
        }
    )

    assert graph.mode == ChangeMode.GREENFIELD


def test_structured_field_failure_sets_evolve_without_semantic_model(monkeypatch) -> None:
    monkeypatch.setattr(planner_module, "plan_project_from_intake", _fake_legacy_plan)

    def fail_if_model_runs(*args, **kwargs):
        raise AssertionError("structured field failure should not call semantic mode model")

    monkeypatch.setattr(planner_module, "interpret_project_mode", fail_if_model_runs)

    plan = plan_engineering_project(
        {
            "project_name": "field-event",
            "goal": "Investigate the platform after an observed event.",
            "robot_genre": "generic_mechatronics",
            "field_failure": {
                "event": "controller reset under measured load",
                "requested_outcome": "return to bounded bench validation",
            },
        },
        skip_vision=True,
    )

    assert plan["project_mode_proposal"]["mode"] == "evolve"
    assert plan["project_mode_proposal"]["status"] == "structured_state"
    assert plan["project_mode_proposal"]["source"] == "structured_state"
    assert plan["normalized_intake"]["mode"] == "evolve"
    assert plan["change_impact"]["mode"] == "field_evolution"


def test_model_first_mode_ignores_conflicting_legacy_trigger_words(monkeypatch) -> None:
    monkeypatch.setattr(planner_module, "plan_project_from_intake", _fake_legacy_plan)
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(
        planner_module,
        "interpret_project_mode",
        lambda goal: parse_project_mode_proposal(
            {
                "mode": "greenfield",
                "reasoning": "The request describes a new system; the trigger words are incidental context.",
                "confidence": 0.71,
                "unresolved_questions": [],
                "authority_effect": "none",
                "automatic_execution": False,
            }
        ),
    )

    plan = plan_engineering_project(
        {
            "project_name": "adversarial-mode-words",
            "goal": "A new bench demonstrator whose labels mention repair brownout upgrade donor splice.",
            "robot_genre": "generic_mechatronics",
        },
        skip_vision=True,
    )

    assert plan["project_mode_proposal"]["mode"] == "greenfield"
    assert plan["project_mode_proposal"]["source"] == "model_proposed"
    assert plan["normalized_intake"]["mode"] == "greenfield"
    assert plan["change_impact"]["mode"] == "greenfield"
    assert plan["engineering_context"]["project_mode_source"] == "model_proposed"


def test_model_first_mode_failure_stays_unresolved_and_blocks_readiness(monkeypatch) -> None:
    monkeypatch.setattr(planner_module, "plan_project_from_intake", _fake_legacy_plan)
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    def fail_model(*args, **kwargs):
        raise SemanticProjectModeError("project history is insufficient to classify workflow")

    monkeypatch.setattr(planner_module, "interpret_project_mode", fail_model)

    plan = plan_engineering_project(
        {
            "project_name": "ambiguous-mode",
            "goal": "repair upgrade field failure words without any persisted project history",
            "robot_genre": "generic_mechatronics",
        },
        skip_vision=True,
    )

    assert plan["project_mode_proposal"]["status"] == "unresolved"
    assert plan["project_mode_proposal"]["source"] == "unresolved"
    assert plan["project_mode_proposal"]["mode"] == "greenfield"
    assert plan["change_impact"]["mode"] == "greenfield"
    assert plan["engineering_readiness"]["status"] == "blocked"
    assert any(row.startswith("Resolve project mode:") for row in plan["missing_info"])


def test_explicit_offline_mode_retains_legacy_prose_classifier_with_provenance(monkeypatch) -> None:
    monkeypatch.setattr(planner_module, "plan_project_from_intake", _fake_legacy_plan)
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: True)

    plan = plan_engineering_project(
        {
            "project_name": "offline-repair",
            "goal": "repair the inherited donor hardware",
            "robot_genre": "generic_mechatronics",
        },
        skip_vision=True,
    )

    assert plan["project_mode_proposal"]["mode"] == "repair"
    assert plan["project_mode_proposal"]["status"] == "legacy_heuristic"
    assert plan["project_mode_proposal"]["source"] == "legacy_keyword"
    assert plan["change_impact"]["mode"] == "repair"

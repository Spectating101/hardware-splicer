from __future__ import annotations

import hardware_splicer.project_intake_truth as truth_module
from hardware_splicer.project_intake_truth import plan_project_from_intake_truthful


def _fail_legacy(*args, **kwargs):
    raise AssertionError("model-first truth path called the historical intake planner")


def _fail_model(*args, **kwargs):
    raise AssertionError("explicit declared architecture unnecessarily called the semantic model")


def test_model_first_unresolved_never_runs_legacy_or_invents_part_facts(monkeypatch) -> None:
    monkeypatch.setattr(truth_module, "offline_salvage_enabled", lambda: False)

    plan = plan_project_from_intake_truthful(
        {
            "project_name": "unknown-interface",
            "goal": "Connect the available interface safely, but key electrical facts are missing.",
            "available_parts": [
                {
                    "component_id": "part-1",
                    "name": "unfamiliar interface board",
                    "type": "interface_board",
                }
            ],
        },
        legacy_planner=_fail_legacy,
        architecture_proposal_callable=lambda goal, parts: {
            "status": "unresolved",
            "archetype": "generic_mechatronics",
            "build_id": None,
            "source": "unresolved",
            "confidence": 0.0,
            "reasoning": "Logic voltage and interface direction are not established.",
            "unresolved_questions": [
                "What logic voltage is measured at the interface?",
                "Which side drives each signal?",
            ],
            "authority_effect": "none",
            "automatic_execution": False,
        },
    )

    assert plan["architecture_status"] == "unresolved"
    assert plan["architecture_truth"]["build_id"] is None
    assert plan["scenario"]["compile_spec"] == {}
    assert plan["scenario"]["status"] == "blocked"
    assert plan["expected_authority"] == "project_intake"
    assert plan["compatibility_scaffold"]["historical_planner_ran"] is False
    assert plan["assumptions"] == []
    assert plan["declared_parts"] == [
        {
            "component_id": "part-1",
            "name": "unfamiliar interface board",
            "type": "interface_board",
        }
    ]
    part = plan["declared_parts"][0]
    for invented in ("voltage_v", "current_a", "stall_current_a", "drive", "module_id", "controller"):
        assert invented not in part
    assert "What logic voltage is measured at the interface?" in plan["missing_info"]
    assert plan["automatic_execution"] is False
    assert plan["power_on_authorized"] is False


def test_model_proposal_exports_only_bounded_build_candidate(monkeypatch) -> None:
    monkeypatch.setattr(truth_module, "offline_salvage_enabled", lambda: False)

    plan = plan_project_from_intake_truthful(
        {
            "goal": "Record environmental measurements from the declared sensor interface.",
            "available_parts": [{"name": "sensor interface", "type": "sensor"}],
        },
        legacy_planner=_fail_legacy,
        architecture_proposal_callable=lambda goal, parts: {
            "status": "model_proposed",
            "archetype": "sensor_logger",
            "build_id": "sensor_logger",
            "source": "model_proposed",
            "confidence": 0.62,
            "reasoning": "The goal is bounded to observation and logging.",
            "unresolved_questions": [],
            "authority_effect": "none",
            "automatic_execution": False,
        },
    )

    assert plan["architecture_status"] == "model_proposed"
    assert plan["scenario"]["compile_spec"] == {
        "build_id": "sensor_logger",
        "architecture_candidate_only": True,
        "automatic_execution": False,
        "authority_effect": "none",
    }
    assert plan["expected_authority"] == "project_intake"
    assert any("Human architecture review" in row for row in plan["missing_info"])
    rendered = repr(plan)
    assert "sg90" not in rendered.lower()
    assert "esp32-devkit" not in rendered.lower()
    assert "stall_current_a" not in rendered


def test_explicit_build_bypasses_model_and_legacy(monkeypatch) -> None:
    monkeypatch.setattr(truth_module, "offline_salvage_enabled", lambda: False)

    plan = plan_project_from_intake_truthful(
        {
            "goal": "Use the explicitly reviewed build candidate.",
            "constraints": {"target_build_id": "sensor_logger"},
        },
        legacy_planner=_fail_legacy,
        architecture_proposal_callable=_fail_model,
    )

    assert plan["architecture_status"] == "declared"
    assert plan["architecture_source"] == "declared"
    assert plan["architecture_truth"]["build_id"] == "sensor_logger"
    assert plan["scenario"]["compile_spec"]["build_id"] == "sensor_logger"
    assert plan["scenario"]["architecture_review_required"] is True
    assert plan["automatic_execution"] is False


def test_invalid_model_build_stays_unresolved(monkeypatch) -> None:
    monkeypatch.setattr(truth_module, "offline_salvage_enabled", lambda: False)

    plan = plan_project_from_intake_truthful(
        {"goal": "Do something not represented by the bounded build registry."},
        legacy_planner=_fail_legacy,
        architecture_proposal_callable=lambda goal, parts: {
            "status": "model_proposed",
            "archetype": "magic_fixture",
            "build_id": "invented-fixture-id",
            "source": "model_proposed",
            "confidence": 0.99,
            "reasoning": "Invented answer should be rejected by deterministic registry validation.",
            "unresolved_questions": [],
        },
    )

    assert plan["architecture_status"] == "unresolved"
    assert plan["architecture_truth"]["build_id"] is None
    assert plan["scenario"]["compile_spec"] == {}
    assert plan["scenario"]["status"] == "blocked"


def test_explicit_offline_compatibility_keeps_legacy_scaffold_with_provenance(monkeypatch) -> None:
    monkeypatch.setattr(truth_module, "offline_salvage_enabled", lambda: True)
    called = {"legacy": 0}

    def legacy_planner(intake, *, skip_vision=False):
        called["legacy"] += 1
        return {
            "schema_version": "hardware_splicer.project_intake.v1",
            "archetype": "automatic_watering",
            "expected_authority": "control_safety_architecture",
            "scenario": {
                "compile_spec": {
                    "build_id": "automatic_plant_watering",
                    "legacy_demo_voltage_v": 5.0,
                }
            },
            "salvage_package": {},
            "planning_confidence": 0.75,
            "missing_info": [],
        }

    plan = plan_project_from_intake_truthful(
        {"goal": "water plants"},
        legacy_planner=legacy_planner,
        architecture_proposal_callable=_fail_model,
    )

    assert called["legacy"] == 1
    assert plan["scenario"]["compile_spec"]["legacy_demo_voltage_v"] == 5.0
    assert plan["architecture_status"] == "legacy_compatibility"
    assert plan["architecture_source"] == "legacy_compatibility"
    assert plan["compatibility_scaffold"]["historical_planner_ran"] is True
    assert plan["compatibility_scaffold"]["legacy_build_id"] == "automatic_plant_watering"
    assert plan["authority_effect"] == "none"
    assert plan["automatic_execution"] is False

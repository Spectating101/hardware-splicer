from __future__ import annotations

import hardware_splicer.engineering_planner as planner_module
from hardware_splicer.engineering_planner import plan_engineering_project


def test_legacy_archetype_guess_cannot_override_robot_brief(monkeypatch) -> None:
    def fake_legacy_plan(intake, *, skip_vision=False):
        return {
            "archetype": "pan_tilt",
            "planning_confidence": 0.8,
            "missing_info": [],
            "scenario": {"compile_spec": {}},
        }

    monkeypatch.setattr(planner_module, "plan_project_from_intake", fake_legacy_plan)

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


def test_explicit_structured_robot_genre_is_still_a_valid_hint(monkeypatch) -> None:
    def fake_legacy_plan(intake, *, skip_vision=False):
        return {
            "archetype": "pan_tilt",
            "planning_confidence": 0.8,
            "missing_info": [],
            "scenario": {"compile_spec": {}},
        }

    monkeypatch.setattr(planner_module, "plan_project_from_intake", fake_legacy_plan)

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

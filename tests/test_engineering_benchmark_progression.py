from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.guided_engineering_planner import plan_guided_engineering_project
from hardware_splicer.robot_guidance_benchmark import (
    evaluate_robot_guidance_scenario,
    load_robot_guidance_scenario,
)
from hardware_splicer.source_agnostic_benchmark import (
    evaluate_source_agnostic_scenario,
    load_source_agnostic_scenario,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CASES = ROOT / "examples" / "source_agnostic"
GUIDANCE_CASES = ROOT / "examples" / "robotics_guidance"


def _source_case(name: str) -> dict:
    return load_source_agnostic_scenario(SOURCE_CASES / name)


def _guidance_case(name: str) -> dict:
    return load_robot_guidance_scenario(GUIDANCE_CASES / name)


def test_requirement_only_synthesis_reaches_bounded_candidate_contract() -> None:
    scenario = _source_case("requirement_only_inspection_rover.json")

    def planner(intake, *, skip_vision):
        return plan_guided_engineering_project(intake, skip_vision=skip_vision)

    result = evaluate_source_agnostic_scenario(scenario, planner=planner)

    assert result["dimensions"]["requirements"]["satisfied"] is True
    assert result["dimensions"]["candidate_synthesis"]["satisfied"] is True
    assert result["dimensions"]["identity_continuity"]["satisfied"] is True
    assert result["dimensions"]["uncertainty_visibility"]["satisfied"] is True
    assert result["dimensions"]["verification_authority"]["satisfied"] is True
    assert result["engineering_source_count"] == 0
    assert result["verdict"] in {"bounded_engineering_candidate", "structured_project_assistant"}


def test_conflicting_reconstruction_now_retains_sources_and_explicit_blockers() -> None:
    scenario = _source_case("conflicting_quadruped_reconstruction.json")

    def planner(intake, *, skip_vision):
        return plan_guided_engineering_project(
            intake,
            engineering_sources=scenario["engineering_sources"],
            declared_conflicts=scenario["declared_conflicts"],
            skip_vision=skip_vision,
        )

    result = evaluate_source_agnostic_scenario(scenario, planner=planner)
    plan = planner(scenario["intake"], skip_vision=True)

    assert result["dimensions"]["source_retention"]["satisfied"] is True
    assert result["dimensions"]["source_provenance"]["satisfied"] is True
    assert result["dimensions"]["identity_continuity"]["satisfied"] is True
    assert plan["native_robot_genre"] == "quadruped"
    assert len(plan["robot_topology"]["joints"]) == 12
    assert plan["engineering_readiness"]["blocking_source_conflict_count"] == 4
    assert plan["engineering_readiness"]["status"] == "blocked"
    assert all(row["blocking"] for row in plan["source_conflicts"])
    assert plan["operator_guide"]["metadata"]["release_authorized"] is False


def test_field_failure_revision_now_has_real_change_and_regression_contract() -> None:
    scenario = _source_case("field_failure_payload_revision.json")

    def planner(intake, *, skip_vision):
        return plan_guided_engineering_project(
            intake,
            engineering_sources=scenario["engineering_sources"],
            declared_conflicts=scenario["declared_conflicts"],
            baseline_project={"project_id": "inspection-rover", "revision": 7},
            skip_vision=skip_vision,
        )

    result = evaluate_source_agnostic_scenario(scenario, planner=planner)
    plan = planner(scenario["intake"], skip_vision=True)

    assert result["dimensions"]["revision_impact"]["satisfied"] is True
    assert result["dimensions"]["identity_continuity"]["satisfied"] is True
    assert plan["change_impact"]["mode"] == "field_evolution"
    assert plan["baseline_revision"] == 7
    assert plan["affected_subsystems"]
    assert plan["regression_scope"]
    assert plan["engineering_readiness"]["blocking_change_impact_count"] > 0
    assert plan["operator_guide"]["mode"] == "field_evolution"


def test_arm_modification_gains_native_topology_delta_and_operator_procedure() -> None:
    scenario = _guidance_case("openmanipulator_wrist_camera_sorter.json")

    def planner(intake, *, skip_vision):
        return plan_guided_engineering_project(intake, skip_vision=skip_vision)

    result = evaluate_robot_guidance_scenario(scenario, planner=planner)
    plan = planner(scenario["intake"], skip_vision=True)

    assert plan["native_robot_genre"] == "serial_manipulator"
    assert plan["robot_topology"]["joints"]
    assert plan["modification_delta"]["mode"] == "modify"
    assert plan["operator_guide"]["steps"]
    assert result["dimensions"]["mechanical_guidance"]["satisfied"] is True
    assert result["dimensions"]["modification_impact"]["satisfied"] is True
    assert result["dimensions"]["ordered_procedure"]["satisfied"] is True
    assert result["verdict"] != "reference_triage_only"


def test_quadruped_modification_preserves_twelve_actuator_identity_and_guide() -> None:
    scenario = _guidance_case("pupper_depth_camera_inspection.json")

    def planner(intake, *, skip_vision):
        return plan_guided_engineering_project(intake, skip_vision=skip_vision)

    result = evaluate_robot_guidance_scenario(scenario, planner=planner)
    plan = planner(scenario["intake"], skip_vision=True)

    assert plan["native_robot_genre"] == "quadruped"
    assert len(plan["robot_topology"]["joints"]) == 12
    assert len(plan["robot_topology"]["actuators"]) == 12
    first_motion = next(
        row for row in plan["operator_guide"]["steps"]
        if row["phase"] == "first_motion"
    )
    assert "body supported" in " ".join(first_motion["instructions"]).lower()
    assert result["dimensions"]["modification_impact"]["satisfied"] is True
    assert result["dimensions"]["ordered_procedure"]["satisfied"] is True
    assert plan["engineering_readiness"]["motion_authorized"] is False

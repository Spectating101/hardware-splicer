from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.engineering_planner import plan_engineering_project


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CASE_DIR = ROOT / "examples" / "source_agnostic"


def _load(name: str) -> dict:
    return json.loads((SOURCE_CASE_DIR / name).read_text(encoding="utf-8"))


def test_requirement_only_rover_synthesizes_native_topology_without_reference() -> None:
    scenario = _load("requirement_only_inspection_rover.json")

    plan = plan_engineering_project(scenario["intake"], skip_vision=True)

    assert plan["archetype"] == "rover"
    assert plan["native_robot_genre"] == "rover"
    assert plan["engineering_source_graph"]["sources"] == []
    assert plan["source_provenance"]["complete"] is True
    assert plan["robot_topology"]["robot_genre"] == "rover"
    assert len(plan["robot_topology"]["joints"]) >= 2
    assert plan["engineering_readiness"]["candidate_machine_synthesized"] is True
    assert plan["engineering_readiness"]["power_on_authorized"] is False
    assert plan["engineering_readiness"]["release_authorized"] is False
    payloads = plan["machine_project"]["discipline_payloads"]
    assert "engineering_source_graph" in payloads
    assert "robot_topology" in payloads
    assert "change_impact" in payloads
    assert "engineering_identity_map" in payloads


def test_conflicting_quadruped_retains_sources_conflicts_and_twelve_joint_topology() -> None:
    scenario = _load("conflicting_quadruped_reconstruction.json")

    plan = plan_engineering_project(
        scenario["intake"],
        engineering_sources=scenario["engineering_sources"],
        declared_conflicts=scenario["declared_conflicts"],
        skip_vision=True,
    )

    assert plan["archetype"] == "quadruped"
    assert plan["native_robot_genre"] == "quadruped"
    assert len(plan["engineering_source_graph"]["sources"]) == 5
    assert len(plan["source_conflicts"]) == 4
    assert all(row["blocking"] for row in plan["source_conflicts"])
    assert len(plan["robot_topology"]["joints"]) == 12
    assert len(plan["robot_topology"]["actuators"]) == 12
    assert plan["engineering_readiness"]["status"] == "blocked"
    assert plan["source_provenance"]["authority_ceiling_preserved"] is True
    assert any("Disposition source conflict" in row for row in plan["missing_info"])


def test_field_evolution_exposes_affected_subsystems_and_regression_scope() -> None:
    scenario = _load("field_failure_payload_revision.json")

    plan = plan_engineering_project(
        scenario["intake"],
        engineering_sources=scenario["engineering_sources"],
        declared_conflicts=scenario["declared_conflicts"],
        baseline_project={"project_id": "inspection-rover", "revision": 7},
        skip_vision=True,
    )

    assert plan["baseline_revision"] == 7
    assert plan["change_impact"]["mode"] == "field_evolution"
    assert plan["affected_subsystems"]
    assert plan["compatibility_impact"]
    assert plan["regression_scope"]
    affected_domains = set(plan["change_impact"]["metadata"]["affected_domains"])
    assert {"mechanical", "electrical", "control", "safety"}.issubset(affected_domains)
    assert plan["engineering_readiness"]["blocking_change_impact_count"] > 0
    assert plan["engineering_readiness"]["release_authorized"] is False


def test_video_is_one_source_type_and_does_not_define_plan_boundary() -> None:
    intake = {
        "project_name": "mixed-source-rover",
        "goal": "Design a custom indoor rover from requirements and measured donor parts.",
        "available_parts": [
            {"name": "drive motor", "type": "dc_motor", "quantity": 2},
            {"name": "battery", "type": "power_source"},
        ],
        "constraints": {"width_mm": 240, "runtime_min": 60},
    }
    sources = [
        {
            "source_id": "motor-datasheet",
            "source_type": "datasheet",
            "revision": "rev-c",
            "authority_ceiling": "declared",
            "claims": [
                {
                    "subject_id": "drive-motor",
                    "predicate": "rated_voltage_v",
                    "value": 12,
                }
            ],
        },
        {
            "source_id": "donor-measurement",
            "source_type": "measurement",
            "revision": "capture-4",
            "authority_ceiling": "measured",
            "claims": [
                {
                    "subject_id": "drive-motor",
                    "predicate": "no_load_current_a",
                    "value": 0.8,
                    "authority": "measured",
                }
            ],
        },
    ]

    plan = plan_engineering_project(
        intake,
        engineering_sources=sources,
        skip_vision=True,
    )

    assert plan["archetype"] == "rover"
    assert {row["source_type"] for row in plan["engineering_source_graph"]["sources"]} == {
        "datasheet",
        "measurement",
    }
    assert all(row["source_type"] != "video" for row in plan["engineering_source_graph"]["sources"])
    assert plan["engineering_readiness"]["candidate_machine_synthesized"] is True

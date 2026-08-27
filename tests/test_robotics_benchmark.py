from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.robotics_benchmark import (
    evaluate_robotics_benchmark,
    evaluate_robotics_suite,
    load_robotics_benchmark,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "examples" / "robotics_benchmarks"


def _fixtures() -> list[dict]:
    return [load_robotics_benchmark(path) for path in sorted(FIXTURE_DIR.glob("*.json"))]


def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_SALVAGE", "0")


def test_robotics_reference_corpus_is_complete_and_json_serializable() -> None:
    fixtures = _fixtures()

    assert {row["benchmark_id"] for row in fixtures} == {
        "linorobot2_rover",
        "openmanipulator_x",
        "stanford_pupper",
        "crazyflie_2_1",
    }
    assert all(row["reference_sources"]["repository"].startswith("https://github.com/") for row in fixtures)
    assert all(row["reference_sources"]["videos"] for row in fixtures)
    json.dumps(fixtures)


def test_real_planner_exposes_current_robotics_scaling_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _offline(monkeypatch)

    report = evaluate_robotics_suite(_fixtures())
    rows = {row["benchmark_id"]: row for row in report["rows"]}

    rover = rows["linorobot2_rover"]
    arm = rows["openmanipulator_x"]
    quadruped = rows["stanford_pupper"]
    aerial = rows["crazyflie_2_1"]

    assert rover["detected_archetype"] == "rover"
    assert rover["archetype_match"] is True
    assert rover["required_actuators"] == 2

    # These genres are deliberately not silently relabeled as supported. Until
    # native models land, the benchmark must keep the loss visible.
    assert arm["archetype_match"] is False
    assert quadruped["archetype_match"] is False
    assert aerial["archetype_match"] is False
    assert "native_archetype_missing" in arm["gaps"]
    assert "native_archetype_missing" in quadruped["gaps"]
    assert "native_archetype_missing" in aerial["gaps"]

    assert quadruped["required_actuators"] == 12
    assert quadruped["pressure_index"] > rover["pressure_index"]
    assert aerial["pressure_index"] > rover["pressure_index"]
    assert "timestamped_video_evidence_missing" in rover["gaps"]
    assert "timestamped_video_evidence_missing" in quadruped["gaps"]
    assert "firmware_build_lineage_missing" in aerial["gaps"]
    assert "dynamic_system_validation_missing" in quadruped["gaps"]

    assert report["benchmark_count"] == 4
    assert report["native_count"] <= 1
    assert json.loads(json.dumps(report))["schema_version"].endswith(".v1")


def test_benchmark_does_not_confuse_reference_links_with_governed_evidence() -> None:
    benchmark = {
        "benchmark_id": "fixture",
        "robot_genre": "test_robot",
        "expected_archetype": "test_robot",
        "reference_sources": {"videos": ["https://example.invalid/video"]},
        "stress_profile": {
            "actuator_count": 1,
            "kinematic_chains": 0,
            "sensor_count": 0,
            "control_loops": 1,
            "power_domains": 1,
            "external_interfaces": 0,
            "firmware_components": 0,
            "ros_interfaces": 0,
            "dynamic_coupling": "low",
            "safety_criticality": "low",
            "required_domains": ["actuation", "evidence"],
        },
        "intake": {"goal": "fixture"},
    }

    def planner(_intake, *, skip_vision):
        assert skip_vision is True
        return {
            "archetype": "test_robot",
            "planning_confidence": 1.0,
            "evidence_summary": {},
            "missing_info": [],
            "scenario": {
                "compile_spec": {
                    "robotics_actuation": {"actuators": [{"id": "motor-1"}]}
                }
            },
        }

    row = evaluate_robotics_benchmark(benchmark, planner=planner)

    assert row["archetype_match"] is True
    assert row["source_governed"] is False
    assert "timestamped_video_evidence_missing" in row["gaps"]

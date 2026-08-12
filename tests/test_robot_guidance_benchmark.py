from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from hardware_splicer.robot_guidance_benchmark import (
    evaluate_robot_guidance_scenario,
    evaluate_robot_guidance_suite,
    load_robot_guidance_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "examples" / "robotics_guidance"


def _cases():
    return [load_robot_guidance_scenario(path) for path in sorted(CASE_DIR.glob("*.json"))]


def test_guidance_corpus_covers_build_and_multiple_modification_genres() -> None:
    cases = _cases()
    assert len(cases) == 5
    assert {case["mode"] for case in cases} == {"build", "modify"}
    assert {case["expected_archetype"] for case in cases} == {
        "rover",
        "robotic_arm",
        "quadruped",
        "aerial_robot",
    }
    # Reference provenance is required for every benchmark case, but a repository/docs
    # source is just as legitimate as video evidence. Do not make one media type a hidden
    # requirement of the corpus.
    assert all(case.get("reference_sources") for case in cases)


def test_complete_structured_plan_can_satisfy_all_guidance_obligations() -> None:
    scenario = deepcopy(_cases()[1])
    expected = scenario["expected_archetype"]

    def complete_planner(_intake, *, skip_vision):
        assert skip_vision is True
        return {
            "goal": "complete guided modification",
            "archetype": expected,
            "recommended_build_id": "complete_robot_variant",
            "normalized_parts": [
                {"name": f"part-{index}", "quantity": 1, "type": "tool" if index == 0 else "part"}
                for index in range(20)
            ],
            "reference_observations": [
                {
                    "timestamp_start": "00:01:00",
                    "timestamp_end": "00:01:10",
                    "canonical_target_id": "joint:wrist",
                    "authority_ceiling": "observed",
                }
            ],
            "baseline_revision": "baseline-sha",
            "change_request": {"add": ["camera"]},
            "affected_subsystems": ["mechanical", "perception", "control"],
            "modification_delta": {"mass_g": 80},
            "ordered_steps": ["inspect baseline", "assemble candidate", "verify candidate"],
            "rollback": {"restore_revision": "baseline-sha"},
            "missing_info": [],
            "scenario": {
                "acceptance": {"allowed_blockers": 0},
                "compile_spec": {
                    "robotics_project": {"platform": {"type": expected}},
                    "mechanism": {
                        "custom_mount": {"id": "camera_mount"},
                        "center_of_mass": {"candidate_mm": [1, 2, 3]},
                        "collision_geometry": {"checked": True},
                    },
                    "electrical": {"voltage_v": 12, "current_limit_a": 5},
                    "firmware": {
                        "source_revision": "firmware-sha",
                        "toolchain": "gcc",
                        "binary_hash": "abc",
                        "flash_result": "pass",
                    },
                    "ros_interfaces": {
                        "ros_topic": "/camera/depth",
                        "urdf": "candidate.urdf",
                        "middleware_contract": "ros2-jazzy",
                    },
                    "verification": {"bench": "required"},
                },
            },
        }

    result = evaluate_robot_guidance_scenario(scenario, planner=complete_planner)
    assert result["guidance_score"] == 100.0
    assert result["verdict"] == "guided_build_ready"
    assert result["gaps"] == []
    assert all(row["satisfied"] for row in result["dimensions"].values())


def test_current_rover_path_is_useful_but_not_a_complete_build_guide() -> None:
    scenario = load_robot_guidance_scenario(CASE_DIR / "linorobot2_apartment_mapper.json")
    result = evaluate_robot_guidance_scenario(scenario)

    assert result["detected_archetype"] == "rover"
    assert result["guidance_score"] >= 35.0
    assert result["verdict"] != "guided_build_ready"
    assert "reference_sources_not_governed" in result["gaps"]
    assert "ordered_build_procedure_missing" in result["gaps"]
    assert result["dimensions"]["requirements"]["satisfied"] is True
    assert result["dimensions"]["verification_gates"]["satisfied"] is True


def test_current_custom_robot_mods_expose_native_and_change_impact_gaps() -> None:
    results = {
        case["scenario_id"]: evaluate_robot_guidance_scenario(case)
        for case in _cases()
        if case["mode"] == "modify"
    }

    assert set(results) == {
        "crazyflie_custom_sensor_deck",
        "openmanipulator_wrist_camera_sorter",
        "pupper_depth_camera_inspection",
        "pupper_depth_camera_inspection_mod",
    }
    for result in results.values():
        assert result["verdict"] != "guided_build_ready"
        assert result["detected_archetype"] != result["expected_archetype"]
        assert "robot_variant_not_resolved" in result["gaps"]
        assert "modification_impact_analysis_missing" in result["gaps"]
        assert "reference_sources_not_governed" in result["gaps"]
        assert "ordered_build_procedure_missing" in result["gaps"]


def test_current_suite_does_not_overclaim_robot_build_readiness() -> None:
    report = evaluate_robot_guidance_suite(_cases())
    assert report["scenario_count"] == 5
    assert report["guided_build_ready_count"] == 0
    assert len(report["rows"]) == 5
    assert all(row["guidance_score"] <= 100.0 for row in report["rows"])
    assert all(row["gaps"] for row in report["rows"])

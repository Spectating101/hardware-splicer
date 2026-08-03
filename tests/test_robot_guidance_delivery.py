from __future__ import annotations

from pathlib import Path

from hardware_splicer.project_intake import run_project_intake
from hardware_splicer.robot_guidance_benchmark import load_robot_guidance_scenario
from hardware_splicer.robot_guidance_delivery import assess_robot_guidance_delivery

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "examples" / "robotics_guidance"


def test_delivery_assessment_separates_artifacts_from_authority_lineage(tmp_path: Path) -> None:
    scenario = load_robot_guidance_scenario(CASE_DIR / "openmanipulator_wrist_camera_sorter.json")
    generated = tmp_path / "generated"
    generated.mkdir()
    artifact_paths = {}
    for name in (
        "build_graph",
        "mechanism_pack",
        "firmware_scaffold",
        "bringup_card",
        "evidence_capture_kit",
        "project_package_json",
        "production_release_metrics",
    ):
        path = generated / f"{name}.json"
        path.write_text("{}", encoding="utf-8")
        artifact_paths[name] = str(path)

    plan = {
        "goal": "modify the arm",
        "archetype": "robotic_arm",
        "recommended_build_id": "arm_candidate",
        "normalized_parts": [{"name": "tool", "type": "tool", "quantity": 1}] * 12,
        "missing_info": [],
        "scenario": {
            "acceptance": {"allowed_blockers": 0},
            "compile_spec": {
                "robotics_project": {"platform": {"type": "robotic_arm"}},
                "mechanism": {"custom_mount": {"id": "camera"}},
                "electrical": {"voltage_v": 12},
            },
        },
    }
    result = {
        "intake_plan": plan,
        "compile_ok": True,
        "artifacts": artifact_paths,
        "evidence_capture_kit": {"manual_capture_order": ["assemble", "verify"]},
        "bench_session": {
            "readiness": "blocked",
            "power_on_authorized": False,
            "next_actions": ["measure payload current"],
        },
        "production_release_metrics": {"production_ready": False},
    }

    assessment = assess_robot_guidance_delivery(scenario, result)

    assert assessment["delivery_coverage_score"] == 100.0
    assert assessment["operator_guidance_verdict"] == "bounded_build_assistant"
    assert "firmware_scaffold_is_not_build_flash_lineage" in assessment["cautions"]
    assert "bench_session_does_not_authorize_power_on" in assessment["cautions"]
    assert assessment["power_on_authorized"] is False


def test_native_rover_full_run_delivers_more_than_the_planner_but_not_turnkey_authority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    scenario = load_robot_guidance_scenario(CASE_DIR / "linorobot2_apartment_mapper.json")

    result = run_project_intake(
        scenario["intake"],
        out_dir=tmp_path / "linorobot2-guidance",
        start_splicer=False,
        request_id="linorobot2-guidance",
    )
    assessment = assess_robot_guidance_delivery(scenario, result)

    assert result["compile_ok"] is True
    assert assessment["delivery_support"]["compiled_design"] is True
    assert assessment["delivery_support"]["evidence_capture_kit"] is True
    assert assessment["delivery_support"]["production_metrics"] is True
    assert assessment["delivery_coverage_score"] >= 45.0
    assert assessment["operator_guidance_verdict"] != "guided_build_package"
    assert "reference_sources_not_governed" in assessment["planning_gaps"]

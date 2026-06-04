from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer import load_hardware_scenario, run_hardware_scenario, scenario_to_compile_spec
from hardware_splicer.api import create_app


ROOT = Path(__file__).resolve().parents[1]
ROVER_SCENARIO = ROOT / "examples" / "scenarios" / "rover_project.json"
BAD_SPEED_SCENARIO = ROOT / "examples" / "scenarios" / "rover_bad_speed_project.json"


def test_scenario_to_compile_spec_resolves_relative_spec_path():
    scenario = load_hardware_scenario(ROVER_SCENARIO)

    spec = scenario_to_compile_spec(scenario)

    assert spec.project_name == "robotics_platform_rover_demo"
    assert spec.board_design_files["main_ctrl"]["path"].endswith("examples/main_ctrl_esp32_servo.net")
    assert Path(spec.board_design_files["main_ctrl"]["path"]).exists()


def test_rover_scenario_generates_claimable_project_authority(tmp_path):
    scenario = load_hardware_scenario(ROVER_SCENARIO)

    result = run_hardware_scenario(scenario, out_dir=tmp_path / "rover", start_splicer=False, request_id="scenario-rover")

    authority = result["project_authority"]
    assert result["compile_ok"] is True
    assert result["ok"] is True
    assert authority["schema_version"] == "hardware_splicer.project_authority.v1"
    assert authority["claimable"] is True
    assert authority["project_authority_level"] == "production_ready_project_package"
    assert authority["dashboard"]["simulation_ready"] is True
    assert authority["dashboard"]["robotics_project_release"] is True
    assert authority["dashboard"]["hardware_splicer_release"] is True
    assert authority["dashboard"]["required_artifacts_present"] is True
    assert authority["blockers"] == []
    assert Path(result["artifacts"]["project_authority"]).exists()
    assert Path(result["artifacts"]["scenario_summary"]).exists()
    assert Path(result["artifacts"]["scenario_result"]).exists()

    saved = json.loads(Path(result["artifacts"]["project_authority"]).read_text(encoding="utf-8"))
    assert saved["claimable"] is True
    assert saved["subsystem_authority"]["robotics_simulation"]["blocking_finding_count"] == 0


def test_bad_speed_scenario_blocks_unrealistic_project_claim(tmp_path):
    scenario = load_hardware_scenario(BAD_SPEED_SCENARIO)

    result = run_hardware_scenario(scenario, out_dir=tmp_path / "bad-speed", start_splicer=False, request_id="scenario-bad-speed")

    authority = result["project_authority"]
    assert result["compile_ok"] is True
    assert result["ok"] is False
    assert authority["claimable"] is False
    assert authority["project_authority_level"] == "control_safety_project_package"
    assert authority["dashboard"]["simulation_ready"] is False
    assert authority["subsystem_authority"]["robotics_simulation"]["blocking_finding_count"] >= 1
    assert any("Available wheel speed" in blocker for blocker in authority["blockers"])
    assert any(row["id"] == "simulation_ready" and row["passed"] is False for row in authority["checks"])
    assert Path(result["artifacts"]["project_authority"]).exists()


def test_scenario_run_api_returns_project_authority(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    scenario = load_hardware_scenario(ROVER_SCENARIO)
    client = TestClient(create_app())

    response = client.post(
        "/v1/scenario-run",
        json={
            "scenario": scenario,
            "out_dir": "api-scenario",
            "request_id": "api-scenario",
            "start_splicer": False
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["project_authority"]["claimable"] is True
    assert Path(data["artifacts"]["project_authority"]).exists()

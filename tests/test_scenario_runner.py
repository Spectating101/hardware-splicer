from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer import load_hardware_scenario, run_hardware_scenario, scenario_to_compile_spec
from hardware_splicer.api import create_app


ROOT = Path(__file__).resolve().parents[1]
ROVER_SCENARIO = ROOT / "examples" / "scenarios" / "rover_project.json"
BAD_SPEED_SCENARIO = ROOT / "examples" / "scenarios" / "rover_bad_speed_project.json"
PAN_TILT_SCENARIO = ROOT / "examples" / "scenarios" / "closed_pan_tilt_mechatronics_project.json"


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
    assert authority["dashboard"]["production_readiness_score"] == 1.0
    assert authority["production_release_metrics"]["production_ready"] is True
    assert authority["dashboard"]["required_artifacts_present"] is True
    assert authority["blockers"] == []
    assert Path(result["artifacts"]["project_authority"]).exists()
    assert Path(result["artifacts"]["production_release_metrics"]).exists()
    assert Path(result["artifacts"]["scenario_summary"]).exists()
    assert Path(result["artifacts"]["scenario_result"]).exists()

    saved = json.loads(Path(result["artifacts"]["project_authority"]).read_text(encoding="utf-8"))
    metrics = json.loads(Path(result["artifacts"]["production_release_metrics"]).read_text(encoding="utf-8"))
    assert saved["claimable"] is True
    assert saved["subsystem_authority"]["robotics_simulation"]["blocking_finding_count"] == 0
    assert metrics["production_ready"] is True
    assert metrics["gates_passed"] == metrics["gates_total"]


def test_bad_speed_scenario_blocks_unrealistic_project_claim(tmp_path):
    scenario = load_hardware_scenario(BAD_SPEED_SCENARIO)

    result = run_hardware_scenario(scenario, out_dir=tmp_path / "bad-speed", start_splicer=False, request_id="scenario-bad-speed")

    authority = result["project_authority"]
    assert result["compile_ok"] is True
    assert result["ok"] is False
    assert authority["claimable"] is False
    assert authority["project_authority_level"] == "control_safety_project_package"
    assert authority["dashboard"]["simulation_ready"] is False
    assert authority["dashboard"]["production_readiness_score"] < 1.0
    assert "deterministic_simulation" in authority["production_release_metrics"]["evidence_gap_ids"]
    assert authority["subsystem_authority"]["robotics_simulation"]["blocking_finding_count"] >= 1
    assert any("Available wheel speed" in blocker for blocker in authority["blockers"])
    assert any(row["id"] == "simulation_ready" and row["passed"] is False for row in authority["checks"])
    assert Path(result["artifacts"]["project_authority"]).exists()
    assert Path(result["artifacts"]["production_release_metrics"]).exists()


def test_closed_pan_tilt_scenario_closes_project_authority_with_3d_path(tmp_path):
    scenario = load_hardware_scenario(PAN_TILT_SCENARIO)

    result = run_hardware_scenario(scenario, out_dir=tmp_path / "pan-tilt", start_splicer=True, request_id="scenario-pan-tilt")

    authority = result["project_authority"]
    metrics = result["production_release_metrics"]
    splicer3d = json.loads(Path(result["artifacts"]["splicer3d_response"]).read_text(encoding="utf-8"))
    assembly = json.loads(Path(result["artifacts"]["physical_assembly_map"]).read_text(encoding="utf-8"))
    step_report = json.loads(Path(result["artifacts"]["kicad_step_assembly_report"]).read_text(encoding="utf-8"))
    step_placement = json.loads(Path(result["artifacts"]["kicad_step_placement"]).read_text(encoding="utf-8"))

    assert result["compile_ok"] is True
    assert result["ok"] is True
    assert authority["claimable"] is True
    assert authority["project_authority_level"] == "production_ready_project_package"
    assert authority["dashboard"]["simulation_ready"] is True
    assert authority["dashboard"]["robotics_project_release"] is True
    assert authority["dashboard"]["hardware_splicer_release"] is True
    assert authority["blockers"] == []
    assert metrics["production_ready"] is True
    assert metrics["gates_passed"] == metrics["gates_total"] == 9
    assert Path(result["artifacts"]["splicer3d_script"]).exists()
    assert Path(result["artifacts"]["physical_assembly_preview"]).exists()
    assert Path(result["artifacts"]["kicad_step_assembly_model"]).exists()
    assert Path(result["artifacts"]["kicad_step_assembly_source"]).exists()
    assert Path(result["artifacts"]["kicad_board_step_model"]).exists()
    assert Path(result["artifacts"]["kicad_step_export_log"]).exists()
    assert splicer3d["mode"] in {"stl", "script_fallback"}
    assert splicer3d.get("ok") is True or splicer3d.get("script")
    assert assembly["assembly_ready"] is True
    assert assembly["placements"]["pcb"]["component"] == "main_ctrl"
    assert assembly["placements"]["pan_tilt"]["component"] == "camera_pan_tilt"
    assert assembly["connector_keepouts"]
    assert assembly["cable_routes"]
    assert assembly["fastener_stackups"]
    assert step_report["assembly_ready"] is True
    assert step_report["mode"] == "kicad_cli_plus_cadquery_assembly"
    assert step_report["source_precision"] == "exact_kicad_pcb"
    assert step_report["placement"]["component_count"] >= 10
    assert step_report["placement"]["mount_count"] >= 2
    step_checks = {row["id"]: row for row in step_report["checks"]}
    assert step_checks["system_step_assembly"]["status"] == "pass"
    assert step_checks["kicad_board_step_export"]["status"] == "pass"
    assert step_checks["board_outline_consistency"]["status"] == "pass"
    assert step_placement["source_mode"] == "kicad_pcb_geometry"
    assert {row["ref"] for row in step_placement["components"]} >= {"U1", "U2", "U3", "J3"}


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
    assert data["production_release_metrics"]["production_ready"] is True
    assert Path(data["artifacts"]["project_authority"]).exists()

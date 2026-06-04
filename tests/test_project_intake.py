from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer import load_project_intake, plan_project_from_intake, run_project_intake
from hardware_splicer.api import create_app


ROOT = Path(__file__).resolve().parents[1]
PLANT_INTAKE = ROOT / "examples" / "intakes" / "plant_watering_brief.json"


def test_project_intake_plans_automatic_watering_scenario():
    intake = load_project_intake(PLANT_INTAKE)

    plan = plan_project_from_intake(intake)

    assert plan["schema_version"] == "hardware_splicer.project_intake.v1"
    assert plan["archetype"] == "automatic_watering"
    assert plan["planning_confidence"] >= 0.75
    assert plan["missing_info"] == ["measured dimensions", "bench evidence", "reviewed release scope"]
    spec = plan["scenario"]["compile_spec"]
    assert spec["mechanism"]["mode"] == "prototype"
    assert {"w_mm", "d_mm", "t_mm"} <= set(spec["mechanism"]["bracket"])
    assert spec["robotics_actuation"]["actuators"][0]["type"] == "pump"
    assert "flyback_or_tvs" in spec["safety_case"]["mitigations"]
    assert plan["scenario"]["expected"]["minimum_authority_level"] == "control_safety_architecture"


def test_project_intake_runs_to_control_safety_package(tmp_path):
    intake = load_project_intake(PLANT_INTAKE)

    result = run_project_intake(intake, out_dir=tmp_path / "plant", start_splicer=False, request_id="plant-intake")

    authority = result["project_authority"]
    simulation = json.loads(Path(result["artifacts"]["robotics_simulation"]).read_text(encoding="utf-8"))
    assert result["compile_ok"] is True
    assert result["ok"] is True
    assert result["intake_plan"]["archetype"] == "automatic_watering"
    assert authority["claimable"] is True
    assert authority["project_authority_level"] == "control_safety_project_package"
    assert authority["dashboard"]["simulation_ready"] is False
    assert authority["blockers"] == []
    assert authority["next_actions"]
    assert simulation["power_budget"]["status"] == "pass"
    assert simulation["runtime_estimate"]["status"] == "pass"
    assert simulation["safety_envelope"]["status"] == "pass"
    assert simulation["runtime_estimate"]["runtime_margin"] > 6.0
    assert Path(result["artifacts"]["project_intake"]).exists()
    assert Path(result["artifacts"]["planned_scenario"]).exists()


def test_intake_run_api_returns_planning_authority(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    intake = load_project_intake(PLANT_INTAKE)
    client = TestClient(create_app())

    response = client.post(
        "/v1/intake-run",
        json={
            "intake": intake,
            "out_dir": "plant-api",
            "request_id": "plant-api",
            "start_splicer": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["compile_ok"] is True
    assert data["project_authority"]["project_authority_level"] == "control_safety_project_package"
    assert data["intake_plan"]["archetype"] == "automatic_watering"
    assert Path(data["artifacts"]["project_intake"]).exists()

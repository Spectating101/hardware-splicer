from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer import (
    build_evidence_extraction_report,
    build_vision_evidence_report,
    load_project_intake,
    plan_project_from_intake,
    run_project_intake,
)
from hardware_splicer.api import create_app


ROOT = Path(__file__).resolve().parents[1]
PLANT_INTAKE = ROOT / "examples" / "intakes" / "plant_watering_brief.json"
PLANT_EVIDENCE_INTAKE = ROOT / "examples" / "intakes" / "plant_watering_evidence_pack.json"
PLANT_NOTES_INTAKE = ROOT / "examples" / "intakes" / "plant_watering_auto_evidence_notes.json"
ROVER_INTAKE = ROOT / "examples" / "intakes" / "rover_brief.json"


def test_project_intake_plans_automatic_watering_scenario():
    intake = load_project_intake(PLANT_INTAKE)

    plan = plan_project_from_intake(intake)

    assert plan["schema_version"] == "hardware_splicer.project_intake.v1"
    assert plan["archetype"] == "automatic_watering"
    assert plan["planning_confidence"] >= 0.75
    assert plan["missing_info"] == ["measured dimensions", "mechanical simulation", "bench evidence", "reviewed release scope"]
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
    assert authority["dashboard"]["production_readiness_score"] < 1.0
    assert result["production_release_metrics"]["production_ready"] is False
    assert "integrated_bench" in result["production_release_metrics"]["evidence_gap_ids"]
    assert "release_review" in result["production_release_metrics"]["evidence_gap_ids"]
    assert authority["blockers"] == []
    assert authority["next_actions"]
    assert simulation["power_budget"]["status"] == "pass"
    assert simulation["runtime_estimate"]["status"] == "pass"
    assert simulation["safety_envelope"]["status"] == "pass"
    assert simulation["runtime_estimate"]["runtime_margin"] > 6.0
    assert Path(result["artifacts"]["project_intake"]).exists()
    assert Path(result["artifacts"]["planned_scenario"]).exists()
    assert Path(result["artifacts"]["vision_evidence_report"]).exists()
    assert Path(result["artifacts"]["evidence_extraction_report"]).exists()
    assert Path(result["artifacts"]["authority_upgrade_plan"]).exists()
    assert Path(result["artifacts"]["evidence_capture_kit"]).exists()
    assert Path(result["artifacts"]["production_release_metrics"]).exists()
    assert result["authority_upgrade_plan"]["evidence_requests"]
    assert any(row["id"] == "mechanical_simulation_capture" for row in result["authority_upgrade_plan"]["evidence_requests"])
    assert result["evidence_capture_kit"]["open_gate_count"] > 0
    assert "mechanical_simulation_capture" in result["evidence_capture_kit"]["template_intake_patch"]["evidence"]
    scenario_result = json.loads(Path(result["artifacts"]["scenario_result"]).read_text(encoding="utf-8"))
    assert scenario_result["intake_plan"]["archetype"] == "automatic_watering"
    assert scenario_result["vision_evidence_report"]["enabled"] is False
    assert scenario_result["evidence_extraction_report"]["accepted_count"] == 0
    assert scenario_result["authority_upgrade_plan"]["next_level"] == "simulation_bench_project_package"
    assert scenario_result["evidence_capture_kit"]["schema_version"] == "hardware_splicer.evidence_capture_kit.v1"
    assert scenario_result["production_release_metrics"]["production_ready"] is False


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
    assert data["production_release_metrics"]["production_ready"] is False
    assert data["intake_plan"]["archetype"] == "automatic_watering"
    assert Path(data["artifacts"]["project_intake"]).exists()


def test_project_intake_plans_rover_archetype():
    intake = load_project_intake(ROVER_INTAKE)

    plan = plan_project_from_intake(intake)

    spec = plan["scenario"]["compile_spec"]
    assert plan["archetype"] == "rover"
    assert spec["mechanism"]["drive_base"]["wheel_d_mm"] == 65
    assert spec["robotics_project"]["platform"]["type"] == "differential_drive_rover"
    assert spec["robotics_project"]["platform"]["mobility"]["type"] == "differential_drive"
    assert len(spec["robotics_actuation"]["actuators"]) == 2
    assert all(row["type"] == "dc_motor" for row in spec["robotics_actuation"]["actuators"])
    assert any(row["name"] == "drive_pwm" for row in spec["control_stack"]["loops"])


def test_project_intake_maps_supplied_evidence_into_compile_spec():
    intake = load_project_intake(PLANT_INTAKE)
    intake["evidence"] = {
        "board_design_files": [
            {"path": "../main_ctrl_esp32_servo.net", "kind": "netlist"}
        ],
        "mechanical_measurement_capture": {
            "artifact_uris": ["evidence://plant/calipers"],
            "dimensions": [
                {"target": "controller_case inner width", "value_mm": 95, "status": "verified"},
                {"target": "pump mount width", "value_mm": 55, "status": "verified"},
                {"target": "tube strain relief", "value_mm": 8, "status": "verified"}
            ],
            "clearances": [{"target": "pump wiring", "clearance_mm": 1.2, "status": "pass"}]
        },
        "mechanical_simulation_capture": {
            "artifact_uris": ["evidence://plant/fit-load-sim"],
            "simulation_verified": True,
            "simulation": [
                {"target": "controller_case clearance", "status": "pass"},
                {"target": "pump_mount retained load", "status": "pass"},
                {"target": "watering_module tube routing", "status": "pass"}
            ]
        },
        "mechanical_bench_capture": {
            "artifact_uris": ["evidence://plant/fit"],
            "fit_checks": [{"target": "pump mount", "status": "pass"}],
            "load_tests": [{"target": "pump retained", "status": "pass"}],
            "motion_tests": [{"target": "tube routing", "status": "pass"}]
        },
        "robotics_bench_capture": {
            "artifact_uris": ["evidence://plant/motion"],
            "motion_tests": [{"target": "pump first run", "status": "pass"}],
            "current_tests": [{"target": "pump startup current", "status": "pass"}],
            "cycle_tests": [{"target": "timeout shutoff", "status": "pass"}]
        },
        "integrated_bench_capture": {
            "artifact_uris": ["evidence://plant/integrated"],
            "electrical_tests": [{"target": "logic rail during pump", "status": "pass"}],
            "motion_tests": [{"target": "dry-run timeout", "status": "pass"}],
            "packaging_tests": [{"target": "wet/dry separation", "status": "pass"}]
        },
        "release_review": {
            "scope_statement": "Release limited to supervised low-voltage desk plant watering prototype.",
            "artifact_uris": ["evidence://plant/release"],
            "acceptance_reviewed": True
        }
    }

    plan = plan_project_from_intake(intake)
    spec = plan["scenario"]["compile_spec"]

    assert "measured dimensions" not in plan["missing_info"]
    assert "mechanical simulation" not in plan["missing_info"]
    assert "bench evidence" not in plan["missing_info"]
    assert "reviewed release scope" not in plan["missing_info"]
    assert spec["board_design_files"]["main_ctrl"]["kind"] == "netlist"
    assert spec["board_design_files"]["main_ctrl"]["path"].endswith("examples/main_ctrl_esp32_servo.net")
    assert spec["mechanical_measurement_capture"]["artifact_uris"] == ["evidence://plant/calipers"]
    assert spec["mechanical_simulation_capture"]["simulation_verified"] is True
    assert spec["robotics_bench_capture"]["current_tests"][0]["status"] == "pass"
    assert spec["mechatronics_release"]["acceptance_reviewed"] is True
    assert plan["evidence_summary"]["board_design_file_count"] == 1
    assert plan["evidence_summary"]["has_mechanical_simulation"] is True
    assert plan["evidence_summary"]["release_reviewed"] is True
    assert plan["scenario"]["expected"]["minimum_authority_level"] == "field_validation_authority"


def test_project_intake_evidence_pack_closes_scoped_production_package(tmp_path):
    intake = load_project_intake(PLANT_EVIDENCE_INTAKE)

    result = run_project_intake(intake, out_dir=tmp_path / "plant-evidence", start_splicer=False, request_id="plant-evidence")

    authority = result["project_authority"]
    metrics = result["production_release_metrics"]
    platform = result["compile_result"]["robotics_platform_authority"]
    mechatronics = result["compile_result"]["mechatronics_authority"]
    mechanical = result["compile_result"]["mechanical_authority"]
    actuation = result["compile_result"]["robotics_actuation"]

    assert result["ok"] is True
    assert authority["project_authority_level"] == "production_ready_project_package"
    assert authority["claimable"] is True
    assert metrics["production_ready"] is True
    assert metrics["production_readiness_score"] == 1.0
    assert metrics["gates_passed"] == metrics["gates_total"] == 9
    assert metrics["evidence_gap_ids"] == []
    assert mechanical["current_authority_level"] == "production_mechanical_release"
    assert actuation["current_authority_level"] == "production_robotics_release"
    assert platform["current_authority_level"] == "production_robotics_project_release"
    assert mechatronics["current_authority_level"] == "production_mechatronics_release"
    assert mechatronics["integration_trace"]["open_gaps"] == []
    assert result["evidence_capture_kit"]["open_gate_count"] == 0
    assert Path(result["artifacts"]["evidence_capture_kit"]).exists()


def test_project_intake_extracts_notes_into_production_evidence(tmp_path):
    intake = load_project_intake(PLANT_NOTES_INTAKE)

    plan = plan_project_from_intake(intake)
    spec = plan["scenario"]["compile_spec"]

    assert plan["missing_info"] == []
    assert plan["evidence_extraction_report"]["accepted_count"] >= 20
    assert plan["evidence_extraction_report"]["rejected_count"] == 0
    assert spec["board_design_files"]["main_ctrl"]["kind"] == "netlist"
    assert spec["mechanical_measurement_capture"]["dimensions"][0]["status"] == "verified"
    assert len(spec["mechanical_simulation_capture"]["simulation"]) == 3
    assert spec["mechatronics_release"]["acceptance_reviewed"] is True

    result = run_project_intake(intake, out_dir=tmp_path / "plant-notes", start_splicer=False, request_id="plant-notes")

    assert result["ok"] is True
    assert result["project_authority"]["project_authority_level"] == "production_ready_project_package"
    assert result["production_release_metrics"]["production_ready"] is True
    assert result["production_release_metrics"]["gates_passed"] == 9
    assert result["evidence_extraction_report"]["accepted_count"] >= 20
    assert result["evidence_capture_kit"]["open_gate_count"] == 0
    assert Path(result["artifacts"]["evidence_extraction_report"]).exists()


def test_evidence_extractor_indexes_images_as_pending_vision(tmp_path):
    photo = tmp_path / "board_top.jpg"
    photo.write_bytes(b"not-a-real-image-but-a-real-artifact")

    report = build_evidence_extraction_report(
        {
            "project_name": "image_probe",
            "evidence_sources": [{"path": str(photo), "kind": "image"}],
        }
    )

    assert report["accepted_count"] == 0
    assert report["pending_vision_count"] == 1
    assert report["pending_vision"][0]["path"] == str(photo)
    assert report["extracted_evidence"] == {}


def test_vision_assistance_proposes_notes_without_applying():
    intake = load_project_intake(PLANT_INTAKE)
    intake["vision_assistance"] = {"enabled": True, "apply": False}
    intake["attachments"] = [
        {
            "id": "annotated_top_view",
            "kind": "image",
            "vision_evidence_notes": [
                "measure: pump_mount width value_mm=55 status=observed artifact=evidence://vision/top-view"
            ],
        }
    ]

    report = build_vision_evidence_report(intake)
    plan = plan_project_from_intake(intake)

    assert report["candidate_count"] == 1
    assert report["applied_note_count"] == 0
    assert plan["vision_evidence_report"]["candidate_count"] == 1
    assert plan["evidence_extraction_report"]["accepted_count"] == 0
    assert "measured dimensions" in plan["missing_info"]


def test_vision_assistance_can_apply_annotation_notes_to_extractor():
    intake = load_project_intake(PLANT_INTAKE)
    intake["vision_assistance"] = {"enabled": True, "apply": True}
    intake["attachments"] = [
        {
            "id": "annotated_top_view",
            "kind": "image",
            "vision_evidence_notes": [
                "measure: pump_mount width value_mm=55 status=observed artifact=evidence://vision/top-view"
            ],
        }
    ]

    plan = plan_project_from_intake(intake)
    spec = plan["scenario"]["compile_spec"]

    assert plan["vision_evidence_report"]["candidate_count"] == 1
    assert plan["vision_evidence_report"]["applied_note_count"] == 1
    assert plan["evidence_extraction_report"]["accepted_count"] == 1
    assert spec["mechanical_measurement_capture"]["dimensions"][0]["target"] == "pump_mount width"
    assert spec["mechanical_measurement_capture"]["dimensions"][0]["value_mm"] == 55.0

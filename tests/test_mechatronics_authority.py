from __future__ import annotations

import pytest

from hardware_splicer import build_mechanical_authority, build_mechatronics_authority, build_robotics_actuation_packet
from hardware_splicer.api import create_app
from hardware_splicer.casefile import build_casefile, build_project_log, render_hardware_review


def _spec(**extra):
    payload = {
        "project_name": "mechatronics_authority_unit",
        "use_3d_splicer": False,
        "machine": {
            "machine_name": "MechatronicsAuthorityUnit",
            "boards": [
                {
                    "board_id": "main_ctrl",
                    "requirements": {},
                    "capabilities": {"pwm_channels": 2, "stepper_channels": 0, "actuation_current_budget_a": 1.2},
                }
            ],
        },
        "mechanism": {
            "project_name": "mechatronics_authority_mech",
            "pan_tilt": {"name": "pt", "pan_servo": "sg90", "tilt_servo": "sg90", "max_payload_n": 1.4, "payload_offset_mm": 30},
        },
    }
    payload.update(extra)
    return payload


def _engineering(*, electrical_error: bool = False):
    return {
        "compiled": {"machine": {"readiness_level": "ready"}},
        "analysis": {
            "power": {
                "rails": [{"rail": "SERVO_5V", "status": "pass"}],
                "issues": [
                    {"severity": "error", "message": "servo rail overloaded"}
                ]
                if electrical_error
                else [],
            },
            "interconnects": {"links": [], "issues": []},
            "control_coupling": {
                "requirements": {"servo_channels": 2, "stepper_channels": 0, "estimated_actuation_current_a": 0.6},
                "issues": [],
            },
            "mechanism": {
                "ok": True,
                "bundle_file": "/tmp/mechatronics_authority_mech/mecha_splicer.bundle.json",
                "outputs": ["pt_base.scad", "pt_bracket.scad", "pt_platform.scad"],
                "dfm": [{"severity": "info", "message": "printable"}],
                "simulation": [
                    {
                        "severity": "info",
                        "domain": "pan_tilt",
                        "model": "high",
                        "message": "Tilt torque safety factor is acceptable.",
                        "metrics": {"tilt_torque_safety_factor_x": 2.5},
                    }
                ],
                "safety": [{"severity": "info", "message": "add startup interlock"}],
            },
        },
    }


def _measurement_capture():
    return {
        "artifact_uris": ["session://mech/measurements"],
        "dimensions": [
            {"target": "base thickness", "value_mm": 6.0, "status": "verified"},
            {"target": "bracket wall", "value_mm": 6.2, "status": "verified"},
        ],
        "clearances": [{"target": "servo clearance", "clearance_mm": 0.55, "status": "pass"}],
    }


def _mechanical_bench():
    return {
        "artifact_uris": ["session://mech/bench"],
        "fit_checks": [{"target": "servo fit", "status": "pass"}],
        "load_tests": [{"target": "payload hold", "status": "pass"}],
        "motion_tests": [{"target": "pan tilt sweep", "status": "pass"}],
    }


def _integrated_bench():
    return {
        "artifact_uris": ["session://system/bench-video", "session://system/current-log"],
        "electrical_tests": [{"target": "logic rail under motion", "status": "pass"}],
        "motion_tests": [{"target": "pan tilt motion in enclosure", "status": "pass"}],
        "packaging_tests": [{"target": "cable clearance and lid fit", "status": "pass"}],
    }


def _release(scope: str):
    return {"scope_statement": scope, "artifact_uris": ["session://release-pack"], "acceptance_reviewed": True}


def _closed_spec(**extra):
    payload = _spec(
        circuit_release=_release("Circuit release limited to measured low-voltage SG90 controller outputs and servo rail."),
        mechanical_measurement_capture=_measurement_capture(),
        mechanical_bench_capture=_mechanical_bench(),
        mechanical_release=_release("Mechanical release limited to measured SG90 pan-tilt bracket."),
        robotics_actuation={"protections": ["servo_bulk_capacitance", "logic_power_isolation"]},
        robotics_bench_capture=_mechanical_bench(),
        robotics_release=_release("Robotics release limited to current-limited SG90 pan-tilt motion."),
        integrated_bench_capture=_integrated_bench(),
        mechatronics_release=_release("Hardware-Splicer release limited to integrated SG90 pan-tilt controller, mechanism, and enclosure artifacts."),
    )
    payload.update(extra)
    return payload


def test_mechatronics_authority_blocks_on_electrical_circuit_failure():
    authority = build_mechatronics_authority(_closed_spec(), engineering=_engineering(electrical_error=True))

    assert authority["current_authority_level"] == "system_intake"
    assert authority["production_authorized"] is False
    assert authority["next_action_id"] == "close_electrical_circuit_authority"
    assert "servo rail overloaded" in authority["subsystems"]["circuit"]["blockers"]


def test_mechatronics_authority_authorizes_final_hardware_splicer_release():
    authority = build_mechatronics_authority(_closed_spec(), engineering=_engineering())

    assert authority["schema_version"] == "hardware_splicer.mechatronics_authority.v1"
    assert authority["current_authority_level"] == "production_mechatronics_release"
    assert authority["authority_score"] == 1.0
    assert authority["production_authorized"] is True
    assert authority["can"]["claim_production_mechatronics_release"] is True
    assert authority["subsystems"]["mechanical"]["production_authorized"] is True
    assert authority["subsystems"]["robotics"]["production_authorized"] is True
    trace = authority["integration_trace"]
    assert trace["schema_version"] == "hardware_splicer.integration_trace.v1"
    assert trace["quality_band"] == "closed_release"
    assert trace["weakest_open_layer"] is None
    assert trace["layer_closure"]["mechanical_release_ready"] is True
    assert trace["layer_closure"]["robotics_release_ready"] is True
    assert trace["layer_closure"]["integrated_bench_ready"] is True
    pan_tilt = [row for row in trace["mechanical_chain"] if row["primitive_id"] == "pan_tilt"][0]
    assert pan_tilt["integration_status"] == "closed"
    assert pan_tilt["simulation_findings"] == 1
    assert len(pan_tilt["actuators"]) == 2
    assert pan_tilt["bench_coverage"]["measurement"] is True
    assert pan_tilt["bench_coverage"]["integrated_bench"] is True
    assert trace["coverage_summary"]["actuator_count"] == 2


def test_casefile_review_matrix_renders_closed_authority_stages():
    spec = _closed_spec()
    engineering = _engineering()
    mechanical = build_mechanical_authority(spec, engineering=engineering)
    robotics = build_robotics_actuation_packet(spec, engineering=engineering)
    mechatronics = build_mechatronics_authority(
        spec,
        engineering=engineering,
        mechanical_authority=mechanical,
        robotics_actuation=robotics,
    )

    casefile = build_casefile(
        spec=spec,
        engineering=engineering,
        mechanical_authority=mechanical,
        robotics_actuation=robotics,
        mechatronics_authority=mechatronics,
        artifacts={"mechatronics_authority": "/tmp/MECHATRONICS_AUTHORITY.json"},
        generated_at="2026-06-04T00:00:00+00:00",
        request_id="casefile-unit",
        ok=True,
    )
    project_log = build_project_log(casefile)
    review = render_hardware_review(casefile, project_log)

    matrix = casefile["bench_and_release"]["review_matrix"]
    assert [row for row in matrix if row["stage"] == "production_mechatronics_release"][0]["passed"] is True
    assert "- `production_mechatronics_release`: `pass` - closed" in review


def test_mechatronics_authority_requires_circuit_release_for_final_product_claim():
    authority = build_mechatronics_authority(_closed_spec(circuit_release={}), engineering=_engineering())

    assert authority["current_authority_level"] == "integrated_bench_authority"
    assert authority["production_authorized"] is False
    assert authority["next_action_id"] == "close_production_mechatronics_release"
    final_stage = [stage for stage in authority["stages"] if stage["stage_id"] == "production_mechatronics_release"][0]
    assert "Circuit/electrical subsystem release is not closed." in final_stage["blockers"]
    trace = authority["integration_trace"]
    assert trace["weakest_open_layer"] == "circuit_release_ready"
    assert "Layer not closed: circuit_release_ready." in trace["open_gaps"]


def test_mechatronics_authority_api_returns_packet():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.post(
        "/v1/mechatronics-authority",
        json={"spec": _closed_spec(), "engineering": _engineering()},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "hardware_splicer.mechatronics_authority.v1"
    assert data["production_authorized"] is True

from __future__ import annotations

import pytest

from hardware_splicer import build_robotics_actuation_packet
from hardware_splicer.api import create_app


def _spec(**extra):
    payload = {
        "project_name": "robotics_actuation_unit",
        "machine": {
            "machine_name": "RoboticsActuationUnit",
            "boards": [
                {
                    "board_id": "main_ctrl",
                    "requirements": {},
                    "capabilities": {"pwm_channels": 3, "stepper_channels": 1, "actuation_current_budget_a": 2.5},
                }
            ],
            "power_tree": [
                {"source": "servo_5v", "board_id": "main_ctrl", "rail": "SERVO_5V", "voltage_v": 5.0, "max_current_a": 2.0, "load_current_a": 1.0}
            ],
        },
        "mechanism": {
            "project_name": "robotics_actuation_mech",
            "pan_tilt": {"name": "pt", "pan_servo": "sg90", "tilt_servo": "sg90", "max_payload_n": 1.8, "payload_offset_mm": 35},
        },
        "use_3d_splicer": False,
    }
    payload.update(extra)
    return payload


def _engineering():
    return {
        "analysis": {
            "control_coupling": {
                "requirements": {"servo_channels": 2, "stepper_channels": 0, "estimated_actuation_current_a": 0.6},
                "issues": [],
            },
            "power": {"rails": [{"rail": "SERVO_5V", "status": "pass"}], "issues": []},
            "mechanism": {
                "ok": True,
                "simulation": [
                    {
                        "severity": "info",
                        "domain": "pan_tilt",
                        "model": "high",
                        "message": "Tilt torque safety factor is acceptable.",
                        "metrics": {"tilt_torque_safety_factor_x": 2.4},
                    }
                ],
            },
        }
    }


def _measurement_capture():
    return {
        "artifact_uris": ["session://robot/measurement-log"],
        "dimensions": [
            {"target": "base plate thickness", "value_mm": 6.0, "status": "verified"},
            {"target": "tilt bracket wall", "value_mm": 6.2, "status": "verified"},
        ],
        "clearances": [{"target": "servo horn clearance", "clearance_mm": 0.55, "status": "pass"}],
    }


def _bench_capture():
    return {
        "artifact_uris": ["session://robot/bench-video"],
        "motion_tests": [{"target": "pan tilt sweep", "status": "pass"}],
        "load_tests": [{"target": "payload hold", "status": "pass"}],
        "current_tests": [{"target": "servo rail peak current", "status": "pass"}],
    }


def _release():
    return {
        "scope_statement": "Release limited to SG90 pan-tilt motion under 1.8 N payload and current-limited 5 V servo rail.",
        "artifact_uris": ["session://robot/release-pack"],
        "acceptance_reviewed": True,
    }


def test_robotics_actuation_infers_servos_but_blocks_before_measurement():
    packet = build_robotics_actuation_packet(_spec(), engineering=_engineering())

    assert packet["current_authority_level"] == "electrical_drive_matched"
    assert packet["production_authorized"] is False
    assert packet["next_action_id"] == "close_mechanical_load_verified"
    assert packet["actuation_profile"]["actuator_count"] == 2
    assert packet["drive_requirements"]["channels"]["servo_pwm"] == 2
    assert packet["can"]["wire_controlled_actuators"] is True
    assert packet["can"]["claim_production_robotics_release"] is False


def test_robotics_actuation_authorizes_scoped_motion_release():
    packet = build_robotics_actuation_packet(
        _spec(
            mechanical_measurement_capture=_measurement_capture(),
            mechanical_bench_capture=_bench_capture(),
            robotics_release=_release(),
            robotics_actuation={"protections": ["servo_bulk_capacitance", "logic_power_isolation"]},
        ),
        engineering=_engineering(),
    )

    assert packet["current_authority_level"] == "production_robotics_release"
    assert packet["authority_score"] == 1.0
    assert packet["production_authorized"] is True
    assert packet["motion_bench_status"]["motion_verified"] is True
    assert packet["can"]["claim_production_robotics_release"] is True


def test_robotics_actuation_models_fan_and_spring_as_first_class_elements():
    packet = build_robotics_actuation_packet(
        _spec(
            mechanism={},
            robotics_actuation={
                "actuators": [
                    {"id": "cooling_fan", "type": "fan", "voltage_v": 12, "current_a": 0.18, "startup_current_a": 0.45},
                    {"id": "drive_motor", "type": "dc_motor", "voltage_v": 6, "run_current_a": 0.6, "stall_current_a": 2.1},
                ],
                "springs": [{"id": "return_spring", "k_n_per_mm": 0.8, "travel_mm": 12.0}],
                "protections": ["flyback_or_tvs", "current_limit", "separate_actuator_supply", "spring_preload_guard", "stored_energy_release_plan"],
            },
        ),
        engineering={
            "analysis": {
                "control_coupling": {"requirements": {}, "issues": []},
                "power": {"rails": [{"rail": "MOTOR_6V", "status": "pass"}], "issues": []},
                "mechanism": {"simulation": [{"severity": "info", "message": "fan bracket load acceptable"}]},
            }
        },
    )

    assert packet["actuation_profile"]["actuator_count"] == 2
    assert packet["actuation_profile"]["spring_count"] == 1
    assert packet["drive_requirements"]["rail_peak_currents_a"]["12V"] == 0.45
    assert packet["drive_requirements"]["spring_stored_energy_j"] > 0
    assert packet["current_authority_level"] == "electrical_drive_matched"


def test_robotics_actuation_api_returns_packet():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.post(
        "/v1/robotics-actuation",
        json={
            "spec": _spec(
                mechanical_measurement_capture=_measurement_capture(),
                mechanical_bench_capture=_bench_capture(),
                robotics_release=_release(),
                robotics_actuation={"protections": ["servo_bulk_capacitance", "logic_power_isolation"]},
            ),
            "engineering": _engineering(),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "hardware_splicer.robotics_actuation.v1"
    assert data["production_authorized"] is True

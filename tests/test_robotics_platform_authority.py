from __future__ import annotations

import pytest

from hardware_splicer import build_robotics_platform_authority
from hardware_splicer.api import create_app


def _release(scope: str):
    return {"scope_statement": scope, "artifact_uris": ["session://robotics-platform/release"], "acceptance_reviewed": True}


def _closed_rover_spec(**extra):
    payload = {
        "project_name": "robotics_platform_rover_unit",
        "use_3d_splicer": False,
        "machine": {
            "machine_name": "RoboticsPlatformRoverUnit",
            "design_intent": "indoor inspection rover prototype",
            "boards": [
                {
                    "board_id": "main_ctrl",
                    "requirements": {},
                    "capabilities": {
                        "pwm_channels": 4,
                        "stepper_channels": 0,
                        "actuation_current_budget_a": 4.0,
                    },
                }
            ],
        },
        "mechanism": {
            "project_name": "robotics_platform_rover_mech",
            "enclosure": {"name": "controller_case", "inner_w_mm": 95, "inner_d_mm": 70, "inner_h_mm": 30},
            "drive_base": {
                "name": "wheel_drive_base",
                "length_mm": 180,
                "width_mm": 120,
                "wheel_d_mm": 65,
                "motor_spacing_mm": 96,
            },
            "pan_tilt": {"name": "sensor_head", "pan_servo": "sg90", "tilt_servo": "sg90", "max_payload_n": 1.0},
        },
        "robotics_project": {
            "robot_class": "wheeled_rover",
            "mission": [
                "teleoperated indoor inspection with camera pan-tilt",
                "low-speed bench and floor traversal inside marked boundary",
            ],
            "operating_environment": {
                "domain": "indoor lab",
                "boundaries": ["flat floor", "marked test area"],
                "hazards": ["wheel pinch", "servo stall", "battery overcurrent"],
            },
            "constraints": {
                "runtime_min": 15,
                "max_speed_mps": 0.55,
                "payload_kg": 0.2,
                "mass_kg": 1.2,
                "acceleration_mps2": 0.5,
                "mission_duty_cycle": 0.65,
            },
            "power": {
                "battery": {
                    "chemistry": "2S Li-ion/LiPo",
                    "nominal_voltage_v": 7.4,
                    "capacity_mah": 2200,
                    "usable_fraction": 0.8,
                }
            },
            "platform": {
                "type": "differential_drive_rover",
                "domains": ["locomotion", "positioning"],
                "degrees_of_freedom": 4,
                "mobility": {"type": "differential_drive", "wheel_count": 2, "caster_count": 1},
            },
        },
        "robotics_actuation": {
            "actuators": [
                {
                    "id": "left_drive_motor",
                    "type": "dc_motor",
                    "role": "left wheel drive",
                    "voltage_v": 6.0,
                    "run_current_a": 0.45,
                    "stall_current_a": 0.9,
                    "output_free_speed_rpm": 220,
                    "stall_torque_nm": 0.18,
                },
                {
                    "id": "right_drive_motor",
                    "type": "dc_motor",
                    "role": "right wheel drive",
                    "voltage_v": 6.0,
                    "run_current_a": 0.45,
                    "stall_current_a": 0.9,
                    "output_free_speed_rpm": 220,
                    "stall_torque_nm": 0.18,
                },
            ],
            "sensors": [
                {"id": "front_range", "type": "tof_range", "role": "obstacle awareness"},
                {"id": "battery_current", "type": "current_sensor", "role": "drive current monitoring"},
            ],
            "protections": [
                "flyback_or_tvs",
                "current_limit",
                "separate_actuator_supply",
                "servo_bulk_capacitance",
                "logic_power_isolation",
            ],
        },
        "control_stack": {
            "controllers": [{"id": "main_ctrl", "board_id": "main_ctrl", "firmware": "teleop_rover_control"}],
            "loops": [
                {"name": "drive_pwm", "rate_hz": 100, "status": "pass"},
                {"name": "pan_tilt_pwm", "rate_hz": 50, "status": "pass"},
            ],
            "sensors": [{"id": "front_range", "type": "tof_range"}, {"id": "battery_current", "type": "current_sensor"}],
            "comms": [{"type": "rc_link", "failsafe": "signal_loss_stop"}],
            "failsafes": ["e_stop", "watchdog", "signal_loss_stop", "current_limit"],
        },
        "safety_case": {
            "hazards": [
                {"id": "wheel_pinch", "mitigation": "low-speed marked boundary and wheel guard", "status": "mitigated"},
                {"id": "servo_stall", "mitigation": "current limit and sweep timeout", "status": "mitigated"},
            ],
            "mitigations": [
                "flyback_or_tvs",
                "separate_actuator_supply",
                "servo_bulk_capacitance",
                "logic_power_isolation",
                "guarded_wheels",
            ],
        },
        "mechanical_measurement_capture": {
            "artifact_uris": ["session://robotics-platform/measurements"],
            "dimensions": [
                {"target": "controller_case enclosure inner width", "value_mm": 95.0, "status": "verified"},
                {"target": "wheel_drive_base motor spacing", "value_mm": 96.0, "status": "verified"},
                {"target": "sensor_head base thickness", "value_mm": 6.0, "status": "verified"},
                {"target": "sensor_head bracket wall", "value_mm": 6.1, "status": "verified"},
            ],
            "clearances": [{"target": "servo clearance", "clearance_mm": 0.55, "status": "pass"}],
        },
        "mechanical_bench_capture": {
            "artifact_uris": ["session://robotics-platform/mech-bench"],
            "fit_checks": [{"target": "sensor_head fit", "status": "pass"}],
            "load_tests": [{"target": "sensor_head payload hold", "status": "pass"}],
            "motion_tests": [{"target": "sensor_head sweep", "status": "pass"}, {"target": "wheel_drive_base drive wheel clearance", "status": "pass"}],
        },
        "robotics_bench_capture": {
            "artifact_uris": ["session://robotics-platform/motion-bench"],
            "motion_tests": [{"target": "drive motor spin", "status": "pass"}, {"target": "pan tilt sweep", "status": "pass"}],
            "current_tests": [{"target": "drive current limit", "status": "pass"}],
        },
        "integrated_bench_capture": {
            "artifact_uris": ["session://robotics-platform/integrated-bench"],
            "electrical_tests": [{"target": "logic rail under motion", "status": "pass"}],
            "motion_tests": [{"target": "drive and pan tilt command response", "status": "pass"}],
            "packaging_tests": [{"target": "controller case cable clearance", "status": "pass"}],
        },
        "field_validation": {
            "artifact_uris": ["session://robotics-platform/field-run-video", "session://robotics-platform/telemetry-log"],
            "simulations": [{"target": "current and runtime budget", "status": "pass"}],
            "bench_tests": [{"target": "tethered first motion", "status": "pass"}],
            "field_tests": [{"target": "marked boundary floor traversal", "status": "pass"}],
        },
        "circuit_release": _release("Circuit release limited to low-voltage controller, motor PWM outputs, servo PWM, and current-limited actuator rail."),
        "mechanical_release": _release("Mechanical release limited to rover controller enclosure and SG90 sensor pan-tilt bracket."),
        "robotics_release": _release("Robotics release limited to low-speed current-limited rover drive and SG90 pan-tilt motion."),
        "mechatronics_release": _release("Hardware-Splicer release limited to integrated indoor inspection rover prototype."),
        "robotics_project_release": _release("Robotics project release limited to indoor teleoperated rover traversal in a marked flat-floor boundary."),
    }
    payload.update(extra)
    return payload


def _engineering():
    return {
        "compiled": {"machine": {"readiness_level": "ready"}},
        "analysis": {
            "power": {
                "rails": [{"rail": "ACT_6V", "status": "pass"}, {"rail": "SERVO_5V", "status": "pass"}],
                "source_currents_a": {"ACT_6V": 2.0, "SERVO_5V": 1.3},
                "issues": [],
            },
            "interconnects": {"links": [], "issues": []},
            "control_coupling": {
                "requirements": {
                    "servo_channels": 2,
                    "stepper_channels": 0,
                    "estimated_actuation_current_a": 2.6,
                },
                "issues": [],
            },
            "mechanism": {
                "ok": True,
                "bundle_file": "/tmp/robotics_platform_rover/mecha_splicer.bundle.json",
                "outputs": ["enclosure.scad", "robotics_platform/drive_base.scad", "pt_base.scad", "pt_bracket.scad", "pt_platform.scad"],
                "parts": [
                    {"file": "enclosure.scad", "kind": "enclosure"},
                    {"file": "robotics_platform/drive_base.scad", "kind": "drive_base"},
                    {"file": "pt_base.scad", "kind": "pan_tilt"},
                    {"file": "pt_bracket.scad", "kind": "pan_tilt"},
                    {"file": "pt_platform.scad", "kind": "pan_tilt"},
                ],
                "dfm": [{"severity": "info", "message": "printable"}],
                "simulation": [
                    {"severity": "info", "domain": "pan_tilt", "message": "payload torque margin acceptable"},
                    {"severity": "info", "domain": "drive_base", "message": "drive base wheel clearance and motor spacing acceptable"},
                ],
                "safety": [{"severity": "info", "message": "keep low-speed current limit during first motion"}],
            },
        },
    }


def test_robotics_platform_authority_blocks_without_project_intent():
    packet = build_robotics_platform_authority(
        _closed_rover_spec(robotics_project={}, field_validation={}, robotics_project_release={}),
        engineering=_engineering(),
    )

    assert packet["current_authority_level"] == "no_robotics_platform_authority"
    assert packet["next_action_id"] == "close_robotics_project_intake"
    assert packet["production_authorized"] is False


def test_robotics_platform_authority_authorizes_general_rover_project():
    packet = build_robotics_platform_authority(_closed_rover_spec(), engineering=_engineering())

    assert packet["schema_version"] == "hardware_splicer.robotics_platform_authority.v1"
    assert packet["current_authority_level"] == "production_robotics_project_release"
    assert packet["authority_score"] == 1.0
    assert packet["production_authorized"] is True
    assert packet["project_profile"]["robot_class"] == "wheeled_rover"
    assert {"locomotion", "positioning"} <= set(packet["platform_topology"]["domains"])
    assert packet["power_drive_budget"]["estimated_peak_current_a"] > 0
    assert packet["control_safety_architecture"]["controller_count"] == 1
    assert packet["simulation_status"]["simulation_ready"] is True
    assert packet["validation_status"]["simulation_ready"] is True
    assert packet["validation_status"]["field_ready"] is True
    assert packet["can"]["claim_production_robotics_project_release"] is True


def test_robotics_platform_authority_blocks_physically_impossible_speed():
    spec = _closed_rover_spec()
    spec["robotics_project"]["constraints"]["max_speed_mps"] = 2.5

    packet = build_robotics_platform_authority(spec, engineering=_engineering())

    assert packet["current_authority_level"] == "control_safety_architecture"
    assert packet["production_authorized"] is False
    assert packet["simulation_status"]["simulation_ready"] is False
    assert any("Available wheel speed" in row["message"] for row in packet["simulation_status"]["blocking_findings"])


def test_robotics_platform_authority_api_returns_packet():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.post(
        "/v1/robotics-platform-authority",
        json={"spec": _closed_rover_spec(), "engineering": _engineering()},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "hardware_splicer.robotics_platform_authority.v1"
    assert data["production_authorized"] is True

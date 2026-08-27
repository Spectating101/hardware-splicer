from __future__ import annotations

from hardware_splicer.engineering_analysis import AnalysisStatus, analyze_engineering_candidate
from hardware_splicer.robot_topology import build_robot_topology


def _finding(report, finding_id: str):
    return next(row for row in report.findings if row.finding_id == finding_id)


def test_runtime_and_current_margin_use_declared_inputs() -> None:
    intake = {
        "goal": "Design a low-speed differential drive rover.",
        "available_parts": [{"name": "drive motor", "type": "dc_motor", "quantity": 2}],
        "constraints": {
            "battery_energy_wh": 100,
            "continuous_power_w": 40,
            "battery_usable_fraction": 0.8,
            "runtime_min": 90,
            "supply_current_limit_a": 10,
            "peak_current_a": 8,
        },
    }
    report = analyze_engineering_candidate(intake, topology=build_robot_topology(intake))

    runtime = _finding(report, "analysis-runtime")
    current = _finding(report, "analysis-current-margin")
    assert runtime.status == AnalysisStatus.PASS
    assert runtime.outputs["estimated_runtime_min"] == 120.0
    assert current.status == AnalysisStatus.PASS
    assert current.outputs["current_margin_a"] == 2.0


def test_stability_and_current_failures_are_blocking() -> None:
    intake = {
        "goal": "Revise a rover after tipping and brownout.",
        "mode": "evolve",
        "available_parts": [{"name": "drive motor", "type": "dc_motor", "quantity": 2}],
        "constraints": {
            "support_width_mm": 200,
            "combined_cg_height_mm": 400,
            "static_tilt_margin_deg": 20,
            "supply_current_limit_a": 5,
            "peak_current_a": 12,
        },
        "field_failure": "The rover tipped and the logic rail browned out.",
    }
    report = analyze_engineering_candidate(intake, topology=build_robot_topology(intake))

    stability = _finding(report, "analysis-static-stability")
    current = _finding(report, "analysis-current-margin")
    assert stability.status == AnalysisStatus.FAIL
    assert stability.blocking is True
    assert stability.outputs["idealized_static_tip_angle_deg"] < 20
    assert current.status == AnalysisStatus.FAIL
    assert current.blocking is True
    assert len(report.blocking_findings) >= 2
    assert report.metadata["release_authorized"] is False


def test_missing_inputs_remain_visible_instead_of_being_guessed() -> None:
    intake = {
        "goal": "Design an inspection rover with ninety minute runtime.",
        "available_parts": [{"name": "unknown battery", "type": "power_source"}],
        "constraints": {"runtime_min": 90},
    }
    report = analyze_engineering_candidate(intake, topology=build_robot_topology(intake))

    runtime = _finding(report, "analysis-runtime")
    torque = _finding(report, "analysis-actuator-torque")
    assert runtime.status == AnalysisStatus.UNKNOWN
    assert runtime.blocking is True
    assert "battery_energy_wh or battery_voltage_v + battery_capacity_ah" in runtime.missing_inputs
    assert torque.status == AnalysisStatus.UNKNOWN
    assert report.summary["counts_by_status"]["unknown"] > 0


def test_static_torque_check_is_explicitly_idealized() -> None:
    intake = {
        "goal": "Build a robotic arm.",
        "available_parts": [{"name": "joint servo", "type": "smart_servo", "quantity": 5}],
        "constraints": {
            "degrees_of_freedom": 5,
            "payload_mass_kg": 0.5,
            "payload_lever_arm_m": 0.2,
            "actuator_continuous_torque_nm": 2.0,
            "load_sharing_actuator_count": 1,
        },
    }
    report = analyze_engineering_candidate(intake, topology=build_robot_topology(intake))

    torque = _finding(report, "analysis-actuator-torque")
    assert torque.status == AnalysisStatus.PASS
    assert torque.outputs["required_static_torque_nm"] > 0
    assert any("Static gravity load only" in row for row in torque.assumptions)

from __future__ import annotations

import pytest

from hardware_splicer.api import create_app
from hardware_splicer.circuit_synthesis import plan_motor_driver
from hardware_splicer.sdk import plan_motor_driver_circuit, sdk_info


def _intent(**extra):
    payload = {
        "goal": "drive a small DC pump from a microcontroller GPIO",
        "supply_rails": [{"name": "+5V", "voltage_v": 5.0, "max_current_a": 1.0}],
        "load_requirements": [{"name": "pump", "type": "dc_motor", "voltage_v": 5.0, "current_a": 0.45}],
        "signal_requirements": [{"name": "control", "type": "pwm", "voltage_v": 3.3}],
        "allowed_modules": ["usb-power-5v", "esp32-devkit", "mosfet-irlz44n", "water_pump_5v"],
        "required_evidence": ["flyback_or_driver_protection"],
    }
    payload.update(extra)
    return payload


def _constraint(candidate, constraint_id: str):
    rows = [row for row in candidate["constraints"] if row["constraint_id"] == constraint_id]
    assert rows, candidate["constraints"]
    return rows[0]


def test_motor_driver_planner_returns_ready_for_review_low_side_switch() -> None:
    candidate = plan_motor_driver(_intent()).to_dict()

    assert candidate["result"] == "ready_for_review"
    assert candidate["selected_modules"] == ["mosfet-irlz44n"]
    assert candidate["generated_topology"][0]["operator_type"] == "low_side_switch"
    assert _constraint(candidate, "supply_current_margin")["status"] == "pass"
    assert _constraint(candidate, "inductive_load_protection")["status"] == "pass"
    assert "psu_current_limit_ramp" in [gate["gate_id"] for gate in candidate["verification_gates"]]
    assert candidate["recommended_build_path"]["can_compile_with_existing_auto_wire"] is True


def test_motor_driver_planner_blocks_missing_inductive_protection() -> None:
    candidate = plan_motor_driver(_intent(required_evidence=[])).to_dict()

    assert candidate["result"] == "blocked"
    assert "flyback_or_driver_protection" in candidate["missing_evidence"]
    assert _constraint(candidate, "inductive_load_protection")["status"] == "blocked"


def test_motor_driver_planner_blocks_missing_load_current() -> None:
    candidate = plan_motor_driver(
        _intent(load_requirements=[{"name": "pump", "type": "dc_motor", "voltage_v": 5.0}])
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert "load_current_estimate" in candidate["missing_evidence"]


def test_motor_driver_planner_blocks_undersized_supply() -> None:
    candidate = plan_motor_driver(
        _intent(supply_rails=[{"name": "+5V", "voltage_v": 5.0, "max_current_a": 0.2}])
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert "supply_current_margin" in candidate["missing_evidence"]
    assert _constraint(candidate, "supply_current_margin")["status"] == "blocked"


def test_motor_driver_planner_blocks_3v3_signal_into_5v_driver_without_level_shift() -> None:
    candidate = plan_motor_driver(
        _intent(
            allowed_modules=["usb-power-5v", "esp32-devkit", "l298n", "water_pump_5v"],
            required_evidence=[],
        )
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert candidate["selected_modules"] == ["l298n"]
    assert "level_shifter_or_compatible_driver" in candidate["missing_evidence"]
    assert _constraint(candidate, "l298n_logic_level")["status"] == "blocked"


def test_motor_driver_planner_allows_5v_driver_with_level_shifter() -> None:
    candidate = plan_motor_driver(
        _intent(
            allowed_modules=["usb-power-5v", "esp32-devkit", "l298n", "level-shifter-4ch", "water_pump_5v"],
            required_evidence=[],
        )
    ).to_dict()

    assert candidate["result"] == "ready_for_review"
    assert _constraint(candidate, "l298n_logic_level_shifted")["status"] == "pass"
    assert candidate["generated_topology"][0]["operator_type"] == "motor_driver"


def test_motor_driver_planner_sdk_and_api_surface() -> None:
    sdk_candidate = plan_motor_driver_circuit(_intent())
    assert sdk_candidate["result"] == "ready_for_review"
    assert "hs_plan_motor_driver_circuit" in sdk_info()["agent_handoff"]["primary_tools"]

    pytest.importorskip("fastapi")

    routes = {getattr(route, "path", "") for route in create_app().routes}

    assert "/v1/circuit-synthesis/motor-driver" in routes

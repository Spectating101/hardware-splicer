from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer.api import create_app
from hardware_splicer.circuit_synthesis import (
    plan_analog_conditioning,
    plan_battery_power,
    plan_circuit,
    plan_h_bridge,
    plan_level_shift,
    plan_power_rail,
    plan_relay_switch,
    plan_sensor_interface,
)
from hardware_splicer.sdk import (
    plan_analog_conditioning_circuit,
    plan_battery_power_circuit,
    plan_h_bridge_circuit,
    plan_level_shift_circuit,
    plan_power_rail_circuit,
    plan_sensor_interface_circuit,
    sdk_info,
    synthesize_circuit,
)


def _constraint(candidate, constraint_id: str):
    rows = [row for row in candidate["constraints"] if row["constraint_id"] == constraint_id]
    assert rows, candidate["constraints"]
    return rows[0]


def test_power_rail_planner_selects_buck_and_compiles(tmp_path: Path) -> None:
    intent = {
        "goal": "make a 12V to 5V regulated rail for an ESP32 sensor node",
        "supply_rails": [{"name": "adapter input", "role": "input", "voltage_v": 12.0}],
        "voltage_constraints": [{"name": "logic rail", "target_voltage_v": 5.0, "load_current_a": 0.45}],
        "allowed_modules": ["dc-barrel-12v", "buck-mp1584", "esp32-devkit"],
    }
    candidate = plan_power_rail(intent).to_dict()

    assert candidate["result"] == "ready_for_review"
    assert candidate["selected_modules"] == ["dc-barrel-12v", "buck-mp1584"]
    assert candidate["generated_topology"][0]["operator_type"] == "buck_regulator"
    assert _constraint(candidate, "buck-mp1584_current_margin")["status"] == "pass"

    compiled = synthesize_circuit(intent, out_dir=tmp_path, export_gerber=False)
    assert compiled["ok"] is True
    assert compiled["candidate"]["candidate_id"] == "power_rail_candidate"
    assert compiled["compose_result"]["compile_result"]["ok"] is True


def test_power_rail_planner_blocks_hot_ldo() -> None:
    candidate = plan_power_rail(
        {
            "goal": "make a 12V to 3.3V rail with an LDO",
            "supply_rails": [{"name": "input", "role": "input", "voltage_v": 12.0}],
            "voltage_constraints": [{"target_voltage_v": 3.3, "load_current_a": 0.4}],
            "allowed_modules": ["dc-barrel-12v", "ldo-ams1117-3v3"],
        }
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert "ldo_thermal_margin" in candidate["missing_evidence"]
    assert _constraint(candidate, "ldo-ams1117-3v3_thermal_dissipation")["status"] == "blocked"


def test_level_shift_planner_routes_3v3_to_5v_bus() -> None:
    intent = {
        "goal": "level shift an ESP32 to a 5V ultrasonic sensor",
        "signal_requirements": [{"type": "digital", "controller_voltage_v": 3.3, "peripheral_voltage_v": 5.0, "channels": 2}],
        "allowed_modules": ["usb-power-5v", "esp32-devkit", "hc-sr04", "level-shifter-4ch"],
    }
    candidate = plan_level_shift(intent).to_dict()

    assert candidate["result"] == "ready_for_review"
    assert candidate["generated_topology"][0]["operator_type"] == "level_shifter"
    assert _constraint(candidate, "level_shifter_channel_count")["status"] == "pass"
    assert plan_level_shift_circuit(intent)["result"] == "ready_for_review"


def test_level_shift_planner_blocks_missing_shifter() -> None:
    candidate = plan_level_shift(
        {
            "goal": "connect ESP32 3.3V logic to a 5V peripheral",
            "signal_requirements": [{"type": "i2c", "controller_voltage_v": 3.3, "peripheral_voltage_v": 5.0}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "hc-sr04"],
        }
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert "level_shifter_module" in candidate["missing_evidence"]


def test_sensor_interface_planner_handles_i2c_sensor_and_compiles(tmp_path: Path) -> None:
    intent = {
        "goal": "wire an ESP32 to a BME280 environmental sensor",
        "allowed_modules": ["usb-power-5v", "esp32-devkit", "bme280"],
        "required_evidence": ["i2c_pullups"],
    }
    candidate = plan_sensor_interface(intent).to_dict()

    assert candidate["result"] == "ready_for_review"
    assert candidate["metadata"]["bus"] == "i2c"
    assert candidate["generated_topology"][0]["operator_type"] == "sensor_interface"
    assert any(row["operator_type"] == "pull_up" for row in candidate["generated_topology"])
    assert plan_sensor_interface_circuit(intent)["result"] == "ready_for_review"

    compiled = synthesize_circuit(intent, out_dir=tmp_path, export_gerber=False)
    assert compiled["ok"] is True
    assert compiled["candidate"]["candidate_id"] == "sensor_interface_candidate"
    assert compiled["compose_result"]["compile_result"]["ok"] is True


def test_sensor_interface_blocks_5v_echo_without_level_shift() -> None:
    candidate = plan_sensor_interface(
        {
            "goal": "wire an ESP32 to an HC-SR04 ultrasonic sensor",
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "hc-sr04"],
        }
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert "sensor_logic_level_shift" in candidate["missing_evidence"]


def test_h_bridge_planner_selects_reversible_driver_and_compiles(tmp_path: Path) -> None:
    intent = {
        "goal": "make a reversible 12V DC geared motor wheel drive with direction control",
        "supply_rails": [{"name": "motor supply", "voltage_v": 12.0}],
        "load_requirements": [{"type": "dc_motor", "voltage_v": 12.0, "run_current_a": 0.4, "stall_current_a": 0.7}],
        "signal_requirements": [{"type": "pwm_direction", "control_voltage_v": 5.0}],
        "allowed_modules": ["dc-barrel-12v", "arduino-nano", "l298n", "dc_geared_motor_12v"],
    }
    candidate = plan_h_bridge(intent).to_dict()

    assert candidate["result"] == "ready_for_review"
    assert candidate["generated_topology"][0]["operator_type"] == "h_bridge"
    assert _constraint(candidate, "h_bridge_current_margin")["status"] == "pass"
    assert plan_h_bridge_circuit(intent)["metadata"]["driver"] == "l298n"

    compiled = synthesize_circuit(intent, out_dir=tmp_path, export_gerber=False)
    assert compiled["ok"] is True
    assert compiled["candidate"]["candidate_id"] == "h_bridge_motor_candidate"
    assert compiled["compose_result"]["compile_result"]["ok"] is True


def test_relay_switch_planner_blocks_mains_and_handles_low_voltage() -> None:
    low_voltage = plan_relay_switch(
        {
            "goal": "switch a 12V lamp load with a relay from an ESP32",
            "load_requirements": [{"type": "lamp", "load_voltage_v": 12.0, "load_current_a": 0.25}],
            "signal_requirements": [{"type": "gpio", "control_voltage_v": 3.3}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "relay-1ch-5v"],
        }
    ).to_dict()
    assert low_voltage["result"] == "ready_for_review"
    assert low_voltage["generated_topology"][0]["operator_type"] == "relay_driver"

    mains = plan_relay_switch(
        {
            "goal": "switch a 120VAC mains lamp with a relay",
            "load_requirements": [{"type": "lamp", "load_voltage_v": 120.0, "load_current_a": 0.5}],
            "signal_requirements": [{"type": "gpio", "control_voltage_v": 3.3}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "relay-1ch-5v"],
        }
    ).to_dict()
    assert mains["result"] == "blocked"
    assert "mains_or_hazardous_load_review" in mains["missing_evidence"]


def test_analog_conditioning_generates_divider_and_blocks_missing_range() -> None:
    intent = {
        "goal": "condition a noisy 5V analog sensor output into an ESP32 ADC with an RC filter",
        "signal_requirements": [{"type": "analog", "sensor_output_max_v": 5.0, "adc_max_v": 3.3, "noise_filter": True}],
        "frequency_constraints": [{"sample_rate_hz": 50}],
        "allowed_modules": ["usb-power-5v", "esp32-devkit", "soil_moisture"],
    }
    candidate = plan_analog_conditioning(intent).to_dict()

    assert candidate["result"] == "ready_for_review"
    assert any(row["operator_type"] == "voltage_divider" for row in candidate["generated_topology"])
    assert any(row["operator_type"] == "rc_filter" for row in candidate["generated_topology"])
    assert _constraint(candidate, "adc_voltage_divider_ratio")["status"] == "pass"
    assert plan_analog_conditioning_circuit(intent)["result"] == "ready_for_review"

    blocked = plan_analog_conditioning(
        {
            "goal": "wire an analog sensor to an ADC",
            "allowed_modules": ["esp32-devkit", "soil_moisture"],
        }
    ).to_dict()
    assert blocked["result"] == "blocked"
    assert "analog_source_max_voltage" in blocked["missing_evidence"]


def test_battery_power_requires_protection_and_plans_boost() -> None:
    protected = plan_battery_power(
        {
            "goal": "make a portable 5V rail from a protected LiPo using TP4056 and boost",
            "supply_rails": [{"type": "lipo", "cell_capacity_mah": 1200}],
            "voltage_constraints": [{"target_output_v": 5.0, "load_current_a": 0.35}],
            "allowed_modules": ["usb-power-5v", "tp4056", "boost-mt3608"],
            "required_evidence": ["protected_cell"],
        }
    ).to_dict()
    assert protected["result"] == "ready_for_review"
    assert any(row["operator_type"] == "battery_charger" for row in protected["generated_topology"])
    assert any(row["operator_type"] == "boost_regulator" for row in protected["generated_topology"])
    assert plan_battery_power_circuit(
        {
            "goal": "portable 5V protected LiPo rail",
            "voltage_constraints": [{"target_output_v": 5.0, "load_current_a": 0.35}],
            "allowed_modules": ["usb-power-5v", "tp4056", "boost-mt3608"],
            "required_evidence": ["protected_cell"],
        }
    )["result"] == "ready_for_review"

    unsafe = plan_battery_power(
        {
            "goal": "make a portable 5V LiPo rail",
            "voltage_constraints": [{"target_output_v": 5.0, "load_current_a": 0.35}],
            "allowed_modules": ["usb-power-5v", "tp4056", "boost-mt3608"],
        }
    ).to_dict()
    assert unsafe["result"] == "blocked"
    assert "battery_protection_evidence" in unsafe["missing_evidence"]


def test_arbitrary_dispatch_routes_new_planners() -> None:
    assert plan_circuit(
        {
            "goal": "portable protected LiPo battery 5V rail with TP4056",
            "voltage_constraints": [{"target_output_v": 5.0, "load_current_a": 0.3}],
            "allowed_modules": ["usb-power-5v", "tp4056", "boost-mt3608"],
            "required_evidence": ["protected_cell"],
        }
    ).metadata["dispatch"]["selected_planner"] == "battery_power"
    assert plan_circuit(
        {
            "goal": "12V to 5V buck rail",
            "supply_rails": [{"role": "input", "voltage_v": 12.0}],
            "voltage_constraints": [{"target_voltage_v": 5.0, "load_current_a": 0.3}],
            "allowed_modules": ["dc-barrel-12v", "buck-lm2596"],
        }
    ).metadata["dispatch"]["selected_planner"] == "power_rail"
    assert plan_circuit(
        {
            "goal": "level shift 3.3V to 5V I2C",
            "signal_requirements": [{"type": "i2c", "controller_voltage_v": 3.3, "peripheral_voltage_v": 5.0}],
            "allowed_modules": ["esp32-devkit", "level-shifter-4ch", "hc-sr04"],
        }
    ).metadata["dispatch"]["selected_planner"] == "level_shift"
    assert plan_circuit(
        {
            "goal": "ESP32 sensor interface for BME280",
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "bme280"],
            "required_evidence": ["i2c_pullups"],
        }
    ).metadata["dispatch"]["selected_planner"] == "sensor_interface"
    assert plan_circuit(
        {
            "goal": "reversible H-bridge drive for a DC motor",
            "supply_rails": [{"voltage_v": 12.0}],
            "load_requirements": [{"type": "dc_motor", "voltage_v": 12.0, "run_current_a": 0.4}],
            "signal_requirements": [{"control_voltage_v": 5.0}],
            "allowed_modules": ["dc-barrel-12v", "arduino-nano", "l298n", "dc_geared_motor_12v"],
        }
    ).metadata["dispatch"]["selected_planner"] == "h_bridge"
    assert plan_circuit(
        {
            "goal": "relay switch a 12V lamp",
            "load_requirements": [{"type": "lamp", "load_voltage_v": 12.0, "load_current_a": 0.2}],
            "signal_requirements": [{"control_voltage_v": 3.3}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "relay-1ch-5v"],
        }
    ).metadata["dispatch"]["selected_planner"] == "relay_switch"
    assert plan_circuit(
        {
            "goal": "analog ADC voltage divider for a 5V sensor output",
            "signal_requirements": [{"type": "analog", "sensor_output_max_v": 5.0, "adc_max_v": 3.3}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "soil_moisture"],
        }
    ).metadata["dispatch"]["selected_planner"] == "analog_conditioning"
    assert plan_circuit(
        {
            "goal": "5V to 3.3V regulator for a sensor board",
            "supply_rails": [{"role": "input", "voltage_v": 5.0}],
            "voltage_constraints": [{"target_voltage_v": 3.3, "load_current_a": 0.1}],
            "allowed_modules": ["usb-power-5v", "ldo-ams1117-3v3"],
        }
    ).metadata["dispatch"]["selected_planner"] == "power_rail"


def test_new_planners_are_exposed_to_sdk_and_api() -> None:
    tools = sdk_info()["agent_handoff"]["primary_tools"]
    assert "hs_plan_power_rail_circuit" in tools
    assert "hs_plan_level_shift_circuit" in tools
    assert "hs_plan_sensor_interface_circuit" in tools
    assert "hs_plan_h_bridge_circuit" in tools
    assert "hs_plan_relay_switch_circuit" in tools
    assert "hs_plan_analog_conditioning_circuit" in tools
    assert "hs_plan_battery_power_circuit" in tools
    assert plan_power_rail_circuit(
        {
            "goal": "12V to 5V buck rail",
            "supply_rails": [{"role": "input", "voltage_v": 12.0}],
            "voltage_constraints": [{"target_voltage_v": 5.0, "load_current_a": 0.3}],
            "allowed_modules": ["dc-barrel-12v", "buck-lm2596"],
        }
    )["result"] == "ready_for_review"

    pytest.importorskip("fastapi")
    routes = {getattr(route, "path", "") for route in create_app().routes}
    assert "/v1/circuit-synthesis/power-rail" in routes
    assert "/v1/circuit-synthesis/level-shift" in routes
    assert "/v1/circuit-synthesis/sensor-interface" in routes
    assert "/v1/circuit-synthesis/h-bridge" in routes
    assert "/v1/circuit-synthesis/relay-switch" in routes
    assert "/v1/circuit-synthesis/analog-conditioning" in routes
    assert "/v1/circuit-synthesis/battery-power" in routes

from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.circuit_synthesis import plan_h_bridge
from hardware_splicer.circuit_synthesis.operator_lowering import apply_operator_lowering
from hardware_splicer.pcb.safety_rules import analyze_build
from hardware_splicer.sdk import synthesize_circuit


def _h_bridge_intent():
    return {
        "goal": "make a reversible 12V DC geared motor wheel drive with direction control",
        "supply_rails": [{"name": "motor supply", "voltage_v": 12.0}],
        "load_requirements": [{"type": "dc_motor", "voltage_v": 12.0, "run_current_a": 0.4, "stall_current_a": 0.7}],
        "signal_requirements": [{"type": "pwm_direction", "control_voltage_v": 5.0}],
        "allowed_modules": ["dc-barrel-12v", "arduino-nano", "l298n", "dc_geared_motor_12v"],
    }


def test_operator_lowering_marks_h_bridge_floating_motor_terminals() -> None:
    candidate = plan_h_bridge(_h_bridge_intent())
    composed = compose_build_graph_from_module_ids(["dc-barrel-12v", "arduino-nano", "l298n", "dc_geared_motor_12v"])

    raw_errors = [row for row in analyze_build(composed["graph"]) if row.get("level") == "error"]
    assert any("Wire connects GND" in str(row.get("message")) for row in raw_errors)

    lowered = apply_operator_lowering(candidate, composed["graph"])
    lowered_errors = [row for row in analyze_build(lowered.graph) if row.get("level") == "error"]
    assert lowered_errors == []
    assert lowered.graph["terminal_semantics"]["n4:GND"]["role"] == "floating_motor_terminal"
    assert lowered.graph["terminal_semantics"]["n3:OUT2"]["role"] == "floating_motor_terminal"
    assert "n3:5V" not in lowered.graph["terminal_semantics"]


def test_h_bridge_compile_uses_operator_lowering_with_actual_motor_load(tmp_path) -> None:
    result = synthesize_circuit(_h_bridge_intent(), out_dir=tmp_path, export_gerber=False)

    assert result["ok"] is True
    assert result["module_ids"] == ["dc-barrel-12v", "arduino-nano", "l298n", "dc_geared_motor_12v"]
    assert result["compose_result"]["compile_result"]["ok"] is True
    assert result["compose_result"]["design_quality"]["electrical_issues"] == []
    assert result["topology_lowering"]["operator_count"] == 1
    assert len(result["topology_lowering"]["actions"]) == 4


def test_analog_conditioning_lowering_emits_physical_divider_and_filter_parts(tmp_path) -> None:
    result = synthesize_circuit(
        {
            "goal": "condition a noisy 5V analog sensor output into an ESP32 ADC with an RC filter",
            "signal_requirements": [
                {"type": "analog", "sensor_output_max_v": 5.0, "adc_max_v": 3.3, "noise_filter": True}
            ],
            "frequency_constraints": [{"sample_rate_hz": 50}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "soil_moisture"],
        },
        out_dir=tmp_path,
        export_gerber=False,
    )

    assert result["ok"] is True
    support = {row["id"]: row for row in result["support_components"]}
    assert support["ADC_PROTECTION_DIVIDER_Rtop"]["value"]["resistance_ohm"] == 5200
    assert support["ADC_PROTECTION_DIVIDER_Rbottom"]["value"]["resistance_ohm"] == 10000
    assert support["ADC_RC_NOISE_FILTER_R"]["role"] == "rc_series_resistor"
    assert support["ADC_RC_NOISE_FILTER_C"]["value"]["capacitance_nf"] > 0
    assert support["ADC_PROTECTION_DIVIDER_Rtop"]["placement"] == "physical_synthetic_footprint"
    assert support["ADC_RC_NOISE_FILTER_C"]["physical_ref"] == "C1"
    assert support["ADC_INPUT_CLAMP_REVIEW_D"]["placement"] == "virtual_support_component"
    assert any(row["role"] == "scaled_analog_signal" for row in result["topology_nets"])
    assert any(row["role"] == "filtered_analog_signal" for row in result["topology_nets"])
    assert result["compose_result"]["netlist"]["metadata"]["support_components"] == result["support_components"]
    components = {row["ref"]: row for row in result["compose_result"]["netlist"]["components"]}
    assert components["R1"]["module_id"] == "resistor-5_2k"
    assert components["R2"]["value"] == "10k"
    assert components["R3"]["footprint"] == "Resistor_SMD:R_0603_1608Metric"
    assert components["C1"]["module_id"].startswith("capacitor-")
    assert result["compose_result"]["netlist"]["metadata"]["physical_support_lowering"]["node_count"] == 4
    bom_path = Path(result["compose_result"]["artifacts"]["build_graph"]).with_name("BOM.json")
    bom = json.loads(bom_path.read_text(encoding="utf-8"))
    bom_lines = {row["ref"]: row for row in bom["lines"]}
    assert bom_lines["R1"]["source"] == "synthetic_support"
    assert bom_lines["R1"]["description"] == "5.2k"
    assert bom_lines["C1"]["footprint"] == "Capacitor_SMD:C_0603_1608Metric"


def test_i2c_pullup_lowering_emits_two_physical_bus_resistors(tmp_path) -> None:
    result = synthesize_circuit(
        {
            "goal": "wire an ESP32 to a BME280 environmental sensor",
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "bme280"],
            "required_evidence": ["i2c_pullups"],
        },
        out_dir=tmp_path,
        export_gerber=False,
    )

    assert result["ok"] is True
    pullups = [row for row in result["support_components"] if row["role"] == "pull_up_resistor"]
    assert len(pullups) == 2
    assert {tuple(row["connects"]) for row in pullups} == {("SDA", "logic_rail"), ("SCL", "logic_rail")}
    assert all(row["value"]["resistance_ohm"] == 4700 for row in pullups)
    assert all(row["placement"] == "physical_synthetic_footprint" for row in pullups)
    assert any(row["role"] == "defined_bus_idle_level" for row in result["topology_nets"])
    assert result["compose_result"]["design_quality"]["electrical_issues"] == []
    assert result["compose_result"]["netlist"]["metadata"]["physical_support_lowering"]["node_count"] == 2


def test_battery_power_lowering_emits_protected_cell_evidence_item(tmp_path) -> None:
    result = synthesize_circuit(
        {
            "goal": "make a portable 5V rail from a protected LiPo using TP4056 and boost",
            "supply_rails": [{"type": "lipo", "cell_capacity_mah": 1200}],
            "voltage_constraints": [{"target_output_v": 5.0, "load_current_a": 0.35}],
            "allowed_modules": ["usb-power-5v", "tp4056", "boost-mt3608"],
            "required_evidence": ["protected_cell"],
        },
        out_dir=tmp_path,
        export_gerber=False,
    )

    assert result["ok"] is True
    assert any(row["role"] == "battery_safety_evidence_item" for row in result["support_components"])
    assert {row["role"] for row in result["topology_nets"]} == {"battery_charger", "boost_regulator"}
    assert result["compose_result"]["netlist"]["metadata"]["topology_nets"] == result["topology_nets"]

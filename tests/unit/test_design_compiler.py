import pytest

from src.engines.design_compiler import compile_design
from src.engines.power_tree_validator import validate_pcb_power_tree


def test_compile_basic_esp32_design_is_safe_under_defaults():
    design = {
        "microcontroller": "esp32",
        "components": ["bme280", "oled_ssd1306"],
        "power_source": {"type": "usb", "voltage_v": 5.0, "current_limit_a": 0.5},
        "scenario": "max",
        # default trace models should be low-drop
    }

    compiled = compile_design(design)
    results, issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)

    assert results["converged"] is True
    assert not any(i.issue in {"Undervoltage", "LDO dropout", "Source current exceeded"} for i in issues)


def test_compile_servo_triggers_usb_overcurrent_and_logic_warning():
    design = {
        "microcontroller": "esp32",
        "components": ["servo_sg90"],
        "power_source": {"type": "usb", "voltage_v": 5.0, "current_limit_a": 0.5},
        "scenario": "max",
    }

    compiled = compile_design(design)
    results, issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)

    assert results["converged"] is True
    assert any(i.issue == "Source current exceeded" for i in issues)

def test_compile_direct_3v3_supply_skips_ldo():
    design = {
        "microcontroller": "esp32",
        "components": ["bme280"],
        "power_source": {"type": "external", "voltage_v": 3.3, "current_limit_a": 1.0},
        "scenario": "max",
    }

    compiled = compile_design(design)
    assert compiled.netlist.ldos == []
    results, issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)
    assert results["converged"] is True
    assert not any(i.issue == "LDO dropout" for i in issues)

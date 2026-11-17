"""A ground wire may strap an input that the module data documents as an active-low enable."""

from __future__ import annotations

from hardware_splicer.pcb.safety_rules import analyze_build


def _graph(a_module: str, a_pin: str, b_module: str, b_pin: str) -> dict:
    return {
        "nodes": [
            {"id": "n1", "moduleId": a_module},
            {"id": "n2", "moduleId": b_module},
        ],
        "wires": [
            {"id": "w1", "from": {"nodeId": "n1", "pinId": a_pin}, "to": {"nodeId": "n2", "pinId": b_pin}}
        ],
    }


def _gnd_errors(graph: dict) -> list:
    return [
        row for row in analyze_build(graph)
        if row.get("level") == "error" and "non-GND" in str(row.get("message"))
    ]


def test_active_low_enable_input_may_be_strapped_to_ground() -> None:
    # A4988 EN is documented "Active-low enable": GND holds the driver enabled.
    assert _gnd_errors(_graph("arduino-nano", "GND", "a4988-stepper", "EN")) == []
    assert _gnd_errors(_graph("a4988-stepper", "EN", "arduino-nano", "GND")) == []


def test_ground_to_an_ordinary_input_is_still_an_error() -> None:
    assert _gnd_errors(_graph("arduino-nano", "GND", "a4988-stepper", "STEP"))


def test_ground_to_a_power_output_is_still_an_error() -> None:
    assert _gnd_errors(_graph("arduino-nano", "GND", "arduino-nano", "5V"))


def test_ground_to_an_active_low_pin_that_is_not_an_input_is_still_an_error() -> None:
    # Strap exemption needs role digital_in; a power rail with the same words in its note would not qualify.
    assert _gnd_errors(_graph("arduino-nano", "GND", "usb-power-5v", "V+"))

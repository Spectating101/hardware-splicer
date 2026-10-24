"""Firmware for a composed design must drive the pins its wiring uses."""

from __future__ import annotations

import re

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.firmware_scaffold import generate_firmware_scaffold

TWO_SERVOS = ["esp32-devkit", "sg90", "sg90", "usb-power-5v"]
BUILD_ID = "generic_low_voltage_build"


def _generate(module_ids: list[str]) -> dict:
    graph = compose_build_graph_from_module_ids(module_ids)["graph"]
    return generate_firmware_scaffold(build_id=BUILD_ID, build_graph=graph)


def test_two_wired_servos_are_driven_on_the_pins_the_graph_wires_them_to() -> None:
    scaffold = _generate(TWO_SERVOS)

    assert scaffold["pins"]["servo_pan"] == 15 and scaffold["pins"]["servo_tilt"] == 16
    source = scaffold["source"]
    assert re.search(r"PAN_PIN\s*=\s*15\b", source)
    assert re.search(r"TILT_PIN\s*=\s*16\b", source)
    assert "ledcAttachPin" in source
    assert "LED_BUILTIN" not in source


def test_the_servo_firmware_claims_only_what_was_derived_from_the_wiring() -> None:
    scaffold = _generate(TWO_SERVOS)

    assert "canvas wiring" in scaffold["claim_boundary"]
    assert "verify" in scaffold["source"].lower() or "bench" in scaffold["source"].lower()


def test_a_single_servo_gets_no_invented_second_pin() -> None:
    scaffold = _generate(["esp32-devkit", "sg90", "usb-power-5v"])

    assert not re.search(r"\b(18|19)\b", scaffold["source"]), "default pins must not be invented"


def test_a_design_with_no_servo_keeps_the_generic_scaffold() -> None:
    scaffold = _generate(["esp32-devkit", "usb-power-5v"])

    assert "LED_BUILTIN" in scaffold["source"]

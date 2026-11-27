"""The engine's logic-level rule asks which side drives the wire, and a USB-fed pin is not mistaken for a dead supply."""

from __future__ import annotations

from hardware_splicer.pcb.safety_rules import analyze_build


def _graph(a, b, wires):
    return {"nodes": [{"id": "a", "moduleId": a}, {"id": "b", "moduleId": b}],
            "wires": [{"id": f"w{i}", "from": {"nodeId": "a", "pinId": x}, "to": {"nodeId": "b", "pinId": y}} for i, (x, y) in enumerate(wires)]}


def _by_wire(graph):
    out = {}
    for w in analyze_build(graph):
        if w.get("wireId"):
            out.setdefault(w["wireId"], set()).add((w["level"], w["id"].split("-", 1)[1]))
    return out


def test_a_5v_output_into_a_3v3_pin_is_an_error_and_a_3v3_output_into_a_5v_input_is_a_warning():
    found = _by_wire(_graph("hc-sr04", "esp32-devkit", [("ECHO", "GPIO18"), ("TRIG", "GPIO5")]))
    assert ("error", "logic") in found["w0"]
    assert found["w1"] == {("warn", "logicLow")}


def test_an_analog_sensor_output_counts_as_driving():
    """The library labels an analog sensor's output analog_in; it still pushes its voltage onto the wire."""
    from hardware_splicer.pcb.module_registry import find_module

    graph = _graph("ws2812b_strip", "esp32-devkit", [("DIN", "GPIO5")])
    assert _by_wire(graph)["w0"] == {("warn", "logicLow")}
    assert find_module("ws2812b_strip")["logicVoltageSource"]["quote"].startswith("VIH")


def test_a_usb_fed_pin_is_an_info_not_a_missing_supply():
    found = _by_wire(_graph("hc-sr04", "rpi-pico", [("VCC", "VBUS")]))
    assert found["w0"] == {("info", "usbFed")}
    assert ("warn", "noSource") in _by_wire(_graph("hc-sr04", "esp32-devkit", [("VCC", "VIN")]))["w0"]


def test_a_5v_lcd_backpack_on_an_esp32_i2c_bus_is_now_caught():
    found = _by_wire(_graph("lcd_16x2_i2c", "esp32-devkit", [("SDA", "GPIO21")]))
    assert ("error", "logic") in found["w0"]

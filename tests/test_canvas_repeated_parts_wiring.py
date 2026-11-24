"""Repeated modules on the canvas each get their own role and their own wires.

The auto-wirer used to key roles by module id, so with two sg90 nodes both servo
signals landed on the last one and the first stayed unwired. Roles are now
per instance, in canvas order, wherever the repeats sit in the node list.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from hardware_splicer.auto_wire import compose_build_graph_from_canvas_nodes
from hardware_splicer.pcb.module_registry import find_module

Wire = Tuple[str, str, str, str]


def _compose(parts: List[Tuple[str, str]]):
    graph = compose_build_graph_from_canvas_nodes(
        [{"id": node_id, "moduleId": module_id} for node_id, module_id in parts]
    )
    module_of = {n["id"]: n["moduleId"] for n in graph["nodes"]}
    wires: List[Wire] = [
        (w["from"]["nodeId"], w["from"]["pinId"], w["to"]["nodeId"], w["to"]["pinId"])
        for w in graph["wires"]
    ]
    return module_of, wires


def _assert_pins_exist(module_of: Dict[str, str], wires: List[Wire]) -> None:
    for from_node, from_pin, to_node, to_pin in wires:
        for node, pin in ((from_node, from_pin), (to_node, to_pin)):
            pins = {str(p.get("id")) for p in find_module(module_of[node])["pins"]}
            assert pin in pins, f"{node} ({module_of[node]}) has no pin {pin}"


def _into(wires: List[Wire], node: str, pin: str) -> List[Wire]:
    return [w for w in wires if w[2] == node and w[3] == pin]


def _check_servos(module_of, wires, servos, mcu, power):
    sigs = []
    for servo in servos:
        sig = _into(wires, servo, "SIG")
        assert len(sig) == 1, f"{servo} needs exactly one SIG wire, got {sig}"
        assert sig[0][0] == mcu
        sigs.append(sig[0][1])
        vcc = _into(wires, servo, "VCC")
        assert vcc == [(power, "V+", servo, "VCC")]
        gnd = _into(wires, servo, "GND")
        assert len(gnd) == 1 and gnd[0][2] == servo
    assert len(set(sigs)) == len(sigs), f"servo SIGs share a GPIO: {sigs}"
    # Power and ground wires never target a SIG pin, and the power node only
    # feeds supply pins.
    for from_node, from_pin, _to_node, to_pin in wires:
        if from_node == power:
            assert to_pin != "SIG"
    _assert_pins_exist(module_of, wires)


def test_two_servos_each_get_their_own_signal_and_power():
    module_of, wires = _compose(
        [("n1", "esp32-devkit"), ("n2", "sg90"), ("n3", "sg90"), ("n4", "usb-power-5v")]
    )
    _check_servos(module_of, wires, ["n2", "n3"], mcu="n1", power="n4")
    assert _into(wires, "n2", "SIG")[0][1] == "GPIO15"
    assert _into(wires, "n3", "SIG")[0][1] == "GPIO16"
    assert _into(wires, "n1", "VIN") == [("n4", "V+", "n1", "VIN")]


def test_repeats_in_the_middle_and_at_the_start_keep_canvas_order():
    module_of, wires = _compose(
        [("n1", "sg90"), ("n2", "esp32-devkit"), ("n3", "sg90"), ("n4", "usb-power-5v")]
    )
    _check_servos(module_of, wires, ["n1", "n3"], mcu="n2", power="n4")
    assert _into(wires, "n1", "SIG")[0][1] == "GPIO15"
    assert _into(wires, "n3", "SIG")[0][1] == "GPIO16"

    module_of, wires = _compose(
        [("a", "sg90"), ("b", "sg90"), ("c", "esp32-devkit"), ("d", "usb-power-5v"), ("e", "sg90")]
    )
    _check_servos(module_of, wires, ["a", "b", "e"], mcu="c", power="d")
    assert [_into(wires, s, "SIG")[0][1] for s in ("a", "b", "e")] == ["GPIO15", "GPIO16", "GPIO17"]


def test_power_never_lands_on_a_servo_when_repeats_are_listed_first():
    module_of, wires = _compose(
        [("n1", "sg90"), ("n2", "sg90"), ("n3", "usb-power-5v"), ("n4", "esp32-devkit")]
    )
    assert _into(wires, "n4", "VIN") == [("n3", "V+", "n4", "VIN")]
    _check_servos(module_of, wires, ["n1", "n2"], mcu="n4", power="n3")
    assert all(w[0] != "n1" and w[0] != "n2" for w in wires)


def test_two_i2c_sensors_share_the_bus_and_both_are_wired():
    module_of, wires = _compose(
        [("n1", "esp32-devkit"), ("n2", "bme280"), ("n3", "bme280"), ("n4", "usb-power-5v")]
    )
    for sensor in ("n2", "n3"):
        assert _into(wires, sensor, "SDA") == [("n1", "GPIO21", sensor, "SDA")]
        assert _into(wires, sensor, "SCL") == [("n1", "GPIO22", sensor, "SCL")]
        assert len(_into(wires, sensor, "VCC")) == 1
        assert len(_into(wires, sensor, "GND")) == 1
    assert _into(wires, "n1", "VIN") == [("n4", "V+", "n1", "VIN")]
    _assert_pins_exist(module_of, wires)


def test_single_servo_design_wiring_is_unchanged():
    # Captured from main before the fix.
    _module_of, wires = _compose([("n1", "esp32-devkit"), ("n2", "sg90"), ("n3", "usb-power-5v")])
    assert wires == [
        ("n3", "V+", "n1", "VIN"),
        ("n3", "GND", "n1", "GND"),
        ("n1", "GND", "n2", "GND"),
        ("n3", "V+", "n2", "VCC"),
        ("n1", "GPIO15", "n2", "SIG"),
    ]


def test_repeated_analog_parts_each_get_their_own_mcu_input():
    from hardware_splicer.auto_wire import compose_build_graph_from_canvas_nodes

    graph = compose_build_graph_from_canvas_nodes([
        {"id": "n1", "moduleId": "esp32-devkit"},
        {"id": "n2", "moduleId": "joystick_module"},
        {"id": "n3", "moduleId": "joystick_module"},
        {"id": "n4", "moduleId": "usb-power-5v"},
    ])
    graph = graph.get("graph", graph)
    analog = [(w["from"]["pinId"], w["to"]["nodeId"]) for w in graph["wires"]
              if w["from"]["nodeId"] == "n1" and w["to"]["pinId"] == "VRx"]
    assert sorted(node for _, node in analog) == ["n2", "n3"]
    assert len({pin for pin, _ in analog}) == 2, f"both joysticks share one MCU input: {analog}"

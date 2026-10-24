"""Two of the same part in a request must become two parts in the design, each wired."""

from __future__ import annotations

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.scratch_pipeline import module_ids_from_resolved

PAN_TILT = ["esp32-devkit", "sg90", "sg90", "usb-power-5v"]


def _nodes(graph: dict, module_id: str) -> list[str]:
    return [node["id"] for node in graph["nodes"] if node["moduleId"] == module_id]


def _pins_wired(graph: dict, node_id: str) -> dict[str, str]:
    """Pin id on this node -> 'node.pin' on the other end."""
    out: dict[str, str] = {}
    for wire in graph["wires"]:
        for here, there in ((wire["from"], wire["to"]), (wire["to"], wire["from"])):
            if here["nodeId"] == node_id:
                out[here["pinId"]] = f"{there['nodeId']}.{there['pinId']}"
    return out


def test_two_requested_servos_become_two_nodes() -> None:
    graph = compose_build_graph_from_module_ids(PAN_TILT)["graph"]

    assert len(_nodes(graph, "sg90")) == 2


def test_each_servo_is_powered_grounded_and_has_its_own_signal_pin() -> None:
    graph = compose_build_graph_from_module_ids(PAN_TILT)["graph"]
    [mcu] = _nodes(graph, "esp32-devkit")
    signal_pins = []
    for servo in _nodes(graph, "sg90"):
        wired = _pins_wired(graph, servo)
        assert set(wired) == {"VCC", "GND", "SIG"}, f"{servo} is missing a connection: {wired}"
        assert wired["SIG"].startswith(f"{mcu}.")
        signal_pins.append(wired["SIG"])

    assert len(set(signal_pins)) == 2, f"both servos share one signal pin: {signal_pins}"


def test_a_single_servo_is_wired_exactly_as_before() -> None:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "sg90", "usb-power-5v"])["graph"]

    assert len(_nodes(graph, "sg90")) == 1
    assert [w["id"] for w in graph["wires"]] == ["w1", "w2", "w3", "w4", "w5"]


def test_resolved_module_ids_keep_repeats_when_asked_and_dedupe_by_default() -> None:
    rows = [{"module_id": m} for m in PAN_TILT]

    assert module_ids_from_resolved(rows) == ["esp32-devkit", "sg90", "usb-power-5v"]
    assert module_ids_from_resolved(rows, keep_repeats=True) == PAN_TILT

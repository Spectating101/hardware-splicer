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


def test_merging_goal_picks_with_inventory_keeps_every_instance_of_a_repeated_part() -> None:
    from hardware_splicer.scratch_pipeline import merge_goal_modules_with_inventory

    inventory = [
        {"module_id": "esp32-devkit", "part_name": "ESP32 DevKit"},
        {"module_id": "sg90", "part_name": "SG90 pan servo"},
        {"module_id": "sg90", "part_name": "SG90 tilt servo"},
        {"module_id": "usb-power-5v", "part_name": "USB 5V power bank"},
    ]
    goal = "Build a pan-tilt inspection camera mount with two SG90 servos and ESP32"

    for constrained in (True, False):
        merged = merge_goal_modules_with_inventory(goal, inventory, constrained=constrained)
        servos = [row for row in merged if row["module_id"] == "sg90"]

        assert [row["part_name"] for row in servos] == ["SG90 pan servo", "SG90 tilt servo"], constrained


def test_the_plan_for_a_request_with_two_servos_lists_both_for_composition(monkeypatch) -> None:
    from pathlib import Path

    from hardware_splicer import load_project_intake, plan_project_from_intake

    for name in ("HARDWARE_SPLICER_OFFLINE_SALVAGE", "HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        monkeypatch.setenv(name, "0")
    root = Path(__file__).resolve().parents[1]
    intake = load_project_intake(root / "examples" / "intakes" / "splice_physical_pan_tilt_loop.json")

    plan = plan_project_from_intake(intake)

    assert plan["salvage_package"]["compose_module_ids"] == PAN_TILT

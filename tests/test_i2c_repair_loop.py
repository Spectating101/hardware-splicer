"""The agent loop: HS finds the clash, offers a repair, the agent submits the repaired design, HS verifies it."""

from __future__ import annotations

import json

import pytest

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.canvas_compose import compile_canvas_build
from hardware_splicer.graph_patch import apply_graph_patch
from hardware_splicer.pcb.safety_rules import analyze_build

TWO_SENSORS = ["esp32-devkit", "bme280", "bme280", "usb-power-5v"]


def _clash(graph: dict) -> dict:
    return next(w for w in analyze_build(graph) if w.get("code") == "i2c_address_clash")


def _repair(graph: dict, kind: str) -> dict:
    return next(r for r in _clash(graph)["repairs"] if r["kind"] == kind)


def test_applying_the_second_bus_patch_removes_the_clash_and_leaves_the_original_untouched() -> None:
    graph = compose_build_graph_from_module_ids(TWO_SENSORS, auto_repair=False)["graph"]
    before = json.dumps(graph, sort_keys=True)

    fixed = apply_graph_patch(graph, _repair(graph, "second_i2c_bus")["graph_patch"])

    assert json.dumps(graph, sort_keys=True) == before
    assert not [w for w in analyze_build(fixed) if w.get("code") == "i2c_address_clash"]
    assert not [w for w in analyze_build(fixed) if w.get("level") == "error"]


def test_the_repaired_design_has_two_buses_and_every_device_still_wired_to_power_and_ground() -> None:
    graph = compose_build_graph_from_module_ids(TWO_SENSORS, auto_repair=False)["graph"]
    fixed = apply_graph_patch(graph, _repair(graph, "second_i2c_bus")["graph_patch"])

    sensors = [n["id"] for n in fixed["nodes"] if n["moduleId"] == "bme280"]
    for sensor in sensors:
        pins = {end["pinId"] for w in fixed["wires"] for end in (w["from"], w["to"]) if end["nodeId"] == sensor}
        assert {"VCC", "GND", "SDA", "SCL"} <= pins, (sensor, pins)


def test_the_strap_patch_does_not_clear_the_design_it_leaves_a_warning_for_a_person() -> None:
    graph = compose_build_graph_from_module_ids(TWO_SENSORS, auto_repair=False)["graph"]
    fixed = apply_graph_patch(graph, _repair(graph, "strap_alternate_address")["graph_patch"])
    codes = [(w["code"], w["level"]) for w in analyze_build(fixed) if w.get("code")]

    assert ("i2c_address_clash", "error") not in codes
    assert ("i2c_address_declared_strap", "warn") in codes


def test_a_patch_that_names_a_wire_or_node_that_does_not_exist_is_refused() -> None:
    graph = compose_build_graph_from_module_ids(TWO_SENSORS, auto_repair=False)["graph"]

    with pytest.raises(ValueError, match="no wire"):
        apply_graph_patch(graph, {"remove_wires": ["w999"], "add_wires": [], "set_node_fields": {}})
    with pytest.raises(ValueError, match="no node"):
        apply_graph_patch(graph, {"remove_wires": [], "add_wires": [], "set_node_fields": {"n99": {"i2c_address": "0x76"}}})
    with pytest.raises(ValueError, match="unknown pin"):
        bad = {"id": "x", "from": {"nodeId": "n2", "pinId": "NOPE"}, "to": {"nodeId": "n1", "pinId": "GPIO4"}}
        apply_graph_patch(graph, {"remove_wires": [], "add_wires": [bad], "set_node_fields": {}})


def test_a_patch_may_only_set_the_address_field_on_a_node_never_change_what_a_part_is() -> None:
    graph = compose_build_graph_from_module_ids(TWO_SENSORS, auto_repair=False)["graph"]

    with pytest.raises(ValueError, match="only i2c_address"):
        apply_graph_patch(graph, {"remove_wires": [], "add_wires": [], "set_node_fields": {"n2": {"moduleId": "sg90"}}})


def test_an_agent_submitting_the_repaired_design_through_the_canvas_path_gets_a_clean_verdict(tmp_path) -> None:
    graph = compose_build_graph_from_module_ids(TWO_SENSORS, auto_repair=False)["graph"]
    broken = compile_canvas_build(out_dir=str(tmp_path / "broken"), nodes=graph["nodes"], wires=graph["wires"], export_gerber=False)
    assert broken.compile_result.design_quality["electrical_safety_pass"] is False

    fixed = apply_graph_patch(graph, _repair(graph, "second_i2c_bus")["graph_patch"])
    result = compile_canvas_build(out_dir=str(tmp_path / "fixed"), nodes=fixed["nodes"], wires=fixed["wires"], export_gerber=False)
    quality = result.compile_result.design_quality

    assert quality["electrical_safety_pass"] is True
    assert quality["drc_pass"] is True
    assert quality["build_ready"] is True

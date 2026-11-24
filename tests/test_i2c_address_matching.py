"""A declared address is matched as an I2C address (7-bit, any hex case), not as a string."""

from __future__ import annotations

import pytest

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.graph_patch import apply_graph_patch
from hardware_splicer.pcb.safety_rules import analyze_build


def _graph(*module_ids: str) -> dict:
    return compose_build_graph_from_module_ids(list(module_ids), auto_repair=False)["graph"]


def _with_address(module_id: str, address) -> list[dict]:
    graph = _graph("esp32-devkit", module_id, "usb-power-5v")
    for node in graph["nodes"]:
        if node["moduleId"] == module_id:
            node["i2c_address"] = address
    return analyze_build(graph)


@pytest.mark.parametrize("module_id,address", [("ssd1306-128x64", "0x3d"), ("bh1750", "0x5c"), ("ssd1306-128x64", 0x3D), ("bh1750", "0X5C")])
def test_a_declared_address_matches_whatever_the_hex_case_or_type(module_id, address) -> None:
    assert not [w for w in _with_address(module_id, address) if w.get("code") == "i2c_address_not_possible"]


def test_a_lowercase_declared_address_does_not_create_a_clash_with_the_default() -> None:
    graph = _graph("esp32-devkit", "ssd1306-128x64", "ssd1306-128x64", "usb-power-5v")
    second = [n for n in graph["nodes"] if n["moduleId"] == "ssd1306-128x64"][1]
    second["i2c_address"] = "0x3d"

    assert not [w for w in analyze_build(graph) if w.get("code") == "i2c_address_clash"]


@pytest.mark.parametrize("address", ["0xEE", "0x00", "0x78", "0x7F", "banana", "0x", -1, 300])
def test_an_address_outside_the_7_bit_device_range_is_an_error_even_for_an_unmapped_part(address) -> None:
    found = [w for w in _with_address("bmp280", address) if w.get("code") == "i2c_address_not_possible"]

    assert found and found[0]["level"] == "error"


def test_a_valid_7_bit_address_on_an_unmapped_part_is_not_an_error() -> None:
    assert not [w for w in _with_address("bmp280", "0x76") if w.get("code") == "i2c_address_not_possible"]


@pytest.mark.parametrize("value", [None, "0xEE", "banana", 0x78])
def test_a_patch_cannot_write_an_invalid_address(value) -> None:
    graph = _graph("esp32-devkit", "bme280", "usb-power-5v")
    node = next(n["id"] for n in graph["nodes"] if n["moduleId"] == "bme280")

    with pytest.raises(ValueError):
        apply_graph_patch(graph, {"set_node_fields": {node: {"i2c_address": value}}})


def test_a_patch_writes_the_address_in_its_normal_form() -> None:
    graph = _graph("esp32-devkit", "bme280", "usb-power-5v")
    node = next(n["id"] for n in graph["nodes"] if n["moduleId"] == "bme280")

    patched = apply_graph_patch(graph, {"set_node_fields": {node: {"i2c_address": "0x76"}}})

    assert next(n for n in patched["nodes"] if n["id"] == node)["i2c_address"] == "0x76"

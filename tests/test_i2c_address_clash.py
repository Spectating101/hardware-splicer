"""Two devices on one I2C bus that answer at the same address cannot both work. HS must say so,
say what to do about it, and not be talked out of it by a claim it cannot check."""

from __future__ import annotations

from copy import deepcopy

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.pcb.safety_rules import analyze_build


def _graph(*module_ids: str) -> dict:
    return compose_build_graph_from_module_ids(list(module_ids), auto_repair=False)["graph"]


def _findings(graph: dict, code: str) -> list[dict]:
    return [w for w in analyze_build(graph) if w.get("code") == code]


def _nodes(graph: dict, module_id: str) -> list[str]:
    return [n["id"] for n in graph["nodes"] if n["moduleId"] == module_id]


def test_two_identical_sensors_on_one_bus_are_an_error_naming_the_address_and_both_parts() -> None:
    graph = _graph("esp32-devkit", "bme280", "bme280", "usb-power-5v")

    [clash] = _findings(graph, "i2c_address_clash")

    assert clash["level"] == "error"
    assert clash["address"] == "0x77"
    assert sorted(clash["nodes"]) == sorted(_nodes(graph, "bme280"))
    assert "0x77" in clash["message"] and "cannot both work" in clash["message"]
    assert clash["bus"] == {"controller": _nodes(graph, "esp32-devkit")[0], "sda": "GPIO21", "scl": "GPIO22"}
    assert "Bosch datasheet" in clash["address_basis"]


def test_different_chips_on_one_bus_are_not_a_clash() -> None:
    assert not _findings(_graph("esp32-devkit", "bme280", "bh1750", "usb-power-5v"), "i2c_address_clash")
    assert not _findings(_graph("esp32-devkit", "bme280", "ds3231_rtc", "usb-power-5v"), "i2c_address_clash")


def test_a_single_device_on_a_bus_is_not_a_clash() -> None:
    assert not _findings(_graph("esp32-devkit", "bme280", "usb-power-5v"), "i2c_address_clash")


def test_parts_with_no_sourced_address_are_reported_as_unknown_never_as_fine() -> None:
    graph = _graph("esp32-devkit", "bmp280", "bmp280", "usb-power-5v")

    assert not _findings(graph, "i2c_address_clash")
    [unknown] = _findings(graph, "i2c_address_unknown")
    assert unknown["level"] == "info"
    assert "cannot tell" in unknown["message"]


def test_a_clash_offers_a_second_bus_repair_with_an_exact_wire_patch_that_needs_no_person() -> None:
    graph = _graph("esp32-devkit", "bme280", "bme280", "usb-power-5v")
    [clash] = _findings(graph, "i2c_address_clash")
    repair = next(r for r in clash["repairs"] if r["kind"] == "second_i2c_bus")
    moved = repair["moves_node"]

    assert moved == sorted(_nodes(graph, "bme280"))[-1] or moved in _nodes(graph, "bme280")
    assert repair["requires_person"] is False
    patch = repair["graph_patch"]
    assert len(patch["remove_wires"]) == 2
    assert {w["to"]["nodeId"] for w in patch["add_wires"]} == {_nodes(graph, "esp32-devkit")[0]}
    new_pins = [w["to"]["pinId"] for w in patch["add_wires"]]
    assert len(set(new_pins)) == 2 and not {"GPIO21", "GPIO22"} & set(new_pins)
    assert not {"GPIO2", "GPIO5", "GPIO15", "GPIO34"} & set(new_pins), "no boot-strapping or input-only pins"
    assert "Wire1" in repair["firmware_effect"]


def test_a_clash_offers_the_alternate_address_repair_as_a_physical_step_for_a_person() -> None:
    graph = _graph("esp32-devkit", "bme280", "bme280", "usb-power-5v")
    [clash] = _findings(graph, "i2c_address_clash")
    repair = next(r for r in clash["repairs"] if r["kind"] == "strap_alternate_address")

    assert repair["to_address"] == "0x76"
    assert repair["requires_person"] is True
    assert repair["physical_steps"] and "depends on your board" in " ".join(repair["physical_steps"])
    assert repair["graph_patch"]["set_node_fields"] == {repair["moves_node"]: {"i2c_address": "0x76"}}


def test_a_part_whose_address_cannot_change_gets_no_strap_repair() -> None:
    [clash] = _findings(_graph("esp32-devkit", "ds3231_rtc", "ds3231_rtc", "usb-power-5v"), "i2c_address_clash")

    assert clash["address"] == "0x68"
    assert [r["kind"] for r in clash["repairs"]] == ["second_i2c_bus"]


def test_without_two_i2c_controllers_there_is_no_second_bus_repair_and_the_message_says_so() -> None:
    graph = _graph("arduino-nano", "ds3231_rtc", "ds3231_rtc", "usb-power-5v")

    [clash] = _findings(graph, "i2c_address_clash")

    assert clash["repairs"] == []
    assert "no automatic repair" in clash["message"]


def test_declaring_a_strap_does_not_clear_the_finding_it_becomes_a_standing_warning_for_a_person() -> None:
    graph = _graph("esp32-devkit", "bme280", "bme280", "usb-power-5v")
    second = sorted(_nodes(graph, "bme280"))[-1]
    declared = deepcopy(graph)
    next(n for n in declared["nodes"] if n["id"] == second)["i2c_address"] = "0x76"

    assert not _findings(declared, "i2c_address_clash")
    [strap] = _findings(declared, "i2c_address_declared_strap")
    assert strap["level"] == "warn"
    assert strap["nodeId"] == second and strap["address"] == "0x76"
    assert "cannot see" in strap["message"]


def test_declaring_an_address_the_chip_cannot_have_is_an_error() -> None:
    graph = _graph("esp32-devkit", "bme280", "usb-power-5v")
    next(n for n in graph["nodes"] if n["moduleId"] == "bme280")["i2c_address"] = "0x10"

    [bad] = _findings(graph, "i2c_address_not_possible")

    assert bad["level"] == "error"
    assert "0x76" in bad["message"] and "0x77" in bad["message"]


def test_a_design_with_no_i2c_devices_gets_no_i2c_findings() -> None:
    codes = {w.get("code") for w in analyze_build(_graph("esp32-devkit", "sg90", "usb-power-5v"))}

    assert not {c for c in codes if c and c.startswith("i2c_")}

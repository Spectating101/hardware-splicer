"""A strap written into a design is a physical claim HS cannot see, wherever the device sits: alone on a
bus, on its own second bus, or on no bus at all. It is always a warning for a person."""

from __future__ import annotations

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.pcb.safety_rules import analyze_build


def _straps(graph: dict) -> list[dict]:
    return [w for w in analyze_build(graph) if w.get("code") == "i2c_address_declared_strap"]


def _declare(graph: dict, address: str, count: int = 99) -> dict:
    for node in [n for n in graph["nodes"] if n["moduleId"] == "bme280"][:count]:
        node["i2c_address"] = address
    return graph


def test_a_strap_on_the_only_device_of_a_bus_is_a_warning_for_a_person() -> None:
    graph = _declare(compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "usb-power-5v"], auto_repair=False)["graph"], "0x76")

    [strap] = _straps(graph)

    assert strap["level"] == "warn" and strap["requires_person"] is True


def test_straps_on_devices_that_each_have_their_own_bus_are_both_reported() -> None:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "bme280", "usb-power-5v"], auto_repair=True)["graph"]

    assert len(_straps(_declare(graph, "0x76"))) == 2


def test_a_strap_on_a_device_wired_to_no_bus_is_still_reported() -> None:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "usb-power-5v"], auto_repair=False)["graph"]
    graph["wires"] = [w for w in graph["wires"] if not any(e["pinId"] in ("SDA", "SCL") for e in (w["from"], w["to"]))]

    assert len(_straps(_declare(graph, "0x76"))) == 1


def test_a_strap_on_a_shared_bus_is_reported_once_per_device() -> None:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "bme280", "usb-power-5v"], auto_repair=False)["graph"]

    assert len(_straps(_declare(graph, "0x76", count=1))) == 1


def test_the_default_address_is_not_a_strap() -> None:
    graph = _declare(compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "usb-power-5v"], auto_repair=False)["graph"], "0x77")

    assert not _straps(graph)

"""A servo is a 5 V load. The compose retry loop added a 3.3 V LDO and the wiring made it the supply rail."""

from __future__ import annotations

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids

LDO = "ldo-ams1117-3v3"


def _source_ids(graph: dict, target_module: str, target_pin: str) -> list[str]:
    modules = {n["id"]: n["moduleId"] for n in graph["nodes"]}
    sources = []
    for wire in graph["wires"]:
        for here, there in ((wire["to"], wire["from"]), (wire["from"], wire["to"])):
            if modules[here["nodeId"]] == target_module and here["pinId"] == target_pin:
                sources.append(f"{modules[there['nodeId']]}.{there['pinId']}")
    return sources


def test_servo_supply_comes_from_the_usb_5v_rail_not_the_3v3_ldo() -> None:
    """The exact module list the probe's retry loop produced on main."""
    graph = compose_build_graph_from_module_ids(
        ["esp32-devkit", "sg90", "sg90", "usb-power-5v", "level-shifter-4ch", LDO, "mosfet-irlz44n"]
    )["graph"]

    supplies = _source_ids(graph, "sg90", "VCC")

    assert len(supplies) == 2
    assert all(s.startswith("usb-power-5v.") for s in supplies), supplies


def test_servo_supply_comes_from_a_buck_output_when_there_is_a_buck_and_an_ldo() -> None:
    graph = compose_build_graph_from_module_ids(
        ["esp32-devkit", "sg90", "dc-barrel-12v", "buck-mp1584", LDO]
    )["graph"]

    assert _source_ids(graph, "sg90", "VCC") == ["buck-mp1584.OUT+"]


def test_the_level_shifter_high_side_is_not_fed_from_the_3v3_ldo_when_a_5v_rail_exists() -> None:
    graph = compose_build_graph_from_module_ids(
        ["esp32-devkit", "hc-sr04", "usb-power-5v", "level-shifter-4ch", LDO]
    )["graph"]

    assert _source_ids(graph, "level-shifter-4ch", "HV") == ["usb-power-5v.V+"]


def test_a_3v3_peripheral_is_still_powered_from_the_mcu_3v3_pin_when_an_ldo_is_present() -> None:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "usb-power-5v", LDO])["graph"]

    assert _source_ids(graph, "bme280", "VCC") == ["esp32-devkit.3V3"]

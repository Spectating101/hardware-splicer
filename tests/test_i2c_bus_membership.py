"""Which devices share an I2C bus is a question about nets, not about direct wires to the controller.

Daisy-chained (Qwiic-style) devices and devices behind a level shifter are on the bus, and HS must
check their addresses like any other."""

from __future__ import annotations

from hardware_splicer.graph_patch import apply_graph_patch
from hardware_splicer.pcb.safety_rules import analyze_build


def _w(i: int, a: str, b: str) -> dict:
    (an, ap), (bn, bp) = a.split("."), b.split(".")
    return {"id": f"w{i}", "from": {"nodeId": an, "pinId": ap}, "to": {"nodeId": bn, "pinId": bp}}


def _graph(nodes: dict[str, str], pairs: list[tuple[str, str]]) -> dict:
    return {
        "nodes": [{"id": nid, "moduleId": mid} for nid, mid in nodes.items()],
        "wires": [_w(i + 1, a, b) for i, (a, b) in enumerate(pairs)],
    }


def _findings(graph: dict, code: str) -> list[dict]:
    return [w for w in analyze_build(graph) if w.get("code") == code]


POWER = [("n4.V+", "n1.VIN"), ("n4.GND", "n1.GND")]
TWO = {"n1": "esp32-devkit", "n2": "bme280", "n3": "bme280", "n4": "usb-power-5v"}


def test_a_daisy_chained_sensor_is_on_the_bus_and_clashes_with_the_first() -> None:
    graph = _graph(TWO, [("n1.GPIO21", "n2.SDA"), ("n1.GPIO22", "n2.SCL"), ("n2.SDA", "n3.SDA"), ("n2.SCL", "n3.SCL"), *POWER])

    [clash] = _findings(graph, "i2c_address_clash")

    assert sorted(clash["nodes"]) == ["n2", "n3"]
    assert clash["bus"] == {"controller": "n1", "sda": "GPIO21", "scl": "GPIO22"}


def test_the_repair_for_a_chained_device_never_leaves_it_on_both_buses() -> None:
    graph = _graph(TWO, [("n1.GPIO21", "n2.SDA"), ("n1.GPIO22", "n2.SCL"), ("n2.SDA", "n3.SDA"), ("n2.SCL", "n3.SCL"), *POWER])
    [clash] = _findings(graph, "i2c_address_clash")

    for repair in clash["repairs"]:
        repaired = apply_graph_patch(graph, repair["graph_patch"])
        if repair["kind"] == "second_i2c_bus":
            assert not _findings(repaired, "i2c_address_clash"), "an offered second-bus repair must clear the clash"


def test_sensors_behind_a_level_shifter_are_on_the_bus() -> None:
    nodes = {**TWO, "n5": "level-shifter-4ch"}
    graph = _graph(
        nodes,
        [
            ("n1.GPIO21", "n5.LV1"), ("n1.GPIO22", "n5.LV2"),
            ("n5.HV1", "n2.SDA"), ("n5.HV1", "n3.SDA"), ("n5.HV2", "n2.SCL"), ("n5.HV2", "n3.SCL"),
            *POWER,
        ],
    )

    [clash] = _findings(graph, "i2c_address_clash")

    assert sorted(clash["nodes"]) == ["n2", "n3"]
    assert clash["bus"]["controller"] == "n1"
    assert not [r for r in clash["repairs"] if r["kind"] == "second_i2c_bus"], "no automatic rewiring through a shifter"


def test_a_device_with_two_wires_on_its_sda_and_scl_still_counts() -> None:
    graph = _graph(
        TWO,
        [("n1.GPIO21", "n2.SDA"), ("n1.GPIO21", "n2.SDA"), ("n1.GPIO22", "n2.SCL"), ("n1.GPIO22", "n2.SCL"),
         ("n1.GPIO21", "n3.SDA"), ("n1.GPIO22", "n3.SCL"), ("n2.SDA", "n3.SDA"), ("n2.SCL", "n3.SCL"), *POWER],
    )

    [clash] = _findings(graph, "i2c_address_clash")

    assert sorted(clash["nodes"]) == ["n2", "n3"]


def test_devices_with_different_addresses_in_a_chain_are_not_a_clash() -> None:
    nodes = {"n1": "esp32-devkit", "n2": "bme280", "n3": "bh1750", "n4": "usb-power-5v"}
    graph = _graph(nodes, [("n1.GPIO21", "n2.SDA"), ("n1.GPIO22", "n2.SCL"), ("n2.SDA", "n3.SDA"), ("n2.SCL", "n3.SCL"), *POWER])

    assert not _findings(graph, "i2c_address_clash")

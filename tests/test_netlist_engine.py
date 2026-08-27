from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.build_compiler import compile_from_netlist
from hardware_splicer.netlist import (
    build_graph_to_netlist,
    netlist_to_build_graph,
    parse_kicad_netlist,
    run_erc,
)
from hardware_splicer.netlist.ir import CircuitNetlist
from hardware_splicer.netlist.lower import build_graph_to_netlist as lower_graph


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "examples" / "netlist_fixtures" / "json"


def _fixture_netlist(name: str) -> CircuitNetlist:
    return CircuitNetlist.from_dict(
        json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    )


def test_build_graph_lowers_to_netlist_and_back() -> None:
    graph = compose_build_graph_from_module_ids(
        ["usb-power-5v", "esp32-devkit", "dht22"]
    )["graph"]
    netlist = build_graph_to_netlist(graph)
    assert len(netlist.components) == 3
    assert len(netlist.nets) >= 2
    net_names = {net.name for net in netlist.nets}
    assert "GND" in net_names
    assert any(name in net_names for name in ("DATA", "GPIO4", "+5V"))
    erc = run_erc(netlist)
    assert erc["pass"] is True
    rebuilt = netlist_to_build_graph(netlist)
    assert len(rebuilt["nodes"]) == 3
    assert len(rebuilt["wires"]) >= 2


def test_netlist_round_trip_preserves_wire_count() -> None:
    graph = compose_build_graph_from_module_ids(
        ["usb-power-5v", "esp32-devkit", "mosfet-irlz44n", "water_pump_5v"]
    )["graph"]
    netlist = lower_graph(graph)
    roundtrip = netlist_to_build_graph(netlist)
    assert len(roundtrip.get("wires") or []) >= len(graph.get("wires") or []) - 2


def test_parse_kicad_netlist_minimal() -> None:
    sample = """
    (export (version "E")
      (components
        (comp (ref "U1") (value "esp32-devkit") (footprint "Module:ESP32"))
        (comp (ref "U2") (value "dht22") (footprint "Sensor:DHT22"))
      )
      (nets
        (net (code "1") (name "GND") (node (ref "U1") (pin "GND")) (node (ref "U2") (pin "GND")))
        (net (code "2") (name "DATA") (node (ref "U1") (pin "GPIO4")) (node (ref "U2") (pin "DATA")))
      )
    )
    """
    netlist = parse_kicad_netlist(sample)
    assert len(netlist.components) == 2
    assert len(netlist.nets) == 2
    assert netlist.components[0].module_id == "esp32-devkit"


def test_compile_from_netlist_produces_erc_artifacts(tmp_path: Path) -> None:
    graph = compose_build_graph_from_module_ids(
        ["usb-power-5v", "esp32-devkit", "relay-1ch-5v"]
    )["graph"]
    netlist = build_graph_to_netlist(graph)
    result = compile_from_netlist(netlist.to_dict(), tmp_path, export_gerber=False)
    assert result.ok is True, result.error
    assert result.design_quality.get("erc_pass") is True
    build_dir = tmp_path / "build_compilation"
    assert (build_dir / "circuit_netlist.json").is_file()
    assert (build_dir / "ERC.json").is_file()
    netlist_data = json.loads((build_dir / "circuit_netlist.json").read_text(encoding="utf-8"))
    assert netlist_data.get("schema_version") == "hardware_splicer.netlist.v1"


def _assert_declared_fixture_compiles(
    fixture_name: str,
    tmp_path: Path,
    *,
    require: set[str] | None = None,
) -> None:
    # Safety topology is architecture truth, not something a generic module-bag auto-wirer
    # may invent. Compile the declared fixture and prove the netlist/PCB stack preserves it.
    netlist = _fixture_netlist(fixture_name)
    present = {component.module_id for component in netlist.components}
    if require:
        assert require <= present, f"missing modules: {require - present}"
    roundtrip = netlist_to_build_graph(netlist)
    from hardware_splicer.pcb.safety_rules import analyze_build

    assert not [w for w in analyze_build(roundtrip) if w.get("level") == "error"]
    result = compile_from_netlist(netlist, tmp_path, export_gerber=False)
    quality = result.design_quality or {}
    assert result.ok is True, result.error
    assert quality.get("erc_pass") is True
    assert quality.get("electrical_safety_pass") is True
    assert int(quality.get("kicad_drc_errors") or 0) == 0


def test_plant_watering_netlist_compiles_with_pump(tmp_path: Path) -> None:
    _assert_declared_fixture_compiles(
        "usb_esp_plant_watering.json",
        tmp_path,
        require={"mini-pump-5v", "level-shifter-4ch", "mosfet-irlz44n"},
    )


def test_ultrasonic_netlist_compiles_with_level_shifter(tmp_path: Path) -> None:
    # This simpler fixture remains a useful generic auto-wire/lowering case because the
    # shifter relationship is already explicitly represented by the module interface.
    graph = compose_build_graph_from_module_ids(
        ["usb-power-5v", "esp32-devkit", "hc-sr04", "level-shifter-4ch"]
    )["graph"]
    present = {n["moduleId"] for n in graph.get("nodes") or []}
    assert {"hc-sr04", "level-shifter-4ch"} <= present
    netlist = build_graph_to_netlist(graph)
    result = compile_from_netlist(netlist, tmp_path, export_gerber=False)
    quality = result.design_quality or {}
    assert result.ok is True, result.error
    assert quality.get("electrical_safety_pass") is True
    assert int(quality.get("kicad_drc_errors") or 0) == 0


def test_fan_mosfet_netlist_compiles_switched_load(tmp_path: Path) -> None:
    _assert_declared_fixture_compiles(
        "usb_esp_fan_mosfet.json",
        tmp_path,
        require={"level-shifter-4ch", "mosfet-irlz44n", "cooling_fan_5v"},
    )

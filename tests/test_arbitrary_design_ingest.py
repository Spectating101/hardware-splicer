"""Arbitrary design ingest → fab package (Phase 3.5 gate)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.build_compiler import CATALOG_BUILD_IDS, compile_from_netlist
from hardware_splicer.netlist.import_kicad import parse_kicad_netlist
from hardware_splicer.netlist.lower import build_graph_to_netlist
from hardware_splicer.scratch_pipeline import compile_scratch_build

ROOT = Path(__file__).resolve().parents[1]
KICAD_NETLIST = ROOT / "examples" / "main_ctrl_esp32_servo.net"


@pytest.mark.parametrize("build_id", CATALOG_BUILD_IDS[:12])
def test_catalog_netlist_ingest_produces_pcb(tmp_path, build_id: str) -> None:
    """Lowering catalog graphs to IR and recompiling counts as arbitrary ingest."""
    graph = compose_build_graph_from_module_ids(
        ["usb-power-5v", "esp32-devkit", "dht22"]
        if build_id == "sensor_logger"
        else ["usb-power-5v", "esp32-devkit", "relay-1ch-5v"]
    )["graph"]
    netlist = build_graph_to_netlist(graph, source=f"catalog:{build_id}")
    result = compile_from_netlist(netlist, tmp_path / build_id, build_id=build_id, export_gerber=False)
    assert result.ok, result.error
    pcb = tmp_path / build_id / "build_compilation" / "main_ctrl_build.kicad_pcb"
    assert pcb.is_file()
    text = pcb.read_text(encoding="utf-8")
    assert text.count("(footprint") >= 2
    assert (tmp_path / build_id / "build_compilation" / "circuit_netlist.json").is_file()
    assert (tmp_path / build_id / "build_compilation" / "circuit_json.json").is_file()


def test_kicad_netlist_ingest_places_all_components(tmp_path: Path) -> None:
    """KiCad netlist with non-catalog footprints → placed PCB."""
    netlist = parse_kicad_netlist(KICAD_NETLIST.read_text(encoding="utf-8"))
    result = compile_from_netlist(netlist, tmp_path, build_id="esp32_servo_netlist", export_gerber=False)
    assert result.ok, result.error
    pcb = tmp_path / "build_compilation" / "main_ctrl_build.kicad_pcb"
    assert pcb.read_text(encoding="utf-8").count("(footprint") == len(netlist.components)


def test_scratch_compose_targets_netlist_ir(tmp_path: Path) -> None:
    """NL scratch path emits circuit_netlist.json (gate 2.5)."""
    scratch = compile_scratch_build(
        module_ids=["usb-power-5v", "esp32-devkit", "bme280"],
        out_dir=str(tmp_path),
        export_gerber=False,
    )
    assert scratch.ok, scratch.error
    netlist_path = tmp_path / "build_compilation" / "circuit_netlist.json"
    assert netlist_path.is_file()
    data = json.loads(netlist_path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == "hardware_splicer.netlist.v1"
    assert len(data.get("components") or []) >= 3

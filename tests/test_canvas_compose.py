"""Canvas compose + schematic symbol coverage (lightweight)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.canvas_compose import compile_canvas_build
from hardware_splicer.integrations.schematic_export import netlist_to_kicad_schematic
from hardware_splicer.integrations.schematic_symbols import schematic_symbol_for_module
from hardware_splicer.netlist.ir import CircuitNetlist, ComponentInstance
from hardware_splicer.netlist.lower import build_graph_to_netlist
from hardware_splicer.auto_wire import compose_build_graph_from_module_ids


def test_canvas_compose_material_mode_scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    nodes = [
        {"id": "n1", "moduleId": "usb-power-5v"},
        {"id": "n2", "moduleId": "esp32-devkit"},
        {"id": "n3", "moduleId": "dht22"},
    ]
    result = compile_canvas_build(
        out_dir=str(tmp_path),
        nodes=nodes,
        constraints={"strategy_mode": "open", "graph_mode": "canvas"},
        export_gerber=False,
    )
    assert result.material_mode == "scratch"
    assert result.ok
    q = (result.compile_result.design_quality if result.compile_result else {}) or {}
    assert q.get("material_mode") == "scratch"
    assert int(q.get("kicad_drc_errors") or 0) == 0


def test_canvas_compose_salvage_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    nodes = [
        {"id": "n1", "moduleId": "usb-power-5v"},
        {"id": "n2", "moduleId": "esp32-devkit"},
        {"id": "n3", "moduleId": "dht22"},
    ]
    result = compile_canvas_build(
        out_dir=str(tmp_path),
        nodes=nodes,
        salvage_mode=True,
        constraints={"strategy_mode": "constrained", "graph_mode": "canvas"},
        export_gerber=False,
    )
    assert result.material_mode == "salvage"
    assert result.graph.get("editor_scratch_unified") is True


def test_schematic_embedded_module_symbols() -> None:
    graph = compose_build_graph_from_module_ids(["usb-power-5v", "esp32-devkit", "bme280"])["graph"]
    netlist = build_graph_to_netlist(graph, source="test")
    text = netlist_to_kicad_schematic(netlist, title="symtest")
    assert "HS:MCU" in text or "HS:Sensor" in text
    assert "HS:PowerIn" in text or "HS:ModuleBlock" in text
    assert 'property "Footprint"' in text
    lib_id, _, fp = schematic_symbol_for_module("esp32-devkit", ref="U1", value="ESP32")
    assert lib_id == "HS:MCU"
    assert fp


def test_schematic_export_fixture(tmp_path: Path) -> None:
    netlist = CircuitNetlist(
        source="test",
        components=[
            ComponentInstance(ref="U1", value="ESP32", module_id="esp32-devkit", footprint="esp32-devkit"),
            ComponentInstance(ref="R1", value="10K", module_id="resistor-10k", footprint="R_0603"),
        ],
        nets=[],
    )
    sch = netlist_to_kicad_schematic(netlist)
    path = tmp_path / "t.kicad_sch"
    path.write_text(sch, encoding="utf-8")
    body = path.read_text(encoding="utf-8")
    assert "HS:MCU" in body
    assert "Device:R" in body


def test_compose_api_wire_only_canvas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from hardware_splicer.api import create_app

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    client = TestClient(create_app())
    nodes = [
        {"id": "n1", "moduleId": "usb-power-5v"},
        {"id": "n2", "moduleId": "esp32-devkit"},
        {"id": "n3", "moduleId": "dht22"},
    ]
    response = client.post(
        "/v1/compose",
        json={"canvas_nodes": nodes, "wire_only": True, "export_gerber": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data.get("wire_only") is True
    assert len(data["graph"]["nodes"]) == 3
    assert len(data["graph"]["wires"]) >= 2
    assert data.get("compile_result") is None


def test_compose_api_wire_only_phrase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from hardware_splicer.api import create_app

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    client = TestClient(create_app())
    response = client.post(
        "/v1/compose",
        json={"phrase": "plant watering with soil moisture sensor and pump", "wire_only": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data.get("wire_only") is True
    assert len(data.get("module_ids") or []) >= 2
    assert len(data["graph"]["wires"]) >= 2

"""Integration tests: FreeRouting, schematic ERC, circuit-json, jlcsearch."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.integrations.circuit_json_adapter import netlist_to_circuit_json
from hardware_splicer.integrations.freerouting_bridge import run_freerouting_pipeline
from hardware_splicer.integrations.jlcsearch_client import JlcSearchClient
from hardware_splicer.integrations.schematic_export import write_schematic_for_netlist
from hardware_splicer.netlist.lower import build_graph_to_netlist
from hardware_splicer.pcb.kicad_cli_erc import run_kicad_cli_erc


def _pcbnew_available() -> bool:
    try:
        import pcbnew  # noqa: F401

        return True
    except ImportError:
        return False


def _freerouting_ready() -> bool:
    jar = os.environ.get("HARDWARE_SPLICER_FREEROUTING_JAR")
    if jar and Path(jar).is_file():
        return bool(shutil.which("java"))
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "hardware-splicer" / "freerouting"
    version = os.environ.get("HARDWARE_SPLICER_FREEROUTING_VERSION", "2.1.0")
    return bool(shutil.which("java") and (cache / f"freerouting-{version}.jar").is_file())


@pytest.mark.skipif(not shutil.which("kicad-cli"), reason="kicad-cli required")
def test_compile_emits_schematic_circuit_json_and_sch_erc(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "0")
    result = compile_catalog_build("sensor_logger", str(tmp_path), export_gerber=False)
    assert result.ok, result.quality

    build_dir = tmp_path / "build_compilation"
    sch = build_dir / "main_ctrl_build.kicad_sch"
    cj = build_dir / "circuit_json.json"
    assert sch.is_file()
    assert cj.is_file()

    payload = json.loads(cj.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    types = {row.get("type") for row in payload}
    assert "source_component" in types
    assert "schematic_trace" in types

    erc = run_kicad_cli_erc(sch, out_dir=tmp_path / "erc")
    assert erc.get("skipped") is not True
    assert isinstance(erc.get("violations"), list)


@pytest.mark.skipif(
    os.environ.get("HARDWARE_SPLICER_RUN_FREEROUTING", "").strip().lower() not in ("1", "true", "yes", "on"),
    reason="set HARDWARE_SPLICER_RUN_FREEROUTING=1 for live FreeRouting test",
)
@pytest.mark.skipif(not _pcbnew_available(), reason="pcbnew required")
@pytest.mark.skipif(not _freerouting_ready(), reason="java + freerouting jar required")
@pytest.mark.skipif(not shutil.which("kicad-cli"), reason="kicad-cli required")
def test_freerouting_pipeline_routes_sensor_logger(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "0")
    result = compile_catalog_build("sensor_logger", str(tmp_path), export_gerber=False)
    assert result.ok
    pcb = Path(result.kicad_pcb_file)
    assert pcb.is_file()

    report = run_freerouting_pipeline(pcb, out_dir=tmp_path / "fr")
    assert report.get("ok"), report
    assert int(report.get("track_count") or 0) > 0
    routed = Path(str(report["routed_pcb_path"]))
    assert routed.is_file()


def test_circuit_json_from_graph_roundtrip() -> None:
    graph = {
        "nodes": [
            {"id": "n1", "moduleId": "esp32-devkit"},
            {"id": "n2", "moduleId": "dht22"},
        ],
        "edges": [{"from": "n1", "to": "n2", "signal": "DATA"}],
    }
    netlist = build_graph_to_netlist(graph)
    docs = netlist_to_circuit_json(netlist, source_build_id="test")
    assert any(d.get("type") == "source_component" for d in docs)


def test_jlcsearch_enrich_bom_mock(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "1")
    from hardware_splicer.bom_generator import build_bom_from_graph, enrich_bom_with_jlcsearch

    graph = {"nodes": [{"id": "n1", "moduleId": "resistor-10k"}]}
    bom = build_bom_from_graph(graph)
    mock = MagicMock(spec=JlcSearchClient)
    mock.search_resistors.return_value = [{"lcsc": "C123", "mpn": "RC0603FR-0710KL"}]
    enriched = enrich_bom_with_jlcsearch(bom, client=mock)
    line = enriched["lines"][0]
    assert line.get("jlc_lcsc") == "C123"
    assert line.get("jlc_mpn") == "RC0603FR-0710KL"


@pytest.mark.skipif(not shutil.which("kicad-cli"), reason="kicad-cli required")
def test_schematic_export_minimal(tmp_path) -> None:
    graph = {
        "nodes": [{"id": "n1", "moduleId": "esp32-devkit"}],
        "edges": [],
    }
    netlist = build_graph_to_netlist(graph)
    sch = write_schematic_for_netlist(netlist, tmp_path / "t.kicad_sch", title="unit")
    assert Path(sch).is_file()
    text = Path(sch).read_text(encoding="utf-8")
    assert "kicad_sch" in text

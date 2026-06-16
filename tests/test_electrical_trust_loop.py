from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.electrical_simulation import run_electrical_simulation
from hardware_splicer.netlist.lower import build_graph_to_netlist
from hardware_splicer.trust_report import build_trust_report


def test_electrical_simulation_on_plant_watering_graph() -> None:
    graph = {
        "nodes": [
            {"id": "n1", "moduleId": "usb-power-5v"},
            {"id": "n2", "moduleId": "esp32-devkit"},
            {"id": "n3", "moduleId": "soil_moisture"},
            {"id": "n4", "moduleId": "mini-pump"},
        ],
        "wires": [],
    }
    netlist = build_graph_to_netlist(graph, source="test")
    sim = run_electrical_simulation(netlist)
    assert sim.get("enabled") is True
    assert sim.get("simulation_pass") is True
    budget = sim.get("power_budget") or {}
    assert float(budget.get("estimated_load_a") or 0) > 0.2


def test_trust_report_marks_build_trusted_when_clean(tmp_path: Path) -> None:
    quality = {
        "build_ready": True,
        "build_graph_compiled": True,
        "electrical_safety_pass": True,
        "kicad_drc_pass": True,
        "kicad_drc_errors": 0,
        "erc_pass": True,
        "fab_recommendation": "review_required_preview_copper",
    }
    sim = {"simulation_pass": True, "skipped": False, "power_budget": {"estimated_load_a": 0.4, "margin_a": 0.5}}
    report = build_trust_report(design_quality=quality, simulation=sim, build_id="sensor_logger")
    assert report["trust_level"] == "build_trusted"
    assert report["gates"]["simulation_pass"] is True


def test_compile_emits_trust_report(tmp_path: Path) -> None:
    result = compile_catalog_build("sensor_logger", tmp_path, export_gerber=False)
    build_dir = tmp_path / "build_compilation"
    trust = build_dir / "TRUST_REPORT.json"
    sim = build_dir / "ELECTRICAL_SIMULATION.json"
    assert trust.is_file(), "TRUST_REPORT.json missing"
    assert sim.is_file(), "ELECTRICAL_SIMULATION.json missing"
    payload = json.loads(trust.read_text(encoding="utf-8"))
    assert payload.get("trust_level") in {"build_trusted", "review_recommended"}
    assert result.design_quality.get("trust_report_path")

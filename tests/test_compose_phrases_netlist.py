"""Compose phrase → netlist round-trip → compile (general engine bar)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.build_compiler import compile_from_netlist
from hardware_splicer.module_picker import pick_modules_for_goal
from hardware_splicer.netlist.lower import build_graph_to_netlist, netlist_to_build_graph
from hardware_splicer.pcb.safety_rules import analyze_build

_PHRASES_PATH = Path(__file__).resolve().parent / "data" / "compose_phrases.json"


def _load_phrases() -> list[str]:
    rows = json.loads(_PHRASES_PATH.read_text(encoding="utf-8"))
    return [str(row["phrase"]) for row in rows if row.get("phrase")]


@pytest.mark.parametrize("phrase", _load_phrases())
def test_compose_phrase_netlist_roundtrip_compiles(tmp_path: Path, phrase: str) -> None:
    pick = pick_modules_for_goal(phrase)
    assert len(pick.module_ids) >= 2, f"picker too small for: {phrase!r}"

    graph = compose_build_graph_from_module_ids(pick.module_ids)["graph"]
    graph_errors = [w for w in analyze_build(graph) if w.get("level") == "error"]
    assert not graph_errors, f"{phrase!r} graph safety: {[w.get('message') for w in graph_errors]}"

    netlist = build_graph_to_netlist(graph, source=phrase)
    roundtrip = netlist_to_build_graph(netlist)
    rt_errors = [w for w in analyze_build(roundtrip) if w.get("level") == "error"]
    assert not rt_errors, f"{phrase!r} round-trip safety: {[w.get('message') for w in rt_errors]}"

    result = compile_from_netlist(netlist, tmp_path, export_gerber=False)
    quality = result.design_quality or {}
    assert result.ok is True, result.error
    assert quality.get("electrical_safety_pass") is True
    assert int(quality.get("kicad_drc_errors") or 0) == 0


def test_science_fair_plant_watering_picks_pump_stack() -> None:
    pick = pick_modules_for_goal("science fair plant watering")
    assert "soil_moisture" in pick.module_ids
    assert "water_pump_5v" in pick.module_ids
    assert "mosfet-irlz44n" in pick.module_ids

"""Offline phrase compatibility → netlist round-trip → deterministic truth bar.

Natural-language module picking remains an explicitly legacy/offline compatibility surface.
These tests must never turn a phrase match into engineering authority: safe picks may compile,
while an electrically incompatible legacy pick must remain blocked by ERC/DRC.  Model-enabled
product selection is separately pinned to stay unresolved rather than fall back to regex.
"""

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


def _direct_uncharacterized_mosfet_drive(module_ids: list[str]) -> bool:
    """Return true only for the known direct 3.3 V MCU → 4.5 V-characterized gate case.

    This is an electrical-contract expectation, not phrase classification.  If the offline
    compatibility composer later inserts an explicit interface/driver, the exception stops
    applying automatically.
    """

    ids = set(module_ids)
    return {
        "esp32-devkit",
        "mosfet-irlz44n",
    }.issubset(ids) and "level-shifter-4ch" not in ids


@pytest.mark.parametrize("phrase", _load_phrases())
def test_offline_phrase_netlist_roundtrip_respects_deterministic_truth(
    tmp_path: Path, phrase: str
) -> None:
    pick = pick_modules_for_goal(phrase)
    assert len(pick.module_ids) >= 2, f"offline compatibility picker too small for: {phrase!r}"

    graph = compose_build_graph_from_module_ids(pick.module_ids)["graph"]
    graph_errors = [w for w in analyze_build(graph) if w.get("level") == "error"]
    assert not graph_errors, f"{phrase!r} graph safety: {[w.get('message') for w in graph_errors]}"

    netlist = build_graph_to_netlist(graph, source=phrase)
    roundtrip = netlist_to_build_graph(netlist)
    rt_errors = [w for w in analyze_build(roundtrip) if w.get("level") == "error"]
    assert not rt_errors, f"{phrase!r} round-trip safety: {[w.get('message') for w in rt_errors]}"

    result = compile_from_netlist(netlist, tmp_path, export_gerber=False)
    quality = result.design_quality or {}

    if _direct_uncharacterized_mosfet_drive(pick.module_ids):
        assert result.ok is False
        assert quality.get("erc_pass") is False
        assert int(quality.get("erc_errors") or 0) > 0
        assert quality.get("circuit_readiness") == "erc_blocked"
        return

    assert result.ok is True, result.error
    assert quality.get("electrical_safety_pass") is True
    assert int(quality.get("kicad_drc_errors") or 0) == 0


def test_model_enabled_selection_does_not_fallback_to_regex(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed semantic selector must leave concrete identity unresolved."""

    monkeypatch.setattr(
        "hardware_splicer.integrations.llm_policy.offline_compose_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "hardware_splicer.integrations.qwen_module_pick.qwen_module_pick_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "hardware_splicer.integrations.qwen_module_pick.call_qwen_module_pick",
        lambda _goal: {"ok": False, "reason": "synthetic provider failure"},
    )

    pick = pick_modules_for_goal("science fair plant watering")

    assert pick.module_ids == []
    assert pick.hints == ["unresolved:synthetic provider failure"]

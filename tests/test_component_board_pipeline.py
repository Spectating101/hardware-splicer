"""Component-board pipeline: parts the design leaves unplaced are placed by HS, then routed and checked."""
from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hardware_splicer import component_board_pipeline as cbp
from hardware_splicer.routing_engine import resolve_kicad_python

ROOT = Path(__file__).resolve().parents[1]
BUS_A = ROOT / "projects" / "hs-bus-a"


def _kicad_ready() -> bool:
    py = resolve_kicad_python() or "/usr/bin/python3"
    jar = os.environ.get("HARDWARE_SPLICER_FREEROUTING_JAR")
    return bool(jar and Path(jar).is_file()) and subprocess.run([py, "-c", "import pcbnew"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _kicad_ready(), reason="needs KiCad's pcbnew Python and HARDWARE_SPLICER_FREEROUTING_JAR")
def test_unplaced_parts_are_placed_then_routed_with_retries(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(BUS_A))
    sys.modules.pop("design", None)
    from design import DESIGN  # HS-BUS-A, a board HS built and checked before
    free = [p.ref for p in DESIGN.parts if p.ref.startswith(("C", "R")) and p.pcb_xy][:6]
    design = dataclasses.replace(DESIGN, parts=[dataclasses.replace(p, pcb_xy=None) if p.ref in free else p for p in DESIGN.parts])
    sch = cbp.schematic_stage(design, tmp_path)
    assert sch["ok"], sch["problems"]
    pcb = cbp.pcb_stage(design, sch["readback"], tmp_path, {
        "outline_mm": [100, 100, 170, 156], "gnd_net": "GND",
        "netclasses": [{"name": "VIN", "track": 2.5, "clearance": 0.3, "via_d": 1.0, "via_drill": 0.5, "patterns": ["*VIN_12V"]}]})
    # placement is HS's and deterministic in what it must do
    assert sorted(pcb["placement"]["placed_by_hs"]) == sorted(free)
    assert not set(free) & set(pcb["placement"]["locked"])
    # routing is FreeRouting's and varies (5 of 14 attempts DRC-clean on this board): the stage must retry and report
    # honestly rather than always succeed
    assert 1 <= len(pcb["route_attempts"]) <= 6
    copper_done = bool((pcb.get("copper") or {}).get("complete")) or pcb.get("kicad_format") == "KiCad 10"
    assert pcb["ok"] == (pcb["route_attempts"][-1] == 0 or copper_done) == (not pcb["problems"])
    assert pcb["drc"]["schematic_parity"]["errors"] == 0


def test_a_fully_placed_design_does_not_run_the_placer(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cbp, "_place_free", lambda *a, **k: calls.append(a))
    design = cbp.design_from_json({"name": "x", "parts": [{"ref": "R1", "lib_id": "Device:R", "pcb_xy": [1, 2]}], "nets": {}})
    assert all(p.pcb_xy for p in design.parts) and not calls



def _stub_stage(monkeypatch, tmp_path, drc_errors):
    from types import SimpleNamespace
    from hardware_splicer import copper_route
    monkeypatch.setattr(cbp.kb, "pcb_spec", lambda *a, **k: {})
    monkeypatch.setattr(cbp, "_netname", lambda readback, plain: "/GND")

    def pcbnew(*args):
        Path(args[-1]).write_text("(kicad_pcb)")
        Path(args[-1]).with_suffix(".kicad_pro").write_text("{}")
    monkeypatch.setattr(cbp, "_pcbnew", pcbnew)
    monkeypatch.setattr(cbp, "route_pcb", lambda *a, **k: SimpleNamespace(text="(kicad_pcb)", stats={"nets_total": 3}))
    item = {"severity": "error", "type": "unconnected_items", "where": ["U1 pad 3"]}
    groups = {g: {"errors": drc_errors if g == "unconnected_items" else 0, "warnings": 0,
                  "items": [item] * drc_errors if g == "unconnected_items" else []}
              for g in ("violations", "unconnected_items", "schematic_parity")}
    monkeypatch.setattr(cbp.kb, "run_drc", lambda pcb, out: groups)
    calls = []

    def fake_copper(placed, out, **kw):
        calls.append(kw)
        return {"complete": True, "routed_board": str(out / "copper_project" / "board.kicad_pcb"), "router": "Freerouting 2.2.3 + guided router",
                "drc_errors": 0, "drc_unconnected": 0, "drc_warnings": 2, "unrouted_before": 9, "unrouted_after": 0}
    monkeypatch.setattr(copper_route, "route_with_copper", fake_copper)
    design = cbp.design_from_json({"name": "x", "parts": [{"ref": "R1", "lib_id": "Device:R", "pcb_xy": [1, 2]}], "nets": {}})
    return design, calls


def test_copper_finishes_when_every_freerouting_attempt_fails(monkeypatch, tmp_path):
    design, calls = _stub_stage(monkeypatch, tmp_path, drc_errors=1)
    res = cbp.pcb_stage(design, {}, tmp_path, {"outline_mm": [0, 0, 50, 40]}, route_attempts=2)
    assert res["ok"] and res["kicad_format"] == "KiCad 10" and res["route_attempts"] == [1, 1]
    assert calls == [{"pour_net": "/GND"}] and res["pcb"].endswith("board.kicad_pcb")


def test_copper_is_not_called_when_freerouting_comes_back_clean(monkeypatch, tmp_path):
    design, calls = _stub_stage(monkeypatch, tmp_path, drc_errors=0)
    res = cbp.pcb_stage(design, {}, tmp_path, {"outline_mm": [0, 0, 50, 40]}, route_attempts=2)
    assert res["ok"] and res["route_attempts"] == [0] and calls == [] and res.get("kicad_format") is None

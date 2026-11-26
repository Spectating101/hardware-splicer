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
def test_unplaced_parts_are_placed_routed_and_pass_drc(tmp_path, monkeypatch):
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
    assert pcb["ok"], pcb["problems"]
    assert sorted(pcb["placement"]["placed_by_hs"]) == sorted(free)
    assert not set(free) & set(pcb["placement"]["locked"])
    assert pcb["drc"]["unconnected_items"]["errors"] == 0 and pcb["drc"]["schematic_parity"]["errors"] == 0


def test_a_fully_placed_design_does_not_run_the_placer(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cbp, "_place_free", lambda *a, **k: calls.append(a))
    design = cbp.design_from_json({"name": "x", "parts": [{"ref": "R1", "lib_id": "Device:R", "pcb_xy": [1, 2]}], "nets": {}})
    assert all(p.pcb_xy for p in design.parts) and not calls

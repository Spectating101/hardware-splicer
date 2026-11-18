"""The cut model must not replace native curved copper with an endpoint chord."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "examples/arbitrage_lab/keyboard_splice/reference_1x6/one_row_six_key_source.kicad_pcb"
EXTRACT = ROOT / "src/hardware_splicer/_pcbnew_helpers/keyboard_splice_extract.py"
NATIVE = "/usr/bin/python3"


def _available():
    if not REFERENCE.is_file():
        return False
    try:
        result = subprocess.run([NATIVE, "-c", "import pcbnew"], capture_output=True, timeout=8)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(not _available(), reason="native KiCad pcbnew unavailable")
def test_classifies_switch_items_independently_of_vendor_library(tmp_path):
    board = tmp_path / "mixed.kicad_pcb"
    subprocess.run([NATIVE, "-c", """
import sys, pcbnew as p
b = p.LoadBoard(sys.argv[1])
items = [
    ("SW2_r1", "custom", "choc-v1-with-millmax"),
    ("K1", "parts", "SW_Cherry_MX_1.00u_PCB"),
    ("J1", "Kailh", "TRRS-PJ-320A"),
    ("G***", "Kailh", "ferris_broom"),
    ("POWER SW", "Kailh", "SPDT_C128955"),
    ("RSW1", "kbd", "SW_SPST_B3U-1000P"),
]
keys = [f for f in b.GetFootprints() if f.GetReference().startswith("SW")]
for f, (ref, lib, name) in zip(keys, items, strict=True):
    f.SetReference(ref)
    f.SetValue("SW_Push")
    f.SetFPID(p.LIB_ID(lib, name))
p.SaveBoard(sys.argv[2], b)
""", str(REFERENCE), str(board)], check=True, timeout=30)
    raw = subprocess.check_output([NATIVE, str(EXTRACT), "--pcb", str(board)], timeout=30)
    assert sorted(f["ref"] for f in json.loads(raw)["switch_positions"]) == ["K1", "SW2_r1"]


@pytest.mark.skipif(not _available(), reason="native KiCad pcbnew unavailable")
def test_cut_extraction_rejects_real_arc_whose_copper_leaves_endpoint_chord(tmp_path):
    derived = tmp_path / "curved-copper.kicad_pcb"
    created = subprocess.run([
        NATIVE, "-c", """
import json,sys
import pcbnew as p
b=p.LoadBoard(sys.argv[1])
pt=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
a=p.PCB_ARC(b)
a.SetStart(pt(10,70));a.SetMid(pt(15,65));a.SetEnd(pt(20,70))
a.SetWidth(p.FromMM(.4));a.SetLayer(p.F_Cu);a.SetNet(b.FindNet('ROW_0'))
b.Add(a);p.SaveBoard(sys.argv[2],b)
reopened=p.LoadBoard(sys.argv[2])
arcs=[t for t in reopened.GetTracks() if type(t).__name__=='PCB_ARC']
assert len(arcs)==1
a=arcs[0]
mm=lambda v:[p.ToMM(v.x),p.ToMM(v.y)]
print(json.dumps({'type':type(a).__name__,'start':mm(a.GetStart()),
                  'mid':mm(a.GetMid()),'end':mm(a.GetEnd()),'width':p.ToMM(a.GetWidth())}))
""", str(REFERENCE), str(derived),
    ], capture_output=True, text=True, timeout=30)
    assert created.returncode == 0, created.stderr
    geometry = json.loads(created.stdout)
    assert geometry == {
        "type": "PCB_ARC", "start": [10.0, 70.0], "mid": [15.0, 65.0],
        "end": [20.0, 70.0], "width": .4,
    }
    # A monotone cut passing through (15,65), then x=25 at y=70, hits this
    # real arc and misses the chord's copper by 4.8 mm. It previously passed
    # extraction with no geometry warning and could therefore appear clear.
    assert abs(geometry["start"][1] - geometry["mid"][1]) - geometry["width"] / 2 == 4.8
    before = hashlib.sha256(derived.read_bytes()).hexdigest()
    result = subprocess.run([NATIVE, str(EXTRACT), "--pcb", str(derived)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "Unsupported curved copper PCB_ARC" in result.stderr
    assert not result.stdout.strip(), "rejected copper must not produce a usable extraction"
    assert hashlib.sha256(derived.read_bytes()).hexdigest() == before

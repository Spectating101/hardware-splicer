"""Free-footprint placer on a real board: every free part lands inside the outline, clear of every other part."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "src/hardware_splicer/_pcbnew_helpers/place_free_footprints.py"
BOARD = ROOT / "projects/hs-bus-a/kicad/hs_bus_a.kicad_pcb"
KICAD_PY = "/usr/bin/python3"

CHECK = r'''
import json, sys, pcbnew
sys.path.insert(0, sys.argv[2]); import place_free_footprints as pf
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox(); edge = (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))
boxes = {fp.GetReference(): pf.keep_clear_box(fp) for fp in b.GetFootprints()}
inside = all(edge[0] + 1.0 <= x0 and edge[1] + 1.0 <= y0 and x1 <= edge[2] - 1.0 and y1 <= edge[3] - 1.0
             for r, (x0, y0, x1, y1) in boxes.items() if not r.startswith("J"))
refs = sorted(boxes); overlaps = []
for i, a in enumerate(refs):
    for c in refs[i + 1:]:
        A, C = boxes[a], boxes[c]
        if A[0] < C[2] and C[0] < A[2] and A[1] < C[3] and C[1] < A[3]:
            overlaps.append((a, c))
print(json.dumps({"inside": inside, "overlaps": overlaps, "flipped": [fp.GetReference() for fp in b.GetFootprints() if fp.IsFlipped()]}))
'''


@pytest.mark.skipif(not Path(KICAD_PY).is_file() or subprocess.run([KICAD_PY, "-c", "import pcbnew"], capture_output=True).returncode,
                    reason="needs KiCad's pcbnew Python")
def test_free_parts_are_placed_on_the_board_and_clear_of_each_other(tmp_path):
    out = tmp_path / "placed.kicad_pcb"
    run = subprocess.run([KICAD_PY, str(HELPER), str(BOARD), str(out), "--locked", "J1,J2,J3,J4,J5", "--gap", "0.3", "--passes", "1"],
                         capture_output=True, text=True, timeout=600)
    assert run.returncode == 0, run.stderr[-2000:]
    placed = json.loads(run.stdout.strip().splitlines()[-1])["placed"]
    assert placed >= 30
    check = subprocess.run([KICAD_PY, "-c", CHECK, str(out), str(HELPER.parent)], capture_output=True, text=True, timeout=300)
    assert check.returncode == 0, check.stderr[-2000:]
    res = json.loads(check.stdout.strip().splitlines()[-1])
    assert res["inside"] and not res["overlaps"] and not res["flipped"], res

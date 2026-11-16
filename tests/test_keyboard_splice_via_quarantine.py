"""Do not confuse floating source copper with a verified or powered repair."""
from __future__ import annotations

import subprocess
import sys

import pytest


def python_with_shapes():
    for candidate in (sys.executable,"/usr/bin/python3"):
        try:
            check=subprocess.run([candidate,"-c","import shapely"],
                                 capture_output=True,timeout=8)
            if check.returncode==0:return candidate
        except (OSError,subprocess.TimeoutExpired):
            continue
    return ""


PYTHON=python_with_shapes()
pytestmark=pytest.mark.skipif(not PYTHON,reason="native Shapely not available")


@pytest.mark.parametrize("kind,area,via_count,expected",[
    ("tracks_only",6.0,0,True),
    ("tracks_only",8.0,0,False),
    ("track_with_vias",15.9,2,True),
    ("track_with_vias",25.1,2,False),
    ("track_with_vias",15.9,5,False),
    ("contains_pad",2.0,0,False),
    ("contains_copper_zone",2.0,0,False),
])
def test_terminal_free_source_copper_only_prunes_bounded_nonfunctional_fragments(
    kind,area,via_count,expected
):
    script=r'''
import json
from types import SimpleNamespace
from keyboard_splice_repair import classify_inert_cut_remnant
kind,area,count=json.loads(__import__("sys").argv[1])
fragments=[{"kind":"track","geometry":SimpleNamespace(area=area)}]
if kind=="track_with_vias":
    fragments=[{"kind":"track","geometry":SimpleNamespace(area=area/2)}]
    fragments += [{"kind":"via","geometry":SimpleNamespace(area=area/(2*count))}
                  for _ in range(count)]
elif kind=="contains_pad":
    fragments.append({"kind":"pad","geometry":SimpleNamespace(area=0.01)})
elif kind=="contains_copper_zone":
    fragments.append({"kind":"zone","geometry":SimpleNamespace(area=0.01)})
result=classify_inert_cut_remnant(fragments,list(range(len(fragments))))
print(json.dumps(result))
'''
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    env=__import__("os").environ.copy()
    env["PYTHONPATH"]=str(root/"src/hardware_splicer/_pcbnew_helpers")
    run=subprocess.run([PYTHON,"-c",script,
         __import__("json").dumps([kind,area,via_count])],
        capture_output=True,text=True,env=env,timeout=20)
    assert run.returncode==0,run.stderr
    outcome=__import__("json").loads(run.stdout)
    assert bool(outcome)==expected
    if outcome:
        assert outcome["retained_electrical_terminal_count"]==0
        assert outcome["physical_discard_verified"] is False
        assert outcome["physical_insulation_verified"] is False
        if kind=="track_with_vias":
            assert outcome["decision"]=="PLAN_QUARANTINE_FLOATING_TRACK_AND_VIA_ISLAND"

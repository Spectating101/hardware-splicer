"""The copper repair operator must iterate past the first incomplete design."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from hardware_splicer.keyboard_splice_repair_loop import run_repair_loop

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "src/hardware_splicer/_pcbnew_helpers/keyboard_splice_islands.py"


def native_available():
    try:
        for python in (sys.executable, "/usr/bin/python3"):
            call = subprocess.run([python, "-c", "import shapely"], capture_output=True, timeout=7)
            if call.returncode == 0:
                return python
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


PYTHON = native_available()
pytestmark = pytest.mark.skipif(not PYTHON, reason="Shapely unavailable")


def board():
    return {
        "source_sha256": "a" * 64,
        "outline_bbox_mm": {"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 50},
        "tracks": [{
            "net": "row1", "x1": 10, "y1": 20, "x2": 90, "y2": 20,
            "layer": "F.Cu", "width_mm": 0.5,
        }],
        "pads": [{
            "net": "row1", "ref": ref, "pad": "1", "x": x, "y": 20,
            "pad_attribute": 1, "pad_shape": 0, "orientation_degrees": 0,
            "size_x_mm": 2, "size_y_mm": 2, "layer": "F.Cu",
        } for ref, x in (("S1", 10), ("S2", 90))],
        "vias": [], "filled_zones": [], "zone_count": 0,
        "source_warnings": [], "copper_layer_count": 2,
    }


def evaluate(tmp_path, data, *, mode="auto"):
    return run_repair_loop(
        script=NATIVE, interpreter=PYTHON, source_board=data,
        net_names=["row1"], seam_x=50.0, kerf_mm=1.0,
        path_file=None, topology_file=tmp_path / "out.json",
        edge_csv=tmp_path / "out.csv", repair_mode=mode,
    )


def test_auto_stops_at_correct_pad_only_solution(tmp_path):
    out=evaluate(tmp_path, board())
    assert out["total_iterations"] == 1
    assert out["selected_strategy"] == "pad_only"
    assert out["required_graph_connected_in_model"] is True
    assert not out["physical_authority_granted"]
    t=json.loads((tmp_path/"out.json").read_text())
    assert t["model_replay_remaining_required_components"]==0
    assert t["candidate_graph_edges"]==1
    assert t["preexisting_unconnected_terminal_net_count"]==0
    assert (tmp_path/"out.csv").read_text().count("\n")==2


def test_auto_escalates_to_via_contacts_instead_of_stopping(tmp_path):
    b=board()
    b["pads"]=[]
    b["vias"]=[
        {"net":"row1","x":x,"y":20,"diameter_mm":1,"via_type":"3"}
        for x in (20,80)
    ]
    out=evaluate(tmp_path,b)
    assert out["selected_strategy"]=="adaptive"
    assert out["total_iterations"]==2
    assert out["iterations"][0]["unconnected_required_groups"]==1
    assert out["iterations"][1]["unconnected_required_groups"]==0
    assert out["iterations"][1]["contact_kinds"]["via_annulus"]==2
    t=json.loads((tmp_path/"out.json").read_text())
    edge=t["bridge_edges"][0]
    assert edge["from_candidate_contact"]["contact_type"]=="via_annulus"
    assert edge["to_candidate_contact"]["contact_type"]=="via_annulus"
    assert edge["from_candidate_pad"] is None
    assert out["fabrication_release"]=="BLOCKED_REFERENCE_ONLY"


def test_repair_loop_rejects_unknown_strategy_and_no_source(tmp_path):
    with pytest.raises(ValueError,match="unsupported repair strategy"):
        evaluate(tmp_path,board(),mode="authorize_it")
    b=board()
    b["source_sha256"]=""
    with pytest.raises((ValueError,KeyError),match="source|digest"):
        evaluate(tmp_path,b)


def test_adaptive_mode_does_not_invent_alternate_contacts(tmp_path):
    b=board()
    b["pads"]=[]
    b["tracks"][0]["width_mm"]=0.2
    out=evaluate(tmp_path,b,mode="adaptive")
    assert out["total_iterations"]==1
    assert not out["required_graph_connected_in_model"]
    assert out["iterations"][0]["unconnected_required_groups"]==1

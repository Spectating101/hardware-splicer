"""A stepped cut is a geometrical proposal, not a physical authority claim."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "src/hardware_splicer/_pcbnew_helpers/keyboard_splice_path.py"
def select_topology_python():
    for candidate in (sys.executable, "/usr/bin/python3"):
        try:
            out = subprocess.run([candidate, "-c", "import shapely,numpy"],
                                 capture_output=True, timeout=10)
            if out.returncode == 0:
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            pass
    return ""


SYSTEM_PYTHON = select_topology_python()
pytestmark = pytest.mark.skipif(not SYSTEM_PYTHON, reason="Shapely/numpy unavailable")


def fixture_board():
    return {
        "source_sha256": "a" * 64,
        "outline_bbox_mm": {"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 60},
        "tracks": [
            {"x1": 10, "y1": 15, "x2": 90, "y2": 15,
             "width_mm": 0.5, "net": "row1", "layer": "F.Cu"},
        ],
        "pads": [
            {"x": x, "y": 15, "size_x_mm": 1.5, "size_y_mm": 1.5,
             "orientation_degrees": 0, "pad_shape": 0, "pad_attribute": 1,
             "net": "row1", "layer": "F.Cu", "ref": ref, "pad": "1"}
            for x, ref in [(10, "S1"), (90, "S2")]
        ],
        "vias": [],
        "switch_positions": [
            {"x": 20, "y": 15, "value": "MX", "ref": "S1"},
            {"x": 80, "y": 15, "value": "MX", "ref": "S2"},
        ],
        "footprints": [{"x": 50, "y": 30, "ref": "IC1", "value": "MCU"}],
        "filled_zones": [],
        "zone_count": 0, "rule_area_count": 0,
        "copper_layer_count": 2,
        "source_warnings": [],
    }


def run_path(tmp_path, board):
    b = tmp_path / "board.json"
    out = tmp_path / "path.json"
    b.write_text(json.dumps(board), encoding="utf-8")
    proc = subprocess.run([SYSTEM_PYTHON, str(HELPER), "--board-json", str(b),
                           "--output", str(out)], capture_output=True, text=True, timeout=35)
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def test_route_around_center_controller_and_bind_source(tmp_path):
    board = fixture_board()
    result = run_path(tmp_path, board)
    assert result["source_sha256"] == board["source_sha256"]
    assert result["physical_cut_authorized"] is False
    assert result["release"] == "PROPOSED_CUT_ONLY_NOT_VERIFIED"
    assert result["collision_counts"]["critical"] == 0
    assert result["affected_nets"] == ["row1"]
    assert max(x for x, _ in result["cut_points_mm"]) - min(
        x for x, _ in result["cut_points_mm"]) > 2
    assert result["cut_points_mm"][0][1] == 0
    assert result["cut_points_mm"][-1][1] == 60
    assert 0 < result["switch_candidates_left"] < 3
    data = {k: v for k, v in result.items() if k != "payload_sha256"}
    assert hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest() == result["payload_sha256"]


def test_missing_controller_or_missing_digest_fails_closed(tmp_path):
    board = fixture_board()
    board["footprints"] = []
    p = tmp_path / "input.json"
    p.write_text(json.dumps(board), encoding="utf-8")
    out = subprocess.run([SYSTEM_PYTHON, str(HELPER), "--board-json", str(p),
                          "--output", str(tmp_path / "out.json")], capture_output=True, text=True, timeout=35)
    assert out.returncode != 0
    assert "no distinguishable controller" in out.stderr

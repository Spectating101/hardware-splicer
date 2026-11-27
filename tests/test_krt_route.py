"""KiCadRoutingTools as HS's second router: refuses clearly when not configured; the trial record keeps its numbers."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hardware_splicer import krt_route

ROOT = Path(__file__).resolve().parents[1]


def test_unconfigured_krt_names_what_to_set(tmp_path, monkeypatch):
    monkeypatch.delenv("HARDWARE_SPLICER_KRT_SRC", raising=False)
    board = tmp_path / "b.kicad_pcb"
    board.write_text("(kicad_pcb)")
    with pytest.raises(krt_route.KrtRouteError, match="HARDWARE_SPLICER_KRT_SRC"):
        krt_route.route_with_krt(board, tmp_path / "out.kicad_pcb")


def test_the_trial_record_shows_why_widths_are_passed_explicitly():
    rec = json.loads((ROOT / "examples/routing_trial/krt_vs_copper_20261128.json").read_text())
    assert all(b["krt"]["unconnected"] == 0 for b in rec["boards"])
    hs = rec["hs_bus_a"]
    assert hs["autoroute"]["track_widths_mm"]["VIN_12V"] == 0.3 and "unsafe" in hs["autoroute"]["track_check"]
    assert hs["route_py_with_widths"]["track_widths_mm"] == {"VIN_12V": 2.5, "DXL_VDD*": 1.2}


@pytest.mark.skipif(not os.environ.get("HARDWARE_SPLICER_KRT_SRC"), reason="KiCadRoutingTools not configured")
def test_krt_routes_a_placed_board_with_the_widths_it_is_given(tmp_path):
    placed = os.environ.get("HS_TEST_PLACED_BOARD")
    if not placed:
        pytest.skip("set HS_TEST_PLACED_BOARD to a placed board (projects/hs-bus-a/build_board.py --stage place)")
    from hardware_splicer import trace_capacity as tc

    res = krt_route.route_with_krt(Path(placed), tmp_path / "routed.kicad_pcb", power_widths={"*VIN_12V": 2.5, "*DXL_VDD*": 1.2})
    widths = tc.routed_widths(Path(res["routed_board"]))
    assert res["complete"] and widths["/VIN_12V"]["outer_min_mm"] >= 2.5

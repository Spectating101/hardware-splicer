"""Copper as HS's outside router: refuses clearly when not configured; the trial record says what was measured."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hardware_splicer import copper_route
from hardware_splicer import engineering_toolbelt as tb

ROOT = Path(__file__).resolve().parents[1]


def test_unconfigured_copper_names_what_to_set(tmp_path, monkeypatch):
    for key in ("HARDWARE_SPLICER_COPPER_SRC", "HARDWARE_SPLICER_COPPER_JAVA", "HARDWARE_SPLICER_COPPER_FREEROUTING_JAR"):
        monkeypatch.delenv(key, raising=False)
    board = tmp_path / "b.kicad_pcb"
    board.write_text("(kicad_pcb)")
    with pytest.raises(copper_route.CopperRouteError, match="HARDWARE_SPLICER_COPPER_SRC"):
        copper_route.route_with_copper(board, tmp_path / "out")
    env = tb.call("hs_route_copper", {"pcb": str(board)})
    assert not env["ok"] and "not configured" in env["problems"][0]


def test_not_a_board_is_refused(tmp_path):
    with pytest.raises(copper_route.CopperRouteError, match="not a KiCad board"):
        copper_route.route_with_copper(tmp_path / "missing.kicad_pcb", tmp_path)


def test_trial_record_counts_complete_runs():
    rec = json.loads((ROOT / "examples/routing_trial/copper_vs_hs_bus_a_20261127.json").read_text())
    hs_done = sum(r["unconnected_after_drc"] == 0 and r["drc_errors"] == 0 for r in rec["hs"]["runs"])
    copper_done = sum(r["unrouted_after"] == 0 and r["drc_errors"] == 0 for r in rec["copper"]["runs"])
    assert (hs_done, copper_done) == (2, 5) and rec["hs"]["complete"] == "2 of 5" and rec["copper"]["complete"] == "5 of 5"


@pytest.mark.skipif(not os.environ.get("HARDWARE_SPLICER_COPPER_SRC"), reason="Copper not configured")
def test_copper_routes_hs_bus_a_placement(tmp_path):
    placed = os.environ.get("HS_TEST_PLACED_BOARD")
    if not placed:
        pytest.skip("set HS_TEST_PLACED_BOARD to a placed board (projects/hs-bus-a/build_board.py --stage place)")
    res = copper_route.route_with_copper(Path(placed), tmp_path)
    assert res["complete"] and res["kicad_format"] == "KiCad 10"

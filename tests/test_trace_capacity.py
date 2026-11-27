"""IPC-2221 track widths: the formula, net classes from currents, and the routed board's narrowest track."""
from pathlib import Path

import pytest

from hardware_splicer import trace_capacity as tc
from hardware_splicer.component_board_pipeline import current_netclasses

BUS_A = Path(__file__).resolve().parents[1] / "projects" / "hs-bus-a" / "kicad" / "hs_bus_a.kicad_pcb"


def test_width_and_rise_invert_each_other():
    for amps in (0.5, 2.5, 5.0, 10.0):
        width = tc.width_for_current(amps, rise_c=10)
        assert tc.temperature_rise(amps, width) <= 10 + 1e-6
        assert tc.temperature_rise(amps, width - 0.05) > 10 or width - 0.05 <= 0
    assert tc.width_for_current(5, 10, external=False) > tc.width_for_current(5, 10)  # inner layers shed heat worse


def test_hs_bus_a_tracks_match_its_own_checks():
    # HS-BUS-A's verification.json: 11.8 C at the 5 A supply limit on 2.5 mm, 8.2 C at the 2.5 A port fuse hold on 1.2 mm.
    report = tc.check_routed(BUS_A, {"*VIN_12V": 5.0, "*DXL_VDD*": 2.5})
    rises = {row["net"]: row["worst_rise_c"] for row in report["nets"]}
    assert rises["/VIN_12V"] == pytest.approx(11.8, abs=0.1)
    assert rises["/DXL_VDD1"] == pytest.approx(8.2, abs=0.1) and report["findings"] == []
    hot = tc.check_routed(BUS_A, {"*VIN_12V": 10.0})
    assert [f["rule"] for f in hot["findings"]] == ["track_too_narrow_for_current"]


def test_currents_become_net_classes_and_explicit_ones_win():
    board = {"net_currents_a": {"*VIN_12V": 5, "VBUS": 0.2}, "netclasses": []}
    classes = current_netclasses(board, {"track": 0.2, "clearance": 0.15})
    assert [(c["patterns"], c["track"]) for c in classes] == [(["*VIN_12V"], 2.8)]  # 0.2 A keeps the default track
    mine = {"name": "VIN", "track": 2.5, "patterns": ["*VIN_12V"]}
    assert current_netclasses(dict(board, netclasses=[mine]), {"track": 0.2}) == [mine]


def test_a_pour_only_net_is_not_judged():
    report = tc.check_routed(BUS_A, {"NO_SUCH_NET": 3.0})
    assert [f["rule"] for f in report["findings"]] == ["current_net_without_tracks"]


def test_the_toolbelt_reports_the_hottest_track():
    from hardware_splicer import engineering_toolbelt as tb

    env = tb.call("hs_trace_current", {"pcb": str(BUS_A), "net_currents_a": {"*VIN_12V": 5.0}})
    assert env["ok"] and "/VIN_12V" in env["summary"]

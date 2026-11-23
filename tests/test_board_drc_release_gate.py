"""An attached KiCad board must pass KiCad's own DRC, with no open connections, before it can count
toward a release, however it was attached."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hardware_splicer import mechatronics_authority
from hardware_splicer.mechatronics_authority import _electrical_status, build_mechatronics_authority

ROOT = Path(__file__).resolve().parents[1]
SHORTED_BOARD = ROOT / "examples" / "main_ctrl_esp32_servo.kicad_pcb"
CLEAN_BOARD = ROOT / "hardware" / "reference_designs" / "spi_flash_adapter_v1" / "spi_flash_adapter_v1.kicad_pcb"

FAILING = {"pass": False, "skipped": False, "errors": 92, "report_errors": 92, "unconnected_items": []}
CLEAN = {"pass": True, "skipped": False, "errors": 0, "report_errors": 0, "unconnected_items": []}


@pytest.fixture(autouse=True)
def _fresh_cache():
    mechatronics_authority._DRC_CACHE.clear()
    yield
    mechatronics_authority._DRC_CACHE.clear()


def _body(files, boards=None):
    # Everything else says "release": production authority is attached and nothing blocks.
    return {
        "machine": {"boards": boards or [{"board_id": "main_ctrl", "requirements": {}}]},
        "board_design_files": files,
        "circuit_authority": {"production_authorized": True},
    }


def _fake(monkeypatch, result, calls=None):
    def run(path, out_dir=None, timeout_s=120):
        if calls is not None:
            calls.append(str(path))
        return dict(result)
    monkeypatch.setattr("hardware_splicer.pcb.kicad_cli_drc.run_kicad_cli_drc", run)


def test_a_failing_board_blocks_release_even_with_production_authority(monkeypatch):
    _fake(monkeypatch, FAILING)
    status = _electrical_status(_body({"main_ctrl": {"path": str(SHORTED_BOARD), "kind": "pcb"}}), {})
    assert status["release_ready"] is False
    assert status["drc_blockers"] == ["Attached board main_ctrl fails KiCad DRC: 92 error(s)."]
    assert status["board_drc"]["main_ctrl"]["pass"] is False


def test_open_connections_block_release(monkeypatch):
    _fake(monkeypatch, {**CLEAN, "unconnected_items": [{"items": []}, {"items": []}]})
    status = _electrical_status(_body({"main_ctrl": {"path": str(CLEAN_BOARD)}}), {})
    assert status["release_ready"] is False
    assert status["drc_blockers"] == ["Attached board main_ctrl fails KiCad DRC: 2 unconnected item(s)."]


def test_an_unrun_or_unparsed_drc_blocks_release(monkeypatch):
    _fake(monkeypatch, {"pass": None, "skipped": True, "reason": "kicad-cli not on PATH"})
    assert "not run on attached board main_ctrl: kicad-cli not on PATH" in \
        _electrical_status(_body({"main_ctrl": {"path": str(SHORTED_BOARD)}}), {})["drc_blockers"][0]
    mechatronics_authority._DRC_CACHE.clear()
    _fake(monkeypatch, {"pass": False, "skipped": False, "errors": 1, "report_errors": None, "reason": "kicad-cli timed out"})
    assert _electrical_status(_body({"main_ctrl": {"path": str(SHORTED_BOARD)}}), {})["drc_blockers"] == [
        "KiCad DRC could not check attached board main_ctrl: kicad-cli timed out."]


@pytest.mark.parametrize("files, boards", [
    ({"main_ctrl": {"path": f"{SHORTED_BOARD}  "}}, None),                      # trailing whitespace
    ({"main_ctrl": {"path": str(SHORTED_BOARD).replace(".kicad_pcb", ".KICAD_PCB")}}, None),  # extension case
    ({"main_ctrl": str(SHORTED_BOARD)}, None),                                 # bare string entry
    ({"main_ctrl": {"kind": "pcb"}}, None),                                     # a board with no path
    ({}, [{"board_id": "main_ctrl", "requirements": {}, "pcb_path": str(SHORTED_BOARD)}]),  # machine pcb_path
    ({"main_ctrl": {"path": "main_ctrl_esp32_servo.kicad_pcb"}}, None),          # relative, as the compiler resolves it
])
def test_every_way_of_attaching_a_board_is_checked(monkeypatch, files, boards):
    calls = []
    _fake(monkeypatch, FAILING, calls)
    status = _electrical_status(_body(files, boards), {})
    assert status["release_ready"] is False and status["drc_blockers"]


def test_a_relative_path_is_resolved_like_the_compiler(monkeypatch, tmp_path):
    calls = []
    _fake(monkeypatch, CLEAN, calls)
    monkeypatch.chdir(tmp_path)
    _electrical_status(_body({"main_ctrl": {"path": "main_ctrl_esp32_servo.kicad_pcb"}}), {})
    assert calls == [str(SHORTED_BOARD.resolve())]


def test_colliding_board_ids_are_all_checked(monkeypatch):
    calls = []
    _fake(monkeypatch, CLEAN, calls)
    status = _electrical_status(_body({1: {"path": str(SHORTED_BOARD)}, "1": {"path": str(CLEAN_BOARD)}}), {})
    assert sorted(status["board_drc"]) == ["1", "1#2"] and len(calls) == 2


def test_netlists_are_not_boards(monkeypatch):
    calls = []
    _fake(monkeypatch, FAILING, calls)
    status = _electrical_status(_body({"main_ctrl": {"path": "examples/main_ctrl_esp32_servo.net", "kind": "netlist"}}), {})
    assert calls == [] and status["release_ready"] is True


def test_drc_is_not_run_when_release_is_blocked_anyway(monkeypatch):
    calls = []
    _fake(monkeypatch, FAILING, calls)
    body = {**_body({"main_ctrl": {"path": str(SHORTED_BOARD)}}), "circuit_authority": {}}
    status = _electrical_status(body, {})
    assert calls == [] and status["release_ready"] is False and status["boards_not_checked"] == ["main_ctrl"]


def test_drc_results_are_cached_per_file(monkeypatch):
    calls = []
    _fake(monkeypatch, CLEAN, calls)
    for _ in range(3):
        _electrical_status(_body({"main_ctrl": {"path": str(CLEAN_BOARD)}}), {})
    assert len(calls) == 1


def test_too_many_boards_block_instead_of_running(monkeypatch):
    calls = []
    _fake(monkeypatch, CLEAN, calls)
    files = {f"b{i}": {"path": str(CLEAN_BOARD)} for i in range(17)}
    status = _electrical_status(_body(files), {})
    assert calls == [] and status["release_ready"] is False


def test_the_drc_reason_reaches_the_release_stage_and_next_actions(monkeypatch):
    _fake(monkeypatch, FAILING)
    authority = build_mechatronics_authority(_body({"main_ctrl": {"path": str(SHORTED_BOARD)}}), engineering={})
    text = str(authority)
    assert "fails KiCad DRC: 92 error(s)" in text
    assert any("fails KiCad DRC" in row for row in authority["next_engineering_actions"])


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_the_real_pan_tilt_board_is_blocked_and_a_clean_board_is_not():
    shorted = _electrical_status(_body({"main_ctrl": {"path": str(SHORTED_BOARD), "kind": "pcb"}}), {})
    assert shorted["release_ready"] is False and shorted["board_drc"]["main_ctrl"]["report_errors"] > 0
    assert _electrical_status(_body({"main_ctrl": {"path": str(CLEAN_BOARD), "kind": "pcb"}}), {})["release_ready"] is True

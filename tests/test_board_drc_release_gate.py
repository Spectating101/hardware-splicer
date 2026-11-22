"""An attached KiCad board must pass KiCad's own DRC before it can count toward a release."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hardware_splicer import mechatronics_authority
from hardware_splicer.mechatronics_authority import _electrical_status

ROOT = Path(__file__).resolve().parents[1]
SHORTED_BOARD = ROOT / "examples" / "main_ctrl_esp32_servo.kicad_pcb"
CLEAN_BOARD = ROOT / "hardware" / "reference_designs" / "spi_flash_adapter_v1" / "spi_flash_adapter_v1.kicad_pcb"


def _body(path):
    # Everything else says "release": production authority is attached and nothing blocks.
    return {
        "machine": {"boards": [{"board_id": "main_ctrl", "requirements": {}}]},
        "board_design_files": {"main_ctrl": {"path": str(path), "kind": "pcb"}},
        "circuit_authority": {"production_authorized": True},
    }


def _fake_drc(result):
    return lambda path, out_dir=None, timeout_s=120: dict(result)


def test_a_failing_board_blocks_release_even_with_production_authority(monkeypatch):
    monkeypatch.setattr("hardware_splicer.pcb.kicad_cli_drc.run_kicad_cli_drc",
                        _fake_drc({"pass": False, "skipped": False, "errors": 92, "report_errors": 92}))
    status = _electrical_status(_body(SHORTED_BOARD), {})
    assert status["release_ready"] is False
    assert any("fails KiCad DRC: 92 error(s)" in row for row in status["release_blockers"])
    assert status["board_drc"]["main_ctrl"]["pass"] is False


def test_an_unrun_drc_blocks_release(monkeypatch):
    monkeypatch.setattr("hardware_splicer.pcb.kicad_cli_drc.run_kicad_cli_drc",
                        _fake_drc({"pass": None, "skipped": True, "reason": "kicad-cli not on PATH"}))
    status = _electrical_status(_body(SHORTED_BOARD), {})
    assert status["release_ready"] is False
    assert any("not run on attached board main_ctrl" in row for row in status["release_blockers"])


def test_a_passing_board_leaves_the_other_evidence_in_charge(monkeypatch):
    monkeypatch.setattr("hardware_splicer.pcb.kicad_cli_drc.run_kicad_cli_drc",
                        _fake_drc({"pass": True, "skipped": False, "errors": 0, "report_errors": 0}))
    assert _electrical_status(_body(CLEAN_BOARD), {})["release_ready"] is True


def test_netlists_are_not_boards():
    assert mechatronics_authority._attached_board_drc({"main_ctrl": {"path": "examples/main_ctrl_esp32_servo.net"}}) == {}


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_the_real_pan_tilt_board_is_blocked_and_a_clean_board_is_not():
    shorted = _electrical_status(_body(SHORTED_BOARD), {})
    assert shorted["release_ready"] is False and shorted["board_drc"]["main_ctrl"]["report_errors"] > 0
    assert _electrical_status(_body(CLEAN_BOARD), {})["release_ready"] is True

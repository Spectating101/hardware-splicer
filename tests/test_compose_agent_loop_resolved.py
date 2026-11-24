"""agent_loop.resolved means the gate says build ready, not only that DRC found nothing.

Probe on main: a pan-tilt compose with an ERC failure reported agent_loop.resolved true (zero DRC errors)
next to a gate that blocked on ERC.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer.compose_agent_loop import compose_agent_loop


def _dispatch_returning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, drc_errors: int, gate: dict | None) -> None:
    def fake(**kwargs):
        result = {
            "ok": bool(gate and gate.get("build_ready")),
            "mode": "scratch",
            "out_dir": str(tmp_path),
            "design_quality": {"kicad_drc_errors": drc_errors},
        }
        if gate is not None:
            result["design_quality_gate"] = gate
        return result

    monkeypatch.setattr("hardware_splicer.compose_agent_loop.compose_dispatch", fake)
    monkeypatch.setattr("hardware_splicer.compose_agent_loop._error_violations", lambda build_dir: [])


def _loop(tmp_path: Path) -> dict:
    return compose_agent_loop(module_ids=["esp32-devkit", "bme280"], out_dir=tmp_path, max_manual_retries=0)["agent_loop"]


def test_zero_drc_errors_with_an_erc_blocked_gate_is_not_resolved(tmp_path, monkeypatch) -> None:
    gate = {
        "build_ready": False,
        "drc_pass": True,
        "blockers": ["KiCad ERC failed with 2 error(s).", "Electrical safety checks failed on the compiled build graph."],
    }
    _dispatch_returning(tmp_path, monkeypatch, drc_errors=0, gate=gate)

    loop = _loop(tmp_path)

    assert loop["final_kicad_drc_errors"] == 0
    assert loop["resolved"] is False
    assert loop["gate_build_ready"] is False
    assert "KiCad ERC failed with 2 error(s)." in loop["unresolved_reasons"]


def test_zero_drc_errors_and_a_build_ready_gate_is_resolved(tmp_path, monkeypatch) -> None:
    _dispatch_returning(tmp_path, monkeypatch, drc_errors=0, gate={"build_ready": True, "blockers": []})

    loop = _loop(tmp_path)

    assert loop["resolved"] is True
    assert loop["unresolved_reasons"] == []


def test_a_build_ready_gate_with_drc_errors_is_not_resolved(tmp_path, monkeypatch) -> None:
    _dispatch_returning(tmp_path, monkeypatch, drc_errors=3, gate={"build_ready": True, "blockers": []})

    loop = _loop(tmp_path)

    assert loop["resolved"] is False
    assert any("DRC" in reason for reason in loop["unresolved_reasons"])


def test_a_result_with_no_gate_is_never_resolved(tmp_path, monkeypatch) -> None:
    _dispatch_returning(tmp_path, monkeypatch, drc_errors=0, gate=None)

    loop = _loop(tmp_path)

    assert loop["resolved"] is False
    assert any("gate" in reason for reason in loop["unresolved_reasons"])


def test_a_gate_that_blocks_without_naming_a_blocker_still_says_why(tmp_path, monkeypatch) -> None:
    _dispatch_returning(tmp_path, monkeypatch, drc_errors=0, gate={"build_ready": False, "blockers": []})

    loop = _loop(tmp_path)

    assert loop["resolved"] is False
    assert loop["unresolved_reasons"]

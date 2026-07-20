"""Compose agent-loop + bench capture closure (Phase 2 kickoff)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hardware_splicer.api import create_app
from hardware_splicer.bench_loop import run_bench_loop_closure
from hardware_splicer.project_intake import _donor_context_from_intake, load_project_intake
from hardware_splicer.sdk import compose_agent_bench_loop

ROOT = Path(__file__).resolve().parents[1]
ROBOT_INTAKE = ROOT / "examples" / "intakes" / "splice_robot_drive_brief.json"


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_compose_agent_bench_loop_salvage_simulated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")

    intake = load_project_intake(ROBOT_INTAKE)
    result = compose_agent_bench_loop(
        goal=str(intake["goal"]),
        parts=list(intake["available_parts"]),
        constraints=dict(intake.get("constraints") or {}),
        donor_context=_donor_context_from_intake(intake),
        salvage_mode=True,
        out_dir=tmp_path / "compose_bench",
        export_gerber=False,
        allow_llm_first=False,
        project_name=str(intake["project_name"]),
        simulate_bench=True,
    )
    loop = result.get("agent_loop") or {}
    bench_loop = result.get("bench_loop") or {}
    assert loop.get("final_kicad_drc_errors") == 0
    assert result.get("project_package")
    assert bench_loop.get("submitted_capture") is True
    assert bench_loop.get("passed") is True
    assert bench_loop.get("authorization_outcome") in {"authorized", "correctly_blocked"}
    if bench_loop.get("authorization_outcome") == "correctly_blocked":
        assert (result.get("bench_session") or {}).get("power_on_authorized") is False
        assert int(bench_loop.get("authority_gates_remaining") or 0) >= 1
    else:
        assert (result.get("bench_session") or {}).get("power_on_authorized") is True
    assert (tmp_path / "compose_bench" / "BENCH_LOOP_REPORT.json").is_file()
    assert (tmp_path / "compose_bench" / "SPLICE_PLAN.json").is_file()


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_compose_bench_loop_http_salvage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")

    intake = load_project_intake(ROBOT_INTAKE)
    client = TestClient(create_app())
    response = client.post(
        "/v1/compose/bench-loop",
        json={
            "goal": intake["goal"],
            "parts": intake["available_parts"],
            "constraints": intake.get("constraints") or {},
            "donor_context": _donor_context_from_intake(intake),
            "salvage_mode": True,
            "simulate_bench": True,
            "allow_llm_first": False,
            "export_gerber": False,
            "project_name": intake["project_name"],
            "out_dir": str(tmp_path / "http_compose_bench"),
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("bench_loop", {}).get("submitted_capture") is True
    assert payload.get("bench_loop", {}).get("authorization_outcome") in {"authorized", "correctly_blocked"}
    assert payload.get("agent_loop", {}).get("final_kicad_drc_errors") == 0


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_bench_loop_closure_on_existing_compose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")

    intake = load_project_intake(ROBOT_INTAKE)
    built = compose_agent_bench_loop(
        goal=str(intake["goal"]),
        parts=list(intake["available_parts"]),
        donor_context=_donor_context_from_intake(intake),
        salvage_mode=True,
        out_dir=tmp_path / "reuse_bench",
        simulate_bench=False,
        allow_llm_first=False,
        export_gerber=False,
    )
    report = run_bench_loop_closure(built["out_dir"], simulate_bench=True)
    assert report.get("submitted_capture") is True
    assert report.get("authorization_outcome") in {"authorized", "correctly_blocked"}

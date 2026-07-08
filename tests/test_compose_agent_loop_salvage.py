"""Salvage donor_context on compose agent-loop — same spine as hs_compose_drc_agent."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hardware_splicer.api import create_app
from hardware_splicer.compose_agent_loop import compose_agent_loop
from hardware_splicer.project_intake import _donor_context_from_intake, load_project_intake
from hardware_splicer.salvage_bridge import resolve_salvage_compose_inputs

ROOT = Path(__file__).resolve().parents[1]
ROBOT_INTAKE = ROOT / "examples" / "intakes" / "splice_robot_drive_brief.json"


def test_resolve_salvage_compose_inputs_robot_drive_catalog() -> None:
    intake = load_project_intake(ROBOT_INTAKE)
    resolved = resolve_salvage_compose_inputs(
        goal=str(intake["goal"]),
        parts=list(intake["available_parts"]),
        constraints=dict(intake.get("constraints") or {}),
        project_name=str(intake["project_name"]),
        donor_context=_donor_context_from_intake(intake),
        salvage_mode=True,
    )
    assert resolved is not None
    assert resolved.get("build_id") == "robot_drive_base"
    assert resolved.get("splice_plan")
    pkg = resolved.get("salvage_package") or {}
    assert pkg.get("graph_mode") == "catalog"


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_compose_agent_loop_donor_context_robot_drive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")

    intake = load_project_intake(ROBOT_INTAKE)
    result = compose_agent_loop(
        goal=str(intake["goal"]),
        parts=list(intake["available_parts"]),
        constraints=dict(intake.get("constraints") or {}),
        donor_context=_donor_context_from_intake(intake),
        salvage_mode=True,
        out_dir=tmp_path / "salvage_agent_loop",
        export_gerber=False,
        finalize_package=True,
        project_name=str(intake["project_name"]),
        allow_llm_first=False,
    )
    loop = result.get("agent_loop") or {}
    assert loop.get("rounds")
    assert result.get("mode") == "salvage_catalog"
    assert result.get("build_id") == "robot_drive_base"
    assert result.get("salvage_package")
    assert result.get("recommended_build_id") == "robot_drive_base"
    assert loop.get("final_kicad_drc_errors") == 0
    assert result.get("project_package")


def test_compose_agent_loop_http_donor_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    if not shutil.which("node"):
        pytest.skip("node not available")

    from fastapi.testclient import TestClient

    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")

    intake = load_project_intake(ROBOT_INTAKE)
    client = TestClient(create_app())
    response = client.post(
        "/v1/compose/agent-loop",
        json={
            "goal": intake["goal"],
            "parts": intake["available_parts"],
            "constraints": intake.get("constraints") or {},
            "donor_context": _donor_context_from_intake(intake),
            "salvage_mode": True,
            "finalize_package": True,
            "project_name": intake["project_name"],
            "allow_llm_first": False,
            "export_gerber": False,
            "out_dir": str(tmp_path / "http_salvage_agent_loop"),
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("mode") == "salvage_catalog"
    assert payload.get("agent_loop", {}).get("final_kicad_drc_errors") == 0
    assert payload.get("salvage_package")

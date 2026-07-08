"""Unified compose dispatch spine (API / CLI / SDK)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.build_compiler import attach_build_compilation_artifacts
from hardware_splicer.compose_dispatch import compose_dispatch
from hardware_splicer.project_intake import load_project_intake, plan_project_from_intake
from hardware_splicer.scratch_pipeline import compile_scratch_build


def test_compose_dispatch_wire_only_phrase() -> None:
    result = compose_dispatch(
        out_dir="/tmp/hs_compose_dispatch_wire",
        phrase="plant watering with soil moisture sensor and pump",
        wire_only=True,
    )
    assert result.get("wire_only") is True
    assert result.get("mode") == "scratch"
    assert len(result.get("module_ids") or []) >= 2
    assert len((result.get("graph") or {}).get("wires") or []) >= 2


def test_compose_dispatch_scratch_matches_direct_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    phrase = "something that measures temperature"
    dispatch = compose_dispatch(
        out_dir=tmp_path / "dispatch",
        phrase=phrase,
        export_gerber=False,
        allow_llm_first=False,
    )
    direct = compile_scratch_build(
        out_dir=str(tmp_path / "direct"),
        goal=phrase,
        export_gerber=False,
    )
    assert dispatch.get("module_ids") == direct.module_ids
    assert dispatch.get("mode") == "scratch"


def test_attach_build_compilation_uses_scratch_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    root = Path(__file__).resolve().parents[1]
    intake = load_project_intake(root / "examples" / "intakes" / "scratch_compose_brief.json")
    plan = plan_project_from_intake(intake)
    spec = plan["scenario"]["compile_spec"]
    payload = attach_build_compilation_artifacts(spec, tmp_path / "scenario", export_gerber=False)
    assert payload.get("graph_mode") == "scratch"
    assert payload.get("scratch_attempts") is not None
    assert int((payload.get("design_quality") or {}).get("kicad_drc_errors") or 0) == 0


def test_finalize_compose_job_result_writes_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    dispatch = compose_dispatch(
        out_dir=tmp_path / "compose_pkg",
        phrase="usb esp32 temperature sensor board",
        export_gerber=False,
        allow_llm_first=False,
    )
    from hardware_splicer.sdk import finalize_compose_job_result

    final = finalize_compose_job_result(
        dispatch,
        goal="usb esp32 temperature sensor board",
        project_name="compose_pkg",
    )
    assert final.get("project_package")
    assert final.get("build_dir")
    assert Path(final["build_dir"], "PROJECT_PACKAGE.json").is_file()

    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    result = compile_scratch_build(
        out_dir=str(tmp_path),
        module_ids=["usb-power-5v"],
        export_gerber=False,
    )
    assert result.ok is False
    assert result.compile_casefile
    casefile = json.loads(Path(result.compile_casefile).read_text(encoding="utf-8"))
    assert casefile.get("stage") == "scratch_compose"
    assert casefile.get("intake") is None

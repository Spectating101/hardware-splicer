"""Design Studio spine — agent/MCP/HTTP parity (no browser)."""

from __future__ import annotations

import os

import pytest

from hardware_splicer.api import create_app
from hardware_splicer.pcb.module_registry import list_canvas_modules
from hardware_splicer.sdk import compose_design, finalize_compose_job_result


def test_modules_catalog_matches_registry() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    body = client.get("/v1/modules/catalog").json()
    assert body.get("ok") is True
    assert body.get("count") == len(list_canvas_modules())
    assert body["modules"][0].get("pins")


def test_agent_compose_canvas_returns_drc_fix_loop(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")

    result = compose_design(
        phrase="agent studio smoke",
        canvas_nodes=[
            {"id": "m1", "moduleId": "esp32-devkit"},
            {"id": "m2", "moduleId": "dht22"},
        ],
        out_dir=tmp_path / "agent_studio",
        export_gerber=False,
        allow_llm_first=False,
    )
    quality = result.get("design_quality") or {}
    assert quality.get("kicad_drc_errors") is not None
    loop = quality.get("drc_fix_loop") or {}
    assert loop.get("attempts")

    retry = compose_design(
        phrase="agent studio smoke retry",
        canvas_nodes=[
            {"id": "m1", "moduleId": "esp32-devkit"},
            {"id": "m2", "moduleId": "dht22"},
        ],
        out_dir=tmp_path / "agent_studio_retry",
        export_gerber=False,
        allow_llm_first=False,
        drc_fixup={
            "edge_pad_extra_mm": 0.35,
            "module_gap_extra_mm": 4.0,
            "via_clearance_mm": 0.27,
        },
    )
    graph = (retry.get("graph") or {})
    assert graph.get("drc_fixup")


def test_compose_http_matches_agent_fields(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    os.environ["HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR"] = "1"

    client = TestClient(create_app())
    payload = client.post(
        "/v1/compose",
        json={
            "phrase": "http agent smoke",
            "canvas_nodes": [
                {"id": "m1", "moduleId": "esp32-devkit"},
                {"id": "m2", "moduleId": "dht22"},
            ],
            "export_gerber": False,
            "allow_llm_first": False,
            "out_dir": str(tmp_path / "http_compose"),
            "drc_fixup": {"edge_pad_extra_mm": 0.35},
        },
    ).json()
    assert payload.get("mode") == "canvas"
    assert (payload.get("graph") or {}).get("drc_fixup")
    dq = payload.get("design_quality") or {}
    assert "drc_fix_loop" in dq or dq.get("kicad_drc_errors") is not None


def test_finalize_compose_after_agent_compose(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")

    result = compose_design(
        phrase="agent package handoff",
        canvas_nodes=[
            {"id": "m1", "moduleId": "esp32-devkit"},
            {"id": "m2", "moduleId": "dht22"},
        ],
        out_dir=tmp_path / "agent_pkg",
        export_gerber=False,
        allow_llm_first=False,
    )
    final = finalize_compose_job_result(
        result,
        goal="agent package handoff",
        project_name="agent_pkg",
    )
    assert final.get("project_package")
    assert final.get("bench_session")

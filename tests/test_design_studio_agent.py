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
    if quality.get("kicad_drc_errors") is None:
        pytest.skip("KiCad DRC was not available in this dependency-light test environment")
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
    graph = retry.get("graph") or {}
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


def test_finalize_compose_result_builds_package_and_bench_projection(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dir = tmp_path / "compose-build"
    build_dir.mkdir()
    bench_session = {
        "readiness": "blocked",
        "open_gate_count": 1,
        "critical_open_count": 1,
        "power_on_authorized": False,
        "level": "bench_required",
        "gates": [{"gate_id": "power_input", "status": "open"}],
        "bench_capture_template": "BENCH_CAPTURE_TEMPLATE.json",
    }

    monkeypatch.setattr(
        "hardware_splicer.project_package.write_project_package_artifacts",
        lambda out_dir, result, source: {
            "package": {"schema_version": "test.project_package.v1", "source": source},
            "artifacts": {"project_package": str(out_dir / "PROJECT_PACKAGE.json")},
        },
    )
    monkeypatch.setattr(
        "hardware_splicer.splice_bench.open_bench_session",
        lambda out_dir, force=False: dict(bench_session),
    )
    monkeypatch.setattr(
        "hardware_splicer.bench_capture_bridge.sync_bench_session_template",
        lambda out_dir: {
            "session": dict(bench_session),
            "template": {"template_path": str(out_dir / "BENCH_CAPTURE_TEMPLATE.json")},
        },
    )

    result = finalize_compose_job_result(
        {
            "ok": True,
            "out_dir": str(build_dir),
            "artifacts": {"pcb": str(build_dir / "board.kicad_pcb")},
        },
        goal="exercise current finalization contract",
        project_name="design-studio-contract",
    )

    assert result["build_dir"] == str(build_dir.resolve())
    assert result["project_name"] == "design-studio-contract"
    assert result["goal"] == "exercise current finalization contract"
    assert result["project_package"]["source"] == "compose"
    assert result["bench_session"]["power_on_authorized"] is False
    assert result["bench_session"]["critical_open_count"] == 1
    assert result["artifacts"]["pcb"].endswith("board.kicad_pcb")
    assert result["artifacts"]["project_package"].endswith("PROJECT_PACKAGE.json")


def test_finalize_compose_result_refuses_missing_build_directory(tmp_path) -> None:
    missing = tmp_path / "does-not-exist"

    with pytest.raises(ValueError, match="compose out_dir missing"):
        finalize_compose_job_result({"ok": False, "out_dir": str(missing)})

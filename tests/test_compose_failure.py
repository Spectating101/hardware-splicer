"""Structured compose failure payloads (gate 3.9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.build_compiler import compile_catalog_build, write_fabrication_artifacts
from hardware_splicer.compose_dispatch import compose_dispatch
from hardware_splicer.compose_failure import SCHEMA_VERSION, attach_compose_failure, build_compose_failure
from hardware_splicer.sdk import engine_doctor


def test_build_compose_failure_module_pick() -> None:
    failure = build_compose_failure(
        mode="scratch",
        error="need >=2 modules, got ['usb-power-5v']",
        design_quality={"circuit_readiness": "module_pick_failed"},
    )
    assert failure["schema_version"] == SCHEMA_VERSION
    assert failure["type"] == "module_pick_failed"
    assert failure["stage"] == "scratch"
    assert failure["blockers"]


def test_compose_dispatch_failure_payload_includes_casefile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    result = compose_dispatch(
        out_dir=tmp_path,
        module_ids=["usb-power-5v"],
        export_gerber=False,
        allow_llm_first=False,
    )
    assert result.get("ok") is False
    failure = result.get("failure") or {}
    assert failure.get("type") == "module_pick_failed"
    assert failure.get("casefile_path")
    casefile = json.loads(Path(failure["casefile_path"]).read_text(encoding="utf-8"))
    assert casefile.get("stage") == "scratch_compose"


def test_attach_compose_failure_skips_success() -> None:
    payload = attach_compose_failure({"ok": True, "mode": "scratch"})
    assert "failure" not in payload


def test_compile_catalog_build_writes_fabrication_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    result = compile_catalog_build("sensor_logger", tmp_path, export_gerber=False)
    assert (tmp_path / "FUNCTIONAL_DELIVERY.json").is_file()
    assert (tmp_path / "FABRICATION_INSPECTION.json").is_file()
    paths = write_fabrication_artifacts(tmp_path, result.to_dict())
    assert paths["functional_delivery"]
    assert paths["fabrication_inspection"]


def test_engine_doctor_fails_when_testing_mode_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_TESTING_MODE", "1")
    doc = engine_doctor()
    assert doc["testing_mode"] is True
    assert doc["ok"] is False
    assert doc.get("testing_mode_blocker")

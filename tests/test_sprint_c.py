"""Sprint C: netlist ingest, inspect fab, async jobs, geometry snapshots."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.integrations.llm_policy import compose_retry_enabled, llm_policy_summary, offline_compose_enabled
from hardware_splicer.netlist.ingest import detect_netlist_format, load_netlist_file
from hardware_splicer.sdk import inspect_fab_build_dir

ROOT = Path(__file__).resolve().parents[1]


def test_llm_policy_summary_offline_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "0")
    summary = llm_policy_summary()
    assert summary["offline_compose"] is True
    assert summary["compose_retry"] is False


def test_compose_retry_requires_qwen_compose_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE_RETRY", "0")
    assert compose_retry_enabled() is False


def test_load_netlist_file_ir_json() -> None:
    fixture = ROOT / "examples" / "netlist_fixtures" / "json" / "usb_esp_pir.json"
    netlist = load_netlist_file(fixture)
    assert len(netlist.components) >= 2


def test_detect_kicad_netlist_format() -> None:
    fixture = ROOT / "examples" / "netlist_fixtures" / "kicad" / "esp32_servo.net"
    assert detect_netlist_format(fixture) == "kicad_netlist"


def test_inspect_fab_build_dir_on_catalog_compile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    from hardware_splicer.build_compiler import compile_catalog_build

    compile_catalog_build("sensor_logger", tmp_path, export_gerber=False)
    result = inspect_fab_build_dir(tmp_path)
    assert "inspection_score" in result
    assert result.get("checks_total", 0) > 0


def test_geometry_golden_snapshots_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    from hardware_splicer.build_compiler import compile_catalog_build
    from hardware_splicer.geometry_snapshot import build_geometry_snapshot, compare_geometry_snapshots

    golden = ROOT / "examples" / "geometry_snapshots" / "sensor_logger.json"
    expected = json.loads(golden.read_text(encoding="utf-8"))
    compile_catalog_build("sensor_logger", tmp_path, export_gerber=False)
    actual = build_geometry_snapshot(tmp_path)
    diff = compare_geometry_snapshots(expected, actual)
    assert diff["ok"] is True, diff["mismatches"]

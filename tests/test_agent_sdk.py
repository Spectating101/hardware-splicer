"""Agent SDK tests (no MCP package required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.sdk import (
    compose_design,
    dump_json,
    engine_doctor,
    list_catalog_builds,
    plan_salvage,
    resolve_inventory_parts,
    sdk_info,
    suggest_modules,
)


ROOT = Path(__file__).resolve().parents[1]


def test_sdk_info_and_catalog() -> None:
    info = sdk_info()
    assert info["schema_version"] == "hardware_splicer.sdk.v1"
    assert "salvage" in " ".join(info["strengths"]).lower()
    builds = list_catalog_builds()
    assert builds["count"] >= 10
    assert "sensor_logger" in builds["build_ids"]


def test_engine_doctor_returns_shape() -> None:
    doc = engine_doctor()
    assert "ok" in doc
    assert "dependencies" in doc
    assert doc["engine_defaults"]["autoroute"] == "0"


def test_resolve_usb_wall_wart() -> None:
    payload = resolve_inventory_parts(
        [
            {"name": "USB 5V wall wart", "type": "power_source", "voltage_v": 5.0},
            {"name": "ESP32", "type": "microcontroller"},
        ]
    )
    assert payload["power_topology"] == "usb_5v"
    assert "usb-power-5v" in payload["module_ids"]
    assert "dc-barrel-12v" not in payload["module_ids"]


def test_plan_salvage_wifi_intake() -> None:
    intake = json.loads(
        (ROOT / "examples" / "intakes" / "salvage_wifi_logger_brief.json").read_text(encoding="utf-8")
    )
    plan = plan_salvage(
        goal=str(intake["goal"]),
        parts=list(intake["available_parts"]),
        constraints=dict(intake.get("constraints") or {}),
    )
    ids = [r.get("module_id") for r in plan.get("resolved_modules") or []]
    assert plan["power_topology"] == "usb_5v"
    assert ids == ["esp32-devkit", "dht22", "usb-power-5v"]


def test_suggest_modules_returns_ids() -> None:
    pick = suggest_modules("room temperature display with wifi")
    assert len(pick["module_ids"]) >= 2


def test_dump_json_roundtrip() -> None:
    text = dump_json({"a": 1})
    assert json.loads(text)["a"] == 1


@pytest.mark.skipif(not (ROOT / "examples" / "intakes" / "salvage_wifi_logger_brief.json").is_file(), reason="intake")
def test_compose_design_constrained_salvage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    intake = json.loads(
        (ROOT / "examples" / "intakes" / "salvage_wifi_logger_brief.json").read_text(encoding="utf-8")
    )
    resolved = resolve_inventory_parts(intake["available_parts"])
    result = compose_design(
        module_ids=resolved["module_ids"],
        resolved_modules=resolved["resolved_modules"],
        constraints=intake.get("constraints"),
        salvage_mode=True,
        out_dir=tmp_path,
        export_gerber=False,
    )
    assert result["ok"] is True, result.get("error")
    assert result["design_quality_gate"]["build_ready"] is True
    assert int(result["design_quality"].get("kicad_drc_errors") or 0) == 0
    bom = json.loads(Path(result["artifacts"]["bom"]).read_text(encoding="utf-8"))
    assert all(line.get("source") == "salvage" for line in bom["lines"])

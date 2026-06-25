from __future__ import annotations

from unittest.mock import patch

import pytest

from hardware_splicer.module_resolver import resolve_parts_to_modules, resolve_parts_to_modules_with_llm
from hardware_splicer.salvage_bridge import build_intake_salvage_package


def test_tof_range_resolves_without_qwen() -> None:
    parts = [{"name": "front ToF range sensor", "type": "tof_range"}]
    resolved = resolve_parts_to_modules(parts)
    assert resolved[0]["module_id"] == "vl53l0x_tof"


def test_qwen_salvage_only_when_unresolved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_SALVAGE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    parts = [
        {"name": "ESP32 dev board", "type": "microcontroller"},
        {"name": "mystery analog widget", "type": "unknown_widget"},
    ]
    resolved, meta = resolve_parts_to_modules_with_llm(parts, goal="test gadget")
    assert meta["qwen"]["used"] is False
    assert any(row.get("module_id") == "esp32-devkit" for row in resolved)


def test_dc_motor_resolves_without_qwen() -> None:
    parts = [{"name": "left 6V DC gear motor", "type": "dc_motor", "voltage_v": 6.0}]
    resolved = resolve_parts_to_modules(parts)
    assert any(row.get("module_id") == "dc_motor_3v_6v" for row in resolved)


def test_fill_salvage_gaps_adds_driver() -> None:
    from hardware_splicer.module_resolver import fill_salvage_gaps

    parts = [{"name": "left 6V DC gear motor", "type": "dc_motor"}]
    resolved = resolve_parts_to_modules(parts)
    filled = fill_salvage_gaps(resolved, parts=parts)
    assert any(row.get("module_id") == "l298n" and row.get("source") == "gap_fill" for row in filled)


def test_qwen_salvage_merge_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "llm_first")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    parts = [{"name": "mystery widget", "type": "widget"}]
    fake = {
        "ok": True,
        "resolved": [
            {
                "part_name": "mystery widget",
                "module_id": "dht22",
                "role": "sns",
                "confidence": 0.8,
                "reason": "test",
            }
        ],
        "rejected": [],
        "suggested_purchases": [],
    }
    with patch(
        "hardware_splicer.integrations.qwen_salvage_resolver.qwen_configured",
        return_value=True,
    ), patch(
        "hardware_splicer.integrations.qwen_salvage_resolver.call_qwen_salvage_map_intake",
        return_value={
            "ok": True,
            "resolved": fake["resolved"],
            "rejected": [],
            "suggested_purchases": [],
            "reasoning": "test",
        },
    ):
        resolved, meta = resolve_parts_to_modules_with_llm(parts, goal="temp sensor")
    assert meta["qwen"]["used"] is True
    assert any(row.get("module_id") == "dht22" for row in resolved)


def test_rover_intake_resolves_tof_in_package() -> None:
    from hardware_splicer.project_intake import load_project_intake

    intake = load_project_intake("examples/intakes/rover_brief.json")
    pkg = build_intake_salvage_package(
        goal=str(intake.get("goal") or ""),
        parts=list(intake.get("available_parts") or []),
        constraints=dict(intake.get("constraints") or {}),
        project_name="rover",
    )
    module_ids = [str(r.get("module_id") or "") for r in pkg.get("resolved_modules") or []]
    assert "vl53l0x_tof" in module_ids or "hc-sr04" in module_ids or "vl6180x-tof" in module_ids

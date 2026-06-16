from __future__ import annotations

from unittest.mock import patch

import pytest

from hardware_splicer.integrations.llm_workshop import run_salvage_workshop
from hardware_splicer.integrations.qwen_workshop_review import (
    apply_workshop_review,
    call_qwen_workshop_review,
)
from hardware_splicer.project_intake import load_project_intake


def test_salvage_workshop_heuristic_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_SALVAGE", "0")
    intake = load_project_intake("examples/intakes/rover_brief.json")
    trace = run_salvage_workshop(
        goal=str(intake.get("goal") or ""),
        parts=list(intake.get("available_parts") or []),
        constraints=dict(intake.get("constraints") or {}),
    )
    assert trace.get("mode") == "salvage"
    ids = [step["id"] for step in trace.get("steps") or []]
    assert "heuristic_resolve" in ids
    assert "qwen_workshop_review" in ids
    assert trace.get("recommendation")


def test_workshop_review_apply_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_WORKSHOP", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_LLM_FIRST", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_SALVAGE", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr(
        "hardware_splicer.integrations.qwen_text_client.qwen_configured",
        lambda: True,
    )
    resolved = [{"part_name": "ESP32", "module_id": "esp32-devkit", "role": "mcu"}]
    fake = {
        "reasoning": "Add level shifter for 5V sensor",
        "add_modules": [{"module_id": "level-shifter-4ch", "role": "misc", "reason": "5V sensor"}],
        "role_overrides": {},
        "confidence": 0.8,
    }
    with patch(
        "hardware_splicer.integrations.qwen_workshop_review.call_qwen_chat",
        return_value={"ok": True, "content": __import__("json").dumps(fake), "model": "qwen-turbo"},
    ):
        review = call_qwen_workshop_review(
            goal="test",
            parts=[{"name": "ESP32", "type": "microcontroller"}],
            resolved_modules=resolved,
        )
    assert review.get("ok") is True
    merged = apply_workshop_review(resolved, review)
    assert any(row.get("module_id") == "level-shifter-4ch" for row in merged)

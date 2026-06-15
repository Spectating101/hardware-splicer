"""Qwen arbitrary compose tests (fallback path without API key)."""

from __future__ import annotations

import pytest

from hardware_splicer.integrations.qwen_netlist_compose import compose_netlist_from_goal


def test_compose_netlist_fallback_without_qwen_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "0")
    result = compose_netlist_from_goal("wifi temperature logger with esp32 and dht22")
    assert result.get("compose_mode") == "module_picker_fallback"
    assert result.get("ok") is True
    assert len(result.get("netlist", {}).get("components") or []) >= 2

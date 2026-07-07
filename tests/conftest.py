"""Shared pytest configuration."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fast_compile_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests fast; integration tests opt in to autoroute."""
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "0")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_BUILD_PICK", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_MODULE_PICK", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_LLM_FIRST", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_WORKSHOP", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    monkeypatch.setattr(
        "hardware_splicer.integrations.qwen_text_client.qwen_configured",
        lambda: False,
    )

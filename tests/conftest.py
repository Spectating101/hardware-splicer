"""Shared pytest configuration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone, tzinfo

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


@pytest.fixture
def authorization_clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[datetime], None]:
    """Control the audited assessor's clock, without replacing any validation logic.

    Opt-in only: unrelated tests and the process clock stay untouched. The audited
    assessor forwards one instant to the real ledger and physical-evidence checks,
    including fresh status/action revalidation. Test teardown restores the clock.
    """
    from hardware_splicer import audited_physical_evidence

    def set_time(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("authorization test clock requires a timezone-aware datetime")
        instant = value.astimezone(timezone.utc)

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz: tzinfo | None = None) -> datetime:
                if tz is None:
                    return instant.astimezone().replace(tzinfo=None)
                return instant.astimezone(tz)

        monkeypatch.setattr(audited_physical_evidence, "datetime", FixedDateTime)

    # After the fixture's evidence capture/review, before its September expiry.
    set_time(datetime(2026, 8, 4, 3, tzinfo=timezone.utc))
    return set_time

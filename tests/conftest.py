"""Shared pytest configuration."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fast_compile_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests fast; integration tests opt in to autoroute."""
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "0")

"""Keep unit tests deterministic — do not inherit machine .env.local Qwen URLs/keys."""
from __future__ import annotations

import pytest

_ENV_KEYS = (
    "QWEN_BASE_URL",
    "DASHSCOPE_BASE_URL",
    "QWEN_API_KEY",
    "DASHSCOPE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)


@pytest.fixture(autouse=True)
def _isolate_local_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

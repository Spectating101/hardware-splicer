"""Central LLM-first vs offline policy for Hardware-Splicer."""

from __future__ import annotations

import os


def _llm_configured() -> bool:
    from .llm_text_client import llm_configured

    return llm_configured()


def _qwen_configured() -> bool:
    from .qwen_text_client import qwen_configured

    return qwen_configured()


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _falsy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"0", "false", "no", "off"}


def qwen_llm_first() -> bool:
    """True when a text LLM backend is configured and user has not disabled LLM paths."""
    if _falsy("HARDWARE_SPLICER_LLM_FIRST"):
        return False
    if _falsy("HARDWARE_SPLICER_QWEN_SALVAGE") and _falsy("HARDWARE_SPLICER_QWEN_COMPOSE"):
        return False
    return _llm_configured()


def offline_compose_enabled() -> bool:
    """Regex module_picker / phrase_expander allowed."""
    if _truthy("HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        return True
    if _falsy("HARDWARE_SPLICER_QWEN_COMPOSE"):
        return True
    return not _llm_configured()


def offline_salvage_enabled() -> bool:
    """Regex part resolve / keyword build pick allowed."""
    if _truthy("HARDWARE_SPLICER_OFFLINE_SALVAGE"):
        return True
    if _falsy("HARDWARE_SPLICER_QWEN_SALVAGE"):
        return True
    return not _llm_configured()


def offline_phrase_expand_enabled() -> bool:
    if _truthy("HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND"):
        return True
    return offline_compose_enabled()

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
    if _truthy("QWEN_DISABLED") or _truthy("HARDWARE_SPLICER_QWEN_DISABLED"):
        return False
    if _falsy("HARDWARE_SPLICER_LLM_FIRST"):
        return False
    if _falsy("HARDWARE_SPLICER_QWEN_SALVAGE") and _falsy("HARDWARE_SPLICER_QWEN_COMPOSE"):
        return False
    return _llm_configured()


def offline_compose_enabled() -> bool:
    """Regex module_picker / phrase_expander allowed."""
    if _truthy("QWEN_DISABLED") or _truthy("HARDWARE_SPLICER_QWEN_DISABLED"):
        return True
    if _truthy("HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        return True
    if _falsy("HARDWARE_SPLICER_QWEN_COMPOSE"):
        return True
    return not _llm_configured()


def offline_salvage_enabled() -> bool:
    """Regex part resolve / keyword build pick allowed."""
    if _truthy("QWEN_DISABLED") or _truthy("HARDWARE_SPLICER_QWEN_DISABLED"):
        return True
    if _truthy("HARDWARE_SPLICER_OFFLINE_SALVAGE"):
        return True
    if _falsy("HARDWARE_SPLICER_QWEN_SALVAGE"):
        return True
    return not _llm_configured()


def offline_phrase_expand_enabled() -> bool:
    if _truthy("HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND"):
        return True
    return offline_compose_enabled()


def compose_retry_enabled() -> bool:
    """Optional Qwen module-pick retries during scratch compose."""
    if _falsy("HARDWARE_SPLICER_QWEN_COMPOSE_RETRY"):
        return False
    return qwen_llm_first()


def llm_policy_summary() -> dict[str, object]:
    """Single source of truth for compose/salvage LLM env knobs."""
    return {
        "offline_compose": offline_compose_enabled(),
        "offline_salvage": offline_salvage_enabled(),
        "offline_phrase_expand": offline_phrase_expand_enabled(),
        "qwen_llm_first": qwen_llm_first(),
        "compose_retry": compose_retry_enabled(),
        "llm_configured": _llm_configured(),
        "qwen_configured": _qwen_configured(),
        "env": {
            "HARDWARE_SPLICER_OFFLINE_COMPOSE": os.environ.get("HARDWARE_SPLICER_OFFLINE_COMPOSE", ""),
            "HARDWARE_SPLICER_OFFLINE_SALVAGE": os.environ.get("HARDWARE_SPLICER_OFFLINE_SALVAGE", ""),
            "HARDWARE_SPLICER_LLM_FIRST": os.environ.get("HARDWARE_SPLICER_LLM_FIRST", ""),
            "HARDWARE_SPLICER_QWEN_COMPOSE": os.environ.get("HARDWARE_SPLICER_QWEN_COMPOSE", ""),
            "HARDWARE_SPLICER_QWEN_COMPOSE_RETRY": os.environ.get("HARDWARE_SPLICER_QWEN_COMPOSE_RETRY", ""),
            "HARDWARE_SPLICER_QWEN_SALVAGE": os.environ.get("HARDWARE_SPLICER_QWEN_SALVAGE", ""),
            "QWEN_DISABLED": os.environ.get("QWEN_DISABLED", ""),
            "HARDWARE_SPLICER_QWEN_DISABLED": os.environ.get("HARDWARE_SPLICER_QWEN_DISABLED", ""),
            "HARDWARE_SPLICER_JOB_TIMEOUT_S": os.environ.get("HARDWARE_SPLICER_JOB_TIMEOUT_S", ""),
        },
    }

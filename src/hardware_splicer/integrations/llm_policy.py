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
    """Legacy regex module selection is allowed for explicit/no-model compatibility."""
    if _truthy("QWEN_DISABLED") or _truthy("HARDWARE_SPLICER_QWEN_DISABLED"):
        return True
    if _truthy("HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        return True
    if _falsy("HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        return False
    if _falsy("HARDWARE_SPLICER_QWEN_COMPOSE"):
        return True
    return not _llm_configured()


def offline_salvage_enabled() -> bool:
    """Return whether legacy regex identity/build hints may execute.

    No-model compatibility remains the default when no explicit policy is supplied.  An
    explicit ``HARDWARE_SPLICER_OFFLINE_SALVAGE=0`` is stronger: it requests the strict
    model-first identity boundary even when the provider is unavailable, so unresolved
    hardware stays unresolved instead of silently falling back to regex/catalog stand-ins.
    """
    if _truthy("QWEN_DISABLED") or _truthy("HARDWARE_SPLICER_QWEN_DISABLED"):
        return True
    if _truthy("HARDWARE_SPLICER_OFFLINE_SALVAGE"):
        return True
    if _falsy("HARDWARE_SPLICER_OFFLINE_SALVAGE"):
        return False
    if _falsy("HARDWARE_SPLICER_QWEN_SALVAGE"):
        return True
    return not _llm_configured()


def offline_phrase_expand_enabled() -> bool:
    """Allow lexical typo normalization on compatibility paths.

    This no longer authorizes semantic rewrites. Those require the separate explicit
    ``HARDWARE_SPLICER_OFFLINE_SEMANTIC_REWRITE`` opt-in.
    """
    if _truthy("HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND"):
        return True
    return offline_compose_enabled()


def offline_semantic_rewrite_enabled() -> bool:
    """Explicit opt-in for historical phrase-to-intent semantic rewrites.

    Semantic rewrites can collapse an unknown request onto a canned architecture, so
    they are never implied merely because no model is configured.
    """
    return _truthy("HARDWARE_SPLICER_OFFLINE_SEMANTIC_REWRITE")


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
        "offline_semantic_rewrite": offline_semantic_rewrite_enabled(),
        "qwen_llm_first": qwen_llm_first(),
        "compose_retry": compose_retry_enabled(),
        "llm_configured": _llm_configured(),
        "qwen_configured": _qwen_configured(),
        "env": {
            "HARDWARE_SPLICER_OFFLINE_COMPOSE": os.environ.get("HARDWARE_SPLICER_OFFLINE_COMPOSE", ""),
            "HARDWARE_SPLICER_OFFLINE_SALVAGE": os.environ.get("HARDWARE_SPLICER_OFFLINE_SALVAGE", ""),
            "HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND": os.environ.get("HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND", ""),
            "HARDWARE_SPLICER_OFFLINE_SEMANTIC_REWRITE": os.environ.get("HARDWARE_SPLICER_OFFLINE_SEMANTIC_REWRITE", ""),
            "HARDWARE_SPLICER_LLM_FIRST": os.environ.get("HARDWARE_SPLICER_LLM_FIRST", ""),
            "HARDWARE_SPLICER_QWEN_COMPOSE": os.environ.get("HARDWARE_SPLICER_QWEN_COMPOSE", ""),
            "HARDWARE_SPLICER_QWEN_COMPOSE_RETRY": os.environ.get("HARDWARE_SPLICER_QWEN_COMPOSE_RETRY", ""),
            "HARDWARE_SPLICER_QWEN_SALVAGE": os.environ.get("HARDWARE_SPLICER_QWEN_SALVAGE", ""),
            "QWEN_DISABLED": os.environ.get("QWEN_DISABLED", ""),
            "HARDWARE_SPLICER_QWEN_DISABLED": os.environ.get("HARDWARE_SPLICER_QWEN_DISABLED", ""),
            "HARDWARE_SPLICER_JOB_TIMEOUT_S": os.environ.get("HARDWARE_SPLICER_JOB_TIMEOUT_S", ""),
        },
    }

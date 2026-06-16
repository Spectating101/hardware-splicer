"""Unified text LLM entry: disk cache, usage ledger, Qwen + agy provider chain."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..env_local import load_env_local
from ..llm_response_cache import cache_enabled, cache_key, read_cached_response, write_cached_response
from ..text_usage_ledger import record_text_usage
from .agy_text_client import agy_configured, call_agy_chat
from .qwen_model_policy import QwenTextStage, qwen_text_model_candidates
from .qwen_text_client import _call_qwen_http, qwen_configured


def llm_provider_mode() -> str:
    load_env_local()
    raw = str(os.getenv("HARDWARE_SPLICER_LLM_PROVIDER") or "qwen_then_agy").strip().lower()
    if raw in {"qwen", "agy", "qwen_then_agy", "agy_then_qwen"}:
        return raw
    return "qwen_then_agy"


def llm_configured() -> bool:
    load_env_local()
    return qwen_configured() or agy_configured()


def _provider_chain() -> List[str]:
    mode = llm_provider_mode()
    if mode == "qwen":
        return ["qwen"]
    if mode == "agy":
        return ["agy"]
    if mode == "agy_then_qwen":
        return ["agy", "qwen"]
    return ["qwen", "agy"]


def _should_try_next_provider(result: Dict[str, Any]) -> bool:
    if result.get("ok"):
        return False
    err = str(result.get("error") or "")
    if err in {"missing_api_key", "agy_unavailable", "agy_spawn_failed"}:
        return True
    if err == "qwen_http_error":
        status = int(result.get("status") or 0)
        detail = str(result.get("detail") or "").lower()
        if status in {402, 403, 429}:
            return True
        if "quota" in detail or "allocationquota" in detail or "free tier" in detail:
            return True
    if err in {"agy_timeout", "agy_nonzero_exit", "agy_empty_response"}:
        return True
    return False


def call_llm_chat(
    prompt: str,
    *,
    model: str | None = None,
    stage: str | QwenTextStage | None = None,
    temperature: float = 0,
    json_mode: bool = False,
    timeout_s: int = 90,
    system: str | None = None,
) -> Dict[str, Any]:
    load_env_local()
    stage_name = str(stage or "general")
    providers = _provider_chain()
    qwen_models = qwen_text_model_candidates(model, stage=stage) if qwen_configured() else []
    primary_model = qwen_models[0] if qwen_models else str(model or os.getenv("HARDWARE_SPLICER_AGY_MODEL") or "gemini-2.5-flash")

    last_error: Dict[str, Any] = {"ok": False, "error": "no_llm_provider"}
    for index, provider in enumerate(providers):
        if provider == "qwen":
            selected_probe = primary_model
        else:
            selected_probe = str(model or os.getenv("HARDWARE_SPLICER_AGY_MODEL") or "gemini-2.5-flash")

        key = cache_key(
            stage=stage_name,
            prompt=prompt,
            system=system,
            model=selected_probe,
            temperature=temperature,
            json_mode=json_mode,
            provider=provider,
        )
        if cache_enabled():
            cached = read_cached_response(key)
            if cached:
                record_text_usage(
                    provider=str(cached.get("provider") or provider),
                    model=str(cached.get("model") or selected_probe),
                    stage=stage_name,
                    usage=cached.get("usage") or {},
                    cached=True,
                    prompt_excerpt=prompt,
                )
                return {**cached, "cached": True, "cache_key": key}

        if provider == "qwen":
            if not qwen_configured():
                last_error = {"ok": False, "error": "missing_api_key", "message": "Set DASHSCOPE_API_KEY or QWEN_API_KEY."}
                if index < len(providers) - 1:
                    continue
                return last_error
            result = _call_qwen_http(
                prompt,
                model=model,
                stage=stage,
                temperature=temperature,
                json_mode=json_mode,
                timeout_s=timeout_s,
                system=system,
            )
            selected_model = str(result.get("model") or primary_model)
        elif provider == "agy":
            if not agy_configured():
                last_error = {
                    "ok": False,
                    "error": "agy_unavailable",
                    "message": "agy CLI not on PATH.",
                }
                if index < len(providers) - 1:
                    continue
                return last_error
            agy_timeout = int(os.getenv("HARDWARE_SPLICER_AGY_TIMEOUT_S") or 600)
            result = call_agy_chat(
                prompt,
                model=model if provider == "agy" and model else None,
                temperature=temperature,
                json_mode=json_mode,
                timeout_s=max(timeout_s, agy_timeout),
                system=system,
            )
            selected_model = str(result.get("model") or selected_probe)
        else:
            continue

        key = cache_key(
            stage=stage_name,
            prompt=prompt,
            system=system,
            model=selected_model,
            temperature=temperature,
            json_mode=json_mode,
            provider=provider,
        )

        if result.get("ok"):
            write_cached_response(
                key,
                result,
                meta={"stage": stage_name, "provider": provider, "model": selected_model},
            )
            record_text_usage(
                provider=str(result.get("provider") or provider),
                model=selected_model,
                stage=stage_name,
                usage=result.get("usage") or {},
                cached=False,
                prompt_excerpt=prompt,
            )
            return {**result, "cached": False, "cache_key": key}

        last_error = result
        if index < len(providers) - 1 and _should_try_next_provider(result):
            last_error = {**result, "fallback_attempted": providers[index + 1 :]}
            continue
        return result

    return last_error

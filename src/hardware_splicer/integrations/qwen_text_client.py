"""Shared Qwen compatible-mode text client (no vision)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from ..env_local import load_env_local
from ..vision_evidence_assistant import DEFAULT_QWEN_BASE_URL, _provider_api_key
from .qwen_model_policy import (
    QwenTextStage,
    qwen_text_model_candidates,
    qwen_text_model_rotation,
    should_rotate_qwen_model,
)

# Back-compat: tuple snapshot; prefer qwen_text_model_rotation() for live env.
QWEN_TEXT_MODEL_ROTATION = qwen_text_model_rotation()


def qwen_api_key() -> str:
    load_env_local()
    return _provider_api_key({"provider": "qwen"}, "qwen")


def qwen_configured() -> bool:
    return bool(qwen_api_key())


def _call_qwen_http(
    prompt: str,
    *,
    model: str | None = None,
    stage: str | QwenTextStage | None = None,
    temperature: float = 0,
    json_mode: bool = False,
    timeout_s: int = 90,
    system: str | None = None,
) -> Dict[str, Any]:
    api_key = qwen_api_key()
    if not api_key:
        return {
            "ok": False,
            "error": "missing_api_key",
            "message": "Set DASHSCOPE_API_KEY or QWEN_API_KEY.",
        }

    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload_base: Dict[str, Any] = {
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload_base["response_format"] = {"type": "json_object"}

    base_url = str(
        os.environ.get("HARDWARE_SPLICER_QWEN_BASE_URL")
        or os.environ.get("QWEN_BASE_URL")
        or DEFAULT_QWEN_BASE_URL
    ).rstrip("/")
    models = qwen_text_model_candidates(model, stage=stage)
    body: Dict[str, Any] = {}
    last_error: Dict[str, Any] = {}
    selected_model = models[0]
    quota_errors: List[Dict[str, Any]] = []

    for index, candidate in enumerate(models):
        payload = {**payload_base, "model": candidate}
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
                selected_model = candidate
                break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            last_error = {"ok": False, "error": "qwen_http_error", "status": exc.code, "detail": detail}
            if should_rotate_qwen_model(
                status=exc.code,
                detail=detail,
                has_more_candidates=index < len(models) - 1,
            ):
                quota_errors.append({"model": candidate, "status": exc.code, "detail": detail[:240]})
                continue
            last_error["model_rotation"] = {
                "candidates": models,
                "quota_errors": quota_errors,
            }
            return last_error
        except Exception as exc:
            return {"ok": False, "error": "qwen_request_failed", "message": str(exc)}
    else:
        failed = last_error or {"ok": False, "error": "qwen_http_error"}
        failed["model_rotation"] = {"candidates": models, "quota_errors": quota_errors}
        return failed

    content = str((body.get("choices") or [{}])[0].get("message", {}).get("content") or "")
    return {
        "ok": True,
        "provider": "qwen",
        "model": body.get("model") or selected_model,
        "content": content,
        "usage": body.get("usage"),
        "model_rotation": {
            "stage": stage or "general",
            "candidates": models,
            "selected_model": body.get("model") or selected_model,
            "quota_errors": quota_errors,
        },
    }


def call_qwen_chat(
    prompt: str,
    *,
    model: str | None = None,
    stage: str | QwenTextStage | None = None,
    temperature: float = 0,
    json_mode: bool = False,
    timeout_s: int = 90,
    system: str | None = None,
) -> Dict[str, Any]:
    from .llm_text_client import call_llm_chat

    return call_llm_chat(
        prompt,
        model=model,
        stage=stage,
        temperature=temperature,
        json_mode=json_mode,
        timeout_s=timeout_s,
        system=system,
    )

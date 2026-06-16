"""Disk cache for text LLM responses (repeat dev runs, benchmarks)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


CACHE_SCHEMA_VERSION = "hardware_splicer.llm_response_cache.v1"
DEFAULT_CACHE_DIR = Path(".cache/hardware-splicer/llm-responses")


def cache_dir(configured: Optional[str] = None) -> Path:
    raw = str(configured or os.getenv("HARDWARE_SPLICER_LLM_CACHE_DIR") or DEFAULT_CACHE_DIR).strip()
    return Path(raw)


def cache_enabled() -> bool:
    raw = os.getenv("HARDWARE_SPLICER_LLM_CACHE", "1").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if os.getenv("HARDWARE_SPLICER_LLM_CACHE_BYPASS", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    return True


def cache_key(
    *,
    stage: str,
    prompt: str,
    system: Optional[str],
    model: str,
    temperature: float,
    json_mode: bool,
    provider: str,
) -> str:
    payload = json.dumps(
        {
            "stage": stage,
            "prompt": prompt,
            "system": system or "",
            "model": model,
            "temperature": temperature,
            "json_mode": json_mode,
            "provider": provider,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def read_cached_response(
    key: str,
    *,
    root: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    if not cache_enabled():
        return None
    path = (root or cache_dir()) / f"{key}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        response = data.get("response")
        if isinstance(response, dict) and response.get("ok"):
            return dict(response)
    except (OSError, json.JSONDecodeError):
        return None
    return None


def write_cached_response(
    key: str,
    response: Mapping[str, Any],
    *,
    meta: Optional[Mapping[str, Any]] = None,
    root: Optional[Path] = None,
) -> Path:
    target_dir = root or cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{key}.json"
    body = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "cache_key": key,
        "meta": dict(meta or {}),
        "response": dict(response),
    }
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path

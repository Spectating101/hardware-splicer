"""Antigravity CLI (`agy`) text backend — separate quota from DashScope."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, Optional


DEFAULT_AGY_MODEL = "gemini-2.5-flash"
DEFAULT_AGY_TIMEOUT_S = 600


def agy_binary() -> str:
    configured = str(os.getenv("HARDWARE_SPLICER_AGY_BIN") or "agy").strip() or "agy"
    return configured


def agy_configured() -> bool:
    if os.getenv("HARDWARE_SPLICER_AGY_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    return bool(shutil.which(agy_binary()))


def agy_model(explicit: Optional[str] = None) -> str:
    return str(
        explicit
        or os.getenv("HARDWARE_SPLICER_AGY_MODEL")
        or os.getenv("AGY_MODEL")
        or DEFAULT_AGY_MODEL
    ).strip()


def agy_timeout_s() -> int:
    raw = str(os.getenv("HARDWARE_SPLICER_AGY_TIMEOUT_S") or DEFAULT_AGY_TIMEOUT_S).strip()
    try:
        return max(30, int(raw))
    except ValueError:
        return DEFAULT_AGY_TIMEOUT_S


def call_agy_chat(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0,
    json_mode: bool = False,
    timeout_s: int | None = None,
    system: str | None = None,
) -> Dict[str, Any]:
    if not agy_configured():
        return {
            "ok": False,
            "error": "agy_unavailable",
            "message": "agy CLI not found on PATH. Install Antigravity CLI or set HARDWARE_SPLICER_AGY_BIN.",
        }

    selected_model = agy_model(model)
    wait_s = timeout_s if timeout_s is not None else agy_timeout_s()

    parts = []
    if system:
        parts.append(str(system).strip())
    user_prompt = str(prompt or "").strip()
    if json_mode and "json" not in user_prompt.lower():
        user_prompt = f"{user_prompt}\n\nReturn ONLY valid JSON. No markdown fences."
    parts.append(user_prompt)
    full_prompt = "\n\n".join(part for part in parts if part)

    cmd = [
        agy_binary(),
        "--print",
        "--model",
        selected_model,
        "--print-timeout",
        f"{wait_s}s",
        full_prompt,
    ]
    if temperature <= 0:
        pass  # agy defaults; no stable temperature flag documented

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=wait_s + 30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "agy_timeout",
            "message": f"agy did not finish within {wait_s}s",
            "model": selected_model,
        }
    except OSError as exc:
        return {"ok": False, "error": "agy_spawn_failed", "message": str(exc), "model": selected_model}

    stdout = str(completed.stdout or "").strip()
    stderr = str(completed.stderr or "").strip()
    if completed.returncode != 0 and not stdout:
        return {
            "ok": False,
            "error": "agy_nonzero_exit",
            "status": completed.returncode,
            "detail": stderr[:800],
            "model": selected_model,
        }

    content = stdout
    if not content:
        return {
            "ok": False,
            "error": "agy_empty_response",
            "detail": stderr[:800],
            "model": selected_model,
        }

    est_tokens = max(1, (len(full_prompt) + len(content)) // 4)
    return {
        "ok": True,
        "provider": "agy",
        "model": selected_model,
        "content": content,
        "usage": {
            "prompt_tokens": est_tokens * 3 // 4,
            "completion_tokens": est_tokens // 4,
            "total_tokens": est_tokens,
            "estimated": True,
        },
    }

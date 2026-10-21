"""Antigravity CLI (`agy`) text backend — separate quota from DashScope."""

from __future__ import annotations

import os
import shutil
import subprocess
import json
import tempfile
from typing import Any, Dict, Optional


DEFAULT_AGY_MODEL = "gemini-3.8-flash-medium"
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

    # Current agy parses --print as an optional-value flag: spelling it as
    # a standalone argument consumes the following --model switch as text.
    # `--print=<prompt>` is required. Sandbox + isolated cwd reduce ambient
    # file/tool access; agy does not yet advertise a strict no-tools switch.
    # Only the separate HS preview executor may mutate project artifacts.
    if len(full_prompt.encode("utf-8")) > 100_000:
        return {"ok": False, "error": "agy_prompt_too_large_for_cli", "model": selected_model}
    cmd = [
        agy_binary(),
        "--model", selected_model,
        "--mode", "plan",
        "--sandbox",
        "--disable-slash-commands",
        "--print-timeout", f"{wait_s}s",
        "--print=" + full_prompt,
    ]
    if temperature <= 0:
        pass  # agy defaults; no stable temperature flag documented

    try:
        # The model is a reasoning backend, not the engineering tool runner.
        # Isolate its workspace so agy's own context cannot read the HS repo.
        with tempfile.TemporaryDirectory(prefix="hs-agy-model-only-") as scratch:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=wait_s + 30,
                check=False,
                cwd=scratch,
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
    # agy can return a non-empty stdout JSON envelope for provider HTTP 429
    # while exiting nonzero. Never report that as a successful model answer.
    provider_failure=('quota' in (stdout+stderr).lower() or
        'RESOURCE_EXHAUSTED' in (stdout+stderr) or
        'Individual quota reached' in (stdout+stderr))
    if completed.returncode != 0:
        return {
            "ok": False,
            "error": "agy_quota_exhausted" if provider_failure else "agy_nonzero_exit",
            "status": completed.returncode,
            "detail": (stderr or stdout)[:800],
            "model": selected_model,
        }

    content = stdout
    if content.startswith('{') and '"conversation_id"' in content[:350]:
        try:
            envelope=json.loads(content)
            if envelope.get('status')=='ERROR' or envelope.get('error'):
                return {'ok':False,'error':'agy_quota_exhausted' if provider_failure else 'agy_provider_error',
                    'model':selected_model,
                    'detail':str(envelope.get('error'))[:500]}
        except (ValueError,TypeError):
            pass
    if json_mode:
        candidate=content
        if candidate.startswith('```json') or candidate.startswith('```'):
            candidate=candidate.partition('\n')[2].rsplit('```',1)[0].strip()
        try:
            json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            return {'ok':False,'error':'agy_invalid_json',
                'model':selected_model,'detail':'provider text was not a parseable JSON object'}
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

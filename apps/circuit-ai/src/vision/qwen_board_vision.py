"""Qwen native-vision adapter for board evidence.

This module is the live-provider boundary for Qwen-VL style board-photo
reasoning. It deliberately returns `board_evidence.v1` candidate evidence and
does not mark anything verified. Hardware authority, trust, and release
decisions remain downstream deterministic gates.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from src.config import settings
from src.intelligence.vision_board_evidence import board_evidence_bridge


PROMPT_VERSION = "qwen_board_evidence_prompt.v1"
DEFAULT_LEDGER = Path("data/vision/qwen-spend-ledger.json")
DEFAULT_MAX_TOKENS = 4096
DEFAULT_VISION_ROTATION = (
    "qwen3-vl-flash",
    "qwen3-vl-30b-a3b-thinking",
    "qwen-vl-ocr-2025-11-20",
)
DEFAULT_LOW_QUOTA_MODELS = ("qwen-plus", "qwen-plus-2025-07-28")


def _env_flag(name: str, fallback: bool = False) -> bool:
    raw = str(os.getenv(name) or "").strip().lower()
    if not raw:
        return fallback
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return fallback


def _qwen_disabled(cfg: Any = None) -> bool:
    cfg = cfg or settings
    return (
        _env_flag("QWEN_DISABLED")
        or _env_flag("QWEN_OUT_OF_QUOTA")
        or bool(getattr(cfg, "qwen_disabled", False))
        or bool(getattr(cfg, "qwen_out_of_quota", False))
    )


def qwen_vision_status() -> Dict[str, Any]:
    """Return non-secret status for native Qwen board vision."""

    key_configured = bool(_api_key())
    model = _model()
    rotation = _model_candidates()
    limits = _budget_limits(settings)
    disabled = _qwen_disabled()
    return {
        "schema_version": "qwen_board_vision_status.v1",
        "provider": "qwen",
        "model": model,
        "model_rotation": rotation,
        "disabled": disabled,
        "disabled_reason": "qwen_disabled_or_out_of_quota" if disabled else "",
        "base_url_configured": bool(_base_url()),
        "api_key_configured": key_configured,
        "ready_for_live_model": (not disabled) and key_configured and limits["monthly_usd"] > 0,
        "dry_run_available": True,
        "budget_limits": limits,
        "policy": {
            "live_calls_require_explicit_flag": True,
            "monthly_limit_required": True,
            "low_quota_models_routed_away": _low_quota_models(),
            "output_contract": "board_evidence.v1 candidate evidence only",
            "cannot_clear_power_or_splice_authority": True,
        },
    }


def analyze_board_image_with_qwen(
    image_bytes: bytes,
    *,
    filename: str = "board.png",
    media_type: str | None = None,
    goal: str = "",
    device_hint: str = "",
    symptoms: Sequence[str] = (),
    live: bool = False,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = 120,
    ledger_path: Path | None = None,
    settings_obj: Any = None,
) -> Dict[str, Any]:
    """Analyze one board image with Qwen, or return a dry-run request preview."""

    cfg = settings_obj or settings
    media = _media_type(filename, media_type)
    model_candidates = _model_candidates(cfg)
    model = model_candidates[0]
    prompt = board_evidence_prompt(goal=goal, device_hint=device_hint, symptoms=symptoms)
    request_body = _request_body(model=model, image_bytes=image_bytes, media_type=media, prompt=prompt, max_tokens=max_tokens, cfg=cfg)
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    estimated_input_tokens = _estimated_input_tokens(image_bytes)
    preflight = {
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": max_tokens,
        "estimated_usd": estimate_qwen_cost(model, estimated_input_tokens, max_tokens),
        "model": model,
        "model_rotation": model_candidates,
        "prompt_version": PROMPT_VERSION,
        "image_sha256": image_hash,
    }
    if not live:
        return {
            "schema_version": "qwen_board_vision_result.v1",
            "mode": "dry_run",
            "provider": "qwen",
            "model": model,
            "ready_for_live_model": qwen_vision_status()["ready_for_live_model"],
            "preflight": preflight,
            "request_preview": _redacted_request(request_body),
            "board_evidence": {},
            "vision_evidence_bridge": {},
            "claim_boundary": _claim_boundary(),
        }

    if _qwen_disabled(cfg):
        return {
            "schema_version": "qwen_board_vision_result.v1",
            "mode": "blocked_disabled",
            "provider": "qwen",
            "model": model,
            "preflight": preflight,
            "budget": {"allowed": False, "reason": "qwen_disabled_or_out_of_quota"},
            "board_evidence": {},
            "vision_evidence_bridge": {},
            "claim_boundary": _claim_boundary(),
        }

    budget = _check_budget(preflight["estimated_usd"], ledger_path=ledger_path)
    if not budget["allowed"]:
        return {
            "schema_version": "qwen_board_vision_result.v1",
            "mode": "blocked_budget",
            "provider": "qwen",
            "model": model,
            "preflight": preflight,
            "budget": budget,
            "board_evidence": {},
            "vision_evidence_bridge": {},
            "claim_boundary": _claim_boundary(),
        }

    started = time.time()
    response = {}
    actual_request_body = request_body
    quota_errors: List[Dict[str, Any]] = []
    for index, candidate in enumerate(model_candidates):
        actual_request_body = _request_body(
            model=candidate,
            image_bytes=image_bytes,
            media_type=media,
            prompt=prompt,
            max_tokens=max_tokens,
            cfg=cfg,
        )
        try:
            response = _call_qwen(actual_request_body, timeout=timeout, cfg=cfg)
            break
        except RuntimeError as exc:
            if index < len(model_candidates) - 1 and _is_quota_error(str(exc)):
                quota_errors.append({"model": candidate, "error": str(exc)[:500]})
                continue
            raise
    elapsed = round(time.time() - started, 3)
    parsed = parse_qwen_board_response(response)
    evidence = parsed.get("board_evidence") if isinstance(parsed.get("board_evidence"), dict) else {}
    diagnostics = parsed.get("parse_diagnostics") if isinstance(parsed.get("parse_diagnostics"), dict) else {}
    bridge = board_evidence_bridge(evidence) if evidence else {}
    usage = response.get("usage") if isinstance(response, dict) else {}
    input_tokens = int((usage or {}).get("prompt_tokens") or preflight["estimated_input_tokens"])
    output_tokens = int((usage or {}).get("completion_tokens") or 0)
    actual_model = str(response.get("model") or model)
    actual_cost = estimate_qwen_cost(actual_model, input_tokens, output_tokens or max_tokens)
    _append_ledger(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "provider": "qwen",
            "model": actual_model,
            "image_sha256": image_hash,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_usd": actual_cost,
            "elapsed_s": elapsed,
        },
        ledger_path=ledger_path,
    )
    return {
        "schema_version": "qwen_board_vision_result.v1",
        "mode": "live",
        "provider": "qwen",
        "model": actual_model,
        "preflight": preflight,
        "model_rotation": {
            "candidates": model_candidates,
            "quota_errors": quota_errors,
            "selected_model": actual_model,
        },
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_usd": actual_cost,
            "elapsed_s": elapsed,
        },
        "parse_diagnostics": diagnostics,
        "parsed": parsed,
        "board_evidence": evidence,
        "vision_evidence_bridge": bridge,
        "claim_boundary": _claim_boundary(),
    }


def board_evidence_prompt(*, goal: str = "", device_hint: str = "", symptoms: Sequence[str] = ()) -> str:
    symptom_text = ", ".join(str(item) for item in symptoms if str(item).strip()) or "none"
    return "\n".join(
        [
            "You are Circuit-AI native board vision.",
            "Return ONLY one compact JSON object.",
            "Top-level keys: safety_level, explanation, board_evidence.",
            "Use safety_level exactly one of: safe, caution, hazard.",
            "board_evidence must use schema_version board_evidence.v1.",
            "Use these board_evidence array keys exactly: components, markings, regions, damage, connectors, test_points, salvage_candidates.",
            "Put connectors, ports, sockets, headers, terminal blocks, USB, HDMI, Ethernet, and GPIO rows under connectors, not components.",
            "Each localized row should include id, label, kind, confidence, bbox when visible, missing_evidence, and warnings.",
            "Normalize bbox coordinates to 0-1 [x1,y1,x2,y2] when possible.",
            "Do not invent pinouts, voltages, nets, exact part numbers, or safe reuse claims without visible markings.",
            "Prefer unknown labels plus missing_evidence when unsure.",
            "Flag batteries, mains, high voltage, swollen cells, burns, corrosion, or cracked connectors as damage/hazard candidates.",
            "Every salvage candidate must include required_tests before reuse.",
            f"Goal: {goal or 'unknown board evidence intake'}",
            f"Device hint: {device_hint or 'none'}",
            f"Symptoms: {symptom_text}",
        ]
    )


def parse_qwen_board_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Qwen/OpenAI-compatible response into a board evidence object."""

    choices = response.get("choices") if isinstance(response, dict) else []
    first_choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = first_choice.get("message") if first_choice else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if isinstance(content, list):
        content = "\n".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
    text = str(content or "")
    parsed, json_error = _extract_json_object_with_error(text)
    if not isinstance(parsed, dict):
        parsed = {}
    finish_reason = str(first_choice.get("finish_reason") or "")
    evidence = parsed.get("board_evidence") if isinstance(parsed.get("board_evidence"), dict) else {}
    if not evidence and any(isinstance(parsed.get(key), list) for key in ("components", "connectors", "damage", "markings")):
        evidence = {
            "schema_version": "board_evidence.v1",
            "components": parsed.get("components") or [],
            "markings": parsed.get("markings") or [],
            "regions": parsed.get("regions") or [],
            "damage": parsed.get("damage") or [],
            "connectors": parsed.get("connectors") or [],
            "test_points": parsed.get("test_points") or [],
            "salvage_candidates": parsed.get("salvage_candidates") or [],
        }
    evidence.setdefault("schema_version", "board_evidence.v1")
    for key in ["components", "markings", "regions", "damage", "connectors", "test_points", "salvage_candidates"]:
        if not isinstance(evidence.get(key), list):
            evidence[key] = []
    parsed["board_evidence"] = evidence
    parsed["parse_diagnostics"] = {
        "json_valid": json_error == "",
        "json_error": json_error,
        "finish_reason": finish_reason or None,
        "truncated": finish_reason == "length" and bool(json_error),
        "content_length": len(text),
        "raw_board_evidence_available": bool(evidence),
        "counts": {
            key: len(evidence.get(key) or [])
            for key in ["components", "markings", "regions", "damage", "connectors", "test_points", "salvage_candidates"]
        },
        "recommendation": "Increase max_tokens or make the prompt more compact." if finish_reason == "length" and json_error else "",
    }
    return parsed


def estimate_qwen_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = _qwen_rates(model, input_tokens)
    return round((input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate, 6)


def _request_body(*, model: str, image_bytes: bytes, media_type: str, prompt: str, max_tokens: int, cfg: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": _image_data_url(image_bytes, media_type)}},
                ],
            }
        ],
    }
    disabled = bool(getattr(cfg, "qwen_json_mode_disabled", False)) or os.getenv("QWEN_JSON_MODE_DISABLED", "").lower() in {"1", "true", "yes", "on"}
    if not disabled:
        body["response_format"] = {"type": "json_object"}
    if os.getenv("QWEN_VL_HIGH_RESOLUTION_IMAGES", "false").lower() in {"1", "true", "yes", "on"}:
        body["vl_high_resolution_images"] = True
    return body


def _call_qwen(body: Dict[str, Any], *, timeout: int, cfg: Any) -> Dict[str, Any]:
    if _qwen_disabled(cfg):
        raise RuntimeError("Qwen is disabled locally because QWEN_DISABLED or QWEN_OUT_OF_QUOTA is set.")
    key = _api_key(cfg)
    if not key:
        raise RuntimeError("QWEN_API_KEY or DASHSCOPE_API_KEY is required for live Qwen vision.")
    base = _base_url(cfg).rstrip("/")
    endpoint = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Qwen vision HTTP {exc.code}: {detail}") from exc


def _is_quota_error(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "allocationquota",
            "freequota",
            "free quota",
            "quota",
            "insufficient",
            "billing",
        )
    )


def _check_budget(estimated_usd: float, *, ledger_path: Path | None) -> Dict[str, Any]:
    limits = _budget_limits(settings)
    if limits["monthly_usd"] <= 0:
        return {"allowed": False, "reason": "monthly_limit_required", "limits": limits}
    if estimated_usd > limits["max_usd_per_call"]:
        return {"allowed": False, "reason": "estimated_call_cost_exceeds_limit", "limits": limits, "estimated_usd": estimated_usd}
    daily, monthly = _ledger_spent(ledger_path=ledger_path)
    if daily + estimated_usd > limits["daily_usd"]:
        return {"allowed": False, "reason": "daily_limit_exceeded", "limits": limits, "daily_spent_usd": daily}
    if monthly + estimated_usd > limits["monthly_usd"]:
        return {"allowed": False, "reason": "monthly_limit_exceeded", "limits": limits, "monthly_spent_usd": monthly}
    return {"allowed": True, "limits": limits, "daily_spent_usd": daily, "monthly_spent_usd": monthly}


def _budget_limits(cfg: Any = None) -> Dict[str, float]:
    cfg = cfg or settings
    return {
        "monthly_usd": _safe_float(
            os.getenv("VISION_MONTHLY_USD_LIMIT") or getattr(cfg, "vision_monthly_usd_limit", None),
            0.0,
        ),
        "daily_usd": _safe_float(
            os.getenv("VISION_DAILY_USD_LIMIT") or getattr(cfg, "vision_daily_usd_limit", None),
            1.0,
        ),
        "max_usd_per_call": _safe_float(
            os.getenv("VISION_MAX_USD_PER_CALL") or getattr(cfg, "vision_max_usd_per_call", None),
            0.05,
        ),
    }


def _ledger_spent(*, ledger_path: Path | None) -> tuple[float, float]:
    path = ledger_path or DEFAULT_LEDGER
    data = _load_json(path, {"entries": []})
    entries = data.get("entries") if isinstance(data, dict) else []
    now = datetime.now(timezone.utc)
    day_prefix = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    daily = 0.0
    monthly = 0.0
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        ts = str(entry.get("ts") or "")
        value = _safe_float(entry.get("estimated_usd") or entry.get("estimatedUsd"), 0.0)
        if ts.startswith(day_prefix):
            daily += value
        if ts.startswith(month_prefix):
            monthly += value
    return round(daily, 6), round(monthly, 6)


def _append_ledger(entry: Dict[str, Any], *, ledger_path: Path | None) -> None:
    path = ledger_path or DEFAULT_LEDGER
    data = _load_json(path, {"schema_version": "qwen_board_vision_spend_ledger.v1", "entries": []})
    entries = data.get("entries") if isinstance(data, dict) and isinstance(data.get("entries"), list) else []
    entries.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "qwen_board_vision_spend_ledger.v1", "entries": entries[-1000:]}, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _redacted_request(body: Dict[str, Any]) -> Dict[str, Any]:
    preview = json.loads(json.dumps(body))
    for message in preview.get("messages", []):
        for block in message.get("content", []):
            if isinstance(block, dict) and block.get("type") == "image_url":
                url = str((block.get("image_url") or {}).get("url") or "")
                block["image_url"]["url"] = f"{url[:32]}...omitted-{len(url)}-chars"
    return preview


def _extract_json_object(text: str) -> Dict[str, Any]:
    parsed, _error = _extract_json_object_with_error(text)
    return parsed


def _extract_json_object_with_error(text: str) -> tuple[Dict[str, Any], str]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
        return (parsed if isinstance(parsed, dict) else {}), "" if isinstance(parsed, dict) else "json_root_not_object"
    except json.JSONDecodeError as exc:
        direct_error = f"{exc.msg} at char {exc.pos}"
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start:end])
                return (parsed if isinstance(parsed, dict) else {}), "" if isinstance(parsed, dict) else "json_root_not_object"
            except json.JSONDecodeError as inner_exc:
                return {}, f"{inner_exc.msg} at char {inner_exc.pos}"
        return {}, direct_error


def _image_data_url(image_bytes: bytes, media_type: str) -> str:
    data = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{media_type};base64,{data}"


def _media_type(filename: str, media_type: str | None) -> str:
    if media_type and "/" in media_type:
        return media_type
    suffix = Path(filename).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _estimated_input_tokens(image_bytes: bytes) -> int:
    return int(900 + 4096 + min(len(image_bytes) / 512, 4096))


def _qwen_rates(model: str, input_tokens: int) -> tuple[float, float]:
    normalized = model.lower()
    high = input_tokens > 128_000
    mid = input_tokens > 32_000
    if "qwen3-vl-plus" in normalized:
        return (0.43, 4.301) if high else (0.215, 2.15) if mid else (0.143, 1.434)
    if "qwen3-vl-flash-us" in normalized:
        return (0.12, 0.96) if high else (0.075, 0.6) if mid else (0.05, 0.4)
    if "qwen3-vl-flash" in normalized:
        return (0.086, 0.859) if high else (0.043, 0.43) if mid else (0.022, 0.215)
    return (_safe_float(os.getenv("QWEN_INPUT_USD_PER_M"), 0.05), _safe_float(os.getenv("QWEN_OUTPUT_USD_PER_M"), 0.4))


def _api_key(cfg: Any = None) -> str:
    cfg = cfg or settings
    return str(os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or getattr(cfg, "qwen_api_key", None) or getattr(cfg, "dashscope_api_key", None) or "").strip()


def _model(cfg: Any = None) -> str:
    return _model_candidates(cfg)[0]


def _model_candidates(cfg: Any = None) -> List[str]:
    cfg = cfg or settings
    configured_rotation = (
        os.getenv("QWEN_VISION_MODEL_ROTATION")
        or getattr(cfg, "qwen_vision_model_rotation", None)
        or ""
    )
    configured_single = os.getenv("QWEN_VISION_MODEL") or getattr(cfg, "qwen_vision_model", None)
    raw_candidates = [
        *_split_csv(configured_rotation),
        str(configured_single or "").strip(),
        *DEFAULT_VISION_ROTATION,
    ]
    blocked = set(_low_quota_models(cfg))
    candidates: List[str] = []
    seen = set()
    for raw in raw_candidates:
        model = str(raw or "").strip()
        if not model:
            continue
        key = model.lower()
        if _model_is_blocked(key, blocked) or key in seen:
            continue
        seen.add(key)
        candidates.append(model)
    if candidates:
        return candidates
    return [DEFAULT_VISION_ROTATION[0]]


def _low_quota_models(cfg: Any = None) -> List[str]:
    cfg = cfg or settings
    configured = (
        os.getenv("QWEN_LOW_QUOTA_MODELS")
        or os.getenv("QWEN_BLOCKED_MODELS")
        or getattr(cfg, "qwen_low_quota_models", None)
        or ",".join(DEFAULT_LOW_QUOTA_MODELS)
    )
    return [item.lower() for item in _split_csv(str(configured))]


def _model_is_blocked(model: str, blocked: set[str]) -> bool:
    normalized = model.lower()
    return any(normalized == item or normalized.startswith(f"{item}-") for item in blocked)


def _split_csv(value: Any) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _base_url(cfg: Any = None) -> str:
    cfg = cfg or settings
    return str(os.getenv("QWEN_BASE_URL") or getattr(cfg, "qwen_base_url", None) or "https://dashscope-intl.aliyuncs.com/compatible-mode/v1").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _claim_boundary() -> str:
    return "Qwen vision returns candidate board evidence only; measurements and deterministic authority gates decide power, splice, and production release."

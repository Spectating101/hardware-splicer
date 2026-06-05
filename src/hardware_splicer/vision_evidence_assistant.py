from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple


SCHEMA_VERSION = "hardware_splicer.vision_evidence_report.v1"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
DEFAULT_QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEFAULT_QWEN_MODEL = "qwen3-vl-flash"


def enrich_intake_with_vision_assistance(intake: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    body = dict(intake)
    report = build_vision_evidence_report(body)
    notes = _string_list(report.get("applied_evidence_notes"))
    if notes:
        existing = body.get("evidence_notes")
        if isinstance(existing, list):
            body["evidence_notes"] = [*existing, *notes]
        elif isinstance(existing, str) and existing.strip():
            body["evidence_notes"] = [existing, *notes]
        else:
            body["evidence_notes"] = notes
    return body, report


def build_vision_evidence_report(intake: Mapping[str, Any]) -> Dict[str, Any]:
    body = dict(intake)
    config = _vision_config(body)
    image_sources, skipped_sources = _vision_sources(body)
    candidates: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for source in image_sources:
        source_id = str(source.get("id") or source.get("path") or source.get("url") or f"vision_{len(candidates) + len(pending)}")
        notes = _source_annotation_notes(source)
        if notes:
            candidates.append(
                {
                    "source_id": source_id,
                    "provider": "attached_annotation",
                    "evidence_notes": notes,
                    "confidence": _float(source.get("confidence"), 0.75),
                    "requires_review": bool(source.get("requires_review", True)),
                }
            )
            continue
        pending.append(
            {
                "source_id": source_id,
                "reason": "No attached vision annotation was provided.",
                "path": source.get("path"),
                "url": source.get("url"),
            }
        )

    if config["enabled"] and config["provider"] == "qwen" and config["live"]:
        qwen_sources = [source for source in image_sources if not _source_annotation_notes(source)]
        if qwen_sources:
            try:
                qwen_candidate = _call_qwen_vision(body, qwen_sources[: config["max_images"]], config)
                if qwen_candidate.get("evidence_notes"):
                    candidates.append(qwen_candidate)
                    pending = [
                        row
                        for row in pending
                        if str(row.get("source_id")) not in set(_string_list(qwen_candidate.get("source_ids")))
                    ]
            except VisionAssistantError as exc:
                errors.append({"provider": "qwen", "message": str(exc), "retryable": exc.retryable})
    elif config["enabled"] and config["provider"] == "qwen" and not config["live"]:
        for source in image_sources:
            if _source_annotation_notes(source):
                continue
            pending.append(
                {
                    "source_id": str(source.get("id") or source.get("path") or source.get("url") or "vision_source"),
                    "reason": "Qwen vision provider is configured but live calls are disabled.",
                }
            )
    elif not config["enabled"] and image_sources:
        for source in image_sources:
            if _source_annotation_notes(source):
                continue
            pending.append(
                {
                    "source_id": str(source.get("id") or source.get("path") or source.get("url") or "vision_source"),
                    "reason": "Vision assistance is disabled.",
                }
            )

    applied_notes: List[str] = []
    if config["enabled"] and config["apply"]:
        for candidate in candidates:
            applied_notes.extend(_string_list(candidate.get("evidence_notes")))

    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": config["enabled"],
        "provider": config["provider"],
        "model": config["model"],
        "live": config["live"],
        "apply": config["apply"],
        "source_count": len(image_sources),
        "skipped_source_count": len(skipped_sources),
        "candidate_count": len(candidates),
        "pending_count": len(_dedupe_pending(pending)),
        "error_count": len(errors),
        "applied_note_count": len(applied_notes),
        "candidates": candidates,
        "applied_evidence_notes": applied_notes,
        "pending": _dedupe_pending(pending),
        "skipped_sources": skipped_sources,
        "errors": errors,
        "trust_policy": {
            "model_output_is_assistive": True,
            "applied_notes_still_pass_through_deterministic_extractor": True,
            "images_do_not_close_authority_gates_without_structured_evidence": True,
        },
    }


class VisionAssistantError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


def _call_qwen_vision(body: Dict[str, Any], sources: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    api_key = _api_key(config)
    if not api_key:
        raise VisionAssistantError(
            "Qwen vision live call requested but no API key was found. Set DASHSCOPE_API_KEY or QWEN_API_KEY.",
            retryable=False,
        )
    base_url = str(config.get("base_url") or DEFAULT_QWEN_BASE_URL).rstrip("/")
    url = f"{base_url}/chat/completions"
    source_ids = [str(row.get("id") or row.get("path") or row.get("url") or index) for index, row in enumerate(sources)]
    content = [{"type": "text", "text": _vision_prompt(body)}]
    for source in sources:
        image_url = _image_url(source, body)
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=int(config["timeout_s"])) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VisionAssistantError(f"Qwen vision request failed with HTTP {exc.code}: {_redact(detail)}", retryable=exc.code >= 500) from exc
    except Exception as exc:
        raise VisionAssistantError(f"Qwen vision request failed: {exc}", retryable=True) from exc

    message = _dict(_dict(_first(response_body.get("choices"))).get("message"))
    content_text = str(message.get("content") or "").strip()
    parsed = _parse_model_json(content_text)
    notes = _string_list(parsed.get("evidence_notes"))
    return {
        "source_ids": source_ids,
        "provider": "qwen",
        "model": config["model"],
        "base_url": base_url,
        "evidence_notes": notes,
        "observations": _string_list(parsed.get("observations")),
        "needs_human_review": _string_list(parsed.get("needs_human_review")),
        "confidence": _float(parsed.get("confidence"), 0.45),
        "requires_review": True,
        "raw_response_excerpt": content_text[:1200],
        "usage": response_body.get("usage") or {},
    }


def _vision_prompt(body: Dict[str, Any]) -> str:
    goal = str(body.get("goal") or body.get("intent") or body.get("brief") or "").strip()
    parts = [
        str(row.get("name") or row.get("type") or row)
        for row in _list_dicts(body.get("available_parts") or body.get("parts") or [])
    ]
    return (
        "You are assisting Hardware-Splicer evidence capture for a mechatronics project.\n"
        "Return strict JSON only with keys: evidence_notes, observations, needs_human_review, confidence.\n"
        "Use evidence_notes in this DSL, one note per string:\n"
        "- measure: <target> value_mm=<number> status=observed artifact=<uri>\n"
        "- clearance: <target> clearance_mm=<number> status=observed artifact=<uri>\n"
        "- mechanical_bench: <target> status=observed artifact=<uri>\n"
        "- robotics_bench: <target> status=observed artifact=<uri>\n"
        "- integrated_bench: <target> status=observed artifact=<uri>\n"
        "Only use status=pass/verified if the image visibly contains a test log, measurement label, or human annotation proving that status.\n"
        "Do not invent dimensions, test results, release approvals, hidden nets, pinouts, or unseen components.\n"
        "Prefer observations and needs_human_review when evidence is uncertain.\n"
        f"Project goal: {goal or 'not declared'}\n"
        f"Declared parts: {', '.join(parts) if parts else 'not declared'}"
    )


def _vision_config(body: Dict[str, Any]) -> Dict[str, Any]:
    raw = _dict(body.get("vision_assistance") or body.get("vision_model_assistance"))
    enabled = _bool(raw.get("enabled") if "enabled" in raw else raw.get("assist"))
    return {
        "enabled": enabled,
        "provider": str(raw.get("provider") or os.getenv("HARDWARE_SPLICER_VISION_PROVIDER") or "qwen").strip().lower(),
        "model": str(raw.get("model") or os.getenv("HARDWARE_SPLICER_VISION_MODEL") or DEFAULT_QWEN_MODEL).strip(),
        "base_url": str(raw.get("base_url") or os.getenv("DASHSCOPE_BASE_URL") or DEFAULT_QWEN_BASE_URL).strip(),
        "live": _bool(raw.get("live") or os.getenv("HARDWARE_SPLICER_VISION_LIVE")),
        "apply": _bool(raw.get("apply") or raw.get("auto_apply")),
        "max_images": max(1, min(int(_float(raw.get("max_images"), 4)), 8)),
        "timeout_s": max(10, min(int(_float(raw.get("timeout_s"), 60)), 180)),
    }


def _vision_sources(body: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    sources: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    base_dir = _base_dir(body)
    for row in _source_rows(body):
        source = dict(row)
        path = str(source.get("path") or source.get("file") or "").strip()
        url = str(source.get("url") or source.get("image_url") or "").strip()
        kind = str(source.get("kind") or source.get("type") or "").strip().lower()
        suffix = Path(path).suffix.lower() if path else ""
        if url:
            if _looks_like_image_url(url) or kind in {"image", "photo", "vision"}:
                source["url"] = url
                sources.append(source)
            else:
                skipped.append({"source_id": source.get("id") or url, "reason": "URL is not an image source."})
            continue
        if path:
            resolved = Path(path)
            if not resolved.is_absolute():
                resolved = base_dir / resolved
            source["path"] = str(resolved.resolve())
            suffix = resolved.suffix.lower()
        if suffix in IMAGE_EXTENSIONS or kind in {"image", "photo", "vision"}:
            sources.append(source)
        elif suffix in VIDEO_EXTENSIONS or kind == "video":
            skipped.append({"source_id": source.get("id") or path or "video", "reason": "Video evidence is indexed but not sent to the still-image vision assistant yet."})
        elif _source_annotation_notes(source):
            sources.append(source)
    return sources, skipped


def _source_rows(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in ["evidence_sources", "attachments"]:
        value = body.get(key)
        if isinstance(value, Mapping):
            value = [value]
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            for index, item in enumerate(value):
                row = dict(item) if isinstance(item, Mapping) else {"path": str(item)}
                row.setdefault("id", f"{key}_{index}")
                rows.append(row)
    return rows


def _source_annotation_notes(source: Dict[str, Any]) -> List[str]:
    for key in ["vision_evidence_notes", "vision_notes", "annotation_notes", "candidate_evidence_notes"]:
        notes = _string_list(source.get(key))
        if notes:
            return notes
    annotation = source.get("vision_annotation") or source.get("annotation")
    if isinstance(annotation, Mapping):
        return _string_list(annotation.get("evidence_notes"))
    return []


def _image_url(source: Dict[str, Any], body: Dict[str, Any]) -> str:
    url = str(source.get("url") or source.get("image_url") or "").strip()
    if url:
        return url
    path_text = str(source.get("path") or source.get("file") or "").strip()
    path = Path(path_text)
    if not path.is_absolute():
        path = _base_dir(body) / path
    path = path.resolve()
    if not path.exists():
        raise VisionAssistantError(f"Image source does not exist: {path}", retryable=False)
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _api_key(config: Dict[str, Any]) -> str:
    configured = str(config.get("api_key") or "").strip()
    if configured:
        return configured
    for name in ["DASHSCOPE_API_KEY", "QWEN_API_KEY", "qwen_api_key"]:
        value = os.getenv(name)
        if value:
            return value.strip()
    for env_file in _env_files():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() in {"DASHSCOPE_API_KEY", "QWEN_API_KEY", "qwen_api_key"}:
                    return value.strip().strip("'\"")
        except OSError:
            continue
    return ""


def _env_files() -> List[Path]:
    cwd = Path.cwd().resolve()
    files = [cwd / ".env.local", cwd / ".env"]
    for parent in cwd.parents:
        files.extend([parent / ".env.local", parent / ".env"])
    out: List[Path] = []
    seen = set()
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        if path.exists() and path.is_file() and path.stat().st_size <= 1024 * 1024:
            out.append(path)
    return out[:8]


def _parse_model_json(content: str) -> Dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
        return _dict(parsed)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return _dict(json.loads(match.group(0)))
            except Exception:
                return {}
    return {}


def _dedupe_pending(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for row in rows:
        key = str(row.get("source_id") or row.get("path") or row.get("url") or row.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _redact(value: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_-]+|[A-Za-z0-9_-]{24,}", "[redacted]", value)


def _base_dir(body: Dict[str, Any]) -> Path:
    source_file = str(body.get("source_file") or "").strip()
    if source_file:
        return Path(source_file).resolve().parent
    return Path.cwd()


def _looks_like_image_url(url: str) -> bool:
    lowered = url.lower().split("?", 1)[0]
    return lowered.startswith("data:image/") or any(lowered.endswith(ext) for ext in IMAGE_EXTENSIONS)


def _first(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return {}


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Iterable) and not isinstance(value, (Mapping, bytes)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value)]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled", "apply", "live"}

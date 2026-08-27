"""Model-backed catalog build proposal over the bounded recipe registry.

This selector receives the project goal, declared parts and optional structured planner
context. Architecture-answer hints from legacy planners are stripped before prompt
construction so callers cannot recreate the old keyword router by smuggling a preferred
build ID into model context. The result remains proposal-only and zero-authority.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Mapping, Sequence

from ..catalog import CATALOG_BUILD_IDS
from .build_id_hints import build_catalog_context_for_pick
from .qwen_text_client import call_qwen_chat, qwen_configured

SCHEMA_VERSION = "hardware_splicer.qwen_build_pick.v2"

_FORBIDDEN_HINT_KEY_FRAGMENTS = (
    "build_id",
    "keyword",
    "archetype",
    "recommended_build",
    "mapped_build",
    "planner_agree",
    "planners_agree",
)


def qwen_build_pick_enabled() -> bool:
    if os.environ.get("HARDWARE_SPLICER_QWEN_BUILD_PICK", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    return qwen_configured()


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, Mapping):
        raise ValueError("build proposal response must be a JSON object")
    return dict(parsed)


def _is_architecture_answer_key(key: str) -> bool:
    lowered = key.strip().lower()
    return any(fragment in lowered for fragment in _FORBIDDEN_HINT_KEY_FRAGMENTS)


def _sanitize_planner_hint_value(value: Any, *, ignored: set[str], path: str = "hints") -> Any:
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if _is_architecture_answer_key(key):
                ignored.add(f"{path}.{key}")
                continue
            result[key] = _sanitize_planner_hint_value(
                raw_value,
                ignored=ignored,
                path=f"{path}.{key}",
            )
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _sanitize_planner_hint_value(row, ignored=ignored, path=f"{path}[{index}]")
            for index, row in enumerate(list(value)[:64])
        ]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def sanitize_planner_hints(planner_hints: Mapping[str, Any] | None) -> tuple[Dict[str, Any], list[str]]:
    """Remove legacy architecture-answer hints while preserving neutral context."""
    ignored: set[str] = set()
    sanitized = _sanitize_planner_hint_value(dict(planner_hints or {}), ignored=ignored)
    return dict(sanitized) if isinstance(sanitized, Mapping) else {}, sorted(ignored)


def call_qwen_build_pick(
    *,
    goal: str,
    parts: List[Mapping[str, Any]] | None = None,
    planner_hints: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Propose one catalog build ID, or remain unresolved when none is defensible."""
    if not qwen_build_pick_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled_or_no_key"}

    part_lines = [
        {
            "name": p.get("name"),
            "type": p.get("type"),
            "voltage_v": p.get("voltage_v"),
            "current_a": p.get("current_a"),
            "capabilities": p.get("capabilities") or p.get("capability_tags"),
        }
        for p in (parts or [])
    ]
    allowed = sorted(CATALOG_BUILD_IDS)
    hints, ignored_hint_keys = sanitize_planner_hints(planner_hints)

    prompt = f"""Propose the best bounded Hardware Splicer catalog build recipe for this project.

Goal:
{goal}

Declared/parsed parts:
{json.dumps(part_lines, indent=2, sort_keys=True)}

Structured planner context, if any (context only; architecture-answer hints are excluded):
{json.dumps(hints, indent=2, sort_keys=True)}

Build recipes (build_id: descriptive scope):
{build_catalog_context_for_pick()}

Allowed build_id values:
{json.dumps(allowed, indent=2)}

Return JSON only:
{{
  "build_id": "one allowed id or null",
  "reasoning": "why the engineering function and supplied constraints fit this bounded recipe",
  "confidence": 0.0,
  "unresolved_questions": []
}}

Rules:
- Select only from the supplied build IDs, or null when no recipe is defensible.
- Reason from the engineering function, declared parts and explicit constraints; do not use literal keyword matching as a decision rule.
- Do not invent voltage, current, interface, donor identity, or component facts.
- If facts needed to choose are missing or conflicting, prefer null and list the unresolved questions.
- A build_id is a proposal only. It does not authorize compilation, fabrication, flashing, power, motion, or release.
"""

    response = call_qwen_chat(
        prompt,
        json_mode=True,
        stage="build_pick",
        system="Choose only from the supplied bounded build registry, or return null when unresolved. Do not infer hidden keyword rules.",
        timeout_s=45,
    )
    if not response.get("ok"):
        return {**response, "skipped": False, "ignored_planner_hint_keys": ignored_hint_keys}

    try:
        body = _extract_json_object(str(response.get("content") or "{}"))
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "ok": False,
            "error": "invalid_json",
            "message": str(exc),
            "ignored_planner_hint_keys": ignored_hint_keys,
        }

    raw_build_id = body.get("build_id")
    build_id = str(raw_build_id or "").strip() or None
    if build_id is not None and build_id not in allowed:
        return {
            "ok": False,
            "error": "invalid_build_id",
            "build_id": build_id,
            "ignored_planner_hint_keys": ignored_hint_keys,
        }

    try:
        confidence = float(body.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    unresolved_questions = [
        str(row).strip()
        for row in list(body.get("unresolved_questions") or [])[:24]
        if str(row).strip()
    ]

    if build_id is None and not unresolved_questions and not str(body.get("reasoning") or "").strip():
        return {
            "ok": False,
            "error": "unresolved_without_explanation",
            "message": "null build proposal must explain why it is unresolved",
            "ignored_planner_hint_keys": ignored_hint_keys,
        }

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "model": response.get("model"),
        "usage": response.get("usage"),
        "build_id": build_id,
        "reasoning": str(body.get("reasoning") or ""),
        "confidence": confidence,
        "unresolved_questions": unresolved_questions,
        "ignored_planner_hint_keys": ignored_hint_keys,
        "proposal_authority": "proposed",
        "authority_effect": "none",
        "automatic_execution": False,
    }

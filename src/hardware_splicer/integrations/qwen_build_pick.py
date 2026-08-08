"""Model-backed catalog build proposal over the bounded recipe registry.

This selector receives the project goal, declared parts and optional structured planner
hints. It does not receive a hidden keyword-derived answer and does not contain phrase
rules that recreate the legacy router inside the prompt. The result is proposal-only;
callers remain responsible for evidence, review and deterministic verification.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Mapping

from ..catalog import CATALOG_BUILD_IDS
from .build_id_hints import build_catalog_context_for_pick
from .qwen_text_client import call_qwen_chat, qwen_configured

SCHEMA_VERSION = "hardware_splicer.qwen_build_pick.v2"


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
    hints = dict(planner_hints or {})

    prompt = f"""Propose the best bounded Hardware Splicer catalog build recipe for this project.

Goal:
{goal}

Declared/parsed parts:
{json.dumps(part_lines, indent=2, sort_keys=True)}

Structured planner hints, if any (these are context, not authority):
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
        return {**response, "skipped": False}

    try:
        body = _extract_json_object(str(response.get("content") or "{}"))
    except (json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "error": "invalid_json", "message": str(exc)}

    raw_build_id = body.get("build_id")
    build_id = str(raw_build_id or "").strip() or None
    if build_id is not None and build_id not in allowed:
        return {"ok": False, "error": "invalid_build_id", "build_id": build_id}

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
        "proposal_authority": "proposed",
        "authority_effect": "none",
        "automatic_execution": False,
    }

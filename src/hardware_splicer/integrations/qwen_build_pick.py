"""LLM catalog build pick — replaces keyword _pick_build_id when keyed."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Mapping, Optional

from ..catalog import CATALOG_BUILD_IDS
from .build_id_hints import build_catalog_context_for_pick, keyword_build_id
from .qwen_text_client import call_qwen_chat, qwen_configured

SCHEMA_VERSION = "hardware_splicer.qwen_build_pick.v1"


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
    return json.loads(text)


def call_qwen_build_pick(
    *,
    goal: str,
    parts: List[Mapping[str, Any]] | None = None,
    planner_hints: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Pick catalog build_id from goal + parts. Validated against CATALOG_BUILD_IDS."""
    if not qwen_build_pick_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled_or_no_key"}

    part_lines = [
        {"name": p.get("name"), "type": p.get("type"), "voltage_v": p.get("voltage_v")}
        for p in (parts or [])
    ]
    allowed = sorted(CATALOG_BUILD_IDS)
    keyword_hint = keyword_build_id(goal, parts)
    hints = dict(planner_hints or {})
    if keyword_hint:
        hints.setdefault("keyword_build_hint", keyword_hint)

    prompt = f"""Pick the best catalog build recipe for this hardware project.

Goal: {goal}
Parts: {json.dumps(part_lines, indent=2)}
Planner hints (may help, may be wrong): {json.dumps(hints, indent=2)}

Build recipes (build_id: when to use):
{build_catalog_context_for_pick()}

Allowed build_id values ONLY:
{json.dumps(allowed, indent=2)}

Return JSON:
{{
  "build_id": "one of the allowed ids",
  "reasoning": "2 sentences",
  "confidence": 0.0-1.0
}}

Rules:
- Fan, airflow, ventilation, solder fumes, cooling → usb_fume_extractor (not generic).
- Fan + temperature sensor + automatic control → usb_fume_extractor.
- Soil, plant, pump, irrigation → automatic_plant_watering.
- Rover, wheels, mobile robot → robot_drive_base.
- Only use generic_low_voltage_build when no specific recipe fits.
- Prefer keyword_build_hint when it matches the goal unless you are highly confident otherwise.
"""

    response = call_qwen_chat(
        prompt,
        json_mode=True,
        stage="build_pick",
        system="Pick catalog build_id from the allowed list only.",
        timeout_s=45,
    )
    if not response.get("ok"):
        return {**response, "skipped": False}

    try:
        body = _extract_json_object(str(response.get("content") or "{}"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": "invalid_json", "message": str(exc)}

    build_id = str(body.get("build_id") or "").strip()
    if build_id not in allowed:
        return {"ok": False, "error": "invalid_build_id", "build_id": build_id}

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "model": response.get("model"),
        "usage": response.get("usage"),
        "build_id": build_id,
        "reasoning": str(body.get("reasoning") or ""),
        "confidence": float(body.get("confidence") or 0.75),
    }

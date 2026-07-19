"""Qwen workshop review: reason over salvage intake after heuristics + gap-fill.

Does not replace catalog/DRC truth — suggests validated module_id additions/overrides only.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Mapping

from ..pcb.module_registry import find_module
from .catalog_context import build_salvage_catalog_context
from .qwen_text_client import call_qwen_chat, qwen_configured

SCHEMA_VERSION = "hardware_splicer.qwen_workshop_review.v1"


def workshop_review_enabled() -> bool:
    from .llm_policy import offline_salvage_enabled, qwen_llm_first

    if offline_salvage_enabled() or not qwen_llm_first():
        return False
    if os.environ.get("HARDWARE_SPLICER_QWEN_WORKSHOP", "").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    if os.environ.get("HARDWARE_SPLICER_QWEN_WORKSHOP", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return qwen_configured()
    # Default on when Qwen is keyed (same spirit as llm_first salvage).
    return qwen_configured()


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _valid_module_id(module_id: str | None) -> bool:
    if not module_id:
        return False
    return find_module(str(module_id).strip()) is not None


def call_qwen_workshop_review(
    *,
    goal: str,
    parts: List[Mapping[str, Any]],
    resolved_modules: List[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None = None,
    recommended_build_id: str | None = None,
) -> Dict[str, Any]:
    """Review salvage plan; return suggestions (not auto-applied unless caller merges)."""
    if not workshop_review_enabled():
        return {"ok": False, "skipped": True, "reason": "workshop_review_disabled_or_no_key"}

    resolved_lines = [
        {
            "part_name": row.get("part_name"),
            "module_id": row.get("module_id"),
            "role": row.get("role"),
            "source": row.get("source"),
        }
        for row in resolved_modules
    ]
    part_lines = [
        {
            "name": part.get("name"),
            "type": part.get("type"),
            "module_id": part.get("module_id"),
            "voltage_v": part.get("voltage_v"),
        }
        for part in parts
    ]

    prompt = f"""You are a hardware workshop assistant reviewing a salvage intake plan BEFORE PCB compile.

Project goal: {goal}
Recommended catalog build (heuristic): {recommended_build_id or "unknown"}
Constraints: {json.dumps(dict(constraints or {}), indent=2)}

Intake parts:
{json.dumps(part_lines, indent=2)}

Resolved modules so far (heuristic + gap-fill):
{json.dumps(resolved_lines, indent=2)}

Return JSON only:
{{
  "reasoning": "2-4 sentences on whether the plan matches the goal",
  "risks": ["short risk bullets"],
  "suggested_build_id": "catalog build id or null",
  "add_modules": [
    {{"module_id": "catalog-id", "role": "drv|sns|pwr|mcu|load|buck|misc", "reason": "why"}}
  ],
  "role_overrides": {{"role": "module_id"}},
  "suggested_purchases": ["module-id"],
  "confidence": 0.0-1.0
}}

Rules:
- module_id values MUST exist in the catalog hint; never invent IDs.
- Prefer keeping heuristic resolves; only add_modules for clear gaps (driver for motors, level shifter for 5V sensor on 3.3V MCU, etc.).
- Do not duplicate module_id already in resolved modules.
- Motors are loads, not L298N — suggest L298N only as driver when motors exist without a driver.
{build_salvage_catalog_context(max_entries=100)}
"""

    response = call_qwen_chat(
        prompt,
        json_mode=True,
        stage="workshop",
        system="You review salvage hardware plans. Output only valid catalog module_id values.",
        timeout_s=60,
    )
    if not response.get("ok"):
        return {**response, "skipped": False}

    try:
        body = _extract_json_object(str(response.get("content") or "{}"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": "invalid_json", "message": str(exc)}

    existing_ids = {
        str(row.get("module_id") or "").strip()
        for row in resolved_modules
        if str(row.get("module_id") or "").strip()
    }
    add_modules: List[Dict[str, Any]] = []
    for row in body.get("add_modules") or []:
        if not isinstance(row, dict):
            continue
        module_id = str(row.get("module_id") or "").strip()
        if not _valid_module_id(module_id) or module_id in existing_ids:
            continue
        add_modules.append(
            {
                "module_id": module_id,
                "role": str(row.get("role") or "misc"),
                "reason": str(row.get("reason") or ""),
            }
        )
        existing_ids.add(module_id)

    role_overrides: Dict[str, str] = {}
    for role, module_id in (body.get("role_overrides") or {}).items():
        mid = str(module_id or "").strip()
        if mid and _valid_module_id(mid):
            role_overrides[str(role)] = mid

    build_id = str(body.get("suggested_build_id") or "").strip() or None

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "provider": response.get("provider"),
        "model": response.get("model"),
        "usage": response.get("usage"),
        "reasoning": str(body.get("reasoning") or ""),
        "risks": [str(x) for x in (body.get("risks") or []) if str(x).strip()],
        "confidence": float(body.get("confidence") or 0.0),
        "suggested_build_id": build_id,
        "add_modules": add_modules,
        "role_overrides": role_overrides,
        "suggested_purchases": [
            str(x).strip() for x in (body.get("suggested_purchases") or []) if str(x).strip()
        ],
    }


_WORKSHOP_DRIVER_IDS = frozenset(
    {
        "l298n",
        "drv8833-motor",
        "l9110-motor",
        "tb6612fng-motor",
        "bts7960-motor",
        "mosfet-irlz44n",
        "a4988-stepper",
        "tmc2209-stepper",
        "drv8825_stepper",
    }
)


def apply_workshop_review(
    resolved_modules: List[Dict[str, Any]],
    review: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Merge validated workshop review suggestions into resolved module rows."""
    if not review.get("ok"):
        return resolved_modules

    from ..module_resolver import donor_has_bound_driver

    rows = [dict(row) for row in resolved_modules]
    seen_ids = {str(row.get("module_id") or "").strip() for row in rows if row.get("module_id")}
    donor_drv = donor_has_bound_driver(rows)

    for hit in review.get("add_modules") or []:
        if not isinstance(hit, dict):
            continue
        module_id = str(hit.get("module_id") or "").strip()
        if not module_id or module_id in seen_ids:
            continue
        # Refuse catalog driver gap-fill when donor actuator_driver is already bound.
        if donor_drv and (
            module_id in _WORKSHOP_DRIVER_IDS or str(hit.get("role") or "") == "drv"
        ):
            continue
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "part_name": str(hit.get("reason") or "workshop suggestion"),
                "module_id": module_id,
                "role": str(hit.get("role") or "misc"),
                "source": "qwen_workshop",
                "confidence": float(review.get("confidence") or 0.75),
                "matched_on": "workshop_review",
            }
        )
        seen_ids.add(module_id)

    overrides = dict(review.get("role_overrides") or {})
    if overrides:
        for row in rows:
            role = str(row.get("role") or "")
            if role in overrides:
                row["module_id"] = overrides[role]
                row["source"] = "qwen_workshop_override"

    return rows

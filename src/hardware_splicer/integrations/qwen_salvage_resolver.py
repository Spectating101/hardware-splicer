"""Qwen salvage mapping — LLM reads parts like a human; catalog is the validated menu."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Mapping, Optional

from ..pcb.module_registry import find_module
from .catalog_context import catalog_context_for_goal, build_salvage_catalog_context
from .qwen_text_client import call_qwen_chat, qwen_configured

SCHEMA_VERSION = "hardware_splicer.qwen_salvage_resolver.v2"


def qwen_salvage_enabled() -> bool:
    from .llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        return False
    if os.environ.get("HARDWARE_SPLICER_QWEN_SALVAGE", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    return qwen_configured()


def salvage_resolve_mode() -> str:
    """llm_only (default when keyed) | llm_first | heuristic."""
    explicit = os.environ.get("HARDWARE_SPLICER_SALVAGE_RESOLVE", "").strip().lower()
    if explicit in {"llm_first", "heuristic", "llm_only"}:
        return explicit
    if qwen_salvage_enabled():
        return "llm_only"
    return "heuristic"


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


def _part_lines(parts: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    lines: List[Dict[str, Any]] = []
    for part in parts:
        lines.append(
            {
                "name": part.get("name"),
                "type": part.get("type"),
                "kind": part.get("kind"),
                "module_id": part.get("module_id"),
                "voltage_v": part.get("voltage_v"),
                "current_a": part.get("current_a"),
            }
        )
    return lines


def call_qwen_salvage_map_intake(
    *,
    goal: str,
    parts: List[Mapping[str, Any]],
    heuristic_hints: List[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Map every intake part to catalog module_id using goal + part context (one LLM call)."""
    if not qwen_salvage_enabled() or not parts:
        return {"ok": False, "skipped": True, "reason": "disabled_or_empty"}

    to_map = [p for p in parts if not str(p.get("module_id") or "").strip()]
    if not to_map:
        return {"ok": False, "skipped": True, "reason": "all_parts_have_explicit_module_id"}

    catalog = catalog_context_for_goal(goal)
    hints = [
        {
            "part_name": row.get("part_name"),
            "module_id": row.get("module_id"),
            "matched_on": row.get("matched_on"),
            "confidence": row.get("confidence"),
        }
        for row in (heuristic_hints or [])
        if row.get("module_id")
    ]

    prompt = f"""You are mapping salvaged physical parts to breakout modules in our compile library.

Read each part like a maker would — name, type, voltage, goal — NOT by keyword regex.
The catalog below is the ONLY allowed source of module_id values. Pick the best fit or reject.

Project goal:
{goal}

Parts to map (one row per physical item):
{json.dumps(_part_lines(to_map), indent=2)}

Weak heuristic guesses (often wrong — verify or override):
{json.dumps(hints, indent=2) if hints else "none"}

Catalog (module_id: label | capabilities):
{catalog}

Return JSON only:
{{
  "reasoning": "2-3 sentences on how parts support the goal",
  "resolved": [
    {{"part_name": "exact name from intake", "module_id": "catalog-id", "role": "mcu|sns|drv|pwr|mot|load|act|buck|misc", "confidence": 0.0-1.0, "reason": "why this module"}}
  ],
  "rejected": [
    {{"part_name": "...", "reason": "no catalog fit / not needed on PCB"}}
  ],
  "suggested_purchases": ["module-id-to-buy"],
  "power_notes": "optional note on USB vs battery vs barrel"
}}

Rules:
- module_id MUST be from the catalog; never invent IDs.
- DC gear motors → dc_motor_3v_6v or dc_geared_motor_12v (role mot), NOT l298n.
- l298n is a driver board you buy separately — only if user has an L298N driver part.
- Two identical motors → same module_id is fine (one catalog motor type).
- Chassis, wheels, zip ties → reject (not PCB modules).
- If a 5V sensor meets a 3.3V MCU, note level shifter in suggested_purchases.
"""

    response = call_qwen_chat(
        prompt,
        json_mode=True,
        stage="salvage",
        system="You map salvage parts to validated catalog module_id values. Reason about the goal.",
        timeout_s=75,
    )
    if not response.get("ok"):
        return {**response, "skipped": False}

    try:
        body = _extract_json_object(str(response.get("content") or "{}"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": "invalid_json", "message": str(exc)}

    resolved_rows: List[Dict[str, Any]] = []
    for row in body.get("resolved") or []:
        if not isinstance(row, dict):
            continue
        module_id = str(row.get("module_id") or "").strip()
        if not _valid_module_id(module_id):
            continue
        resolved_rows.append(
            {
                "part_name": str(row.get("part_name") or ""),
                "module_id": module_id,
                "role": str(row.get("role") or "misc"),
                "confidence": float(row.get("confidence") or 0.8),
                "reason": str(row.get("reason") or ""),
            }
        )

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "provider": response.get("provider"),
        "model": response.get("model"),
        "usage": response.get("usage"),
        "reasoning": str(body.get("reasoning") or ""),
        "power_notes": str(body.get("power_notes") or ""),
        "resolved": resolved_rows,
        "rejected": [dict(r) for r in (body.get("rejected") or []) if isinstance(r, dict)],
        "suggested_purchases": [
            str(x).strip() for x in (body.get("suggested_purchases") or []) if str(x).strip()
        ],
    }


def call_qwen_salvage_resolve(
    *,
    goal: str,
    parts: List[Mapping[str, Any]],
    unresolved: List[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Legacy: unresolved-only path. Prefer call_qwen_salvage_map_intake."""
    if not unresolved:
        return {"ok": False, "skipped": True, "reason": "nothing_to_resolve"}
    need_names = {str(row.get("part_name") or "").lower() for row in unresolved}
    subset = [
        p
        for p in parts
        if str(p.get("name") or "").lower() in need_names or not str(p.get("module_id") or "").strip()
    ]
    return call_qwen_salvage_map_intake(goal=goal, parts=subset or parts, heuristic_hints=unresolved)


def merge_qwen_intake_map(
    parts: List[Mapping[str, Any]],
    qwen: Mapping[str, Any],
    *,
    explicit_rows: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Build resolved module rows from LLM intake map (+ explicit module_id parts)."""
    from ..module_resolver import SCHEMA_VERSION, _role_for_module_id

    by_name = {str(r.get("part_name") or "").lower(): r for r in qwen.get("resolved") or [] if isinstance(r, dict)}
    rows: List[Dict[str, Any]] = list(explicit_rows or [])
    seen_ids: set[str] = {str(r.get("module_id")) for r in rows if r.get("module_id")}

    for part in parts:
        explicit_id = str(part.get("module_id") or "").strip()
        if explicit_id:
            continue
        name = str(part.get("name") or "")
        hit = by_name.get(name.lower())
        if not hit:
            continue
        module_id = str(hit.get("module_id") or "").strip()
        if not module_id or module_id in seen_ids:
            # allow duplicate motor parts to collapse later; still append if new id
            if module_id in seen_ids:
                continue
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "part_name": name,
                "module_id": module_id,
                "role": str(hit.get("role") or _role_for_module_id(module_id, part)),
                "source": "qwen_salvage",
                "confidence": float(hit.get("confidence") or 0.8),
                "matched_on": str(hit.get("reason") or "qwen_intake_map"),
            }
        )
        seen_ids.add(module_id)

    return rows


def merge_qwen_salvage_into_resolved(
    resolved: List[Dict[str, Any]],
    qwen: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Apply Qwen salvage rows onto heuristic resolve output."""
    if not qwen.get("ok"):
        return resolved

    by_name = {str(r.get("part_name") or "").lower(): i for i, r in enumerate(resolved)}
    rows = [dict(r) for r in resolved]
    seen_ids = {str(r.get("module_id")) for r in rows if r.get("module_id")}

    for hit in qwen.get("resolved") or []:
        if not isinstance(hit, dict):
            continue
        part_name = str(hit.get("part_name") or "")
        module_id = str(hit.get("module_id") or "").strip()
        if not part_name or not module_id:
            continue
        row = {
            "schema_version": SCHEMA_VERSION,
            "part_name": part_name,
            "module_id": module_id,
            "role": str(hit.get("role") or "misc"),
            "source": "qwen_salvage",
            "confidence": float(hit.get("confidence") or 0.75),
            "matched_on": str(hit.get("reason") or "qwen_salvage"),
        }
        key = part_name.lower()
        if key in by_name:
            prev = rows[by_name[key]]
            if prev.get("source") != "user_inventory":
                rows[by_name[key]] = row
        elif module_id not in seen_ids:
            rows.append(row)
        seen_ids.add(module_id)

    return rows

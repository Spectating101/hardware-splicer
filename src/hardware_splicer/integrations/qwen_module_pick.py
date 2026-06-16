"""LLM module pick for open compose — replaces regex MODULE_HINTS when keyed."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Mapping

from ..pcb.module_registry import find_module
from .catalog_context import catalog_context_for_goal
from .qwen_text_client import call_qwen_chat, qwen_configured

SCHEMA_VERSION = "hardware_splicer.qwen_module_pick.v1"


def qwen_module_pick_enabled() -> bool:
    if os.environ.get("HARDWARE_SPLICER_QWEN_MODULE_PICK", "1").strip().lower() in {
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


def call_qwen_module_pick(
    goal: str,
    *,
    constraints: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Pick module_id list for a NL goal. All IDs validated against module library."""
    if not qwen_module_pick_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled_or_no_key"}

    catalog = catalog_context_for_goal(goal, max_entries=100)
    prompt = f"""Pick breakout modules to build this project on a solderless breadboard / module PCB.

Goal: {goal}
Constraints: {json.dumps(dict(constraints or {}), indent=2)}

Catalog (module_id: label | capabilities):
{catalog}

Return JSON:
{{
  "reasoning": "2-3 sentences",
  "module_ids": ["id1", "id2", ...],
  "power_topology": "usb_5v|barrel_12v|hybrid|battery"
}}

Rules:
- 2 to 8 module_id values from catalog only.
- Include power (usb-power-5v or dc-barrel-12v) when needed.
- Include MCU (esp32-devkit, arduino-nano, rpi-pico) when logic is needed.
- Pump or fan loads need mosfet-irlz44n (or relay-1ch-5v) as driver — never wire pump/fan GPIO-direct.
- 5V sensors (hc-sr04) on 3.3V MCU need level-shifter-4ch.
- Do not invent module_id values.
"""

    response = call_qwen_chat(
        prompt,
        json_mode=True,
        stage="module_pick",
        system="Output only valid catalog module_id values for the stated goal.",
        timeout_s=60,
    )
    if not response.get("ok"):
        return {**response, "skipped": False}

    try:
        body = _extract_json_object(str(response.get("content") or "{}"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": "invalid_json", "message": str(exc)}

    ids: List[str] = []
    for raw in body.get("module_ids") or []:
        mid = str(raw).strip()
        if mid and find_module(mid) and mid not in ids:
            ids.append(mid)

    if len(ids) < 2:
        return {"ok": False, "error": "too_few_valid_modules", "module_ids": ids}

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "model": response.get("model"),
        "usage": response.get("usage"),
        "reasoning": str(body.get("reasoning") or ""),
        "module_ids": ids,
        "power_topology": str(body.get("power_topology") or ""),
    }

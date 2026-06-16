"""Qwen text → hardware_splicer.netlist.v1 for arbitrary compose (not vision)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Mapping

from ..netlist import run_erc
from ..netlist.ir import CircuitNetlist
from ..pcb.module_registry import find_module
from .catalog_context import catalog_context_for_goal
from .qwen_model_policy import qwen_text_model_rotation
from .qwen_text_client import call_qwen_chat, qwen_configured

# Back-compat
QWEN_TEXT_MODEL_ROTATION = qwen_text_model_rotation()


def _catalog_hint_for_goal(goal: str) -> str:
    return catalog_context_for_goal(goal, max_entries=100)


# Back-compat alias for imports; prefer _catalog_hint_for_goal(goal).
_MODULE_CATALOG_HINT = ""


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _normalize_netlist_payload(raw: Mapping[str, Any], *, source: str) -> Dict[str, Any]:
    body = dict(raw)
    body.setdefault("schema_version", "hardware_splicer.netlist.v1")
    body["source"] = source
    for comp in body.get("components") or []:
        if not isinstance(comp, dict):
            continue
        mid = str(comp.get("module_id") or comp.get("footprint") or "").strip()
        if mid and not comp.get("footprint"):
            comp["footprint"] = mid
        if mid and find_module(mid):
            comp["module_id"] = mid
    return body


def call_qwen_netlist_compose(
    goal: str,
    *,
    constraints: Mapping[str, Any] | None = None,
    model: str | None = None,
    timeout_s: int = 90,
) -> Dict[str, Any]:
    """Ask Qwen for a circuit netlist IR JSON. Requires DASHSCOPE_API_KEY or QWEN_API_KEY."""
    if not qwen_configured():
        return {
            "ok": False,
            "error": "missing_api_key",
            "message": "Set DASHSCOPE_API_KEY or QWEN_API_KEY for Qwen arbitrary compose.",
        }

    constraint_text = json.dumps(dict(constraints or {}), indent=2)
    prompt = f"""You are an electrical engineering assistant emitting a machine-readable netlist.

Goal: {goal}
Constraints JSON:
{constraint_text}

Return ONLY one JSON object matching schema hardware_splicer.netlist.v1:
{{
  "schema_version": "hardware_splicer.netlist.v1",
  "source": "qwen_compose",
  "components": [{{"ref":"U1","value":"...","footprint":"module_id","module_id":"module_id"}}],
  "nets": [{{"name":"GND","pins":[{{"component_ref":"U1","pin":"GND"}}, ...]}}]
}}

Rules:
- At least 2 components and 2 nets; every net needs >=2 pins.
- If the design is USB or 5V powered, include usb-power-5v as U1 and wire V+/GND to loads.
- Name power nets GND, +5V, +3V3, SDA, SCL, DATA where appropriate.
- Only use module_id values from the catalog below unless truly custom.
{_catalog_hint_for_goal(goal)}
"""

    response = call_qwen_chat(
        prompt,
        model=model,
        stage="compose",
        json_mode=True,
        timeout_s=timeout_s,
        system="Emit hardware_splicer.netlist.v1 JSON only.",
    )
    if not response.get("ok"):
        return response

    content = str(response.get("content") or "")
    try:
        netlist_dict = _normalize_netlist_payload(_extract_json_object(content), source="qwen_compose")
        netlist = CircuitNetlist.from_dict(netlist_dict)
    except Exception as exc:
        return {
            "ok": False,
            "error": "invalid_netlist_json",
            "message": str(exc),
            "raw_excerpt": content[:1200],
            "model_rotation": response.get("model_rotation"),
        }

    erc = run_erc(netlist)
    return {
        "ok": bool(erc.get("pass")),
        "provider": "qwen",
        "model": response.get("model"),
        "netlist": netlist.to_dict(),
        "erc": erc,
        "usage": response.get("usage"),
        "module_ids": [c.module_id for c in netlist.components if c.module_id],
        "model_rotation": response.get("model_rotation"),
    }


def compose_netlist_from_goal(
    goal: str,
    *,
    constraints: Mapping[str, Any] | None = None,
    allow_qwen: bool = True,
) -> Dict[str, Any]:
    """Deterministic module fallback, optional Qwen text when keyed."""
    from .llm_policy import offline_compose_enabled

    qwen_disabled = os.environ.get("HARDWARE_SPLICER_QWEN_COMPOSE", "1").strip().lower() in (
        "0",
        "false",
        "no",
    )
    offline_ok = not allow_qwen or qwen_disabled or offline_compose_enabled()

    if allow_qwen and not qwen_disabled:
        qwen = call_qwen_netlist_compose(goal, constraints=constraints)
        if qwen.get("ok"):
            return {**qwen, "compose_mode": "qwen_netlist"}
        if qwen.get("error") != "missing_api_key":
            from .qwen_module_pick import call_qwen_module_pick, qwen_module_pick_enabled

            if qwen_module_pick_enabled():
                picked = call_qwen_module_pick(goal, constraints=constraints)
                if picked.get("ok") and picked.get("module_ids"):
                    from ..auto_wire import compose_build_graph_from_module_ids
                    from ..netlist.lower import build_graph_to_netlist

                    graph = compose_build_graph_from_module_ids(picked["module_ids"])["graph"]
                    netlist = build_graph_to_netlist(graph, source="qwen_module_pick")
                    erc = run_erc(netlist)
                    if erc.get("pass"):
                        return {
                            "ok": True,
                            "compose_mode": "qwen_module_pick",
                            "netlist": netlist.to_dict(),
                            "erc": erc,
                            "module_ids": picked["module_ids"],
                            "usage": picked.get("usage"),
                            "reasoning": picked.get("reasoning"),
                        }
            if not offline_ok:
                return {**qwen, "compose_mode": "qwen_netlist_failed"}

    if not offline_ok:
        return {"ok": False, "error": "no_llm_compose", "compose_mode": "llm_required"}

    from ..module_picker import pick_modules_for_goal
    from ..auto_wire import compose_build_graph_from_module_ids
    from ..netlist.lower import build_graph_to_netlist

    pick = pick_modules_for_goal(goal)
    if len(pick.module_ids) < 2:
        return {"ok": False, "error": "no_modules", "compose_mode": "module_picker"}
    graph = compose_build_graph_from_module_ids(pick.module_ids)["graph"]
    netlist = build_graph_to_netlist(graph, source="module_picker_fallback")
    erc = run_erc(netlist)
    return {
        "ok": bool(erc.get("pass")),
        "compose_mode": "module_picker_fallback",
        "netlist": netlist.to_dict(),
        "erc": erc,
        "module_ids": list(pick.module_ids),
    }

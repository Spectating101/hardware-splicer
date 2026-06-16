"""One-shot Qwen compose retry when compile/DRC fails on first netlist."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Mapping, Optional

from ..netlist import run_erc
from ..netlist.ir import CircuitNetlist
from .catalog_context import build_salvage_catalog_context
from .qwen_netlist_compose import _normalize_netlist_payload
from .qwen_text_client import call_qwen_chat, qwen_configured

SCHEMA_VERSION = "hardware_splicer.qwen_compose_retry.v1"


def compose_retry_enabled() -> bool:
    if os.environ.get("HARDWARE_SPLICER_QWEN_COMPOSE_RETRY", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    return qwen_configured()


def call_qwen_compose_retry(
    goal: str,
    *,
    constraints: Mapping[str, Any] | None = None,
    prior_netlist: Mapping[str, Any] | None = None,
    design_quality: Mapping[str, Any] | None = None,
    erc: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Ask Qwen to fix a netlist using ERC/DRC/safety feedback (single retry)."""
    if not compose_retry_enabled():
        return {"ok": False, "skipped": True, "reason": "compose_retry_disabled_or_no_key"}

    dq = dict(design_quality or {})
    issues = {
        "erc": erc or {},
        "kicad_drc_errors": dq.get("kicad_drc_errors"),
        "drc_violations": dq.get("drc_violations"),
        "electrical_issues": dq.get("electrical_issues"),
        "safety_error_messages": dq.get("safety_error_messages"),
        "electrical_safety_pass": dq.get("electrical_safety_pass"),
    }

    prompt = f"""You previously composed a circuit netlist that failed electrical prove checks.

Goal: {goal}
Constraints: {json.dumps(dict(constraints or {}), indent=2)}

Failure feedback (fix these):
{json.dumps(issues, indent=2)[:4000]}

Prior netlist (repair, do not discard working structure blindly):
{json.dumps(dict(prior_netlist or {}), indent=2)[:6000]}

Return ONLY one JSON object matching schema hardware_splicer.netlist.v1.
Fix power connections, missing GND ties, wrong voltage domains, and unconnected sensor power.
{build_salvage_catalog_context(max_entries=100)}
"""

    response = call_qwen_chat(
        prompt,
        json_mode=True,
        stage="compose_retry",
        system="You fix machine-checkable netlist errors. Output valid hardware_splicer.netlist.v1 JSON only.",
        timeout_s=90,
    )
    if not response.get("ok"):
        return {**response, "skipped": False}

    content = str(response.get("content") or "")
    try:
        from .qwen_netlist_compose import _extract_json_object

        netlist_dict = _normalize_netlist_payload(
            _extract_json_object(content),
            source="qwen_compose_retry",
        )
        netlist = CircuitNetlist.from_dict(netlist_dict)
    except Exception as exc:
        return {"ok": False, "error": "invalid_netlist_json", "message": str(exc), "raw_excerpt": content[:800]}

    erc_out = run_erc(netlist)
    return {
        "ok": bool(erc_out.get("pass")),
        "schema_version": SCHEMA_VERSION,
        "compose_mode": "qwen_compose_retry",
        "provider": response.get("provider"),
        "model": response.get("model"),
        "usage": response.get("usage"),
        "netlist": netlist.to_dict(),
        "erc": erc_out,
        "module_ids": [c.module_id for c in netlist.components if c.module_id],
    }

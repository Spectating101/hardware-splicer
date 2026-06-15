"""Qwen text → hardware_splicer.netlist.v1 for arbitrary compose (not vision)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Mapping, Optional

from ..netlist import run_erc
from ..netlist.ir import CircuitNetlist
from ..pcb.module_registry import find_module
from ..env_local import load_env_local
from ..vision_evidence_assistant import DEFAULT_QWEN_BASE_URL, _provider_api_key

DEFAULT_QWEN_TEXT_MODEL = os.environ.get("HARDWARE_SPLICER_QWEN_TEXT_MODEL", "qwen-turbo")
QWEN_TEXT_MODEL_ROTATION = ("qwen-turbo", "qwen3-vl-flash", "qwen-plus")

_MODULE_CATALOG_HINT = """
Prefer these module_id values when they fit (breakout modules, not bare ICs):
usb-power-5v, esp32-devkit, arduino-nano, rpi-pico, dht22, bme280, soil_moisture,
ssd1306-128x64, relay-1ch-5v, mosfet-irlz44n, buck-mp1584, level-shifter-4ch,
hc-sr04, ch340-usb-ttl, fan-5v, mini-pump-5v, sg90, l298n, mpu6050
Use footprint = module_id when unsure. Pin names must match the module (e.g. DHT22 DATA, ESP32 GPIO4).
"""


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
    load_env_local()
    api_key = _provider_api_key({"provider": "qwen"}, "qwen")
    if not api_key:
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
- Only use module_id values from the catalog hint unless truly custom.
{_MODULE_CATALOG_HINT}
"""

    payload_base = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    base_url = os.environ.get("HARDWARE_SPLICER_QWEN_BASE_URL") or os.environ.get("QWEN_BASE_URL") or DEFAULT_QWEN_BASE_URL
    base_url = str(base_url).rstrip("/")
    models = [model] if model else list(QWEN_TEXT_MODEL_ROTATION)
    body: Dict[str, Any] = {}
    last_error: Dict[str, Any] = {}
    selected_model = models[0]
    for candidate in models:
        payload = {**payload_base, "model": candidate}
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
                selected_model = candidate
                break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            last_error = {"ok": False, "error": "qwen_http_error", "status": exc.code, "detail": detail}
            if exc.code in (403, 429) and candidate != models[-1]:
                continue
            return last_error
        except Exception as exc:
            return {"ok": False, "error": "qwen_request_failed", "message": str(exc)}
    else:
        return last_error or {"ok": False, "error": "qwen_http_error"}

    content = str((body.get("choices") or [{}])[0].get("message", {}).get("content") or "")
    try:
        netlist_dict = _normalize_netlist_payload(_extract_json_object(content), source="qwen_compose")
        netlist = CircuitNetlist.from_dict(netlist_dict)
    except Exception as exc:
        return {"ok": False, "error": "invalid_netlist_json", "message": str(exc), "raw_excerpt": content[:1200]}

    erc = run_erc(netlist)
    return {
        "ok": bool(erc.get("pass")),
        "provider": "qwen",
        "model": body.get("model") or selected_model,
        "netlist": netlist.to_dict(),
        "erc": erc,
        "usage": body.get("usage"),
        "module_ids": [c.module_id for c in netlist.components if c.module_id],
    }


def compose_netlist_from_goal(
    goal: str,
    *,
    constraints: Mapping[str, Any] | None = None,
    allow_qwen: bool = True,
) -> Dict[str, Any]:
    """Deterministic module fallback, optional Qwen text when keyed."""
    if allow_qwen and os.environ.get("HARDWARE_SPLICER_QWEN_COMPOSE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    ):
        qwen = call_qwen_netlist_compose(goal, constraints=constraints)
        if qwen.get("ok"):
            return {**qwen, "compose_mode": "qwen_netlist"}
        if qwen.get("error") != "missing_api_key":
            return {**qwen, "compose_mode": "qwen_netlist_failed"}

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

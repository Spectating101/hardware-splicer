"""Extract MCU pin numbers from a build graph — mirrors frontend graph-pin-map.ts."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Set

LEVEL_SHIFTER_ID = "level-shifter-4ch"
HV_TO_LV = {"HV1": "LV1", "HV2": "LV2", "HV3": "LV3", "HV4": "LV4"}
LV_TO_HV = {v: k for k, v in HV_TO_LV.items()}


def _parse_pin_number(pin_id: str) -> Optional[int]:
    for pat in (r"^GPIO(\d+)$", r"^D(\d+)$", r"^A(\d+)$", r"^GP(\d+)$"):
        m = re.match(pat, pin_id, re.I)
        if m:
            return int(m.group(1))
    return None


def _find_mcu_node_id(graph: Mapping[str, Any]) -> Optional[str]:
    nodes = graph.get("nodes") or []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        mid = str(n.get("moduleId") or "")
        if mid.endswith("-devkit") or mid in ("esp32-devkit", "arduino-nano", "rpi-pico"):
            return str(n.get("id"))
    return None


def trace_mcu_pin(graph: Mapping[str, Any], target_module_id: str, target_pin_id: str) -> Optional[str]:
    mcu_node_id = _find_mcu_node_id(graph)
    nodes = graph.get("nodes") or []
    target_node = next((n for n in nodes if isinstance(n, dict) and n.get("moduleId") == target_module_id), None)
    if not mcu_node_id or not target_node:
        return None
    target_node_id = str(target_node["id"])
    visited: Set[str] = set()

    def walk(node_id: str, pin_id: str) -> Optional[str]:
        key = f"{node_id}:{pin_id}"
        if key in visited:
            return None
        visited.add(key)
        if node_id == mcu_node_id:
            return pin_id
        for w in graph.get("wires") or []:
            if not isinstance(w, dict):
                continue
            fr, to = w.get("from") or {}, w.get("to") or {}
            other = None
            if fr.get("nodeId") == node_id and fr.get("pinId") == pin_id:
                other = to
            elif to.get("nodeId") == node_id and to.get("pinId") == pin_id:
                other = fr
            if not other:
                continue
            other_node_id = str(other.get("nodeId"))
            other_pin_id = str(other.get("pinId"))
            other_node = next((n for n in nodes if isinstance(n, dict) and str(n.get("id")) == other_node_id), None)
            if other_node and other_node.get("moduleId") == LEVEL_SHIFTER_ID:
                paired = HV_TO_LV.get(other_pin_id) or LV_TO_HV.get(other_pin_id)
                if paired:
                    via = walk(other_node_id, paired)
                    if via:
                        return via
            direct = walk(other_node_id, other_pin_id)
            if direct:
                return direct
        return None

    return walk(target_node_id, target_pin_id)


def extract_pins_from_graph(graph: Mapping[str, Any]) -> Dict[str, Any]:
    module_ids = {str(n.get("moduleId")) for n in (graph.get("nodes") or []) if isinstance(n, dict)}
    out: Dict[str, Any] = {"sourced_from_graph": False}

    def pin_num(module_id: str, pin_id: str) -> Optional[int]:
        mcu_pin = trace_mcu_pin(graph, module_id, pin_id)
        if not mcu_pin:
            return None
        return _parse_pin_number(mcu_pin)

    if "soil_moisture" in module_ids:
        soil = pin_num("soil_moisture", "A0")
        if soil is not None:
            out["soil"] = soil
            out["sourced_from_graph"] = True
    if "mosfet-irlz44n" in module_ids:
        pump = pin_num("mosfet-irlz44n", "SIG")
        if pump is not None:
            out["pump"] = pump
            out["sourced_from_graph"] = True
    if "dht22" in module_ids:
        dht = pin_num("dht22", "DATA")
        if dht is not None:
            out["dht"] = dht
            out["sourced_from_graph"] = True
    return out

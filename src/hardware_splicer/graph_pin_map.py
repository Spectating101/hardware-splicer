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
        if mid.endswith("-devkit") or mid in {
            "esp32-devkit",
            "esp32-cam-module",
            "arduino-nano",
            "rpi-pico",
        }:
            return str(n.get("id"))
        if "esp32" in mid and "cam" in mid:
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


def _trace_mcu_pin_for_node(graph: Mapping[str, Any], node_id: str, pin_id: str) -> Optional[str]:
    """Like trace_mcu_pin but targets a specific node id (handles duplicate moduleIds)."""
    mcu_node_id = _find_mcu_node_id(graph)
    if not mcu_node_id:
        return None
    visited: Set[str] = set()

    def walk(cur_node: str, cur_pin: str) -> Optional[str]:
        key = f"{cur_node}:{cur_pin}"
        if key in visited:
            return None
        visited.add(key)
        if cur_node == mcu_node_id:
            return cur_pin
        for w in graph.get("wires") or []:
            if not isinstance(w, dict):
                continue
            fr, to = w.get("from") or {}, w.get("to") or {}
            other = None
            if fr.get("nodeId") == cur_node and fr.get("pinId") == cur_pin:
                other = to
            elif to.get("nodeId") == cur_node and to.get("pinId") == cur_pin:
                other = fr
            if not other:
                continue
            other_node_id = str(other.get("nodeId"))
            other_pin_id = str(other.get("pinId"))
            nodes = graph.get("nodes") or []
            other_node = next(
                (n for n in nodes if isinstance(n, dict) and str(n.get("id")) == other_node_id),
                None,
            )
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

    return walk(node_id, pin_id)


def extract_pins_from_graph(graph: Mapping[str, Any]) -> Dict[str, Any]:
    nodes = [n for n in (graph.get("nodes") or []) if isinstance(n, dict)]
    module_ids = {str(n.get("moduleId")) for n in nodes}
    out: Dict[str, Any] = {"sourced_from_graph": False}

    def pin_num(module_id: str, pin_id: str) -> Optional[int]:
        mcu_pin = trace_mcu_pin(graph, module_id, pin_id)
        if not mcu_pin:
            return None
        return _parse_pin_number(mcu_pin)

    def mark(key: str, value: Optional[int]) -> None:
        if value is not None:
            out[key] = value
            out["sourced_from_graph"] = True

    if "soil_moisture" in module_ids:
        mark("soil", pin_num("soil_moisture", "A0"))
    if "mosfet-irlz44n" in module_ids:
        mos = pin_num("mosfet-irlz44n", "SIG")
        mark("pump", mos)
        # Fan / fume builds reuse MOSFET SIG as fan enable
        if any("fan" in mid for mid in module_ids) or "cooling_fan_5v" in module_ids:
            mark("fan", mos)
    if "dht22" in module_ids:
        mark("dht", pin_num("dht22", "DATA"))
    for relay_id in ("relay-1ch-5v", "relay_module_1ch_5v", "relay-1ch"):
        if relay_id in module_ids:
            mark("relay", pin_num(relay_id, "IN") or pin_num(relay_id, "SIG"))
            break
    if "l298n" in module_ids:
        for name in ("IN1", "IN2", "IN3", "IN4"):
            mark(name.lower(), pin_num("l298n", name))
    for stepper_drv in ("a4988-stepper", "tmc2209-stepper", "drv8825_stepper"):
        if stepper_drv in module_ids:
            mark("step", pin_num(stepper_drv, "STEP"))
            mark("dir", pin_num(stepper_drv, "DIR"))
            break

    # Dual/multi SG90 — assign pan/tilt from node order (not first-match only)
    servo_nodes = [n for n in nodes if str(n.get("moduleId") or "") in {"sg90", "mg996r"}]
    servo_nums: List[int] = []
    for n in servo_nodes:
        mcu_pin = _trace_mcu_pin_for_node(graph, str(n.get("id")), "SIG")
        num = _parse_pin_number(mcu_pin or "")
        if num is not None:
            servo_nums.append(num)
    if servo_nums:
        mark("servo_pan", servo_nums[0])
        if len(servo_nums) > 1:
            mark("servo_tilt", servo_nums[1])

    return out

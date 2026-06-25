"""Electrical safety/correctness checks for build graphs (Python engine port)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .module_registry import find_module, find_pin

BuildGraph = Dict[str, Any]
BuildWarning = Dict[str, Any]


def _pin_accepts_peer_logic(pin: Mapping[str, Any], peer_logic_v: float) -> bool:
    text = f"{pin.get('voltage') or ''} {pin.get('notes') or ''}"
    if re.search(r"3\.3\s*[-–to]+\s*5|3\.3-5", text, re.I):
        return peer_logic_v in (3.3, 5.0)
    return False


def _resolve(graph: BuildGraph, node_id: str, pin_id: str) -> Optional[Dict[str, Any]]:
    node = next((n for n in graph.get("nodes") or [] if n.get("id") == node_id), None)
    if not node:
        return None
    module_spec = find_module(str(node.get("moduleId") or ""))
    if not module_spec:
        return None
    pin = find_pin(module_spec, pin_id)
    if not pin:
        return None
    return {"node": node, "moduleSpec": module_spec, "pin": pin}


def _terminal_semantics(graph: BuildGraph, node_id: str, pin_id: str) -> Dict[str, Any]:
    semantics = graph.get("terminal_semantics")
    if not isinstance(semantics, Mapping):
        return {}
    row = semantics.get(f"{node_id}:{pin_id}")
    return dict(row) if isinstance(row, Mapping) else {}


def _effective_role(graph: BuildGraph, resolved: Mapping[str, Any]) -> str:
    node = dict(resolved.get("node") or {})
    pin = dict(resolved.get("pin") or {})
    semantic = _terminal_semantics(graph, str(node.get("id") or ""), str(pin.get("id") or ""))
    return str(semantic.get("role") or pin.get("role") or "")


def _effective_pin_role(graph: BuildGraph, node: Mapping[str, Any], pin: Mapping[str, Any]) -> str:
    semantic = _terminal_semantics(graph, str(node.get("id") or ""), str(pin.get("id") or ""))
    return str(semantic.get("role") or pin.get("role") or "")


def _has_support_component(graph: BuildGraph, role: str) -> bool:
    return any(
        isinstance(row, Mapping) and row.get("role") == role
        for row in graph.get("support_components") or []
    )


def _parse_voltage(v: Optional[str]) -> Optional[float]:
    if not v:
        return None
    m = re.search(r"([\d.]+)\s*V", v, re.I)
    return float(m.group(1)) if m else None


def _voltage_range(v: Optional[str]) -> Optional[Tuple[float, float]]:
    if not v:
        return None
    m = re.search(r"([\d.]+)\s*-\s*([\d.]+)\s*V", v, re.I)
    if m:
        return float(m.group(1)), float(m.group(2))
    single = _parse_voltage(v)
    return (single, single) if single is not None else None


def analyze_build(graph: BuildGraph) -> List[BuildWarning]:
    warnings: List[BuildWarning] = []

    for w in graph.get("wires") or []:
        a = _resolve(graph, w["from"]["nodeId"], w["from"]["pinId"])
        b = _resolve(graph, w["to"]["nodeId"], w["to"]["pinId"])
        if not a or not b:
            continue

        a_role = _effective_role(graph, a)
        b_role = _effective_role(graph, b)
        a_gnd = a_role == "gnd"
        b_gnd = b_role == "gnd"
        if a_gnd != b_gnd:
            warnings.append(
                {
                    "id": f"{w['id']}-gnd",
                    "level": "error",
                    "message": (
                        f"Wire connects GND ({a['moduleSpec']['label'] if a_gnd else b['moduleSpec']['label']}) "
                        "to a non-GND pin. This will short or misbehave."
                    ),
                    "wireId": w["id"],
                }
            )
            continue
        if a_gnd and b_gnd:
            continue

        if a_role == "power_in" and b_role == "power_in":
            warnings.append(
                {
                    "id": f"{w['id']}-noSource",
                    "level": "warn",
                    "message": "Both ends of this wire are power inputs — nothing actually sources power. Connect to a power_out pin.",
                    "wireId": w["id"],
                }
            )
        if a_role == "power_out" and b_role == "power_out":
            warnings.append(
                {
                    "id": f"{w['id']}-twoSources",
                    "level": "error",
                    "message": (
                        f"Two power sources ({a['moduleSpec']['label']}:{a['pin']['id']} and "
                        f"{b['moduleSpec']['label']}:{b['pin']['id']}) fighting on the same rail."
                    ),
                    "wireId": w["id"],
                }
            )

        def is_power(role: str) -> bool:
            return role in ("power_in", "power_out")

        if is_power(a_role) and is_power(b_role):
            src = a if a_role == "power_out" else b if b_role == "power_out" else None
            snk = b if src is a else a if src is b else None
            if src and snk:
                src_range = _voltage_range(src["pin"].get("voltage"))
                snk_range = _voltage_range(snk["pin"].get("voltage")) or tuple(
                    snk["moduleSpec"].get("inputVoltageRange") or ()
                ) or None
                src_v = _parse_voltage(src["pin"].get("voltage"))
                if src_range and snk_range and src_range[1] >= snk_range[0] and src_range[0] <= snk_range[1]:
                    if re.search(r"adjust|trim|set", src["pin"].get("voltage") or "", re.I) or re.search(
                        r"adjust|trim|set", src["pin"].get("notes") or "", re.I
                    ):
                        warnings.append(
                            {
                                "id": f"{w['id']}-adjustable",
                                "level": "info",
                                "message": (
                                    f"{src['moduleSpec']['label']} is adjustable — set output to "
                                    f"{snk_range[0]}–{snk_range[1]}V with a multimeter before connecting "
                                    f"{snk['moduleSpec']['label']}."
                                ),
                                "wireId": w["id"],
                            }
                        )
                elif src_v is not None and snk_range:
                    if src_v < snk_range[0] - 0.2 or src_v > snk_range[1] + 0.2:
                        warnings.append(
                            {
                                "id": f"{w['id']}-voltage",
                                "level": "error",
                                "message": (
                                    f"{src['moduleSpec']['label']} outputs {src_v}V but "
                                    f"{snk['moduleSpec']['label']} expects {snk_range[0]}–{snk_range[1]}V. "
                                    "Insert a regulator."
                                ),
                                "wireId": w["id"],
                            }
                        )

        a_lv = a["moduleSpec"].get("logicVoltage")
        b_lv = b["moduleSpec"].get("logicVoltage")

        def is_digital(role: str) -> bool:
            return role not in ("power_in", "power_out", "gnd", "other", "floating_motor_terminal", "isolated_relay_contact")

        if is_digital(a_role) and is_digital(b_role) and a_lv and b_lv and a_lv != b_lv:
            if not (_pin_accepts_peer_logic(a["pin"], float(b_lv)) or _pin_accepts_peer_logic(b["pin"], float(a_lv))):
                warnings.append(
                    {
                        "id": f"{w['id']}-logic",
                        "level": "error",
                        "message": (
                            f"{a['moduleSpec']['label']} uses {a_lv}V logic, "
                            f"{b['moduleSpec']['label']} uses {b_lv}V logic. Add a level shifter."
                        ),
                        "wireId": w["id"],
                    }
                )

        if any(r in (a_role, b_role) for r in ("i2c_sda", "i2c_scl")):
            any_builtin = any(re.search(r"pull", (e["pin"].get("notes") or ""), re.I) for e in (a, b))
            if not any_builtin and not _has_support_component(graph, "pull_up_resistor"):
                warnings.append(
                    {
                        "id": f"{w['id']}-pullup",
                        "level": "info",
                        "message": "I2C bus: confirm 4.7k pull-ups to VCC exist. Many breakouts include them; MCU boards usually do not.",
                        "wireId": w["id"],
                    }
                )

        if (a["moduleSpec"]["id"] == "mosfet-irf520" and b_lv == 3.3) or (
            b["moduleSpec"]["id"] == "mosfet-irf520" and a_lv == 3.3
        ):
            warnings.append(
                {
                    "id": f"{w['id']}-fetDrive",
                    "level": "warn",
                    "message": "IRF520 does not switch fully from 3.3V logic. Use IRLZ44N, AO3400, or a 5V MCU.",
                    "wireId": w["id"],
                }
            )

    for n in graph.get("nodes") or []:
        module_spec = find_module(str(n.get("moduleId") or ""))
        if not module_spec:
            continue

        power_in_pins = [
            p
            for p in module_spec.get("pins") or []
            if _effective_pin_role(graph, n, p) == "power_in"
        ]
        power_in_wired = any(
            any(
                (w["from"]["nodeId"] == n["id"] and w["from"]["pinId"] == p["id"])
                or (w["to"]["nodeId"] == n["id"] and w["to"]["pinId"] == p["id"])
                for w in graph.get("wires") or []
            )
            for p in power_in_pins
        )
        self_powered_usb = any(
            re.search(r"usb|host", f"{p.get('notes') or ''} {p.get('label') or ''} {p.get('id')}", re.I)
            for p in power_in_pins
        )
        if not power_in_wired and power_in_pins and not self_powered_usb:
            warnings.append(
                {
                    "id": f"{n['id']}-unpowered",
                    "level": "warn",
                    "message": f"{module_spec['label']} has no power connection yet.",
                    "nodeId": n["id"],
                }
            )

        gnd_wired = any(
            any(
                (w["from"]["nodeId"] == n["id"] and w["from"]["pinId"] == p["id"])
                or (w["to"]["nodeId"] == n["id"] and w["to"]["pinId"] == p["id"])
                for w in graph.get("wires") or []
            )
            for p in module_spec.get("pins") or []
            if _effective_pin_role(graph, n, p) == "gnd"
        )
        if not gnd_wired and any(_effective_pin_role(graph, n, p) == "gnd" for p in module_spec.get("pins") or []):
            warnings.append(
                {
                    "id": f"{n['id']}-nognd",
                    "level": "error",
                    "message": f"{module_spec['label']} has no GND connection. All modules need a common ground.",
                    "nodeId": n["id"],
                }
            )

        if module_spec["id"] in ("sg90", "l298n"):
            powered_from_mcu = False
            for w in graph.get("wires") or []:
                ends = [w["from"], w["to"]]
                mine = next((e for e in ends if e["nodeId"] == n["id"]), None)
                other = next((e for e in ends if e["nodeId"] != n["id"]), None)
                if not mine or not other:
                    continue
                my_pin = find_pin(module_spec, mine["pinId"])
                if my_pin and _effective_pin_role(graph, n, my_pin) == "power_in":
                    other_node = next((x for x in graph.get("nodes") or [] if x["id"] == other["nodeId"]), None)
                    other_mod = find_module(str(other_node.get("moduleId") or "")) if other_node else None
                    if other_mod and other_mod.get("category") == "mcu":
                        powered_from_mcu = True
            if powered_from_mcu:
                warnings.append(
                    {
                        "id": f"{n['id']}-highCurrent",
                        "level": "error",
                        "message": (
                            f"{module_spec['label']} can pull >200mA. Don't power it from the MCU's 5V pin — "
                            "use a separate supply."
                        ),
                        "nodeId": n["id"],
                    }
                )

    return warnings

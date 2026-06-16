from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Tuple


SCHEMA_VERSION = "hardware_splicer.module_resolver.v1"

# Fuzzy part-name → module-library id. Order matters (first match wins).
_MODULE_PATTERNS: List[Tuple[re.Pattern[str], str, str, float]] = [
    (re.compile(r"irlz44n|irlz", re.I), "mosfet-irlz44n", "drv", 0.95),
    (re.compile(r"logic.?level.*mosfet|logic.?level.*fet", re.I), "mosfet-irlz44n", "drv", 0.93),
    (re.compile(r"irf520", re.I), "mosfet-irf520", "drv", 0.85),
    (re.compile(r"mosfet", re.I), "mosfet-irlz44n", "drv", 0.8),
    (re.compile(r"ao3400", re.I), "mosfet-irlz44n", "drv", 0.9),
    (re.compile(r"lm2596", re.I), "buck-lm2596", "buck", 0.92),
    (re.compile(r"mp1584|mini buck", re.I), "buck-mp1584", "buck", 0.9),
    (re.compile(r"tp4056|lipo charger", re.I), "tp4056", "usb", 0.9),
    (re.compile(r"esp32", re.I), "esp32-devkit", "mcu", 0.95),
    (re.compile(r"arduino nano|nano", re.I), "arduino-nano", "mcu", 0.9),
    (re.compile(r"pico|raspberry pi pico", re.I), "rpi-pico", "mcu", 0.9),
    (re.compile(r"soil|moisture", re.I), "soil_moisture", "sns", 0.92),
    (re.compile(r"dht22|dht11|temp.*humid", re.I), "dht22", "sns", 0.88),
    (re.compile(r"bme280", re.I), "bme280", "sns", 0.9),
    (re.compile(r"vl53|tof|time.?of.?flight|range sensor|lidar", re.I), "vl53l0x_tof", "sns", 0.88),
    (re.compile(r"vl6180", re.I), "vl6180x-tof", "sns", 0.86),
    (re.compile(r"ultrasonic|hc-?sr04|sonar", re.I), "hc-sr04", "sns", 0.85),
    (re.compile(r"sg90", re.I), "sg90", "act", 0.92),
    (re.compile(r"mg996r", re.I), "mg996r", "act", 0.9),
    (re.compile(r"l298n", re.I), "l298n", "drv", 0.9),
    (re.compile(r"dc.*gear.*motor|gear.*motor|brushed.*motor|dc[_ ]motor|6v.*motor", re.I), "dc_motor_3v_6v", "mot", 0.86),
    (re.compile(r"12v.*gear.*motor|geared.*motor.*12", re.I), "dc_geared_motor_12v", "mot", 0.84),
    (re.compile(r"relay", re.I), "relay-1ch", "drv", 0.85),
    (re.compile(r"pump|peristaltic", re.I), "mini-pump-5v", "load", 0.8),
    (re.compile(r"fan|blower", re.I), "fan-5v", "load", 0.8),
    (re.compile(r"usb.*serial|cp210|ch340|ftdi", re.I), "usb-uart", "usb", 0.85),
    (re.compile(r"ssd1306|oled", re.I), "ssd1306", "ui", 0.85),
    (
        re.compile(
            r"power.?bank|usb.*power|5v.*usb|phone charger|(?:usb|5v).*wall wart|wall wart.*(?:usb|5v)",
            re.I,
        ),
        "usb-power-5v",
        "pwr",
        0.92,
    ),
    (
        re.compile(r"barrel|12v.*(?:supply|adapter)|(?:wall wart.*12v|12v.*wall wart)", re.I),
        "dc-barrel-12v",
        "pwr",
        0.8,
    ),
]

_POWER_TOPOLOGY_USB = re.compile(
    r"power.?bank|usb.*power|5v.*usb|phone charger|(?:usb|5v).*wall wart|wall wart.*(?:usb|5v)",
    re.I,
)
_POWER_TOPOLOGY_BARREL = re.compile(
    r"barrel|12v.*(?:supply|adapter)|(?:wall wart.*12v|12v.*wall wart)",
    re.I,
)

_USB_WALL_MODULE_IDS = frozenset({"usb-power-5v"})
_BARREL_POWER_MODULE_IDS = frozenset({"dc-barrel-12v"})

# 3.3V MCU + non-logic-level MOSFET → prefer logic-level FET.
_SUBSTITUTIONS: Dict[str, str] = {
    "mosfet-irf520": "mosfet-irlz44n",
}

_ROLE_ALIASES = {
    "controller": "mcu",
    "microcontroller": "mcu",
    "sensor": "sns",
    "actuator": "act",
    "driver": "drv",
    "power": "buck",
    "pump": "load",
    "fan": "load",
    "motor": "load",
    "dc_motor": "load",
    "tof_range": "sns",
}


def _part_text(part: Mapping[str, Any]) -> str:
    bits = [
        str(part.get("name") or ""),
        str(part.get("type") or ""),
        str(part.get("kind") or ""),
        str(part.get("part_class") or ""),
    ]
    return " ".join(bits).strip()


def _part_voltage_v(part: Mapping[str, Any]) -> Optional[float]:
    raw = part.get("voltage_v")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _part_implies_usb_5v(part: Mapping[str, Any]) -> bool:
    text = _part_text(part)
    if not text:
        return False
    if str(part.get("module_id") or "").strip() in _USB_WALL_MODULE_IDS | {"tp4056"}:
        return True
    voltage = _part_voltage_v(part)
    if voltage is not None and voltage <= 5.5:
        if _POWER_TOPOLOGY_USB.search(text) or "wall wart" in text.lower():
            return True
    return bool(_POWER_TOPOLOGY_USB.search(text))


def _part_implies_barrel_12v(part: Mapping[str, Any]) -> bool:
    if _part_implies_usb_5v(part):
        return False
    text = _part_text(part)
    return bool(text and _POWER_TOPOLOGY_BARREL.search(text))


def _role_for_module_id(module_id: str, part: Mapping[str, Any]) -> str:
    for _pattern, mid, role, _confidence in _MODULE_PATTERNS:
        if mid == module_id:
            return role
    cap = str(part.get("part_class") or part.get("type") or "").lower()
    return _ROLE_ALIASES.get(cap, cap or "misc")


def coalesce_resolved_modules(
    parts: List[Mapping[str, Any]],
    resolved_modules: List[Mapping[str, Any]],
    *,
    power_topology: str | None = None,
) -> List[Dict[str, Any]]:
    """Drop conflicting power modules after fuzzy resolve / goal merge."""
    topology = power_topology or infer_power_topology(parts, resolved_modules)
    rows: List[Dict[str, Any]] = [dict(row) for row in resolved_modules if isinstance(row, Mapping)]
    unresolved = [row for row in rows if not str(row.get("module_id") or "").strip()]
    rows = [row for row in rows if str(row.get("module_id") or "").strip()]
    if topology == "usb_5v":
        rows = [row for row in rows if str(row.get("module_id") or "") not in _BARREL_POWER_MODULE_IDS]
    elif topology == "barrel_12v":
        rows = [row for row in rows if str(row.get("module_id") or "") not in _USB_WALL_MODULE_IDS]

    by_id: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        module_id = str(row.get("module_id") or "").strip()
        if not module_id:
            continue
        existing = by_id.get(module_id)
        if not existing:
            by_id[module_id] = row
            continue
        if existing.get("source") != "user_inventory" and row.get("source") == "user_inventory":
            by_id[module_id] = row
    return list(by_id.values()) + unresolved


def resolve_parts_to_modules(parts: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Map intake-normalized parts to module-library IDs with role hints."""
    resolved: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for part in parts:
        text = _part_text(part)
        explicit_id = str(part.get("module_id") or "").strip()
        if explicit_id:
            if explicit_id in seen_ids:
                continue
            seen_ids.add(explicit_id)
            resolved.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "part_name": str(part.get("name") or text or explicit_id),
                    "module_id": explicit_id,
                    "role": _role_for_module_id(explicit_id, part),
                    "source": "user_inventory",
                    "confidence": 1.0,
                    "matched_on": "explicit_module_id",
                }
            )
            continue
        if not text:
            continue
        match: Optional[Dict[str, Any]] = None
        for pattern, module_id, role, confidence in _MODULE_PATTERNS:
            if pattern.search(text):
                match = {
                    "schema_version": SCHEMA_VERSION,
                    "part_name": str(part.get("name") or text),
                    "module_id": module_id,
                    "role": role,
                    "source": "user_inventory",
                    "confidence": confidence,
                    "matched_on": pattern.pattern,
                }
                break
        if match and match.get("module_id") in _SUBSTITUTIONS:
            match = dict(match)
            match["module_id"] = _SUBSTITUTIONS[str(match["module_id"])]

        if not match:
            cap = str(part.get("part_class") or part.get("type") or "").lower()
            role = _ROLE_ALIASES.get(cap, cap or "misc")
            match = {
                "schema_version": SCHEMA_VERSION,
                "part_name": str(part.get("name") or text),
                "module_id": None,
                "role": role,
                "source": "unresolved",
                "confidence": 0.2,
                "matched_on": cap,
            }
        if match.get("module_id") and match["module_id"] in seen_ids:
            continue
        if match.get("module_id"):
            seen_ids.add(str(match["module_id"]))
        resolved.append(match)
    return coalesce_resolved_modules(parts, resolved)


def resolve_parts_to_modules_with_llm(
    parts: List[Mapping[str, Any]],
    *,
    goal: str = "",
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Map intake parts → module_id. LLM-first when keyed; regex is offline fallback only."""
    from .integrations.qwen_salvage_resolver import (
        call_qwen_salvage_map_intake,
        merge_qwen_intake_map,
        merge_qwen_salvage_into_resolved,
        qwen_salvage_enabled,
        salvage_resolve_mode,
    )

    mode = salvage_resolve_mode()
    heuristic = resolve_parts_to_modules(parts) if mode != "llm_only" else []
    meta: Dict[str, Any] = {
        "resolve_mode": mode,
        "heuristic": mode in {"heuristic", "llm_first"},
        "qwen": {"used": False},
    }

    explicit_rows: List[Dict[str, Any]] = [
        dict(row)
        for row in heuristic
        if str(row.get("matched_on") or "") == "explicit_module_id" and row.get("module_id")
    ]
    if not explicit_rows:
        for part in parts:
            explicit_id = str(part.get("module_id") or "").strip()
            if explicit_id:
                explicit_rows.append(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "part_name": str(part.get("name") or explicit_id),
                        "module_id": explicit_id,
                        "role": _role_for_module_id(explicit_id, part),
                        "source": "user_inventory",
                        "confidence": 1.0,
                        "matched_on": "explicit_module_id",
                    }
                )

    if mode in {"llm_first", "llm_only"} and qwen_salvage_enabled():
        qwen = call_qwen_salvage_map_intake(
            goal=goal,
            parts=parts,
            heuristic_hints=heuristic if mode == "llm_first" else None,
        )
        if qwen.get("ok"):
            if mode == "llm_only":
                merged = merge_qwen_intake_map(parts, qwen, explicit_rows=explicit_rows)
            else:
                merged = merge_qwen_salvage_into_resolved(heuristic, qwen)
            merged = coalesce_resolved_modules(parts, merged)
            meta["qwen"] = {
                "used": True,
                "model": qwen.get("model"),
                "reasoning": qwen.get("reasoning"),
                "power_notes": qwen.get("power_notes"),
                "rejected": qwen.get("rejected") or [],
                "suggested_purchases": qwen.get("suggested_purchases") or [],
                "unresolved_after": [r.get("part_name") for r in merged if not r.get("module_id")],
            }
            return merged, meta
        meta["qwen"] = {
            "used": False,
            "reason": qwen.get("error") or qwen.get("reason") or "qwen_map_failed",
            "fallback": "heuristic",
        }
        if mode == "llm_only":
            merged = coalesce_resolved_modules(parts, explicit_rows + [r for r in heuristic if not r.get("module_id")])
            return merged, meta

    unresolved = [row for row in heuristic if not row.get("module_id")]
    if unresolved and qwen_salvage_enabled() and mode == "heuristic":
        qwen = call_qwen_salvage_map_intake(
            goal=goal,
            parts=parts,
            heuristic_hints=unresolved,
        )
        merged = coalesce_resolved_modules(parts, merge_qwen_salvage_into_resolved(heuristic, qwen))
        meta["qwen"] = {
            "used": bool(qwen.get("ok")),
            "model": qwen.get("model"),
            "reasoning": qwen.get("reasoning"),
            "rejected": qwen.get("rejected") or [],
            "suggested_purchases": qwen.get("suggested_purchases") or [],
            "unresolved_after": [r.get("part_name") for r in merged if not r.get("module_id")],
        }
        return merged, meta

    meta["qwen"] = {
        "used": False,
        "reason": "heuristic_only" if mode == "heuristic" else "qwen_unavailable",
    }
    return heuristic, meta


_MOTOR_PART_TYPES = frozenset({"dc_motor", "motor", "gear_motor", "brushed_motor"})
_MOTOR_MODULE_PREFIXES = ("dc_motor", "dc_geared_motor", "vibration_motor")
_DRIVER_MODULE_IDS = frozenset(
    {"l298n", "drv8833-motor", "l9110-motor", "tb6612fng-motor", "bts7960-motor", "mosfet-irlz44n"}
)


def _inventory_has_dc_motors(
    parts: List[Mapping[str, Any]] | None,
    resolved_modules: List[Mapping[str, Any]],
) -> bool:
    for part in parts or []:
        if str(part.get("type") or "").lower() in _MOTOR_PART_TYPES:
            return True
        text = _part_text(part).lower()
        if "motor" in text and "driver" not in text:
            return True
    for row in resolved_modules:
        role = str(row.get("role") or "")
        module_id = str(row.get("module_id") or "")
        if role in {"mot", "load"} and module_id.startswith(_MOTOR_MODULE_PREFIXES):
            return True
    return False


def fill_salvage_gaps(
    resolved_modules: List[Dict[str, Any]],
    *,
    parts: List[Mapping[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Deterministic gap-fill for salvage (driver for motors, etc.) — no LLM."""
    rows = [dict(row) for row in resolved_modules]
    module_ids = {str(row.get("module_id") or "").strip() for row in rows if row.get("module_id")}
    has_driver = bool(module_ids & _DRIVER_MODULE_IDS) or any(
        str(row.get("role") or "") == "drv" and row.get("module_id") for row in rows
    )
    if _inventory_has_dc_motors(parts, rows) and not has_driver:
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "part_name": "motor driver (gap fill)",
                "module_id": "l298n",
                "role": "drv",
                "source": "gap_fill",
                "confidence": 0.7,
                "matched_on": "dc_motor_without_driver",
            }
        )
    return coalesce_resolved_modules(parts or [], rows)


def infer_power_topology(
    parts: List[Mapping[str, Any]],
    resolved_modules: List[Mapping[str, Any]] | None = None,
    *,
    constraints: Mapping[str, Any] | None = None,
) -> str:
    """Return usb_5v | barrel_12v | hybrid from inventory."""
    resolved_modules = resolved_modules or []
    constraints_map = dict(constraints or {})
    battery_v = constraints_map.get("battery_voltage_v")
    if battery_v is not None:
        try:
            if float(battery_v) >= 6.0:
                has_usb = any(_part_implies_usb_5v(part) for part in parts)
                has_usb_module = any(
                    str(row.get("module_id") or "") == "usb-power-5v" for row in resolved_modules
                )
                if has_usb or has_usb_module:
                    return "hybrid"
                return "barrel_12v"
        except (TypeError, ValueError):
            pass

    has_usb = any(_part_implies_usb_5v(part) for part in parts)
    has_barrel = any(_part_implies_barrel_12v(part) for part in parts)
    has_usb_module = any(str(row.get("module_id") or "") == "usb-power-5v" for row in resolved_modules)
    has_barrel_module = any(str(row.get("module_id") or "") == "dc-barrel-12v" for row in resolved_modules)
    usb_only = (has_usb or has_usb_module) and not (has_barrel or has_barrel_module)
    if usb_only:
        return "usb_5v"
    if has_barrel or has_barrel_module:
        return "barrel_12v"
    if has_usb or has_usb_module:
        return "hybrid"
    return "barrel_12v"


def overrides_from_resource_plan(diy_plan: Mapping[str, Any]) -> Dict[str, str]:
    """Map DIY resource_strategy selected_resources → role overrides."""
    resource_plan = dict(diy_plan.get("resource_plan") or {})
    selected = list(resource_plan.get("selected_resources") or [])
    if not selected:
        return {}
    pseudo_parts: List[Dict[str, Any]] = []
    for row in selected:
        if not isinstance(row, dict):
            continue
        caps = [str(c).lower() for c in (row.get("capabilities") or [])]
        pseudo_parts.append(
            {
                "name": str(row.get("name") or row.get("resource_id") or ""),
                "type": caps[0] if caps else str(row.get("resource_kind") or ""),
            }
        )
    if not pseudo_parts:
        return {}
    resolved = resolve_parts_to_modules(pseudo_parts)
    return module_overrides_for_build(build_id=None, resolved_modules=resolved)


def module_overrides_for_build(
    *,
    build_id: str | None,
    resolved_modules: List[Mapping[str, Any]],
    mcu_logic_voltage: float = 3.3,
) -> Dict[str, str]:
    """Role → module_id overrides from user inventory and substitution rules."""
    overrides: Dict[str, str] = {}
    for row in resolved_modules:
        module_id = row.get("module_id")
        role = row.get("role")
        if module_id and role:
            overrides[str(role)] = str(module_id)

    has_esp32 = any(str(row.get("module_id") or "") == "esp32-devkit" for row in resolved_modules)
    if (mcu_logic_voltage <= 3.4 or has_esp32) and overrides.get("drv") == "mosfet-irf520":
        overrides["drv"] = _SUBSTITUTIONS["mosfet-irf520"]
    if has_esp32 and overrides.get("drv") in {None, "mosfet-irf520"} and build_id == "automatic_plant_watering":
        overrides["drv"] = "mosfet-irlz44n"

    # LM2596 needs ≥7V in; prefer MP1584 when user only has 5V USB path.
    if build_id == "automatic_plant_watering" and overrides.get("buck") == "buck-lm2596":
        overrides["buck"] = "buck-mp1584"

    return overrides


def merge_module_overrides(*maps: Mapping[str, str] | None) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for mapping in maps:
        if not mapping:
            continue
        for key, value in mapping.items():
            if value:
                merged[str(key)] = str(value)
    return merged


def salvage_plan_input_from_intake(
    splice_plan: Mapping[str, Any],
    *,
    resolved_modules: List[Mapping[str, Any]] | None = None,
    module_overrides: Mapping[str, str] | None = None,
    power_topology: str | None = None,
    strategy_mode: str | None = None,
    compose_from_inventory: bool | None = None,
) -> Dict[str, Any]:
    """Shape consumed by plan-to-graph / compile_build_graph.cjs."""
    target = dict(splice_plan.get("target") or {})
    body: Dict[str, Any] = {
        "target": target,
        "reusable_blocks": list(splice_plan.get("reusable_blocks") or []),
        "build_candidates": list(splice_plan.get("build_candidates") or []),
    }
    if resolved_modules:
        body["resolved_modules"] = [dict(row) for row in resolved_modules]
    if module_overrides:
        body["module_overrides"] = dict(module_overrides)
    if power_topology:
        body["power_topology"] = power_topology
    if strategy_mode:
        body["strategy_mode"] = strategy_mode
    resolved_ids = [
        str(row.get("module_id") or "").strip()
        for row in (resolved_modules or [])
        if isinstance(row, dict) and str(row.get("module_id") or "").strip()
    ]
    build_id = str((target.get("recommended_build_id") or "")).strip()
    if compose_from_inventory is True:
        body["compose_from_inventory"] = True
    elif (
        strategy_mode == "constrained"
        and len(set(resolved_ids)) >= 2
        and build_id == "generic_low_voltage_build"
    ):
        body["compose_from_inventory"] = True
    return body

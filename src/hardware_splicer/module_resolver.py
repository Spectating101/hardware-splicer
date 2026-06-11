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
    (re.compile(r"sg90", re.I), "sg90", "act", 0.92),
    (re.compile(r"mg996r", re.I), "mg996r", "act", 0.9),
    (re.compile(r"l298n", re.I), "l298n", "drv", 0.9),
    (re.compile(r"relay", re.I), "relay-1ch", "drv", 0.85),
    (re.compile(r"pump|peristaltic", re.I), "mini-pump-5v", "load", 0.8),
    (re.compile(r"fan|blower", re.I), "fan-5v", "load", 0.8),
    (re.compile(r"usb.*serial|cp210|ch340|ftdi", re.I), "usb-uart", "usb", 0.85),
    (re.compile(r"ssd1306|oled", re.I), "ssd1306", "ui", 0.85),
    (re.compile(r"barrel|12v.*supply|12v adapter", re.I), "dc-barrel-12v", "pwr", 0.8),
    (re.compile(r"power.?bank|usb.*power|5v.*usb|phone charger", re.I), "usb-power-5v", "pwr", 0.92),
]

_POWER_TOPOLOGY_USB = re.compile(
    r"power.?bank|usb.*power|5v.*usb|phone charger|power_source",
    re.I,
)
_POWER_TOPOLOGY_BARREL = re.compile(r"barrel|12v.*supply|12v adapter|wall wart", re.I)

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
}


def _part_text(part: Mapping[str, Any]) -> str:
    bits = [
        str(part.get("name") or ""),
        str(part.get("type") or ""),
        str(part.get("kind") or ""),
        str(part.get("part_class") or ""),
    ]
    return " ".join(bits).strip()


def resolve_parts_to_modules(parts: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Map intake-normalized parts to module-library IDs with role hints."""
    resolved: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for part in parts:
        text = _part_text(part)
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
    return resolved


def infer_power_topology(
    parts: List[Mapping[str, Any]],
    resolved_modules: List[Mapping[str, Any]] | None = None,
) -> str:
    """Return usb_5v | barrel_12v | hybrid from inventory."""
    resolved_modules = resolved_modules or []
    texts = [_part_text(part) for part in parts]
    has_usb = any(_POWER_TOPOLOGY_USB.search(t) for t in texts if t)
    has_barrel = any(_POWER_TOPOLOGY_BARREL.search(t) for t in texts if t)
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
    return body

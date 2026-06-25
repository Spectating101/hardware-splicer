"""Shared helpers for bounded circuit-synthesis planners."""

from __future__ import annotations

import re
from typing import Any, Iterable, List, Mapping

from ..pcb.module_registry import find_module
from .ir import CircuitIntent, Constraint


POWER_SOURCE_CURRENT_A = {
    "usb-power-5v": 0.9,
    "dc-barrel-12v": 2.0,
}
POWER_SOURCE_VOLTAGE_V = {
    "usb-power-5v": 5.0,
    "dc-barrel-12v": 12.0,
}
MCU_MODULE_IDS = {"esp32-devkit", "arduino-nano", "rpi-pico"}


def available_module_ids(intent: CircuitIntent) -> set[str]:
    ids = set(intent.allowed_modules)
    for row in intent.allowed_parts:
        for key in ("module_id", "id"):
            module_id = str(row.get(key) or "").strip()
            if module_id and find_module(module_id):
                ids.add(module_id)
    return ids


def first_available(available: set[str], candidates: Iterable[str]) -> str:
    for module_id in candidates:
        if module_id in available and find_module(module_id):
            return module_id
    return ""


def first_controller(available: set[str]) -> str:
    for module_id in ("esp32-devkit", "arduino-nano", "rpi-pico"):
        if module_id in available:
            return module_id
    for module_id in available:
        spec = find_module(module_id) or {}
        if spec.get("category") == "mcu" or "controller" in set(spec.get("capabilityTags") or []):
            return module_id
    return ""


def first_power_source(available: set[str], input_v: float | None = None) -> str:
    if input_v is not None:
        for module_id, voltage in POWER_SOURCE_VOLTAGE_V.items():
            if module_id in available and abs(voltage - input_v) <= 0.75:
                return module_id
    return first_available(available, ("usb-power-5v", "dc-barrel-12v"))


def module_logic_voltage(module_id: str) -> float | None:
    spec = find_module(module_id) or {}
    return float_or_none(spec.get("logicVoltage"))


def module_input_range(module_id: str) -> tuple[float | None, float | None]:
    spec = find_module(module_id) or {}
    rng = spec.get("inputVoltageRange")
    if isinstance(rng, list) and len(rng) >= 2:
        return float_or_none(rng[0]), float_or_none(rng[1])
    return None, None


def module_current_limit_a(module_id: str, *, default_a: float | None = None) -> float | None:
    spec = find_module(module_id) or {}
    values: List[float] = []
    for pin in spec.get("pins") or []:
        ma = float_or_none(pin.get("currentMaxMa"))
        if ma is not None:
            values.append(ma / 1000.0)
    if values:
        return max(values)
    return default_a


def module_has_role(module_id: str, roles: set[str]) -> bool:
    spec = find_module(module_id) or {}
    return any(str(pin.get("role") or "") in roles for pin in spec.get("pins") or [])


def voltage_from_text(value: str) -> float | None:
    text = str(value or "").lower()
    if "3v3" in text or "3.3v" in text or "3.3 v" in text:
        return 3.3
    match = re.search(r"(?<![0-9.])([0-9]+(?:\.[0-9]+)?)\s*v\b", text)
    if not match:
        return None
    return float_or_none(match.group(1))


def float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_float(row: Mapping[str, Any], keys: Iterable[str]) -> float | None:
    for key in keys:
        value = float_or_none(row.get(key))
        if value is not None:
            return value
    return None


def passed(
    constraint_id: str,
    type: str,
    target: str,
    requirement: str,
    *,
    value: Any = None,
    notes: str = "",
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        type=type,
        target=target,
        requirement=requirement,
        status="pass",
        value=value,
        notes=notes,
    )


def warned(
    constraint_id: str,
    type: str,
    target: str,
    requirement: str,
    *,
    value: Any = None,
    notes: str = "",
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        type=type,
        target=target,
        requirement=requirement,
        status="warn",
        value=value,
        notes=notes,
    )


def blocked(
    constraint_id: str,
    type: str,
    target: str,
    requirement: str,
    *,
    value: Any = None,
    notes: str = "",
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        type=type,
        target=target,
        requirement=requirement,
        status="blocked",
        value=value,
        notes=notes,
    )


def dedupe(rows: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for row in rows:
        text = str(row or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def has_blocker(constraints: Iterable[Constraint], missing: Iterable[str]) -> bool:
    return bool(list(missing)) or any(row.status == "blocked" for row in constraints)


def build_path(
    *,
    available: set[str],
    selected: Iterable[str],
    build_id: str = "generic_low_voltage_build",
    notes: Iterable[str] = (),
) -> dict[str, Any]:
    module_ids = dedupe([module_id for module_id in selected if module_id in available and find_module(module_id)])
    return {
        "build_id": build_id,
        "compose_mode": "module_graph_candidate",
        "module_ids": module_ids,
        "can_compile_with_existing_auto_wire": len(module_ids) >= 2,
        "notes": list(notes)
        or [
            "Use compose_dispatch only after blocked constraints are resolved.",
            "This candidate is topology planning, not certified schematic synthesis.",
        ],
    }

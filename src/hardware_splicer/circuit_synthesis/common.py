"""Shared helpers for bounded circuit-synthesis planners.

Shared helpers may parse declared structured fields, but they do not inject representative
USB/barrel currents, preferred MCU identities, or voltage facts from goal prose.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Mapping

from ..electrical_contract_truth import exact_output_voltage_v, is_power_source, max_output_current_a
from ..pcb.module_registry import find_module
from .ir import CircuitIntent, Constraint


def available_module_ids(intent: CircuitIntent) -> set[str]:
    ids = set(intent.allowed_modules)
    for row in intent.allowed_parts:
        for key in ("module_id", "id"):
            module_id = str(row.get(key) or "").strip()
            if module_id and find_module(module_id):
                ids.add(module_id)
    return ids


def first_available(available: set[str], candidates: Iterable[str]) -> str:
    matches = [module_id for module_id in candidates if module_id in available and find_module(module_id)]
    return matches[0] if len(matches) == 1 else ""


def first_controller(available: set[str]) -> str:
    candidates: list[str] = []
    for module_id in sorted(available):
        spec = find_module(module_id) or {}
        if spec.get("category") == "mcu" or "controller" in set(spec.get("capabilityTags") or []):
            candidates.append(module_id)
    return candidates[0] if len(candidates) == 1 else ""


def first_power_source(available: set[str], input_v: float | None = None) -> str:
    candidates = sorted(module_id for module_id in available if is_power_source(module_id))
    if input_v is not None:
        exact = [
            module_id
            for module_id in candidates
            if exact_output_voltage_v(module_id) is not None
            and abs(float(exact_output_voltage_v(module_id)) - input_v) <= 0.75
        ]
        return exact[0] if len(exact) == 1 else ""
    return candidates[0] if len(candidates) == 1 else ""


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
    """Compatibility wrapper: return only structured catalog current truth.

    ``default_a`` is accepted so older bounded planners do not break at call sites, but it
    is intentionally ignored. A missing contract remains unresolved instead of becoming a
    prettier hardcoded rating.
    """
    _ = default_a
    return max_output_current_a(module_id)


def module_has_role(module_id: str, roles: set[str]) -> bool:
    spec = find_module(module_id) or {}
    return any(str(pin.get("role") or "") in roles for pin in spec.get("pins") or [])


def voltage_from_text(value: str) -> float | None:
    """Legacy compatibility hook; model-first planners must not infer voltage from prose."""
    _ = value
    return None


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
    module_ids = dedupe(
        [module_id for module_id in selected if module_id in available and find_module(module_id)]
    )
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

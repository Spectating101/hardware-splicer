"""Structured electrical truth accessors for catalog modules.

Only explicit machine-readable catalog fields count as electrical authority here. Human
summaries, warnings, labels and module IDs are deliberately not parsed into ratings. When
a precise rating/threshold is absent, callers receive ``None`` and must keep the
engineering decision unresolved.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Sequence

from .pcb.module_registry import find_module


SCHEMA_VERSION = "hardware_splicer.electrical_contract_truth.v1"
_EXACT_VOLTAGE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*[vV]\s*$")


def module_spec(module_id: str) -> Dict[str, Any]:
    spec = find_module(str(module_id or "").strip())
    return dict(spec) if isinstance(spec, Mapping) else {}


def pin_rows(module_id: str) -> list[Dict[str, Any]]:
    spec = module_spec(module_id)
    pins = spec.get("pins")
    if not isinstance(pins, Sequence) or isinstance(pins, (str, bytes, bytearray)):
        return []
    return [dict(row) for row in pins if isinstance(row, Mapping)]


def pin_ids(module_id: str) -> set[str]:
    return {
        str(row.get("id") or "").strip()
        for row in pin_rows(module_id)
        if str(row.get("id") or "").strip()
    }


def capability_tags(module_id: str) -> set[str]:
    values = module_spec(module_id).get("capabilityTags")
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return set()
    return {str(value).strip() for value in values if str(value).strip()}


def category(module_id: str) -> str:
    return str(module_spec(module_id).get("category") or "").strip()


def structured_contract(module_id: str) -> Dict[str, Any]:
    """Return optional explicit component contract fields without inventing defaults."""
    spec = module_spec(module_id)
    raw = spec.get("electricalContract")
    return dict(raw) if isinstance(raw, Mapping) else {}


def max_output_current_a(module_id: str) -> float | None:
    """Maximum declared output current from structured contract/pin fields.

    A component-level ``electricalContract.outputCurrentMaxA`` wins when present. Otherwise
    use the most conservative explicit ``currentMaxMa`` among power-output pins. Text such
    as "~2A/ch" in a summary is intentionally ignored.
    """
    contract = structured_contract(module_id)
    direct = _float_or_none(contract.get("outputCurrentMaxA"))
    if direct is not None:
        return direct

    declared: list[float] = []
    for row in pin_rows(module_id):
        if str(row.get("role") or "") != "power_out":
            continue
        current_ma = _float_or_none(row.get("currentMaxMa"))
        if current_ma is not None:
            declared.append(current_ma / 1000.0)
    return min(declared) if declared else None


def exact_output_voltage_v(module_id: str) -> float | None:
    """Return one exact declared power-output voltage, never an adjustable/range guess."""
    contract = structured_contract(module_id)
    direct = _float_or_none(contract.get("outputVoltageV"))
    if direct is not None:
        return direct

    values: set[float] = set()
    for row in pin_rows(module_id):
        if str(row.get("role") or "") != "power_out":
            continue
        raw = str(row.get("voltage") or "")
        match = _EXACT_VOLTAGE_RE.match(raw)
        if match:
            values.add(float(match.group(1)))
    return next(iter(values)) if len(values) == 1 else None


def logic_input_min_v(module_id: str) -> float | None:
    """Return an explicit guaranteed logic-high/input threshold if the catalog has one."""
    contract = structured_contract(module_id)
    for key in ("logicInputHighMinV", "logicInputMinV"):
        value = _float_or_none(contract.get(key))
        if value is not None:
            return value
    return None


def integrated_inductive_protection(module_id: str) -> bool | None:
    """Return explicit integrated clamp/protection truth, otherwise unknown."""
    contract = structured_contract(module_id)
    value = contract.get("integratedInductiveProtection")
    return value if isinstance(value, bool) else None


def is_power_source(module_id: str) -> bool:
    return category(module_id) == "power" and any(
        str(row.get("role") or "") == "power_out" for row in pin_rows(module_id)
    )


def is_mcu(module_id: str) -> bool:
    return category(module_id) == "mcu"


def is_h_bridge_interface(module_id: str) -> bool:
    required = {"VCC", "GND", "IN1", "IN2", "OUT1", "OUT2"}
    return required.issubset(pin_ids(module_id)) and "actuator_driver" in capability_tags(module_id)


def is_low_side_switch_interface(module_id: str) -> bool:
    required = {"VIN", "VIN-", "SIG", "GND", "VOUT+", "VOUT-"}
    return required.issubset(pin_ids(module_id)) and "actuator_driver" in capability_tags(module_id)


def is_level_shifter_interface(module_id: str) -> bool:
    required = {"LV", "HV", "GND", "LV1", "HV1"}
    return required.issubset(pin_ids(module_id))


def contract_snapshot(module_id: str) -> Dict[str, Any]:
    """Small auditable view used by planners/tests without copying catalog prose."""
    return {
        "schema_version": SCHEMA_VERSION,
        "module_id": module_id,
        "category": category(module_id) or None,
        "capability_tags": sorted(capability_tags(module_id)),
        "pin_ids": sorted(pin_ids(module_id)),
        "exact_output_voltage_v": exact_output_voltage_v(module_id),
        "max_output_current_a": max_output_current_a(module_id),
        "logic_input_min_v": logic_input_min_v(module_id),
        "integrated_inductive_protection": integrated_inductive_protection(module_id),
        "source": "structured_catalog_fields_only",
        "authority_effect": "none",
    }


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

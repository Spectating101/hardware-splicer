"""Structured electrical truth accessors for catalog modules.

Only explicit machine-readable catalog/component-contract fields count as electrical
authority here. Human summaries, warnings, labels and module IDs are deliberately not
parsed into ratings. When a precise rating/threshold is absent, callers receive ``None``
and must keep the engineering decision unresolved.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .pcb.module_registry import find_module


SCHEMA_VERSION = "hardware_splicer.electrical_contract_truth.v1"
_CONTRACTS_PATH = Path(__file__).resolve().parent / "data" / "electrical_contracts.json"
_EXACT_VOLTAGE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*[vV]\s*$")
_VOLTAGE_RANGE_RE = re.compile(
    r"^\s*([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*[vV](?:\s+.*)?$"
)


@lru_cache(maxsize=1)
def _component_contracts() -> Dict[str, Dict[str, Any]]:
    """Load explicit component contracts shipped as package data.

    The sidecar exists so authoritative electrical facts do not have to be inferred from
    human-facing catalog prose or wait for a generated frontend catalog refresh. Inline
    ``electricalContract`` fields remain supported and are merged with this sidecar.
    """
    try:
        payload = json.loads(_CONTRACTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = payload.get("contracts") if isinstance(payload, Mapping) else None
    if not isinstance(rows, Mapping):
        return {}
    return {
        str(module_id): dict(contract)
        for module_id, contract in rows.items()
        if isinstance(contract, Mapping)
    }


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
    """Return explicit component contract fields without inventing defaults."""
    module_id = str(module_id or "").strip()
    spec = module_spec(module_id)
    inline = spec.get("electricalContract")
    merged = dict(inline) if isinstance(inline, Mapping) else {}
    # Sidecar fields are deliberate authority upgrades and therefore win over stale
    # generated catalog copies. Provenance travels with the same machine-readable row.
    merged.update(_component_contracts().get(module_id) or {})
    return merged


def max_output_current_a(module_id: str) -> float | None:
    """Return a machine-readable output/load-current rating when one actually exists.

    A component-level ``electricalContract.outputCurrentMaxA`` is authoritative for any
    module. Pin ``currentMaxMa`` is only interpreted as a source rating for catalog power
    modules; on an actuator/driver a 5 V auxiliary pin must not be mistaken for motor
    channel current. Text such as "~2A/ch" in a summary is intentionally ignored.
    """
    contract = structured_contract(module_id)
    direct = _float_or_none(contract.get("outputCurrentMaxA"))
    if direct is not None:
        return direct
    if category(module_id) != "power":
        return None

    declared: list[float] = []
    for row in pin_rows(module_id):
        if str(row.get("role") or "") != "power_out":
            continue
        current_ma = _float_or_none(row.get("currentMaxMa"))
        if current_ma is not None:
            declared.append(current_ma / 1000.0)
    return min(declared) if declared else None


def output_voltage_range_v(module_id: str) -> tuple[float | None, float | None]:
    """Return one unambiguous declared output range from structured contract/pin fields."""
    contract = structured_contract(module_id)
    raw_range = contract.get("outputVoltageRangeV")
    if isinstance(raw_range, Sequence) and not isinstance(raw_range, (str, bytes, bytearray)) and len(raw_range) >= 2:
        low = _float_or_none(raw_range[0])
        high = _float_or_none(raw_range[1])
        if low is not None and high is not None:
            return min(low, high), max(low, high)
    direct = _float_or_none(contract.get("outputVoltageV"))
    if direct is not None:
        return direct, direct

    ranges: set[tuple[float, float]] = set()
    for row in pin_rows(module_id):
        if str(row.get("role") or "") != "power_out":
            continue
        raw = str(row.get("voltage") or "")
        exact = _EXACT_VOLTAGE_RE.match(raw)
        if exact:
            value = float(exact.group(1))
            ranges.add((value, value))
            continue
        ranged = _VOLTAGE_RANGE_RE.match(raw)
        if ranged:
            low = float(ranged.group(1))
            high = float(ranged.group(2))
            ranges.add((min(low, high), max(low, high)))
    return next(iter(ranges)) if len(ranges) == 1 else (None, None)


def exact_output_voltage_v(module_id: str) -> float | None:
    """Return one exact declared power-output voltage, never an adjustable/range guess."""
    low, high = output_voltage_range_v(module_id)
    if low is not None and high is not None and abs(low - high) <= 1e-12:
        return low
    return None


def logic_input_min_v(module_id: str) -> float | None:
    """Return an explicit guaranteed logic-high/input threshold if one is structured."""
    contract = structured_contract(module_id)
    for key in ("logicInputHighMinV", "logicInputMinV"):
        value = _float_or_none(contract.get(key))
        if value is not None:
            return value
    return None


def logic_input_max_v(module_id: str) -> float | None:
    """Return an explicit normal logic-input ceiling when one is structured."""
    contract = structured_contract(module_id)
    for key in ("logicInputMaxV", "logicInputHighMaxV"):
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


def is_motor_or_load(module_id: str) -> bool:
    return "motor_or_load" in capability_tags(module_id) and "actuator_driver" not in capability_tags(module_id)


def is_bidirectional_motor_driver_interface(module_id: str) -> bool:
    """Recognize a motor-driver interface from declared capabilities and pin roles."""
    tags = capability_tags(module_id)
    if not {"actuator_driver", "motor_or_load"}.issubset(tags):
        return False
    controls = 0
    outputs = 0
    for row in pin_rows(module_id):
        role = str(row.get("role") or "")
        pin_id = str(row.get("id") or "").upper()
        if role in {"digital_in", "pwm", "digital_io"}:
            controls += 1
        if role == "power_out" and pin_id not in {"3V3", "5V", "VCC", "VDD"}:
            outputs += 1
    return controls >= 2 and outputs >= 2


def is_h_bridge_interface(module_id: str) -> bool:
    # Backward-compatible name now uses the structural interface classifier.
    return is_bidirectional_motor_driver_interface(module_id)


def is_low_side_switch_interface(module_id: str) -> bool:
    required = {"VIN", "VIN-", "SIG", "GND", "VOUT+", "VOUT-"}
    return required.issubset(pin_ids(module_id)) and "actuator_driver" in capability_tags(module_id)


def is_level_shifter_interface(module_id: str) -> bool:
    required = {"LV", "HV", "GND", "LV1", "HV1"}
    return required.issubset(pin_ids(module_id))


def contract_snapshot(module_id: str) -> Dict[str, Any]:
    """Small auditable view used by planners/tests without copying catalog prose."""
    low_v, high_v = output_voltage_range_v(module_id)
    contract = structured_contract(module_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "module_id": module_id,
        "category": category(module_id) or None,
        "capability_tags": sorted(capability_tags(module_id)),
        "pin_ids": sorted(pin_ids(module_id)),
        "exact_output_voltage_v": exact_output_voltage_v(module_id),
        "output_voltage_range_v": [low_v, high_v] if low_v is not None and high_v is not None else None,
        "max_output_current_a": max_output_current_a(module_id),
        "logic_input_min_v": logic_input_min_v(module_id),
        "logic_input_max_v": logic_input_max_v(module_id),
        "integrated_inductive_protection": integrated_inductive_protection(module_id),
        "contract_provenance": dict(contract.get("provenance") or {}) if isinstance(contract.get("provenance"), Mapping) else {},
        "source": "structured_component_contracts",
        "authority_effect": "none",
    }


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

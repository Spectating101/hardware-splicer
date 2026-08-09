"""Reference/catalog-backed electronics benchmark for HS electrical truth boundaries.

The benchmark separates four questions that PCB demos often blur together:

1. does the model reference only visible component/pin identities?
2. is the electrical netlist safe at signal-domain boundaries?
3. can HS lower the reviewed module-level netlist to KiCad artifacts?
4. does geometric DRC agree, without being mistaken for electrical correctness?

The strict signal oracle is deliberately independent from the historical ERC voltage policy.
It uses exact catalog pin evidence and rejects direct nets that join different fixed logic
voltages. Translation is represented as separate nets on either side of a translator; the
oracle does not pretend the translator's internal circuit has been independently verified.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .netlist import CircuitNetlist, run_erc
from .pcb.module_registry import find_module, find_pin


SCHEMA_VERSION = "hardware_splicer.electronics_foundation_benchmark.v1"
_SIGNAL_ROLES = {
    "digital_in",
    "digital_out",
    "digital_io",
    "pwm",
    "uart_rx",
    "uart_tx",
    "i2c_sda",
    "i2c_scl",
    "analog_in",
    "analog_out",
}
_POWER_ROLES = {"power_in", "power_out", "gnd", "power_3v3"}


def load_electronics_bundle(path: str | Path) -> Dict[str, Any]:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(body, Mapping):
        raise ValueError("electronics benchmark bundle must be one JSON object")
    return dict(body)


def _fixed_voltage(pin: Mapping[str, Any] | None) -> float | None:
    if not pin:
        return None
    text = str(pin.get("voltage") or "").strip()
    # Ranges such as 0-3.3V, 1.8-5.5V, and adjustable rails are not fixed logic evidence.
    if not text or re.search(r"[-–]|\bto\b|adjust|battery|or", text, re.I):
        return None
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*V(?:\s*\([^)]*\))?\s*", text, re.I)
    if not match:
        return None
    return float(match.group(1))


def _catalog_pin(netlist: CircuitNetlist, component_ref: str, pin_id: str) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    comp = netlist.component_map().get(component_ref)
    if comp is None or not comp.module_id:
        return None, None
    module = find_module(comp.module_id)
    return module, find_pin(module, pin_id) if module else None


def validate_catalog_identity_and_pins(netlist: CircuitNetlist) -> Dict[str, Any]:
    findings: list[Dict[str, Any]] = []
    valid = True
    comp_map = netlist.component_map()

    for comp in netlist.components:
        if not comp.module_id or find_module(comp.module_id) is None:
            findings.append(
                {
                    "severity": "error",
                    "code": "UNKNOWN_COMPONENT_IDENTITY",
                    "component_ref": comp.ref,
                    "module_id": comp.module_id,
                }
            )
            valid = False

    for net in netlist.nets:
        for pin_ref in net.pins:
            comp = comp_map.get(pin_ref.component_ref)
            if comp is None:
                findings.append(
                    {
                        "severity": "error",
                        "code": "UNKNOWN_COMPONENT_REF",
                        "net": net.name,
                        "component_ref": pin_ref.component_ref,
                    }
                )
                valid = False
                continue
            module = find_module(str(comp.module_id or ""))
            if module is None or find_pin(module, pin_ref.pin) is None:
                findings.append(
                    {
                        "severity": "error",
                        "code": "UNKNOWN_PIN_IDENTITY",
                        "net": net.name,
                        "component_ref": pin_ref.component_ref,
                        "module_id": comp.module_id,
                        "pin": pin_ref.pin,
                    }
                )
                valid = False

    return {
        "pass": valid,
        "findings": findings,
        "authority_effect": "none",
        "fabrication_authorized": False,
        "power_on_authorized": False,
    }


def strict_signal_voltage_audit(netlist: CircuitNetlist) -> Dict[str, Any]:
    """Reject direct signal nets that mix fixed catalog logic voltages.

    This is intentionally narrower and stricter than generic ERC. It does not infer that
    two voltage domains are safe merely because a common translator module exists elsewhere
    in the design. Safe translation must create separate high- and low-side nets.
    """

    findings: list[Dict[str, Any]] = []
    audited_nets = 0

    for net in netlist.nets:
        endpoints: list[Dict[str, Any]] = []
        powerish = False
        has_signal = False
        fixed_voltages: set[float] = set()
        for pin_ref in net.pins:
            module, pin = _catalog_pin(netlist, pin_ref.component_ref, pin_ref.pin)
            role = str((pin or {}).get("role") or "").strip().lower()
            voltage = _fixed_voltage(pin)
            if role in _POWER_ROLES:
                powerish = True
            if role in _SIGNAL_ROLES:
                has_signal = True
            if voltage is not None and role in _SIGNAL_ROLES:
                fixed_voltages.add(voltage)
            endpoints.append(
                {
                    "component_ref": pin_ref.component_ref,
                    "module_id": (module or {}).get("id"),
                    "pin": pin_ref.pin,
                    "role": role or None,
                    "fixed_voltage_v": voltage,
                }
            )

        if powerish and not has_signal:
            continue
        if not has_signal:
            continue
        audited_nets += 1
        if len(fixed_voltages) > 1:
            findings.append(
                {
                    "severity": "error",
                    "code": "DIRECT_LOGIC_VOLTAGE_MISMATCH",
                    "net": net.name,
                    "fixed_voltages_v": sorted(fixed_voltages),
                    "endpoints": endpoints,
                    "message": "Direct signal net joins pins with different fixed logic voltages; explicit translation or a defensible tolerance contract is required.",
                }
            )

    errors = sum(row.get("severity") == "error" for row in findings)
    return {
        "pass": errors == 0,
        "errors": errors,
        "audited_signal_nets": audited_nets,
        "findings": findings,
        "authority_effect": "none",
        "fabrication_authorized": False,
        "power_on_authorized": False,
    }


def _pin_set(netlist: CircuitNetlist, net_name: str) -> set[str]:
    for net in netlist.nets:
        if net.name == net_name:
            return {f"{row.component_ref}.{row.pin}" for row in net.pins}
    return set()


def translated_hcsr04_contract_audit(netlist: CircuitNetlist) -> Dict[str, Any]:
    """Audit the explicit module-level translator topology for this benchmark fixture."""

    expected = {
        "+5V": {"J1.V+", "U1.VIN", "U2.HV", "S1.VCC"},
        "GND": {"J1.GND", "U1.GND", "U2.GND", "S1.GND"},
        "+3V3": {"U1.3V3", "U2.LV"},
        "TRIG_3V3": {"U1.GPIO4", "U2.LV1"},
        "TRIG_5V": {"U2.HV1", "S1.TRIG"},
        "ECHO_5V": {"S1.ECHO", "U2.HV2"},
        "ECHO_3V3": {"U2.LV2", "U1.GPIO16"},
    }
    findings: list[Dict[str, Any]] = []
    for net_name, expected_pins in expected.items():
        actual = _pin_set(netlist, net_name)
        if actual != expected_pins:
            findings.append(
                {
                    "severity": "error",
                    "code": "TRANSLATOR_TOPOLOGY_MISMATCH",
                    "net": net_name,
                    "expected": sorted(expected_pins),
                    "actual": sorted(actual),
                }
            )

    # A critical invariant: neither signal channel may collapse HV and LV sides onto one net.
    for net in netlist.nets:
        pins = {f"{row.component_ref}.{row.pin}" for row in net.pins}
        if {"U2.HV1", "U2.LV1"} <= pins or {"U2.HV2", "U2.LV2"} <= pins:
            findings.append(
                {
                    "severity": "error",
                    "code": "TRANSLATOR_CHANNEL_BYPASSED",
                    "net": net.name,
                    "message": "High- and low-voltage sides of a translator channel were shorted into the same external net.",
                }
            )

    errors = sum(row.get("severity") == "error" for row in findings)
    return {
        "pass": errors == 0,
        "errors": errors,
        "findings": findings,
        "contract_scope": "module_level_topology_only",
        "translator_internal_electrical_behavior_verified": False,
        "authority_effect": "none",
        "fabrication_authorized": False,
        "power_on_authorized": False,
    }


def run_electronics_foundation_benchmark(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    good = CircuitNetlist.from_dict(bundle["translated_design"])
    unsafe = CircuitNetlist.from_dict(bundle["unsafe_direct_design"])

    good_identity = validate_catalog_identity_and_pins(good)
    unsafe_identity = validate_catalog_identity_and_pins(unsafe)
    good_erc = run_erc(good)
    unsafe_erc = run_erc(unsafe)
    good_strict = strict_signal_voltage_audit(good)
    unsafe_strict = strict_signal_voltage_audit(unsafe)
    translator_contract = translated_hcsr04_contract_audit(good)

    checks = {
        "translated_design_uses_only_known_component_and_pin_identities": good_identity["pass"],
        "unsafe_comparator_uses_only_known_component_and_pin_identities": unsafe_identity["pass"],
        "translated_design_passes_strict_signal_voltage_audit": good_strict["pass"],
        "translated_design_has_explicit_separate_hv_lv_channel_nets": translator_contract["pass"],
        "unsafe_direct_5v_to_3v3_is_rejected_by_strict_oracle": not unsafe_strict["pass"],
        "baseline_historical_erc_false_negative_detected": bool(unsafe_erc.get("pass")),
        "all_physical_authority_closed": True,
    }

    diagnostic_pass = all(checks.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "esp32_hcsr04_logic_domain_truth",
        "diagnostic_pass": diagnostic_pass,
        "design_ready": False,
        "fabrication_ready": False,
        "power_on_ready": False,
        "checks": checks,
        "translated_design": {
            "netlist": good.to_dict(),
            "identity_audit": good_identity,
            "historical_erc": good_erc,
            "strict_signal_audit": good_strict,
            "translator_contract_audit": translator_contract,
        },
        "unsafe_direct_design": {
            "netlist": unsafe.to_dict(),
            "identity_audit": unsafe_identity,
            "historical_erc": unsafe_erc,
            "strict_signal_audit": unsafe_strict,
        },
        "system_diagnosis": {
            "classification": "TOOL_IMPLEMENTATION" if unsafe_erc.get("pass") else "none",
            "signal": "historical_erc_treats_3v3_and_5v_as_compatible" if unsafe_erc.get("pass") else None,
            "recommended_fix": "Make fixed logic-voltage mismatch fail closed unless a net-local tolerance/translation contract explicitly permits it.",
        },
        "authority_effect": "none",
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "release_authorized": False,
    }

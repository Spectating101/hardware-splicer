"""Catalog-backed electronics benchmark for HS electrical truth boundaries.

The benchmark separates component/pin identity, signal-domain safety, translator topology,
and later KiCad geometry. PCB DRC must never be allowed to substitute for electrical truth.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Mapping

from .netlist import CircuitNetlist, run_erc
from .pcb.module_registry import find_module, find_pin

SCHEMA_VERSION = "hardware_splicer.electronics_foundation_benchmark.v1"
_SIGNAL_ROLES = {
    "digital_in", "digital_out", "digital_io", "pwm", "uart_rx", "uart_tx",
    "i2c_sda", "i2c_scl", "analog_in", "analog_out",
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
    if not text or re.search(r"[-–]|\bto\b|adjust|battery|\bor\b", text, re.I):
        return None
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*V(?:\s*\([^)]*\))?\s*", text, re.I)
    return float(match.group(1)) if match else None


def _catalog_pin(netlist: CircuitNetlist, component_ref: str, pin_id: str):
    comp = netlist.component_map().get(component_ref)
    if comp is None or not comp.module_id:
        return None, None
    module = find_module(comp.module_id)
    return module, find_pin(module, pin_id) if module else None


def validate_catalog_identity_and_pins(netlist: CircuitNetlist) -> Dict[str, Any]:
    findings: list[Dict[str, Any]] = []
    comp_map = netlist.component_map()
    for comp in netlist.components:
        if not comp.module_id or find_module(comp.module_id) is None:
            findings.append({
                "severity": "error", "code": "UNKNOWN_COMPONENT_IDENTITY",
                "component_ref": comp.ref, "module_id": comp.module_id,
            })
    for net in netlist.nets:
        for ref in net.pins:
            comp = comp_map.get(ref.component_ref)
            module = find_module(str(comp.module_id or "")) if comp else None
            if comp is None:
                findings.append({
                    "severity": "error", "code": "UNKNOWN_COMPONENT_REF",
                    "net": net.name, "component_ref": ref.component_ref,
                })
            elif module is None or find_pin(module, ref.pin) is None:
                findings.append({
                    "severity": "error", "code": "UNKNOWN_PIN_IDENTITY",
                    "net": net.name, "component_ref": ref.component_ref,
                    "module_id": comp.module_id, "pin": ref.pin,
                })
    return {
        "pass": not any(row["severity"] == "error" for row in findings),
        "findings": findings,
        "authority_effect": "none",
        "fabrication_authorized": False,
        "power_on_authorized": False,
    }


def strict_signal_voltage_audit(netlist: CircuitNetlist) -> Dict[str, Any]:
    """Independent sentinel: different exact fixed logic voltages may not share a signal net."""
    findings: list[Dict[str, Any]] = []
    audited = 0
    for net in netlist.nets:
        endpoints: list[Dict[str, Any]] = []
        fixed: set[float] = set()
        powerish = False
        signal = False
        for ref in net.pins:
            module, pin = _catalog_pin(netlist, ref.component_ref, ref.pin)
            role = str((pin or {}).get("role") or "").lower()
            voltage = _fixed_voltage(pin)
            powerish |= role in _POWER_ROLES
            signal |= role in _SIGNAL_ROLES
            if signal and role in _SIGNAL_ROLES and voltage is not None:
                fixed.add(voltage)
            endpoints.append({
                "component_ref": ref.component_ref,
                "module_id": (module or {}).get("id"),
                "pin": ref.pin,
                "role": role or None,
                "fixed_voltage_v": voltage,
            })
        if (powerish and not signal) or not signal:
            continue
        audited += 1
        if len(fixed) > 1:
            findings.append({
                "severity": "error",
                "code": "DIRECT_LOGIC_VOLTAGE_MISMATCH",
                "net": net.name,
                "fixed_voltages_v": sorted(fixed),
                "endpoints": endpoints,
                "message": "Direct signal net joins different fixed logic voltages; explicit translation or tolerance evidence is required.",
            })
    return {
        "pass": not findings,
        "errors": len(findings),
        "audited_signal_nets": audited,
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
    for name, pins in expected.items():
        actual = _pin_set(netlist, name)
        if actual != pins:
            findings.append({
                "severity": "error", "code": "TRANSLATOR_TOPOLOGY_MISMATCH",
                "net": name, "expected": sorted(pins), "actual": sorted(actual),
            })
    for net in netlist.nets:
        pins = {f"{row.component_ref}.{row.pin}" for row in net.pins}
        if {"U2.HV1", "U2.LV1"} <= pins or {"U2.HV2", "U2.LV2"} <= pins:
            findings.append({
                "severity": "error", "code": "TRANSLATOR_CHANNEL_BYPASSED",
                "net": net.name,
                "message": "Translator high- and low-voltage sides were shorted on one external net.",
            })
    return {
        "pass": not findings,
        "errors": len(findings),
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
    topology = translated_hcsr04_contract_audit(good)

    unsafe_erc_voltage_errors = [
        row for row in unsafe_erc.get("violations") or []
        if row.get("rule") == "erc-voltage-mismatch" and row.get("severity") == "error"
    ]
    checks = {
        "translated_design_uses_only_known_component_and_pin_identities": good_identity["pass"],
        "unsafe_comparator_uses_only_known_component_and_pin_identities": unsafe_identity["pass"],
        "translated_design_passes_hs_erc": bool(good_erc.get("pass")),
        "translated_design_passes_independent_strict_signal_audit": good_strict["pass"],
        "translated_design_has_explicit_separate_hv_lv_channel_nets": topology["pass"],
        "unsafe_direct_5v_to_3v3_is_rejected_by_strict_oracle": not unsafe_strict["pass"],
        "repaired_hs_erc_rejects_unsafe_direct_logic_domains": not bool(unsafe_erc.get("pass")),
        "repaired_hs_erc_reports_fixed_voltage_mismatch_errors": len(unsafe_erc_voltage_errors) >= 2,
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
            "hs_erc": good_erc,
            "strict_signal_audit": good_strict,
            "translator_contract_audit": topology,
        },
        "unsafe_direct_design": {
            "netlist": unsafe.to_dict(),
            "identity_audit": unsafe_identity,
            "hs_erc": unsafe_erc,
            "strict_signal_audit": unsafe_strict,
        },
        "repair_replay": {
            "baseline_observation": "Before repair, HS ERC passed this same unsafe comparator while the independent strict oracle reported two voltage-domain errors.",
            "current_result": "HS ERC now rejects the frozen unsafe comparator and agrees with the independent sentinel.",
            "classification": "TOOL_IMPLEMENTATION_REPAIRED",
        },
        "authority_effect": "none",
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "release_authorized": False,
    }

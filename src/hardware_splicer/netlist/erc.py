"""Electrical rule check on circuit netlist IR."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Set

from ..pcb.module_registry import find_module, find_pin
from .ir import CircuitNetlist, PinRef

ErcViolation = Dict[str, Any]

_POWER_NET_RE = re.compile(r"gnd|ground|vcc|vdd|v\+|5v|3v3|3\.3|vin|vbus|power", re.I)
_OUTPUT_ROLES = {"power_out", "digital_out", "pwm"}
_INPUT_ROLES = {"digital_in", "digital_io", "analog_in", "i2c_sda", "i2c_scl"}


def _pin_electrical(pin: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not pin:
        return {"role": None, "voltage_v": None, "voltage_range": None}
    role = pin.get("role")
    text = str(pin.get("voltage") or "") + " " + str(pin.get("notes") or "")
    voltage_v: Optional[float] = None
    voltage_range: Optional[tuple[float, float]] = None
    if re.search(r"3\.3\s*[-–to]+\s*5|3\.3\s*or\s*5|5\s*or\s*3\.3", text, re.I):
        voltage_range = (3.3, 5.0)
    match = re.search(r"([\d.]+)\s*V", text, re.I)
    if match:
        voltage_v = float(match.group(1))
    return {"role": role, "voltage_v": voltage_v, "voltage_range": voltage_range}


def _voltages_compatible(values: Set[float]) -> bool:
    if len(values) <= 1:
        return True
    if values <= {3.3, 5.0}:
        return True
    return False


def _net_is_power(net_name: str, pins: List[PinRef], comp_map: Mapping[str, Any]) -> bool:
    if _POWER_NET_RE.search(net_name):
        return True
    for pin_ref in pins:
        comp = comp_map.get(pin_ref.component_ref)
        if not comp or not comp.module_id:
            continue
        spec = find_module(comp.module_id)
        if not spec:
            continue
        pin = find_pin(spec, pin_ref.pin)
        if pin and pin.get("role") in ("power_in", "power_out", "gnd"):
            return True
        if pin_ref.pin.upper() in {"GND", "VCC", "V+", "V-", "5V", "3V3", "VIN", "VBUS"}:
            return True
    return False


def run_erc(netlist: CircuitNetlist) -> Dict[str, Any]:
    """Run schematic-level ERC on netlist IR."""
    violations: List[ErcViolation] = []
    comp_map = netlist.component_map()

    for net in netlist.nets:
        if len(net.pins) < 2:
            if not net.name.endswith("_singleton"):
                violations.append(
                    {
                        "rule": "erc-floating-pin",
                        "severity": "warn",
                        "net": net.name,
                        "message": f"Net {net.name} has fewer than 2 connections.",
                    }
                )
            continue

        if _net_is_power(net.name, net.pins, comp_map):
            continue

        voltages: Set[float] = set()
        roles: List[str] = []
        flexible = False
        for pin_ref in net.pins:
            comp = comp_map.get(pin_ref.component_ref)
            if not comp or not comp.module_id:
                continue
            spec = find_module(comp.module_id)
            elec = _pin_electrical(find_pin(spec, pin_ref.pin) if spec else None)
            if elec.get("voltage_range"):
                flexible = True
            if elec["voltage_v"] is not None:
                voltages.add(float(elec["voltage_v"]))
            if elec["role"]:
                roles.append(str(elec["role"]))

        if len(voltages) > 1 and not flexible and not _voltages_compatible(voltages):
            violations.append(
                {
                    "rule": "erc-voltage-mismatch",
                    "severity": "error",
                    "net": net.name,
                    "message": f"Net {net.name} mixes logic/power voltages: {sorted(voltages)}.",
                }
            )
        elif len(voltages) > 1 and not _voltages_compatible(voltages):
            violations.append(
                {
                    "rule": "erc-voltage-mismatch",
                    "severity": "warn",
                    "net": net.name,
                    "message": f"Net {net.name} mixes voltages {sorted(voltages)} — review before fab.",
                }
            )

        if "power_out" in roles and any(r in _INPUT_ROLES for r in roles) and len(voltages) <= 1:
            pass

    errors = sum(1 for v in violations if v.get("severity") == "error")
    warnings = sum(1 for v in violations if v.get("severity") == "warn")
    return {
        "pass": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "violations": violations,
    }


def verify_net_coverage(netlist: CircuitNetlist, graph: Mapping[str, Any]) -> Dict[str, Any]:
    """Ensure multi-pin nets in netlist appear in build graph wires."""
    from .lower import build_graph_to_netlist

    lowered = build_graph_to_netlist(graph, source="coverage_check")
    net_pin_sets = {
        net.name: {p.key() for p in net.pins if len(net.pins) >= 2}
        for net in netlist.nets
        if len(net.pins) >= 2
    }
    graph_pin_sets = {
        net.name: {p.key() for p in net.pins}
        for net in lowered.nets
        if len(net.pins) >= 2
    }
    missing: List[str] = []
    for name, pins in net_pin_sets.items():
        if not pins:
            continue
        matched = any(pins <= gps for gps in graph_pin_sets.values())
        if not matched:
            missing.append(name)
    return {"pass": not missing, "missing_nets": missing}

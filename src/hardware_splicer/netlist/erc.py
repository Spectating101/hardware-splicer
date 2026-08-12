"""Electrical rule check on circuit netlist IR."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Set

from ..electrical_contract_truth import logic_input_max_v, logic_input_min_v
from ..pcb.module_registry import find_module, find_pin
from .ir import CircuitNetlist, PinRef

ErcViolation = Dict[str, Any]

_POWER_NET_RE = re.compile(r"gnd|ground|vcc|vdd|v\+|5v|3v3|3\.3|vin|vbus|power", re.I)
_OUTPUT_ROLES = {"power_out", "digital_out", "digital_io", "pwm", "uart_tx", "spi_mosi", "spi_sck", "spi_cs"}
_INPUT_ROLES = {"digital_in", "digital_io", "analog_in", "i2c_sda", "i2c_scl", "uart_rx", "spi_miso"}
_CONTRACT_RECEIVER_ROLES = {"digital_in", "uart_rx"}


def _pin_electrical(pin: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not pin:
        return {"role": None, "voltage_v": None, "voltage_range": None}
    role = pin.get("role")
    text = str(pin.get("voltage") or "") + " " + str(pin.get("notes") or "")
    voltage_v: Optional[float] = None
    voltage_range: Optional[tuple[float, float]] = None

    range_match = re.search(
        r"([\d.]+)\s*(?:V\s*)?[-–]\s*([\d.]+)\s*V",
        text,
        re.I,
    )
    if range_match:
        low, high = float(range_match.group(1)), float(range_match.group(2))
        voltage_range = (min(low, high), max(low, high))
    elif re.search(r"3\.3\s*V?\s*(?:or|↔|<->)\s*5\s*V|5\s*V?\s*(?:or|↔|<->)\s*3\.3\s*V", text, re.I):
        voltage_range = (3.3, 5.0)
    else:
        fixed_match = re.search(r"([\d.]+)\s*V", text, re.I)
        if fixed_match:
            voltage_v = float(fixed_match.group(1))

    return {"role": role, "voltage_v": voltage_v, "voltage_range": voltage_range}


def _voltages_compatible(values: Set[float]) -> bool:
    """Exact fixed-voltage drivers are compatible only when they agree.

    Historical ERC treated the common set {3.3 V, 5 V} as inherently compatible. That
    silently approved direct 5 V outputs into 3.3 V GPIO. Voltage-domain translation or
    tolerance must instead be represented by explicit component/net structure or a
    structured receiver contract; familiarity of the voltage pair is never a safety
    contract.
    """
    return len(values) <= 1


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


def _receiver_contract(module_id: str, pin_role: str) -> Dict[str, Any] | None:
    """Return a bounded input contract only when both ends are explicit.

    A minimum threshold alone cannot prove over-voltage safety, and a maximum alone cannot
    prove a valid logic high. Requiring both keeps ERC fail-closed unless the component
    contract genuinely defines an accepted logic-input window.
    """
    if pin_role not in _CONTRACT_RECEIVER_ROLES:
        return None
    low = logic_input_min_v(module_id)
    high = logic_input_max_v(module_id)
    if low is None or high is None:
        return None
    return {
        "module_id": module_id,
        "min_v": min(low, high),
        "max_v": max(low, high),
    }


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
        receiver_contracts: List[Dict[str, Any]] = []
        for pin_ref in net.pins:
            comp = comp_map.get(pin_ref.component_ref)
            if not comp or not comp.module_id:
                continue
            spec = find_module(comp.module_id)
            pin = find_pin(spec, pin_ref.pin) if spec else None
            elec = _pin_electrical(pin)
            role = str(elec.get("role") or "")
            if role:
                roles.append(role)

            receiver = _receiver_contract(str(comp.module_id), role)
            if receiver is not None:
                receiver_contracts.append(
                    {
                        **receiver,
                        "component_ref": pin_ref.component_ref,
                        "pin": pin_ref.pin,
                    }
                )
                # The catalog pin's human-facing nominal logic label is not a driven
                # voltage. The structured receiver window is the authoritative fact.
                continue

            if elec.get("voltage_range"):
                flexible = True
            if elec["voltage_v"] is not None:
                voltages.add(float(elec["voltage_v"]))

        if len(voltages) > 1 and not flexible and not _voltages_compatible(voltages):
            violations.append(
                {
                    "rule": "erc-voltage-mismatch",
                    "severity": "error",
                    "net": net.name,
                    "message": f"Net {net.name} directly mixes fixed logic/power voltages: {sorted(voltages)}. Explicit translation or tolerance evidence is required.",
                }
            )
        elif len(voltages) > 1 and not _voltages_compatible(voltages):
            violations.append(
                {
                    "rule": "erc-voltage-mismatch",
                    "severity": "warn",
                    "net": net.name,
                    "message": f"Net {net.name} mixes voltages {sorted(voltages)} with range/tolerance evidence present — review before fab.",
                }
            )

        # Validate explicit logic receivers against every fixed voltage visible on the
        # signal net. This admits evidence-backed 3.3 V -> TTL inputs without restoring
        # the old global 3.3/5 V compatibility exception.
        for receiver in receiver_contracts:
            outside = sorted(
                value
                for value in voltages
                if value < float(receiver["min_v"]) or value > float(receiver["max_v"])
            )
            if outside:
                violations.append(
                    {
                        "rule": "erc-logic-input-range",
                        "severity": "error",
                        "net": net.name,
                        "component_ref": receiver["component_ref"],
                        "pin": receiver["pin"],
                        "module_id": receiver["module_id"],
                        "message": (
                            f"Net {net.name} drives {receiver['module_id']} {receiver['pin']} "
                            f"outside its structured logic-input window "
                            f"[{receiver['min_v']}, {receiver['max_v']}] V: {outside}."
                        ),
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

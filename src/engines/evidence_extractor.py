from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.engines.kicad_netlist_compiler import parse_resistance_ohms
from src.engines.kicad_parser import KiCadParser


def _normalize_net(n: str) -> str:
    if not n:
        return ""
    s = n.strip()
    up = s.upper()
    if up in {"GND", "GNDPWR", "PGND", "AGND", "0"}:
        return "0"
    return s


def is_ground_net(n: str) -> bool:
    return _normalize_net(n) == "0"


def is_power_net(n: str) -> bool:
    if not n:
        return False
    up = n.upper()
    if up in {"VCC", "VDD", "VIN", "VBAT", "VBUS", "+5V", "+3V3", "+3.3V", "+12V", "+24V"}:
        return True
    if up.startswith("+") and any(ch.isdigit() for ch in up):
        return True
    if up.startswith("V") and any(ch.isdigit() for ch in up):
        return True
    if up.startswith("VREF"):
        return True
    return False


@dataclass(frozen=True)
class ParsedResistor:
    ref: str
    ohms: float
    n1: str
    n2: str


@dataclass(frozen=True)
class ParsedCapacitor:
    ref: str
    value: str
    n1: str
    n2: str


def _pinmap_from_parsed(parsed: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    pinmap: Dict[str, Dict[str, str]] = {}
    nets: Dict[str, Dict[str, Any]] = parsed.get("nets") or {}
    for net_name, net_data in nets.items():
        nn = _normalize_net(net_name)
        for node in net_data.get("nodes", []) or []:
            ref = node.get("ref")
            pin = node.get("pin")
            if not ref or not pin:
                continue
            pinmap.setdefault(ref, {})[str(pin)] = nn
    return pinmap


def extract_evidence_from_kicad_netlist(netlist_path: Path) -> Dict[str, Any]:
    parsed = KiCadParser(str(netlist_path)).parse()
    components: Dict[str, Dict[str, Any]] = parsed.get("components") or {}
    pinmap = _pinmap_from_parsed(parsed)

    resistors: List[ParsedResistor] = []
    capacitors: List[ParsedCapacitor] = []
    rails: set[str] = set()

    for net_name in (parsed.get("nets") or {}).keys():
        nn = _normalize_net(net_name)
        if is_power_net(nn):
            rails.add(nn)

    for ref, meta in components.items():
        if not isinstance(meta, dict):
            continue
        value = str(meta.get("value") or "").strip()
        pins = pinmap.get(ref, {})
        if len(pins) < 2:
            continue
        pin_names = sorted(pins.keys())
        n1 = pins[pin_names[0]]
        n2 = pins[pin_names[1]]

        if ref.upper().startswith("R"):
            ohms = parse_resistance_ohms(value or "")
            if ohms is not None and ohms > 0:
                resistors.append(ParsedResistor(ref=ref, ohms=float(ohms), n1=n1, n2=n2))
        if ref.upper().startswith("C"):
            capacitors.append(ParsedCapacitor(ref=ref, value=value, n1=n1, n2=n2))

    findings = infer_common_interface_facts(
        resistors=resistors,
        capacitors=capacitors,
        rails=sorted(rails),
    )

    return {
        "source": {"type": "kicad_netlist", "path": str(netlist_path)},
        "components": components,
        "pinmap": pinmap,
        "resistors": [r.__dict__ for r in resistors],
        "capacitors": [c.__dict__ for c in capacitors],
        "rails": sorted(rails),
        "findings": findings,
    }


def infer_common_interface_facts(
    *,
    resistors: List[ParsedResistor],
    capacitors: List[ParsedCapacitor],
    rails: List[str],
) -> Dict[str, Any]:
    rails_set = set(rails)
    pullups: Dict[str, Any] = {"detected": [], "by_net": {}}

    # Pullup heuristic: resistor 1k..100k from signal net to a power rail.
    for r in resistors:
        if not (1_000 <= r.ohms <= 100_000):
            continue
        a = _normalize_net(r.n1)
        b = _normalize_net(r.n2)
        if is_ground_net(a) or is_ground_net(b):
            continue
        if a in rails_set and b not in rails_set:
            pullups["detected"].append({"ref": r.ref, "signal_net": b, "rail": a, "ohms": r.ohms})
            pullups["by_net"].setdefault(b, []).append({"ref": r.ref, "rail": a, "ohms": r.ohms})
        if b in rails_set and a not in rails_set:
            pullups["detected"].append({"ref": r.ref, "signal_net": a, "rail": b, "ohms": r.ohms})
            pullups["by_net"].setdefault(a, []).append({"ref": r.ref, "rail": b, "ohms": r.ohms})

    # Decoupling heuristic: any C* between a power rail and ground is a decoupling candidate for that rail.
    decoupling: Dict[str, Any] = {"by_rail": {}}
    for c in capacitors:
        a = _normalize_net(c.n1)
        b = _normalize_net(c.n2)
        if is_ground_net(a) and is_power_net(b):
            decoupling["by_rail"].setdefault(b, []).append({"ref": c.ref, "value": c.value})
        if is_ground_net(b) and is_power_net(a):
            decoupling["by_rail"].setdefault(a, []).append({"ref": c.ref, "value": c.value})

    # CAN termination heuristic: a ~120Ω resistor between two CAN-like nets.
    can_terms: List[Dict[str, Any]] = []
    for r in resistors:
        if not (90 <= r.ohms <= 140):
            continue
        a = _normalize_net(r.n1).upper()
        b = _normalize_net(r.n2).upper()
        if "CAN" in a and "CAN" in b and a != b:
            can_terms.append({"ref": r.ref, "n1": r.n1, "n2": r.n2, "ohms": r.ohms})

    return {"pullups": pullups, "decoupling": decoupling, "can_termination": {"detected": can_terms}}


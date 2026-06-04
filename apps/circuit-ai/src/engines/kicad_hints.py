"""Generate helpful hint templates for KiCad netlist validation.

Goal: reduce manual work. KiCad `.net` gives connectivity, but not electrical
models for ICs. This module scans nets and proposes:
- likely ground net
- likely rail nets and their nominal voltages (3.3/5/12)
- a skeleton hints JSON (sources + voltage constraints) that a user/LLM can fill

This is intentionally conservative: it prefers explicit, named rails and will
not invent load currents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.engines.kicad_parser import KiCadParser


GROUND_NAMES = {"GND", "GNDPWR", "PGND", "AGND", "GROUND"}


RAIL_PATTERNS: List[Tuple[re.Pattern[str], float]] = [
    (re.compile(r"(^|\b)(\+?3V3|3V3|3\.3V|VCC3V3|VDD3V3)(\b|$)", re.I), 3.3),
    (re.compile(r"(^|\b)(\+?5V|5V0|VBUS|USB_5V|VCC5V|VDD5V)(\b|$)", re.I), 5.0),
    (re.compile(r"(^|\b)(\+?12V|12V0|VCC12V|VDD12V)(\b|$)", re.I), 12.0),
]

# Intentionally modest: should not trigger warnings for typical hobby boards, but
# still enables trace-drop analysis when loads are heavier.
DEFAULT_TRACE_SPEC = {"length_m": 0.03, "width_m": 0.5e-3, "copper_oz": 1.0}

SOURCE_PRIORITY = [
    re.compile(r"(^|\b)(VIN|VBUS|VCC|VDD)(\b|$)", re.I),
    re.compile(r"(^|\b)(\+?5V|\+?3V3|\+?12V)(\b|$)", re.I),
]


@dataclass(frozen=True)
class RailCandidate:
    net: str
    nominal_v: float
    node_count: int


def guess_ground_net(nets: Dict[str, Any]) -> Optional[str]:
    for name in nets.keys():
        if name.strip().upper() in GROUND_NAMES:
            return name
    # common KiCad: "0" isn't typical; fallback to first net containing GND
    for name in nets.keys():
        if "GND" in name.upper():
            return name
    return None


def find_rail_candidates(nets: Dict[str, Any]) -> List[RailCandidate]:
    out: List[RailCandidate] = []
    for name, data in (nets or {}).items():
        for pat, v in RAIL_PATTERNS:
            if pat.search(name or ""):
                nodes = data.get("nodes") or []
                out.append(RailCandidate(net=name, nominal_v=v, node_count=len(nodes)))
                break
    # stable order: higher node count first, then name
    out.sort(key=lambda r: (-r.node_count, r.net))
    return out


def net_candidates(nets: Dict[str, Any], gnd: str, limit: int = 5) -> List[Dict[str, Any]]:
    items = []
    for name, data in (nets or {}).items():
        if name == gnd:
            continue
        nodes = data.get("nodes") or []
        items.append({"net": name, "node_count": len(nodes)})
    items.sort(key=lambda x: (-x["node_count"], x["net"]))
    return items[:limit]


def _ref_prefix(ref: str) -> str:
    ref = (ref or "").strip().upper()
    # KiCad refs: R1, C10, U3, J2, D1, Q5...
    for i, ch in enumerate(ref):
        if ch.isdigit():
            return ref[:i]
    return ref


def estimate_load_current_amps(ref: str, value: str) -> tuple[float, str]:
    """Return a conservative DC current guess and a note.

    This is a heuristic to make auto-hints actually useful.
    """

    v = (value or "").upper()
    prefix = _ref_prefix(ref)

    # Known high-ROI guesses
    if "ESP32" in v:
        return 0.24, "heuristic: ESP32 peak current ~240mA"
    if "ESP8266" in v:
        return 0.20, "heuristic: ESP8266 peak current ~200mA"
    if "STM32" in v:
        return 0.12, "heuristic: STM32-class MCU ~120mA worst-case"
    if "ATMEGA" in v or "ARDUINO" in v:
        return 0.20, "heuristic: AVR/Arduino-class board ~200mA worst-case"
    if "RP2040" in v:
        return 0.10, "heuristic: RP2040-class MCU ~100mA worst-case"

    # Ref-prefix fallback
    if prefix in {"U", "IC"}:
        return 0.05, "heuristic: unknown IC default 50mA (adjust)"

    return 0.0, "no load estimate"


def is_likely_load_ref(ref: str) -> bool:
    prefix = _ref_prefix(ref)
    return prefix in {"U", "IC", "MCU", "MOD"}


REGULATOR_KEYWORDS = [
    "LDO",
    "REG",
    "AMS1117",
    "AP2112",
    "MIC",
    "TLV",
    "XC620",
]


def _is_regulator_value(value: str) -> bool:
    v = (value or "").upper()
    return any(k in v for k in REGULATOR_KEYWORDS)


def infer_ldo_candidates(components: Dict[str, Any], ref_nets: Dict[str, set[str]], gnd: str) -> List[Dict[str, Any]]:
    """Infer likely LDO regulators bridging a higher-voltage net to a lower-voltage rail net."""

    out: List[Dict[str, Any]] = []

    # Identify rail-ish nets by name
    rail5 = []
    rail3 = []
    for ref, nets_for_ref in ref_nets.items():
        # no-op; just to satisfy type checker in some environments
        pass

    def _is_3v3(name: str) -> bool:
        return bool(RAIL_PATTERNS[0][0].search(name or ""))

    def _is_5v(name: str) -> bool:
        return bool(RAIL_PATTERNS[1][0].search(name or ""))

    for ref, meta in components.items():
        if _ref_prefix(ref) not in {"U", "IC"}:
            continue
        nets_for_ref = ref_nets.get(ref, set())
        if not nets_for_ref:
            continue
        if gnd not in nets_for_ref:
            continue

        hi = next((n for n in sorted(nets_for_ref) if _is_5v(n)), None)
        lo = next((n for n in sorted(nets_for_ref) if _is_3v3(n)), None)
        if not hi or not lo:
            continue

        value = meta.get("value", "")
        # accept either explicit regulator-ish value or just a U* bridging 5V<->3V3
        if not (_is_regulator_value(value) or True):
            continue

        out.append(
            {
                "name": ref,
                "vin_net": hi,
                "vout_net": lo,
                "gnd_net": gnd,
                "vout_nom_v": 3.3,
                "dropout_v": 0.3,
                "max_current_a": 1.0,
                "quiescent_current_a": 0.002,
                "note": f"inferred from nets: {hi}->{lo} and GND; value={value!r}",
            }
        )

    return out


def generate_hints_template(netlist_path: str) -> Dict[str, Any]:
    parsed = KiCadParser(netlist_path).parse()
    nets = parsed.get("nets") or {}
    components = parsed.get("components") or {}

    gnd = guess_ground_net(nets) or "GND"
    rails = find_rail_candidates(nets)
    candidates = net_candidates(nets, gnd)

    sources = []
    voltage_constraints = []

    # Prefer a single upstream source: VBUS/+5V if present, else highest-voltage rail.
    if rails:
        preferred = next((r for r in rails if abs(r.nominal_v - 5.0) < 1e-6), rails[0])
        sources.append(
            {
                "name": "V1",
                "net": preferred.net,
                "gnd": gnd,
                "volts": preferred.nominal_v,
                "max_current_a": 0.5 if abs(preferred.nominal_v - 5.0) < 1e-6 else 1.0,
                "note": "Assumed by heuristic; adjust as needed",
            }
        )

    else:
        # No obvious rails; suggest the most connected non-ground net as a candidate source.
        if candidates:
            preferred = None
            for pat in SOURCE_PRIORITY:
                preferred = next((c for c in candidates if pat.search(c["net"])), None)
                if preferred:
                    break
            chosen = preferred or candidates[0]
            sources.append({
                "name": "V1",
                "net": chosen["net"],
                "gnd": gnd,
                "volts": 5.0,
                "max_current_a": 0.5,
                "note": "No rail names matched; this is a placeholder. Set the correct voltage/current limit.",
            })

    for r in rails:
        voltage_constraints.append(
            {
                "name": f"RAIL::{r.net}",
                "net": r.net,
                "gnd": gnd,
                "min_v": r.nominal_v * 0.9,
                "max_v": r.nominal_v * 1.1,
                "severity": "error",
                "note": "Heuristic bounds; tighten for your parts",
            }
        )

    # Suggest loads (ICs) connected to likely rails.
    # This is only a starting point; user should correct values.
    rail_nets = {r.net for r in rails}
    if not rail_nets and sources:
        rail_nets.add(sources[0]["net"])

    # Build ref -> set(nets)
    ref_nets: dict[str, set[str]] = {}
    for net_name, net_data in (nets or {}).items():
        for node in (net_data.get("nodes") or []):
            ref = node.get("ref")
            if not ref:
                continue
            ref_nets.setdefault(ref, set()).add(net_name)

    ldo_candidates = infer_ldo_candidates(components, ref_nets, gnd)
    ldo_refs = {ldo.get("name") for ldo in ldo_candidates if ldo.get("name")}

    suggested_loads_cc = []
    for ref, meta in components.items():
        if not is_likely_load_ref(ref):
            continue
        if ref in ldo_refs:
            continue
        nets_for_ref = ref_nets.get(ref, set())
        # pick a rail net this ref touches
        rail = next((n for n in sorted(nets_for_ref) if n in rail_nets), None)
        if rail is None:
            continue
        amps, note = estimate_load_current_amps(ref, meta.get("value", ""))
        if amps <= 0:
            continue
        suggested_loads_cc.append({
            "name": ref,
            "net": rail,
            "gnd": gnd,
            "amps": amps,
            "min_v_off": None,
            "note": note,
        })

    # Series trace modeling (optional): split select nets into SRC/RAIL nodes and add a trace resistor.
    #
    # Goal: unlock trace-drop validation on KiCad netlists without PCB geometry.
    # The compiler interprets these by rewiring:
    # - kind=source_to_rail: move the voltage source to NET__SRC and add NET__SRC->NET trace
    # - kind=ldo_to_rail: move the LDO output to NET__SRC and add NET__SRC->NET trace
    #
    # One entry per net (deduped). If a net is both a source rail and an LDO output rail,
    # prefer modeling the LDO output (ldo_to_rail).
    series_traces: List[Dict[str, Any]] = []
    ldo_vout_nets = {ldo.get("vout_net") for ldo in (ldo_candidates or []) if ldo.get("vout_net")}
    source_nets = {src.get("net") for src in (sources or []) if src.get("net")}

    def _kind_for_net(net_name: str) -> Optional[str]:
        if not net_name or net_name == gnd:
            return None
        if net_name in ldo_vout_nets:
            return "ldo_to_rail"
        if net_name in source_nets:
            return "source_to_rail"
        return None

    for net_name in sorted(ldo_vout_nets.union(source_nets)):
        kind = _kind_for_net(net_name)
        if kind is None:
            continue
        series_traces.append(
            {
                "name": f"SERIES::{net_name}",
                "net": net_name,
                "kind": kind,
                "spec": dict(DEFAULT_TRACE_SPEC),
                "note": "Heuristic default trace; adjust length/width/copper for your board",
            }
        )

    return {
        "netlist": netlist_path,
        "ground_net": gnd,
        "rail_candidates": [r.__dict__ for r in rails],
        "net_candidates": candidates,
        "hints": {
            "sources": sources,
            "ldos": ldo_candidates,
            "loads_cc": suggested_loads_cc,
            "voltage_constraints": voltage_constraints,
            "max_trace_drop_v": 0.25,
            "series_traces": series_traces,
        },
    }

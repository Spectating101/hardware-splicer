"""Compile a KiCad S-expression netlist into `CircuitNetlist` + constraints.

KiCad netlists contain connectivity but not necessarily electrical models for ICs.
High-ROI approach:
- Deterministically compile what we can (resistors) from connectivity + values.
- Accept a small JSON "hints" object for power sources, current limits, and loads.

Hints schema (dict / JSON):
{
  "sources": [
    {"name": "VUSB", "net": "VBUS", "volts": 5.0, "gnd": "GND", "max_current_a": 0.5}
  ],
  "loads_cc": [
    {"name": "ESP32", "net": "+3V3", "amps": 0.24, "gnd": "GND", "min_v_off": 2.3}
  ],
  "voltage_constraints": [
    {"name": "RAIL_3V3", "net": "+3V3", "gnd": "GND", "min_v": 3.0, "max_v": 3.6, "severity": "error"}
  ]
}
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

from src.engines.netlist import (
    CircuitNetlist,
    ConstantCurrentLoad,
    ConstantPowerLoad,
    LDO,
    Resistor,
    TraceResistor,
    TraceSpec,
    VoltageConstraint,
    VoltageSource,
    is_ground,
)
from src.engines.power_tree_validator import PowerTreeConstraints, SourceCurrentLimit
from src.engines.kicad_parser import KiCadParser


@dataclass(frozen=True)
class KiCadCompiled:
    netlist: CircuitNetlist
    constraints: PowerTreeConstraints


SI_SUFFIX = {
    "R": 1.0,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}


def parse_resistance_ohms(value: str) -> Optional[float]:
    if not value:
        return None

    v = value.strip().upper().replace("OHM", "").replace("Ω", "").strip()

    # Handle forms like 4K7, 1R0, 10K
    for suffix, mult in SI_SUFFIX.items():
        if suffix in v and v != suffix:
            parts = v.split(suffix)
            if len(parts) != 2:
                continue
            left, right = parts
            if left == "":
                continue
            if right == "":
                num = left
            else:
                num = f"{left}.{right}"
            try:
                return float(num) * mult
            except ValueError:
                return None

    try:
        return float(v)
    except ValueError:
        return None


def _normalize_net(net: str) -> str:
    if not net:
        return ""
    n = net.strip()
    if is_ground(n):
        return "0"
    # Common KiCad ground names
    if n.upper() in {"GND", "GNDPWR", "PGND", "AGND"}:
        return "0"
    return n


def compile_kicad_netlist(
    netlist_path: str,
    hints: Optional[Dict[str, Any]] = None,
) -> KiCadCompiled:
    hints = hints or {}
    parsed = KiCadParser(netlist_path).parse()

    components: Dict[str, Dict[str, Any]] = parsed.get("components") or {}
    nets: Dict[str, Dict[str, Any]] = parsed.get("nets") or {}

    # Build ref -> pin -> net map
    pinmap: Dict[str, Dict[str, str]] = {}
    for net_name, net_data in nets.items():
        for node in net_data.get("nodes", []) or []:
            ref = node.get("ref")
            pin = node.get("pin")
            if not ref or not pin:
                continue
            pinmap.setdefault(ref, {})[pin] = _normalize_net(net_name)

    net = CircuitNetlist()

    # Compile resistors (R*)
    for ref, meta in components.items():
        if not ref or not ref.upper().startswith("R"):
            continue
        value = (meta.get("value") or "").strip()
        ohms = parse_resistance_ohms(value)
        if ohms is None or ohms <= 0:
            continue

        pins = pinmap.get(ref, {})
        if len(pins) < 2:
            continue
        # Choose two pins deterministically
        pin_names = sorted(pins.keys())
        n1 = pins[pin_names[0]]
        n2 = pins[pin_names[1]]
        if not n1 or not n2:
            continue
        net.resistors.append(Resistor(name=ref, n1=n1, n2=n2, ohms=ohms))

    # Power sources from hints
    source_limits: List[SourceCurrentLimit] = []
    for src in hints.get("sources", []) or []:
        name = src.get("name", "VSRC")
        net_name = _normalize_net(src.get("net", ""))
        gnd = _normalize_net(src.get("gnd", "0"))
        volts = float(src.get("volts", 0.0))
        if not net_name:
            continue
        net.voltage_sources.append(VoltageSource(name=name, n_plus=net_name, n_minus=gnd, volts=volts))

        max_i = src.get("max_current_a")
        if max_i is not None:
            source_limits.append(SourceCurrentLimit(source_name=name, max_current_a=float(max_i)))

    # Constant-current loads from hints
    for load in hints.get("loads_cc", []) or []:
        name = load.get("name", "LOAD")
        net_name = _normalize_net(load.get("net", ""))
        gnd = _normalize_net(load.get("gnd", "0"))
        amps = float(load.get("amps", 0.0))
        min_v_off = load.get("min_v_off")
        net.loads_cc.append(
            ConstantCurrentLoad(
                name=name,
                node=net_name,
                gnd=gnd,
                amps=amps,
                min_v_off=float(min_v_off) if min_v_off is not None else None,
            )
        )

    # Traces from hints (optional, DC copper drop model)
    for t in hints.get("traces", []) or []:
        name = t.get("name", "TRACE")
        n1 = _normalize_net(t.get("n1", ""))
        n2 = _normalize_net(t.get("n2", ""))
        spec = t.get("spec") or {}
        if not n1 or not n2:
            continue
        net.traces.append(
            TraceResistor(
                name=name,
                n1=n1,
                n2=n2,
                spec=TraceSpec(
                    length_m=float(spec.get("length_m", 0.05)),
                    width_m=float(spec.get("width_m", 0.2e-3)),
                    copper_oz=float(spec.get("copper_oz", 1.0)),
                ),
            )
        )

    # LDOs from hints (optional)
    for l in hints.get("ldos", []) or []:
        name = l.get("name", "LDO")
        vin = _normalize_net(l.get("vin_net") or l.get("vin") or "")
        vout = _normalize_net(l.get("vout_net") or l.get("vout") or "")
        gnd = _normalize_net(l.get("gnd_net") or l.get("gnd") or "0")
        if not vin or not vout:
            continue
        net.ldos.append(
            LDO(
                name=name,
                vin=vin,
                vout=vout,
                gnd=gnd,
                vout_nom_v=float(l.get("vout_nom_v", 3.3)),
                dropout_v=float(l.get("dropout_v", 0.3)),
                max_current_a=float(l.get("max_current_a", 1.0)),
                quiescent_current_a=float(l.get("quiescent_current_a", 0.002)),
                r_theta_ja_c_per_w=float(l.get("r_theta_ja_c_per_w", 60.0)),
                tj_max_c=float(l.get("tj_max_c", 125.0)),
                ambient_c=float(l.get("ambient_c", 25.0)),
            )
        )

    # Constant-power loads from hints (optional)
    for load in hints.get("loads_cp", []) or []:
        name = load.get("name", "LOADP")
        net_name = _normalize_net(load.get("net", ""))
        gnd = _normalize_net(load.get("gnd", "0"))
        watts = float(load.get("watts", 0.0))
        if not net_name or watts <= 0:
            continue
        net.loads_cp.append(
            ConstantPowerLoad(
                name=name,
                node=net_name,
                gnd=gnd,
                watts=watts,
                v_min=float(load.get("v_min", 0.1)),
                max_amps=float(load.get("max_amps")) if load.get("max_amps") is not None else None,
                min_v_off=float(load.get("min_v_off")) if load.get("min_v_off") is not None else None,
            )
        )

    # Voltage constraints from hints
    for vc in hints.get("voltage_constraints", []) or []:
        net.voltage_constraints.append(
            VoltageConstraint(
                name=vc.get("name", "VCONSTRAINT"),
                node=_normalize_net(vc.get("net", "")),
                gnd=_normalize_net(vc.get("gnd", "0")),
                min_v=float(vc["min_v"]) if vc.get("min_v") is not None else None,
                max_v=float(vc["max_v"]) if vc.get("max_v") is not None else None,
                severity=str(vc.get("severity", "error")),
            )
        )

    # Series trace modeling (optional): split select nets into SRC/RAIL nodes and add a trace resistor.
    #
    # This is used primarily by auto-hints to enable trace-drop validation on KiCad netlists.
    def _spec_from_dict(d: Dict[str, Any]) -> TraceSpec:
        return TraceSpec(
            length_m=float(d.get("length_m", 0.03)),
            width_m=float(d.get("width_m", 0.5e-3)),
            copper_oz=float(d.get("copper_oz", 1.0)),
        )

    def _has_trace(a: str, b: str) -> bool:
        for t in net.traces:
            if {t.n1, t.n2} == {a, b}:
                return True
        return False

    def _apply_series_trace(net_name_raw: str, kind: str, spec: TraceSpec, name: str) -> None:
        net_name = _normalize_net(net_name_raw)
        if not net_name or is_ground(net_name):
            return

        if kind == "source_to_rail":
            src_node = f"{net_name}__SRC"
            if not any(vs.n_plus == net_name for vs in net.voltage_sources):
                return
            net.voltage_sources = [
                replace(vs, n_plus=src_node) if vs.n_plus == net_name else vs for vs in net.voltage_sources
            ]
            if not _has_trace(src_node, net_name):
                net.traces.append(TraceResistor(name=name, n1=src_node, n2=net_name, spec=spec))
            return

        if kind == "ldo_to_rail":
            src_node = f"{net_name}__SRC"
            if not any(ldo.vout == net_name for ldo in net.ldos):
                return
            net.ldos = [replace(ldo, vout=src_node) if ldo.vout == net_name else ldo for ldo in net.ldos]
            if not _has_trace(src_node, net_name):
                net.traces.append(TraceResistor(name=name, n1=src_node, n2=net_name, spec=spec))
            return

        if kind == "rail_to_ldo":
            # Optional: model a shared trace from a rail net to one or more LDO VIN pins.
            # This is heuristic and may not match layout, but can help surface dropout issues.
            src_node = f"{net_name}__LDOIN"
            if not any(ldo.vin == net_name for ldo in net.ldos):
                return
            net.ldos = [replace(ldo, vin=src_node) if ldo.vin == net_name else ldo for ldo in net.ldos]
            if not _has_trace(net_name, src_node):
                net.traces.append(TraceResistor(name=name, n1=net_name, n2=src_node, spec=spec))
            return

    for st in hints.get("series_traces", []) or []:
        _apply_series_trace(
            net_name_raw=str(st.get("net", "")),
            kind=str(st.get("kind", "")),
            spec=_spec_from_dict(st.get("spec") or {}),
            name=str(st.get("name") or f"SERIES::{st.get('net', '')}"),
        )

    constraints = PowerTreeConstraints(
        source_limits=source_limits,
        max_trace_drop_v=float(hints.get("max_trace_drop_v", 0.25)),
    )

    return KiCadCompiled(netlist=net, constraints=constraints)

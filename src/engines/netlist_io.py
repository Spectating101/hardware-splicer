"""JSON/dict serialization for `CircuitNetlist`.

This exists so:
- LLMs can propose structured designs
- the physics engine can validate deterministically
- UIs (Blender addon / web / AR) can exchange designs safely

Schema is versioned and intentionally minimal.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict

from src.engines.netlist import (
    CircuitNetlist,
    ConstantCurrentLoad,
    ConstantPowerLoad,
    CurrentSource,
    LDO,
    Resistor,
    TraceResistor,
    TraceSpec,
    VoltageConstraint,
    VoltageSource,
)


SCHEMA_VERSION = 1


def netlist_to_dict(netlist: CircuitNetlist) -> Dict[str, Any]:
    def trace_to_dict(t: TraceResistor) -> Dict[str, Any]:
        return {
            "name": t.name,
            "n1": t.n1,
            "n2": t.n2,
            "spec": {
                "length_m": t.spec.length_m,
                "width_m": t.spec.width_m,
                "copper_oz": t.spec.copper_oz,
            },
        }

    return {
        "version": SCHEMA_VERSION,
        "resistors": [asdict(r) for r in netlist.resistors],
        "current_sources": [asdict(i) for i in netlist.current_sources],
        "voltage_sources": [asdict(v) for v in netlist.voltage_sources],
        "traces": [trace_to_dict(t) for t in netlist.traces],
        "ldos": [asdict(l) for l in netlist.ldos],
        "loads_cc": [asdict(l) for l in netlist.loads_cc],
        "loads_cp": [asdict(l) for l in netlist.loads_cp],
        "voltage_constraints": [asdict(vc) for vc in netlist.voltage_constraints],
    }


def netlist_from_dict(data: Dict[str, Any]) -> CircuitNetlist:
    version = data.get("version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported netlist schema version: {version}")

    net = CircuitNetlist()

    for r in data.get("resistors", []) or []:
        net.resistors.append(Resistor(**r))
    for i in data.get("current_sources", []) or []:
        net.current_sources.append(CurrentSource(**i))
    for v in data.get("voltage_sources", []) or []:
        net.voltage_sources.append(VoltageSource(**v))

    for t in data.get("traces", []) or []:
        spec = t.get("spec") or {}
        net.traces.append(
            TraceResistor(
                name=t["name"],
                n1=t["n1"],
                n2=t["n2"],
                spec=TraceSpec(
                    length_m=spec["length_m"],
                    width_m=spec["width_m"],
                    copper_oz=spec.get("copper_oz", 1.0),
                ),
            )
        )

    for l in data.get("ldos", []) or []:
        net.ldos.append(LDO(**l))

    for l in data.get("loads_cc", []) or []:
        net.loads_cc.append(ConstantCurrentLoad(**l))
    for l in data.get("loads_cp", []) or []:
        net.loads_cp.append(ConstantPowerLoad(**l))

    for vc in data.get("voltage_constraints", []) or []:
        net.voltage_constraints.append(VoltageConstraint(**vc))

    return net


def netlist_to_json(netlist: CircuitNetlist, *, indent: int = 2) -> str:
    return json.dumps(netlist_to_dict(netlist), indent=indent, sort_keys=True)


def netlist_from_json(text: str) -> CircuitNetlist:
    return netlist_from_dict(json.loads(text))

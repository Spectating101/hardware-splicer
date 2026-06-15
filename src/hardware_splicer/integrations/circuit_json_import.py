"""Import tscircuit circuit-json subset → CircuitNetlist."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from ..netlist.ir import CircuitNetlist, ComponentInstance, Net, PinRef


def circuit_json_to_netlist(
    docs: Sequence[Mapping[str, Any]],
    *,
    source: str = "circuit_json",
) -> CircuitNetlist:
    """Parse minimal circuit-json export back into netlist IR."""
    components: List[ComponentInstance] = []
    source_to_ref: Dict[str, str] = {}

    for doc in docs:
        if doc.get("type") != "source_component":
            continue
        sid = str(doc.get("source_component_id") or "")
        ref = str(doc.get("name") or sid or f"U{len(components) + 1}")
        source_to_ref[sid] = ref
        components.append(
            ComponentInstance(
                ref=ref,
                value=ref,
                footprint=str(doc.get("footprint") or ref),
                module_id=str(doc.get("module_id") or ref),
            )
        )

    net_pins: Dict[str, List[PinRef]] = {}
    for doc in docs:
        if doc.get("type") != "schematic_trace":
            continue
        net_name = str(doc.get("source_net_id") or "NET")
        ports = list(doc.get("connected_source_port_ids") or [])
        for port in ports:
            if "." not in str(port):
                continue
            ref, pin = str(port).split(".", 1)
            net_pins.setdefault(net_name, [])
            pref = PinRef(component_ref=ref, pin=pin)
            if pref not in net_pins[net_name]:
                net_pins[net_name].append(pref)

    nets = [Net(name=name, pins=pins) for name, pins in sorted(net_pins.items()) if len(pins) >= 2]
    return CircuitNetlist(source=source, components=components, nets=nets)

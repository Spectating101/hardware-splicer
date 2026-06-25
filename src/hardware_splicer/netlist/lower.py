"""Lower module build graphs to netlists and rebuild graphs from netlists."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from ..pcb.module_registry import find_module, find_pin
from .ir import CircuitNetlist, ComponentInstance, Net, PinRef

BuildGraph = Dict[str, Any]

_GND_PIN_IDS = frozenset(
    {"GND", "GND1", "GND_MOTOR", "GND_LOGIC", "IN-", "OUT-", "VIN-", "BAT-"}
)
_POWER_POS_PIN_IDS = frozenset(
    {"5V", "V+", "VBUS", "VOUT", "OUT+", "VIN", "VCC", "HV", "LV", "VMOT", "VSYS", "BAT+"}
)


def _pin_role_name(module_id: str, pin_id: str) -> Optional[str]:
    spec = find_module(module_id) if module_id else None
    pin = find_pin(spec, pin_id) if spec else None
    role = str((pin or {}).get("role") or "").lower()
    pid = pin_id.upper()
    if role == "gnd" or pid in _GND_PIN_IDS:
        return "GND"
    if role in {"i2c_sda", "sda"} or pid == "SDA":
        return "SDA"
    if role in {"i2c_scl", "scl"} or pid == "SCL":
        return "SCL"
    if role in {"uart_tx", "tx"} or pid in {"TX", "U0T"}:
        return "TX"
    if role in {"uart_rx", "rx"} or pid in {"RX", "U0R"}:
        return "RX"
    if pid in {"DATA", "SIG", "TRIG", "ECHO", "A0", "D0"}:
        return pid
    if pid in {"5V", "V+", "VBUS"} or (role == "power_out" and "3" not in pid):
        return "+5V"
    if pid in {"3V3", "3.3V"} or role == "power_3v3":
        return "+3V3"
    if pid.startswith("GPIO") or pid.startswith("D") or pid.startswith("GP"):
        return pin_id
    return None


def _infer_net_name(
    pins: List[PinRef],
    components_by_ref: Mapping[str, ComponentInstance],
) -> Optional[str]:
    labels: List[str] = []
    for pin_ref in pins:
        comp = components_by_ref.get(pin_ref.component_ref)
        module_id = str(comp.module_id or "") if comp else ""
        label = _pin_role_name(module_id, pin_ref.pin)
        if label:
            labels.append(label)
    if not labels:
        return None
    if all(label == "GND" for label in labels):
        return "GND"
    if all(label == "+5V" for label in labels):
        return "+5V"
    if all(label == "+3V3" for label in labels):
        return "+3V3"
    if all(label == "SDA" for label in labels):
        return "SDA"
    if all(label == "SCL" for label in labels):
        return "SCL"
    signal_labels = [label for label in labels if label not in {"GND", "+5V", "+3V3"}]
    if "DATA" in signal_labels and any(label.startswith("GPIO") for label in signal_labels):
        return "DATA"
    if len(signal_labels) == 1:
        return signal_labels[0]
    if len(set(labels)) == 1:
        return labels[0]
    return None


def _unique_net_name(base: str, used: Set[str]) -> str:
    if base not in used:
        used.add(base)
        return base
    index = 2
    while f"{base}_{index}" in used:
        index += 1
    name = f"{base}_{index}"
    used.add(name)
    return name


def _union_find_parent(parent: Dict[str, str], key: str) -> str:
    while parent[key] != key:
        parent[key] = parent[parent[key]]
        key = parent[key]
    return key


def _union(parent: Dict[str, str], a: str, b: str) -> None:
    ra, rb = _union_find_parent(parent, a), _union_find_parent(parent, b)
    if ra != rb:
        parent[rb] = ra


def build_graph_to_netlist(graph: Mapping[str, Any], *, source: str = "build_graph") -> CircuitNetlist:
    """Deterministic lowering: each graph node → component; wires → nets (union-find)."""
    nodes = list(graph.get("nodes") or [])
    wires = list(graph.get("wires") or [])
    node_by_id = {str(n.get("id")): n for n in nodes if n.get("id")}

    components: List[ComponentInstance] = []
    ref_by_node: Dict[str, str] = {}
    used_refs: Set[str] = set()
    for index, node in enumerate(nodes):
        node_id = str(node.get("id") or f"n{index + 1}")
        module_id = str(node.get("moduleId") or "")
        spec = find_module(module_id) if module_id else None
        ref = _unique_component_ref(str(node.get("ref") or f"U{index + 1}"), used_refs)
        ref_by_node[node_id] = ref
        components.append(
            ComponentInstance(
                ref=ref,
                value=str((spec or {}).get("label") or node.get("value") or module_id),
                footprint=str((spec or {}).get("footprint") or node.get("footprint") or module_id),
                module_id=module_id or None,
                metadata={
                    "graph_node_id": node_id,
                    **(
                        {"support_component_id": node.get("supportComponentId")}
                        if node.get("supportComponentId")
                        else {}
                    ),
                    **({"operator_id": node.get("operatorId")} if node.get("operatorId") else {}),
                    **({"synthetic": True} if node.get("synthetic") else {}),
                },
            )
        )

    parent: Dict[str, str] = {}
    pin_keys: List[Tuple[str, str, str]] = []
    for wire in wires:
        from_ep = wire.get("from") or {}
        to_ep = wire.get("to") or {}
        from_node = str(from_ep.get("nodeId") or "")
        to_node = str(to_ep.get("nodeId") or "")
        from_pin = str(from_ep.get("pinId") or "")
        to_pin = str(to_ep.get("pinId") or "")
        if not from_node or not to_node or not from_pin or not to_pin:
            continue
        from_ref = ref_by_node.get(from_node)
        to_ref = ref_by_node.get(to_node)
        if not from_ref or not to_ref:
            continue
        a = f"{from_ref}.{from_pin}"
        b = f"{to_ref}.{to_pin}"
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        pin_keys.append((a, from_ref, from_pin))
        pin_keys.append((b, to_ref, to_pin))
        _union(parent, a, b)

    groups: Dict[str, List[PinRef]] = {}
    seen_pin: Set[str] = set()
    for key, ref, pin in pin_keys:
        if key in seen_pin:
            continue
        seen_pin.add(key)
        root = _union_find_parent(parent, key)
        groups.setdefault(root, []).append(PinRef(component_ref=ref, pin=pin))

    nets: List[Net] = []
    components_by_ref = {comp.ref: comp for comp in components}
    used_names: Set[str] = set()
    for index, (_root, pins) in enumerate(sorted(groups.items(), key=lambda row: row[0]), start=1):
        unique: List[PinRef] = []
        seen: Set[str] = set()
        for pin_ref in pins:
            k = pin_ref.key()
            if k in seen:
                continue
            seen.add(k)
            unique.append(pin_ref)
        inferred = _infer_net_name(unique, components_by_ref) if len(unique) >= 2 else None
        if len(unique) >= 2:
            net_name = _unique_net_name(inferred or f"N{index}", used_names)
            nets.append(Net(name=net_name, pins=unique))
        elif len(unique) == 1:
            nets.append(Net(name=f"N{index}_singleton", pins=unique))

    return CircuitNetlist(
        source=source,
        components=components,
        nets=nets,
        metadata={
            "node_count": len(nodes),
            "wire_count": len(wires),
            **(
                {"terminal_semantics": dict(graph.get("terminal_semantics") or {})}
                if isinstance(graph.get("terminal_semantics"), Mapping)
                else {}
            ),
            **(
                {"topology_lowering": dict(graph.get("topology_lowering") or {})}
                if isinstance(graph.get("topology_lowering"), Mapping)
                else {}
            ),
            **(
                {"support_components": [dict(row) for row in graph.get("support_components") or [] if isinstance(row, Mapping)]}
                if isinstance(graph.get("support_components"), list)
                else {}
            ),
            **(
                {"topology_nets": [dict(row) for row in graph.get("topology_nets") or [] if isinstance(row, Mapping)]}
                if isinstance(graph.get("topology_nets"), list)
                else {}
            ),
            **(
                {"physical_support_lowering": dict(graph.get("physical_support_lowering") or {})}
                if isinstance(graph.get("physical_support_lowering"), Mapping)
                else {}
            ),
        },
    )


def netlist_to_build_graph(netlist: CircuitNetlist) -> BuildGraph:
    """Rebuild a module build graph from a netlist (module_id or footprint-based)."""
    ref_to_node: Dict[str, str] = {}
    nodes: List[Dict[str, Any]] = []
    pins_by_ref: Dict[str, List[str]] = {}
    for net in netlist.nets:
        for pin in net.pins:
            pins_by_ref.setdefault(pin.component_ref, [])
            if pin.pin not in pins_by_ref[pin.component_ref]:
                pins_by_ref[pin.component_ref].append(pin.pin)

    for index, comp in enumerate(netlist.components):
        module_id = comp.module_id or comp.value or comp.ref
        node_id = str(comp.metadata.get("graph_node_id") or f"n{index + 1}")
        ref_to_node[comp.ref] = node_id
        nodes.append(
            {
                "id": node_id,
                "moduleId": module_id,
                "ref": comp.ref,
                "value": comp.value,
                "footprint": comp.footprint,
                "pinIds": pins_by_ref.get(comp.ref) or [],
                **(
                    {"supportComponentId": comp.metadata.get("support_component_id")}
                    if comp.metadata.get("support_component_id")
                    else {}
                ),
                **({"operatorId": comp.metadata.get("operator_id")} if comp.metadata.get("operator_id") else {}),
                **({"synthetic": True} if comp.metadata.get("synthetic") else {}),
            }
        )

    wires: List[Dict[str, Any]] = []
    wire_index = 0
    connected: Set[Tuple[str, str, str, str]] = set()
    for net in netlist.nets:
        pins = net.pins
        if len(pins) < 2:
            continue
        hub = pins[0]
        hub_node = ref_to_node.get(hub.component_ref)
        if not hub_node:
            continue
        for other in pins[1:]:
            other_node = ref_to_node.get(other.component_ref)
            if not other_node:
                continue
            key = tuple(sorted([(hub_node, hub.pin), (other_node, other.pin)]))
            flat = (key[0][0], key[0][1], key[1][0], key[1][1])
            if flat in connected:
                continue
            connected.add(flat)
            wire_index += 1
            wires.append(
                {
                    "id": f"w{wire_index}",
                    "from": {"nodeId": hub_node, "pinId": hub.pin},
                    "to": {"nodeId": other_node, "pinId": other.pin},
                }
            )

    graph: BuildGraph = {"nodes": nodes, "wires": wires}
    if isinstance(netlist.metadata.get("terminal_semantics"), Mapping):
        graph["terminal_semantics"] = dict(netlist.metadata.get("terminal_semantics") or {})
    if isinstance(netlist.metadata.get("topology_lowering"), Mapping):
        graph["topology_lowering"] = dict(netlist.metadata.get("topology_lowering") or {})
    if isinstance(netlist.metadata.get("support_components"), list):
        graph["support_components"] = [
            dict(row) for row in netlist.metadata.get("support_components") or [] if isinstance(row, Mapping)
        ]
    if isinstance(netlist.metadata.get("topology_nets"), list):
        graph["topology_nets"] = [
            dict(row) for row in netlist.metadata.get("topology_nets") or [] if isinstance(row, Mapping)
        ]
    if isinstance(netlist.metadata.get("physical_support_lowering"), Mapping):
        graph["physical_support_lowering"] = dict(netlist.metadata.get("physical_support_lowering") or {})
    return graph


def _unique_component_ref(candidate: str, used: Set[str]) -> str:
    ref = candidate.strip() or "U"
    if ref not in used:
        used.add(ref)
        return ref
    prefix = ref.rstrip("0123456789") or ref
    index = 2
    while f"{prefix}{index}" in used:
        index += 1
    unique = f"{prefix}{index}"
    used.add(unique)
    return unique

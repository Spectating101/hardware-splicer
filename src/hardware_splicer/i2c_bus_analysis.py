"""Find I2C devices that would answer at the same address, and say how to fix it.

Runs inside the build safety analysis, so it checks every design the same way, whether HS composed
it or an agent submitted it. A finding is machine-readable: a code, the nodes involved, and a list
of repairs, each an exact wire patch. HS verifies the result of any repair by running this again.

Authority: HS only trusts what the wiring shows. A second bus is visible in the wires, so HS can
verify it. An address strap is a physical act HS cannot see, so a declared strap never clears a
finding: it becomes a standing warning for a person to carry out.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from .i2c_addresses import i2c_addresses_for
from .pcb.module_registry import find_module

Graph = Mapping[str, Any]
Finding = Dict[str, Any]
Bus = Tuple[str, str, str]  # (controller node, controller SDA pin, controller SCL pin)

# Pins offered for a second bus, in order. The ESP32 boot-strapping pins (0, 2, 5, 12, 15) and the
# input-only pins (34-39) are left out: the first can stop the board starting, the second cannot drive SDA.
_SECOND_BUS_PINS = ("GPIO18", "GPIO23", "GPIO4", "GPIO16", "GPIO17", "GPIO19", "GPIO25", "GPIO26", "GPIO27", "GPIO32", "GPIO33")


def i2c_findings(graph: Graph) -> List[Finding]:
    nodes = {str(n.get("id")): n for n in graph.get("nodes") or []}
    specs = {nid: find_module(str(n.get("moduleId") or "")) for nid, n in nodes.items()}
    controllers = {nid for nid, spec in specs.items() if spec and spec.get("category") == "mcu"}
    wires = list(graph.get("wires") or [])
    buses = _buses(nodes, specs, controllers, wires)
    findings: List[Finding] = []

    for node_id, node in nodes.items():
        declared = node.get("i2c_address")
        info = i2c_addresses_for(str(node.get("moduleId") or ""))
        if declared is not None and info and str(declared) not in info["addresses"]:
            findings.append(_not_possible(node_id, specs[node_id], str(declared), info))

    for bus, members in buses.items():
        if len(members) < 2:
            continue
        resolved = {nid: _effective(nodes[nid]) for nid in members}
        unknown = [nid for nid, addr in resolved.items() if addr is None]
        if unknown:
            findings.append(_unknown(bus, members, unknown, specs))
        by_address: Dict[str, List[str]] = {}
        for nid, addr in resolved.items():
            if addr is not None:
                by_address.setdefault(addr, []).append(nid)
        for address, group in by_address.items():
            if len(group) > 1:
                findings.append(_clash(bus, address, group, nodes, specs, wires, buses, resolved))
        for nid in members:
            info = i2c_addresses_for(str(nodes[nid].get("moduleId") or ""))
            declared = nodes[nid].get("i2c_address")
            if declared is not None and info and str(declared) in info["addresses"] and str(declared) != info["default"]:
                findings.append(_declared_strap(nid, specs[nid], str(declared), info))
    return findings


def _effective(node: Mapping[str, Any]) -> Optional[str]:
    info = i2c_addresses_for(str(node.get("moduleId") or ""))
    if info is None:
        return None
    declared = node.get("i2c_address")
    return str(declared) if declared is not None and str(declared) in info["addresses"] else info["default"]


def _device_pins(spec: Mapping[str, Any]) -> Optional[Tuple[str, str]]:
    sda = next((p["id"] for p in spec.get("pins") or [] if p.get("role") == "i2c_sda"), None)
    scl = next((p["id"] for p in spec.get("pins") or [] if p.get("role") == "i2c_scl"), None)
    return (sda, scl) if sda and scl else None


def _peers(wires: List[Mapping[str, Any]], node_id: str, pin_id: str) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    for w in wires:
        a, b = w.get("from") or {}, w.get("to") or {}
        if a.get("nodeId") == node_id and a.get("pinId") == pin_id:
            out.append((str(b.get("nodeId")), str(b.get("pinId")), str(w.get("id"))))
        elif b.get("nodeId") == node_id and b.get("pinId") == pin_id:
            out.append((str(a.get("nodeId")), str(a.get("pinId")), str(w.get("id"))))
    return out


def _buses(nodes, specs, controllers, wires) -> Dict[Bus, List[str]]:
    buses: Dict[Bus, List[str]] = {}
    for nid in nodes:
        spec = specs.get(nid)
        pins = _device_pins(spec) if spec and nid not in controllers else None
        if not pins:
            continue
        sda_peers = [p for p in _peers(wires, nid, pins[0]) if p[0] in controllers]
        scl_peers = [p for p in _peers(wires, nid, pins[1]) if p[0] in controllers]
        if len(sda_peers) == 1 and len(scl_peers) == 1 and sda_peers[0][0] == scl_peers[0][0]:
            buses.setdefault((sda_peers[0][0], sda_peers[0][1], scl_peers[0][1]), []).append(nid)
    return buses


def _label(spec: Optional[Mapping[str, Any]], node_id: str) -> str:
    return f"{(spec or {}).get('label') or (spec or {}).get('id') or 'device'} ({node_id})"


def _unknown(bus: Bus, members: List[str], unknown: List[str], specs) -> Finding:
    names = ", ".join(_label(specs[n], n) for n in unknown)
    return {
        "id": f"i2c-unknown-{bus[0]}-{bus[1]}-{bus[2]}",
        "level": "info",
        "code": "i2c_address_unknown",
        "message": (
            f"HS cannot tell whether the {len(members)} devices on one I2C bus have different addresses: "
            f"no sourced address for {names}. Check each address in its datasheet."
        ),
        "nodeId": unknown[0],
        "nodes": list(members),
        "bus": {"controller": bus[0], "sda": bus[1], "scl": bus[2]},
    }


def _not_possible(node_id: str, spec, declared: str, info: Mapping[str, Any]) -> Finding:
    options = " or ".join(sorted(info["addresses"]))
    return {
        "id": f"{node_id}-i2c-address-not-possible",
        "level": "error",
        "code": "i2c_address_not_possible",
        "message": f"{_label(spec, node_id)} is declared at {declared}, but this chip can only answer at {options}.",
        "nodeId": node_id,
        "address": declared,
        "address_basis": info["basis"],
    }


def _declared_strap(node_id: str, spec, declared: str, info: Mapping[str, Any]) -> Finding:
    return {
        "id": f"{node_id}-i2c-declared-strap",
        "level": "warn",
        "code": "i2c_address_declared_strap",
        "message": (
            f"{_label(spec, node_id)} is declared at {declared}, not its default {info['default']}. "
            "That only works if a person sets the address pin on the board, which HS cannot see."
        ),
        "nodeId": node_id,
        "address": declared,
        "address_basis": info["basis"],
        "requires_person": True,
    }


def _clash(bus: Bus, address: str, group: List[str], nodes, specs, wires, buses, resolved) -> Finding:
    labels = ", ".join(_label(specs[n], n) for n in group)
    moved = group[1]
    repairs = _repairs(bus, address, group, moved, nodes, specs, wires, buses, resolved)
    message = (
        f"{len(group)} devices on one I2C bus would all answer at {address}: {labels}. "
        "They cannot both work, because the controller cannot tell them apart."
    )
    if not repairs:
        message += " There is no automatic repair for this design."
    info = i2c_addresses_for(str(nodes[group[0]].get("moduleId") or "")) or {}
    return {
        "id": f"i2c-clash-{bus[0]}-{bus[1]}-{bus[2]}-{address}",
        "level": "error",
        "code": "i2c_address_clash",
        "message": message,
        "nodeId": group[0],
        "nodes": list(group),
        "address": address,
        "address_basis": info.get("basis", ""),
        "bus": {"controller": bus[0], "sda": bus[1], "scl": bus[2]},
        "repairs": repairs,
    }


def _repairs(bus, address, group, moved, nodes, specs, wires, buses, resolved) -> List[Dict[str, Any]]:
    repairs: List[Dict[str, Any]] = []
    second = _second_bus_repair(bus, moved, nodes, specs, wires, buses)
    if second:
        repairs.append(second)
    strap = _strap_repair(moved, nodes, specs, resolved, buses.get(bus, []))
    if strap:
        repairs.append(strap)
    return repairs


def _second_bus_repair(bus: Bus, moved: str, nodes, specs, wires, buses) -> Optional[Dict[str, Any]]:
    controller = bus[0]
    spec = specs.get(controller) or {}
    if not str(spec.get("id") or "").startswith("esp32"):
        return None  # only the ESP32 has two I2C controllers on freely chosen pins
    if len({b for b in buses if b[0] == controller}) >= 2:
        return None  # both controllers already carry a bus
    used = {p for w in wires for end in (w.get("from") or {}, w.get("to") or {}) if end.get("nodeId") == controller for p in [end.get("pinId")]}
    present = {p["id"] for p in spec.get("pins") or []}
    free = [p for p in _SECOND_BUS_PINS if p in present and p not in used][:2]
    pins = _device_pins(specs[moved])
    if len(free) < 2 or not pins:
        return None
    sda_pin, scl_pin = free
    remove = [w[2] for pin in pins for w in _peers(wires, moved, pin) if w[0] == controller]
    add = [
        {"id": f"i2c2-sda-{moved}", "from": {"nodeId": moved, "pinId": pins[0]}, "to": {"nodeId": controller, "pinId": sda_pin}},
        {"id": f"i2c2-scl-{moved}", "from": {"nodeId": moved, "pinId": pins[1]}, "to": {"nodeId": controller, "pinId": scl_pin}},
    ]
    number = lambda pin: "".join(c for c in pin if c.isdigit())  # noqa: E731
    return {
        "id": f"second_i2c_bus:{moved}",
        "kind": "second_i2c_bus",
        "moves_node": moved,
        "summary": f"Move {_label(specs[moved], moved)} to a second I2C bus on {sda_pin} (SDA) and {scl_pin} (SCL).",
        "requires_person": False,
        "graph_patch": {"remove_wires": remove, "add_wires": add, "set_node_fields": {}},
        "firmware_effect": (
            f"Start the second bus with Wire1.begin({number(sda_pin)}, {number(scl_pin)}) and use Wire1 "
            f"for {_label(specs[moved], moved)}. The first bus stays on its default pins."
        ),
    }


def _strap_repair(moved: str, nodes, specs, resolved, members) -> Optional[Dict[str, Any]]:
    info = i2c_addresses_for(str(nodes[moved].get("moduleId") or ""))
    if not info or not info["selectable"]:
        return None
    taken = {addr for nid, addr in resolved.items() if nid != moved and addr}
    target = next((a for a in info["addresses"] if a not in taken and a != resolved.get(moved)), None)
    if not target:
        return None
    return {
        "id": f"strap_alternate_address:{moved}",
        "kind": "strap_alternate_address",
        "moves_node": moved,
        "to_address": target,
        "summary": f"Set {_label(specs[moved], moved)} to answer at {target} instead of {resolved.get(moved)}.",
        "requires_person": True,
        "physical_steps": [
            f"Set the address-select pin or jumper on {_label(specs[moved], moved)} so it answers at {target}.",
            "How this is done depends on your board: check its silkscreen or documentation. HS cannot see the strap.",
            f"Source for the two addresses: {info['basis']}",
        ],
        "graph_patch": {"remove_wires": [], "add_wires": [], "set_node_fields": {moved: {"i2c_address": target}}},
    }

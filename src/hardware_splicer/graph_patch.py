"""Apply a repair's wire patch to a build graph, refusing anything that is not a plain wiring change.

A patch is what HS offers in a finding's `repairs`. An agent may apply it as given or submit its own
edit; either way HS re-runs its checks on the resulting design. This function is deliberately narrow:
it can remove wires, add wires between pins that exist, and write an I2C address on a node. It cannot
change what a part is, add or remove parts, or touch any other field.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from .pcb.module_registry import find_module, find_pin

_SETTABLE_NODE_FIELDS = frozenset({"i2c_address"})


def apply_graph_patch(graph: Mapping[str, Any], patch: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a new graph with the patch applied; the input graph is never modified."""
    out = deepcopy(dict(graph))
    nodes = {str(n.get("id")): n for n in out.get("nodes") or []}
    wires = list(out.get("wires") or [])
    existing = {str(w.get("id")) for w in wires}

    for wire_id in patch.get("remove_wires") or []:
        if str(wire_id) not in existing:
            raise ValueError(f"patch removes a wire that does not exist: no wire {wire_id!r}")
    removed = {str(w) for w in patch.get("remove_wires") or []}
    wires = [w for w in wires if str(w.get("id")) not in removed]
    existing -= removed

    for wire in patch.get("add_wires") or []:
        wire_id = str(wire.get("id") or "")
        if not wire_id or wire_id in existing:
            raise ValueError(f"patch adds a wire without a fresh id: {wire_id!r}")
        for end_name in ("from", "to"):
            end = wire.get(end_name) or {}
            node = nodes.get(str(end.get("nodeId")))
            if node is None:
                raise ValueError(f"patch wire {wire_id!r} uses no node {end.get('nodeId')!r}")
            spec = find_module(str(node.get("moduleId") or ""))
            if not spec or not find_pin(spec, str(end.get("pinId"))):
                raise ValueError(f"patch wire {wire_id!r} uses unknown pin {end.get('pinId')!r} on {end.get('nodeId')!r}")
        existing.add(wire_id)
        wires.append(deepcopy(dict(wire)))

    for node_id, fields in (patch.get("set_node_fields") or {}).items():
        if str(node_id) not in nodes:
            raise ValueError(f"patch sets fields on no node {node_id!r}")
        extra = set(fields) - _SETTABLE_NODE_FIELDS
        if extra:
            raise ValueError(f"a patch may set only i2c_address on a node, not {sorted(extra)}")
        nodes[str(node_id)].update({k: str(v) for k, v in fields.items()})

    out["wires"] = wires
    return out


def auto_repair_i2c(graph: Mapping[str, Any], *, max_steps: int = 4) -> tuple[Dict[str, Any], list[str]]:
    """Apply the I2C repairs that need no person, one at a time, until none is left.

    Used when HS composes a design itself, with no agent to choose. A repair that needs a person
    (an address strap) is never applied here, and a clash with no automatic repair is left as the
    error it is. Returns the design and a plain-language note for each repair made.
    """
    from .i2c_bus_analysis import i2c_findings

    current: Dict[str, Any] = deepcopy(dict(graph))
    notes: list[str] = []
    for _ in range(max_steps):
        chosen = None
        for finding in i2c_findings(current):
            if finding.get("code") != "i2c_address_clash":
                continue
            repair = next((r for r in finding.get("repairs") or [] if not r.get("requires_person")), None)
            if repair:
                chosen = (finding, repair)
                break
        if chosen is None:
            break
        finding, repair = chosen
        current = apply_graph_patch(current, repair["graph_patch"])
        notes.append(
            f"HS moved the later device: {repair.get('applied_summary', repair['summary'])} "
            f"Both would otherwise answer at {finding['address']}. {repair['firmware_effect']}"
        )
    return current, notes

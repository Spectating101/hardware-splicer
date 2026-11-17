"""Netlist-to-PCB connectivity parity.

KiCad's own ``--schematic-parity`` cannot judge generated boards (reference designators and
footprint ids are assigned independently of the schematic symbols), so this check compares the
connectivity itself: every net of the circuit netlist with two or more pins must appear on the
PCB as a net holding exactly the matching footprint pads, and the PCB must not join pads the
netlist keeps apart. Footprints are matched by their KiCad footprint id and pads by the pad's
position in the module pad table, which is how the PCB serializer numbers them.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Mapping, Tuple

from ..netlist.ir import CircuitNetlist
from .module_registry import find_module, resolve_module_footprint, resolve_module_pads

_FOOTPRINT_RE = re.compile(r'\(footprint "([^"]+)"')
_PAD_RE = re.compile(r'\(pad "([^"]+)"[^\n]*?\(net (\d+) "([^"]*)"\)\)')

Signature = Tuple[Tuple[str, str], ...]


def _netlist_signatures(netlist: CircuitNetlist) -> Counter:
    comps = {c.ref: c for c in netlist.components}
    signatures: Counter = Counter()
    for net in netlist.nets:
        members: List[Tuple[str, str]] = []
        for pin in net.pins:
            comp = comps.get(pin.component_ref)
            module_id = str(comp.module_id or "") if comp else ""
            spec = find_module(module_id) if module_id else None
            pads = resolve_module_pads(module_id, spec) if module_id else None
            footprint = resolve_module_footprint(module_id) if module_id else ""
            index = next((i for i, p in enumerate(pads or []) if p["pinId"] == pin.pin), None)
            members.append((footprint, str(index + 1) if index is not None else f"missing:{pin.pin}"))
        if len(members) >= 2:
            signatures[tuple(sorted(members))] += 1
    return signatures


def _pcb_signatures(pcb_text: str) -> Counter:
    nets: Dict[str, List[Tuple[str, str]]] = {}
    parts = re.split(r"(?=\n\s*\(footprint )", pcb_text)
    for part in parts:
        match = _FOOTPRINT_RE.search(part)
        if not match:
            continue
        footprint = match.group(1)
        for number, net_id, _name in _PAD_RE.findall(part):
            if net_id == "0":
                continue
            nets.setdefault(net_id, []).append((footprint, number))
    return Counter(tuple(sorted(pads)) for pads in nets.values() if len(pads) >= 2)


def netlist_pcb_parity(netlist: CircuitNetlist, pcb_text: str) -> Dict[str, Any]:
    """Return ``{"pass", "missing_on_pcb", "extra_on_pcb"}`` for nets of two or more pads."""

    expected = _netlist_signatures(netlist)
    actual = _pcb_signatures(pcb_text)
    missing = expected - actual
    extra = actual - expected
    return {
        "pass": not missing and not extra,
        "missing_on_pcb": [list(sig) for sig in missing.elements()],
        "extra_on_pcb": [list(sig) for sig in extra.elements()],
    }

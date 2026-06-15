"""Parse KiCad netlist (sexpr export) into CircuitNetlist."""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from .ir import CircuitNetlist, ComponentInstance, Net, PinRef


def _tokenize_sexpr(text: str) -> List[str]:
    text = text.replace("\n", " ")
    tokens: List[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "()":
            tokens.append(ch)
            i += 1
        elif ch in ('"', "'"):
            quote = ch
            i += 1
            start = i
            while i < len(text) and text[i] != quote:
                if text[i] == "\\":
                    i += 2
                    continue
                i += 1
            tokens.append(text[start:i])
            i += 1
        elif ch.isspace():
            i += 1
        else:
            start = i
            while i < len(text) and not text[i].isspace() and text[i] not in "()":
                i += 1
            tokens.append(text[start:i])
    return tokens


def _parse_sexpr(tokens: List[str], index: int = 0) -> Tuple[Any, int]:
    if index >= len(tokens):
        return None, index
    if tokens[index] != "(":
        return tokens[index], index + 1
    items: List[Any] = []
    i = index + 1
    while i < len(tokens) and tokens[i] != ")":
        value, i = _parse_sexpr(tokens, i)
        items.append(value)
    return items, i + 1


def _find_child(node: List[Any], name: str) -> Optional[List[Any]]:
    for item in node:
        if isinstance(item, list) and item and item[0] == name:
            return item
    return None


def _module_id_from_fields(fields: List[Any]) -> Optional[str]:
    for field in fields:
        if not isinstance(field, list) or len(field) < 3 or field[0] != "fields":
            continue
        for entry in field[1:]:
            if isinstance(entry, list) and len(entry) >= 3 and entry[1] == "module_id":
                return str(entry[2])
    return None


def parse_kicad_netlist(text: str) -> CircuitNetlist:
    """Parse KiCad `(export ...)` netlist into IR."""
    tokens = _tokenize_sexpr(text)
    tree, _ = _parse_sexpr(tokens, 0)
    if not isinstance(tree, list) or not tree or tree[0] != "export":
        raise ValueError("not a KiCad export netlist")

    components: List[ComponentInstance] = []
    comp_section = _find_child(tree, "components")
    if comp_section:
        for comp in comp_section[1:]:
            if not isinstance(comp, list) or not comp or comp[0] != "comp":
                continue
            ref = ""
            value = ""
            footprint = ""
            fields: List[Any] = []
            for item in comp[1:]:
                if not isinstance(item, list) or not item:
                    continue
                if item[0] == "ref" and len(item) > 1:
                    ref = str(item[1])
                elif item[0] == "value" and len(item) > 1:
                    value = str(item[1])
                elif item[0] == "footprint" and len(item) > 1:
                    footprint = str(item[1])
                elif item[0] == "fields":
                    fields.append(item)
            module_id = _module_id_from_fields(fields) or (value if re.match(r"^[a-z0-9_-]+$", value) else None)
            components.append(
                ComponentInstance(ref=ref, value=value, footprint=footprint, module_id=module_id)
            )

    nets: List[Net] = []
    nets_section = _find_child(tree, "nets")
    if nets_section:
        for net in nets_section[1:]:
            if not isinstance(net, list) or not net or net[0] != "net":
                continue
            code = str(net[1]) if len(net) > 1 else ""
            name = str(net[2]) if len(net) > 2 else code
            pins: List[PinRef] = []
            for node in net[3:]:
                if isinstance(node, list) and len(node) >= 3 and node[0] == "node":
                    pins.append(PinRef(component_ref=str(node[1]), pin=str(node[2])))
            nets.append(Net(name=name, pins=pins))

    return CircuitNetlist(source="kicad_netlist", components=components, nets=nets)

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


def _child_text(node: List[Any], key: str) -> str:
    """Extract standard nested KiCad s-expression child scalars."""
    child = _find_child(node, key)
    return str(child[1]) if child and len(child) > 1 else ""


def parse_kicad_netlist(text: str) -> CircuitNetlist:
    """Parse KiCad `(export ...)` netlist into IR."""
    tokens = _tokenize_sexpr(text)
    tree, _ = _parse_sexpr(tokens, 0)
    if not isinstance(tree, list) or not tree or tree[0] != "export":
        raise ValueError("not a KiCad export netlist")

    # KiCad records sheet instance paths on both design sheets and components.
    # A repeated channel may share its source schematic but have distinct
    # exported references and distinct sheet instance paths. Preserve this
    # provenance rather than merging symbols with identical library IDs.
    design = _find_child(tree, "design")
    sheets: List[dict[str, str]] = []
    for sheet in (design or [])[1:]:
        if isinstance(sheet, list) and sheet and sheet[0] == "sheet":
            sheets.append({
                "name": _child_text(sheet, "name"),
                "uuid_path": _child_text(sheet, "tstamps"),
                "source_filename": _child_text(_find_child(sheet, "title_block") or [], "source"),
            })

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
            instance = _find_child(comp, "sheetpath") or []
            # Actual KiCad 9 emits (sheetpath (names "/CH2/")
            # (tstamps "/uuid/")) plus (tstamps "symbol-uuid"...).
            # Do not use symbol-library names as instance identifiers.
            sheet_name = _child_text(instance, "names")
            sheet_uuids = _child_text(instance, "tstamps")
            symbol_uuids = _find_child(comp, "tstamps") or []
            metadata = {
                "kicad_sheet_name": sheet_name,
                "kicad_sheet_uuid_path": sheet_uuids,
                "kicad_symbol_tstamps": [str(x) for x in symbol_uuids[1:]],
            }
            components.append(
                ComponentInstance(ref=ref, value=value, footprint=footprint,
                                  module_id=module_id, metadata=metadata)
            )

    nets: List[Net] = []
    unnumbered_no_connect: List[dict[str, str]] = []
    nets_section = _find_child(tree, "nets")
    if nets_section:
        for net in nets_section[1:]:
            if not isinstance(net, list) or not net or net[0] != "net":
                continue
            # KiCad CLI uses (net (code "1") (name "GND")
            # (node (ref "U1") (pin "2")) ...). The old importer was
            # stringifying entire child arrays and silently importing ZERO
            # pins; read the nested fields rather than array positions.
            name = _child_text(net, "name") or _child_text(net, "code")
            # Keep compatibility with historical flattened net fixtures.
            if not name and len(net) > 2 and isinstance(net[2], str):
                name = str(net[2])
            pins: List[PinRef] = []
            for node in net[1:]:
                if not isinstance(node, list) or not node or node[0] != "node":
                    continue
                ref = _child_text(node, "ref") or (
                    str(node[1]) if len(node) > 2 and isinstance(node[1], str) else ""
                )
                pin = _child_text(node, "pin") or (
                    str(node[2]) if len(node) > 2 and isinstance(node[2], str) else ""
                )
                if not ref or not pin:
                    pin_field = _find_child(node, "pin")
                    pintype = _child_text(node, "pintype")
                    # Official KiCad flat-hierarchy demos include mounting
                    # holes with (pin "") (pinfunction "1")
                    # (pintype "passive+no_connect"). This is an explicitly
                    # *unnumbered* NC terminal, not a fabricated REF.PIN.
                    # Preserve the original source evidence separately.
                    if (
                        ref and pin_field is not None and len(pin_field) > 1
                        and pin_field[1] == "" and "no_connect" in pintype
                        and name.startswith("unconnected-")
                        and sum(isinstance(n, list) and n and n[0] == "node"
                                for n in net[1:]) == 1
                    ):
                        unnumbered_no_connect.append({
                            "net": name, "ref": ref,
                            "pin": "", "pinfunction": _child_text(node, "pinfunction"),
                            "pintype": pintype,
                        })
                        continue
                    raise ValueError(f"Malformed KiCad net node on {name!r}: {node!r}")
                pins.append(PinRef(component_ref=ref, pin=pin))
            if not name:
                raise ValueError("KiCad net missing code and name")
            nets.append(Net(name=name, pins=pins))

    return CircuitNetlist(
        source="kicad_netlist", components=components, nets=nets,
        metadata={"kicad_export": {
            "sheets": sheets,
            "unnumbered_no_connect_terminals": unnumbered_no_connect,
        }},
    )

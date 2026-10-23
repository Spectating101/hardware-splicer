"""Recover a source-connected Circuit JSON interchange from an actual KiCad export.

The third-party kicad-to-circuit-json converter currently emits geometric
schematic_trace records with no source_trace port connections. Geometry is NOT
a wire/net graph. An explicitly supplied KiCad Eeschema netlist export is the
only connectivity authority in this bridge.

This is a *separate* normalized source topology, NOT an assertion that all
external converter components/geometry map to those KiCad source refs.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping, Sequence

from ..netlist.import_kicad import parse_kicad_netlist
from .circuit_json_import import circuit_json_to_netlist


def _pin_signature(nets: Any) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for net in nets:
        if not net.name or net.name in result:
            raise ValueError("Missing/duplicate KiCad source net name")
        pins = [f"{p.component_ref}.{p.pin}" for p in net.pins]
        if len(pins) != len(set(pins)):
            raise ValueError(f"Duplicate REF.PIN on source net {net.name}")
        result[net.name] = sorted(pins)
    return result


def recover_connected_source_circuit_json(
    kicad_netlist_text: str,
    *,
    external_converter_docs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return reproducible connected Circuit JSON plus strict comparison receipt.

    Does not use the untrusted converter to invent circuit topology. Requires
    KiCad exported `(export ... (components ...) (nets ...))` structure.
    """
    source = parse_kicad_netlist(kicad_netlist_text)
    if not source.components or not source.nets:
        raise ValueError("KiCad exported netlist requires components and nets")
    refs = [c.ref for c in source.components]
    if not all(refs) or len(set(refs)) != len(refs):
        raise ValueError("KiCad source component identities missing or duplicated")
    net_pins = _pin_signature(source.nets)
    mapped: dict[str, str] = {}
    for name, pins in net_pins.items():
        for pin in pins:
            comp = pin.rsplit(".", 1)[0]
            if comp not in refs:
                raise ValueError(f"Unknown KiCad source component on net {name}: {pin}")
            if pin in mapped:
                raise ValueError(f"REF.PIN occurs in multiple nets: {pin}")
            mapped[pin] = name

    # The importer intentionally drops single-pin nets, since they do not
    # establish an actual electrical connection between two endpoints.
    # Keep them in a separate source-only manifest; never fabricate another pin.
    connected_nets = {name: pins for name, pins in net_pins.items() if len(pins) >= 2}
    single_pin = {name: pins for name, pins in net_pins.items() if len(pins) == 1}
    empty_nets = [name for name, pins in net_pins.items() if not pins]
    # Real KiCad can export an unnumbered mounting-hole no-connect terminal
    # as (pin "") on a 1-node unconnected net. The parser records its raw
    # identity instead of assigning a fabricated pin identifier. No other
    # empty or electrically connected net may disappear.
    special = list(
        source.metadata.get("kicad_export", {}).get("unnumbered_no_connect_terminals", [])
    )
    special_by_net = {x["net"]: x for x in special}
    if len(special_by_net) != len(special):
        raise ValueError("Duplicate unnumbered source terminal references")
    if any(x["ref"] not in refs for x in special):
        raise ValueError("Unnumbered disconnected source contact has no component reference")
    if any(name not in empty_nets for name in special_by_net):
        raise ValueError("Unnumbered contact unexpectedly has mapped electrical pins")
    unnumbered_only = {name: special_by_net[name] for name in empty_nets
                       if name in special_by_net}
    unsupported_empty = sorted(set(empty_nets) - set(unnumbered_only))
    if unsupported_empty:
        raise ValueError(f"KiCad source nets missing any pins: {unsupported_empty[:5]}")
    if not connected_nets:
        raise ValueError("KiCad source export provides no connected electrical nets")

    docs: list[dict[str, Any]] = []
    port_ids: dict[str, str] = {}
    source_instances = {}
    for comp in source.components:
        hierarchy_path = comp.metadata.get("kicad_sheet_name") or ""
        if hierarchy_path:
            source_instances[comp.ref] = {
                "sheet_name": hierarchy_path,
                "sheet_uuid_path": comp.metadata.get("kicad_sheet_uuid_path") or "",
                "symbol_tstamps": comp.metadata.get("kicad_symbol_tstamps") or [],
            }
        entry = {
            "type": "source_component",
            "source_component_id": f"kicad_component_{comp.ref}",
            "name": comp.ref,
            "ftype": "simple_chip",
            "display_value": comp.value or comp.ref,
            "footprint": comp.footprint,
        }
        # Circuit JSON importer supports subcircuit_id and preserves it in
        # ComponentInstance.metadata; do not lose original KiCad instances.
        if hierarchy_path:
            entry["subcircuit_id"] = hierarchy_path
        docs.append(entry)
    for index, refpin in enumerate(sorted(mapped)):
        ref, pin = refpin.rsplit(".", 1)
        # Use stable ordinal IDs, not ambiguous ref + "_" + pin strings:
        # ("U_1", "2") and ("U", "1_2") must never collapse to one ID.
        pid = f"kicad_port_{index}"
        port_ids[refpin] = pid
        docs.append({
            "type": "source_port",
            "source_port_id": pid,
            "source_component_id": f"kicad_component_{ref}",
            "name": pin,
            "pin_number": pin,
        })
    for index, (name, pins) in enumerate(sorted(net_pins.items())):
        sid = f"kicad_net_{index}"
        docs.append({"type": "source_net", "source_net_id": sid, "name": name})
        if len(pins) >= 2:
            docs.append({
                "type": "source_trace",
                "source_trace_id": f"kicad_trace_{index}",
                "connected_source_net_ids": [sid],
                "connected_source_port_ids": [port_ids[refpin] for refpin in pins],
            })

    # Exercise the actual HS source-port/trace/net interchange importer.
    imported = circuit_json_to_netlist(docs, source="kicad_export_connected_source")
    resulting = _pin_signature(imported.nets)
    if resulting != connected_nets:
        diff = {
            "missing_or_changed": sorted(
                name for name, pins in connected_nets.items() if resulting.get(name) != pins
            ),
            "unexpected": sorted(name for name in resulting if name not in connected_nets),
        }
        raise ValueError(f"Source connectivity did not survive Circuit JSON reimport: {diff}")
    if len(imported.components) != len(source.components):
        raise ValueError("Component identity/count changed on Circuit JSON reimport")
    imported_components = {x.ref: x for x in imported.components}
    if set(imported_components) != set(refs):
        raise ValueError("Component reference identities changed on Circuit JSON reimport")
    for ref, item in source_instances.items():
        mapped = imported_components[ref].metadata.get("subcircuit_id") or ""
        if mapped != item["sheet_name"]:
            raise ValueError(f"Component {ref} lost its KiCad sheet-instance scope")
    converter = list(external_converter_docs or [])
    converter_types = Counter(str(doc.get("type")) for doc in converter)
    upstream_names = [
        str(doc.get("name") or "")
        for doc in converter if doc.get("type") == "source_net"
    ]
    # Root-sheet KiCad names carry a leading "/" while the converter may
    # omit it. Normalize only that root-sheet prefix for a *name audit*.
    # This does NOT associate converter source_port IDs with KiCad pins.
    root_source_names = [name[1:] if name.startswith("/") else name
                         for name in connected_nets]
    unique_names = (
        len(set(root_source_names)) == len(root_source_names)
        and len(set(upstream_names)) == len(upstream_names)
    )
    converter_net_name_audit = (
        sorted(upstream_names) == sorted(root_source_names) if converter and unique_names
        else None
    )
    extra_power_flags = sum(
        doc.get("type") == "source_component"
        and str(doc.get("name") or "") == "power:PWR_FLAG"
        for doc in converter
    )
    # Critically, converter comparison is descriptive; its 40 components do
    # not get merged with 36 KiCad source components without a validated
    # reference/designator mapping.
    verdict = {
        "authority": "kicad_export_netlist_only",
        "source_sha256": hashlib.sha256(kicad_netlist_text.encode("utf-8")).hexdigest(),
        "components": len(source.components),
        "source_nets": len(source.nets),
        "source_pin_memberships": sum(len(pins) for pins in net_pins.values()),
        "connected_multi_pin_nets": len(connected_nets),
        "source_single_pin_nets": single_pin,
        "source_unnumbered_no_connect_nets": unnumbered_only,
        "hierarchy": {
            "sheet_count": len(source.metadata.get("kicad_export", {}).get("sheets", [])),
            "sheets": source.metadata.get("kicad_export", {}).get("sheets", []),
            "component_instances_with_sheet_path": len(source_instances),
            "component_instance_provenance": source_instances,
            "source_sheet_scopes_preserved": all(
                imported_components[ref].metadata.get("subcircuit_id") == info["sheet_name"]
                for ref, info in source_instances.items()
            ),
        },
        "imported_components": len(imported.components),
        "imported_multi_pin_nets": len(imported.nets),
        "imported_multi_pin_memberships": sum(len(n.pins) for n in imported.nets),
        "topology_exact_multi_pin_match": resulting == connected_nets,
        "external_converter": {
            "provided": external_converter_docs is not None,
            "document_count": len(converter),
            "source_components": converter_types["source_component"],
            "source_ports": converter_types["source_port"],
            "source_nets": converter_types["source_net"],
            "source_traces": converter_types["source_trace"],
            "schematic_geometry_traces": converter_types["schematic_trace"],
            "root_sheet_net_names_correspond_only": converter_net_name_audit,
            "converter_power_flag_symbol_count": extra_power_flags,
            "power_flag_symbols_excluded_from_authoritative_bom": True,
            "geometry_and_component_identity_reconciled": False,
            "original_converter_topology_approved": False,
        },
        "physical_evidence": False,
        "pcb_erc_or_drc_certified": False,
        "manufacturing_authorized": False,
        "claim": (
            "Source-level KiCad connectivity preserved using a separate authoritative "
            "export; original converter geometry and its component identities remain unverified."
        ),
    }
    return {"documents": docs, "receipt": verdict}


def write_recovery(
    netlist_text: str,
    output_json: str,
    *,
    external_converter_docs: Sequence[Mapping[str, Any]] | None = None,
    receipt_json: str | None = None,
) -> dict[str, Any]:
    from pathlib import Path
    result = recover_connected_source_circuit_json(
        netlist_text, external_converter_docs=external_converter_docs
    )
    Path(output_json).write_text(json.dumps(result["documents"], indent=2) + "\n", encoding="utf-8")
    if receipt_json:
        Path(receipt_json).write_text(json.dumps(result["receipt"], indent=2) + "\n", encoding="utf-8")
    return result["receipt"]

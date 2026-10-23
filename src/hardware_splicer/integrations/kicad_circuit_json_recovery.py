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
    if empty_nets:
        raise ValueError(f"KiCad source nets missing any pins: {empty_nets[:5]}")
    if not connected_nets:
        raise ValueError("KiCad source export provides no connected electrical nets")

    docs: list[dict[str, Any]] = []
    port_ids: dict[str, str] = {}
    for comp in source.components:
        docs.append({
            "type": "source_component",
            "source_component_id": f"kicad_component_{comp.ref}",
            "name": comp.ref,
            "ftype": "simple_chip",
            "display_value": comp.value or comp.ref,
            "footprint": comp.footprint,
        })
    for refpin in sorted(mapped):
        ref, pin = refpin.rsplit(".", 1)
        pid = f"kicad_port_{ref}_{pin}"
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
    converter = list(external_converter_docs or [])
    converter_types = Counter(str(doc.get("type")) for doc in converter)
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

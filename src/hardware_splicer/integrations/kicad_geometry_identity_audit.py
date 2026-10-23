"""Conservative KiCad-export to third-party Circuit JSON visual identity audit.

The upstream converter omits explicit KiCad designators and symbol UUIDs.
We MAY associate a schematic picture with one source component only if the
(exported library ID, displayed value) pair is unique on BOTH sides, the exact
set of source pin numbers matches, and every schematic port points to the
associated schematic component. This is a *correlated candidate identity*
not an authenticated source symbol UUID link; original visual geometry must
remain quarantined and never enter authoritative electrical topology.

No positional matching, list ordering, BOM guessing or wiring inference.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from ..netlist.import_kicad import (
    _child_text,
    _find_child,
    _parse_sexpr,
    _tokenize_sexpr,
    parse_kicad_netlist,
)

SCHEMA = "hardware_splicer.kicad_geometry_identity_audit.v1"


def _index_documents(docs: Sequence[Mapping[str, Any]], kind: str, field: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in docs:
        if item.get("type") != kind:
            continue
        ref = str(item.get(field) or "")
        if not ref or ref in result:
            raise ValueError(f"Missing/duplicate {kind} identity {ref!r}")
        result[ref] = dict(item)
    return result


def audit_converter_geometry_identity(
    kicad_export_text: str,
    converter_docs: Sequence[Mapping[str, Any]],
    *,
    schematic_sha256: str | None = None,
) -> dict[str, Any]:
    if not isinstance(converter_docs, list) or any(not isinstance(x, Mapping) for x in converter_docs):
        raise ValueError("Converter input must be an array of document objects")
    source = parse_kicad_netlist(kicad_export_text)
    if not source.components or not source.nets:
        raise ValueError("KiCad electrical source components and nets required")
    tree, next_index = _parse_sexpr(_tokenize_sexpr(kicad_export_text))
    if not isinstance(tree, list) or tree[0] != "export":
        raise ValueError("Expected actual KiCad netlist export")
    original_comp = _find_child(tree, "components") or []
    lib_keys_by_ref: dict[str, tuple[str, str]] = {}
    for item in original_comp[1:]:
        if not isinstance(item, list) or not item or item[0] != "comp":
            continue
        ref = _child_text(item, "ref")
        lib = _find_child(item, "libsource") or []
        libname = _child_text(lib, "lib")
        partname = _child_text(lib, "part")
        if not ref or ref in lib_keys_by_ref:
            raise ValueError("Duplicate or blank original KiCad component reference")
        if not libname or not partname:
            raise ValueError(f"KiCad export lacks source library symbol identity: {ref}")
        lib_keys_by_ref[ref] = (libname + ":" + partname, _child_text(item, "value"))
    if set(lib_keys_by_ref) != {x.ref for x in source.components}:
        raise ValueError("Source library metadata does not match parsed KiCad component list")
    by_source_key: dict[tuple[str, str], list[str]] = defaultdict(list)
    for ref, key in lib_keys_by_ref.items():
        by_source_key[key].append(ref)

    ext_components = _index_documents(converter_docs, "source_component", "source_component_id")
    ext_ports = _index_documents(converter_docs, "source_port", "source_port_id")
    schematic_components = _index_documents(converter_docs, "schematic_component", "schematic_component_id")
    schematic_ports = _index_documents(converter_docs, "schematic_port", "schematic_port_id")
    by_ext_key: dict[tuple[str, str], list[str]] = defaultdict(list)
    for cid, component in ext_components.items():
        # The upstream converter uses manufacturer_part_number as *displayed
        # symbol value* for this format. Do NOT infer actual manufacturer MPN.
        by_ext_key[(str(component.get("name") or ""), str(component.get("manufacturer_part_number") or ""))].append(cid)

    pins_by_source_ref: dict[str, set[str]] = defaultdict(set)
    for net in source.nets:
        for pin in net.pins:
            pins_by_source_ref[pin.component_ref].add(str(pin.pin))
    ports_by_ext_component: dict[str, list[dict]] = defaultdict(list)
    for port in ext_ports.values():
        parent = str(port.get("source_component_id") or "")
        if parent not in ext_components:
            raise ValueError("Upstream source_port points to an unknown source_component")
        ports_by_ext_component[parent].append(port)
    visual_by_ext_component: dict[str, list[dict]] = defaultdict(list)
    for comp in schematic_components.values():
        parent = str(comp.get("source_component_id") or "")
        if parent not in ext_components:
            raise ValueError("Upstream visual schematic component has no source component")
        visual_by_ext_component[parent].append(comp)
    schematic_ports_by_source_port: dict[str, list[dict]] = defaultdict(list)
    for port in schematic_ports.values():
        spid = str(port.get("source_port_id") or "")
        if spid not in ext_ports:
            raise ValueError("Schematic port points to an unknown source port")
        schematic_ports_by_source_port[spid].append(port)

    matches: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    matched_refs: set[str] = set()
    matched_ext_ids: set[str] = set()
    for key, refs in sorted(by_source_key.items()):
        ext_ids = by_ext_key.get(key, [])
        if len(refs) != 1 or len(ext_ids) != 1:
            refused.append({
                "symbol_library_and_value": list(key),
                "source_refs": sorted(refs),
                "converter_component_ids": sorted(ext_ids),
                "reason": "not_one_to_one_unique_symbol_and_display_value",
            })
            continue
        ref, cid = refs[0], ext_ids[0]
        ext_pin_rows = ports_by_ext_component.get(cid, [])
        ext_pin_numbers = [str(p.get("pin_number") if p.get("pin_number") is not None else "") for p in ext_pin_rows]
        expected = pins_by_source_ref.get(ref, set())
        visual_rows = visual_by_ext_component.get(cid, [])
        reasons = []
        if not expected:
            reasons.append("no_source_exported_pin_membership")
        if len(ext_pin_numbers) != len(set(ext_pin_numbers)) or not all(ext_pin_numbers):
            reasons.append("duplicate_or_missing_converter_pin_number")
        if set(ext_pin_numbers) != expected:
            reasons.append("pin_number_set_differs_from_kicad_source")
        if len(visual_rows) != 1:
            reasons.append("missing_or_ambiguous_visual_component")
        else:
            geom = visual_rows[0]
            center, size = geom.get("center"), geom.get("size")
            if (not isinstance(center, dict) or not isinstance(size, dict)
                or any(not isinstance(m.get(k), (int, float)) or not math.isfinite(float(m[k]))
                       for m, keys in ((center, ("x", "y")), (size, ("width", "height")))
                       for k in keys)):
                reasons.append("invalid_visual_geometry")
        visual_id = str(visual_rows[0].get("schematic_component_id")) if len(visual_rows) == 1 else None
        for port in ext_pin_rows:
            port_id = port["source_port_id"]
            candidate = schematic_ports_by_source_port.get(port_id, [])
            if len(candidate) != 1 or str(candidate[0].get("schematic_component_id")) != visual_id:
                reasons.append("source_port_visual_link_missing_or_wrong_component")
                break
            if str(candidate[0].get("pin_number")) != str(port["pin_number"]):
                reasons.append("schematic_port_pin_number_mismatch")
                break
        if reasons:
            refused.append({
                "symbol_library_and_value": list(key),
                "source_refs": [ref],
                "converter_component_ids": [cid],
                "reason": ",".join(sorted(set(reasons))),
            })
            continue
        matched_refs.add(ref)
        matched_ext_ids.add(cid)
        matches.append({
            "kicad_ref": ref,
            "converter_source_component_id": cid,
            "converter_schematic_component_id": visual_id,
            "library_symbol": key[0],
            "symbol_display_value": key[1],
            "matching_pin_numbers": sorted(expected),
            "matched_source_pins": len(expected),
            "evidence_class": "unique_library_value_and_exact_pin_set_correlated_no_uuid",
            "kicad_symbol_uuid_authenticated": False,
            "source_schematic_visual_position_authoritative": False,
        })
    remaining_ext = sorted(set(ext_components) - matched_ext_ids)
    additional_ext = sorted(
        cid for cid in remaining_ext if (str(ext_components[cid].get("name") or ""),
        str(ext_components[cid].get("manufacturer_part_number") or "")) not in by_source_key
    )
    source_ref_list = sorted({x.ref for x in source.components})
    # A positive candidate match is never permission to merge image coordinates
    # or infer pin-to-net traces; this is explicit audit metadata only.
    return {
        "schema_version": SCHEMA,
        "source_netlist_sha256": hashlib.sha256(kicad_export_text.encode()).hexdigest(),
        "source_schematic_sha256": schematic_sha256,
        "converter_docs_sha256": hashlib.sha256(json.dumps(converter_docs,sort_keys=True).encode()).hexdigest(),
        "source_component_count": len(source_ref_list),
        "converter_source_component_count": len(ext_components),
        "source_nets": len(source.nets),
        "unique_candidate_matches": len(matches),
        "matched_source_pin_numbers": sum(len(x["matching_pin_numbers"]) for x in matches),
        "matched_visual_components": len(matches),
        "unmatched_kicad_references": sorted(set(source_ref_list) - matched_refs),
        "unmatched_converter_component_ids": remaining_ext,
        "converter_only_component_ids": additional_ext,
        "refused_groups": refused,
        "candidate_matches": sorted(matches, key=lambda m: m["kicad_ref"]),
        "evidence_level": "partial_metadata_and_exact_pin_set_correlation_not_uuid_identity",
        "visual_geometry_merged": False,
        "electrical_connectivity_from_visual_traces_inferred": False,
        "automatic_fabrication_authorized": False,
        "external_converter_component_identity_completely_verified": False,
        "next_required_evidence": "Preserve per-symbol native KiCad UUIDs/designators across converter boundary before any visual geometry can become part of an authoritative merged circuit.",
    }

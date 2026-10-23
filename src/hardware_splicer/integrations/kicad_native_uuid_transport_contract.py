"""Fail-closed contract for UUID transport from KiCad into converter records.

This checks *consistency* of emitted provenance against the native schematic
and independently exported netlist. It cannot establish that a post-conversion
annotation was genuinely emitted by the upstream parser: that requires
instrumenting and testing the converter at its source boundary.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from ..netlist.import_kicad import parse_kicad_netlist
from .kicad_native_pin_geometry_audit import _placed_symbols
from .kicad_native_coordinate_proof import prove_native_visual_positions
from .kicad_geometry_identity_audit import _index_documents


def verify_native_uuid_transport(
    schematic_text: str,
    official_netlist_text: str,
    converter_docs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate native UUID + hierarchical sheet-path transport, abstaining on missing fields.

    Expected on each source_component:
      native_kicad_symbol_uuid, native_kicad_sheet_uuid_path
    Expected on each source_port:
      native_kicad_symbol_uuid, native_kicad_sheet_uuid_path
    No IDs are inserted, guessed, or repaired by this verifier.
    """
    _, placed = _placed_symbols(schematic_text)
    exported = parse_kicad_netlist(official_netlist_text)
    physical = {c.ref: c for c in exported.components}
    geometry = prove_native_visual_positions(schematic_text, official_netlist_text, converter_docs)
    source = _index_documents(converter_docs, "source_component", "source_component_id")
    ports = _index_documents(converter_docs, "source_port", "source_port_id")
    by_ref = {row["kicad_ref"]: row for row in geometry["correlations"]}
    failures: list[dict[str, str]] = []
    checked = 0
    checked_ports = 0
    for ref in sorted(physical):
        candidate = by_ref.get(ref)
        native = placed.get(ref)
        if not candidate or not native:
            failures.append({"ref": ref, "reason": "geometry_or_native_reference_missing"})
            continue
        identity = physical[ref].metadata
        expected_uuid = native["uuid"]
        expected_path = identity.get("kicad_sheet_uuid_path")
        if expected_uuid not in (identity.get("kicad_symbol_tstamps") or []):
            failures.append({"ref": ref, "reason": "official_export_symbol_uuid_disagrees"})
            continue
        if not isinstance(expected_path, str) or not expected_path.startswith("/"):
            failures.append({"ref": ref, "reason": "official_export_sheet_path_missing"})
            continue
        cid = candidate["converter_source_component_id"]
        row = source[cid]
        if (row.get("native_kicad_symbol_uuid") != expected_uuid or
                row.get("native_kicad_sheet_uuid_path") != expected_path):
            failures.append({"ref": ref, "reason": "converter_component_uuid_or_sheet_path_missing_or_mismatched"})
            continue
        matched_ports = [p for p in ports.values() if p.get("source_component_id") == cid]
        expected_numbers = Counter(candidate["source_pin_numbers"])
        if Counter(str(p.get("pin_number")) for p in matched_ports) != expected_numbers:
            failures.append({"ref": ref, "reason": "converter_port_set_mismatch"})
            continue
        mismatched = [p for p in matched_ports if
                      p.get("native_kicad_symbol_uuid") != expected_uuid or
                      p.get("native_kicad_sheet_uuid_path") != expected_path]
        if mismatched:
            failures.append({"ref": ref, "reason": "converter_port_uuid_or_sheet_path_missing_or_mismatched"})
            continue
        checked += 1
        checked_ports += len(matched_ports)
    full = (not failures and checked == len(physical)
            and len(source) == len(physical) and
            checked_ports == len(ports) and
            geometry["geometry_positions_correlated"])
    return {
        "schema_version": "hardware_splicer.kicad_native_uuid_transport_contract.v1",
        "source_components": len(physical),
        "converter_components": len(source),
        "uuid_path_consistent_components": checked,
        "uuid_path_consistent_ports": checked_ports,
        "failure_count": len(failures),
        "failures": failures,
        "converter_uuid_transport_contract_satisfied": full,
        "converter_provenance_authenticated": False,
        "original_converter_emission_proven": False,
        "visual_electrical_merge_allowed": False,
        "physical_manufacturing_authorized": False,
        "limitation": "A post-hoc annotation can pass consistency checks. Parser-origin provenance requires upstream converter instrumentation and trusted execution receipts.",
    }

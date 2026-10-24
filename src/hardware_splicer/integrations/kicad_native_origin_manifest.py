"""Capture original KiCad identity before invoking an external converter.

Manifest is source-origin evidence, not proof the external converter preserved
identity. Capture runs on the original bytes and independently exported netlist.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

from ..netlist.import_kicad import parse_kicad_netlist
from .kicad_native_pin_geometry_audit import _placed_symbols


def capture_native_identity_manifest(schematic_text: str, official_netlist_text: str) -> dict:
    _, placed = _placed_symbols(schematic_text)
    export = parse_kicad_netlist(official_netlist_text)
    exported = {x.ref: x for x in export.components}
    if len(exported) != len(export.components) or set(exported) != set(placed):
        raise ValueError("Physical source/export symbol references are incomplete or ambiguous")
    identities = []
    keys = set()
    for ref, item in sorted(placed.items()):
        metadata = exported[ref].metadata
        symbol_uuid = item["uuid"]
        stamps = metadata.get("kicad_symbol_tstamps") or []
        sheet_path = metadata.get("kicad_sheet_uuid_path")
        if symbol_uuid not in stamps or not isinstance(sheet_path, str) or not sheet_path.startswith("/"):
            raise ValueError(f"Native symbol/export UUID or sheet path disagreement: {ref}")
        identity = (sheet_path, symbol_uuid)
        if identity in keys:
            raise ValueError("Repeated native instance UUID within a sheet path")
        keys.add(identity)
        identities.append({"reference": ref, "symbol_uuid": symbol_uuid,
                           "sheet_uuid_path": sheet_path,
                           "native_instance_key": sheet_path + "|" + symbol_uuid})
    return {
        "schema_version": "hardware_splicer.kicad_native_preconversion_identity_manifest.v1",
        "original_schematic_sha256": hashlib.sha256(schematic_text.encode()).hexdigest(),
        "official_netlist_sha256": hashlib.sha256(official_netlist_text.encode()).hexdigest(),
        "physical_instance_count": len(identities),
        "instances": identities,
        "captured_before_external_conversion": True,
        "external_converter_emission_authenticated": False,
        "converter_uuid_transport_satisfied": False,
        "visual_electrical_merge_allowed": False,
        "manufacturing_authorized": False,
    }


def canonical_manifest_sha256(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

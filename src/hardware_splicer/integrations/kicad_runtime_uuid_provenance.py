"""Independently check converter-RUNTIME native KiCad UUID provenance receipts.

The upstream kicad-to-circuit-json converter v0.0.144 already maps native
KiCad UUIDs to generated schematic_component IDs internally. The companion
JS adapter captures that map DURING conversion, not by post-hoc positioning.

Verify this record against the same original source, official KiCad export,
converter's unchanged Circuit JSON, exact native UUID, instance path, source
component, pin numbering, count bijection and SHA256 evidence.

Not a cryptographically signed attestation of an untrusted external converter
process, nor proof of schematic wires/junctions or physical fabrication.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..netlist.import_kicad import _child_text, _find_child, _parse_sexpr, _tokenize_sexpr, parse_kicad_netlist


def _native_instances(source_text: str) -> dict[str, dict[str, Any]]:
    root = _parse_sexpr(_tokenize_sexpr(source_text))[0]
    if not isinstance(root,list) or not root or root[0]!="kicad_sch":
        raise ValueError("Native original KiCad .kicad_sch source required")
    symbols={}
    for s in root[1:]:
        if not isinstance(s,list) or not s or s[0]!="symbol":
            continue
        uuid=_child_text(s,"uuid")
        library=_child_text(s,"lib_id")
        at=_find_child(s,"at")
        reference_properties=[
            x[2] for x in s[1:] if isinstance(x,list) and len(x)>2
            and x[0]=="property" and x[1]=="Reference"
        ]
        if not uuid or uuid in symbols or not library or not at or len(reference_properties)!=1:
            raise ValueError("Missing or duplicate KiCad native symbol UUID/library/ref")
        ref=str(reference_properties[0])
        instances=_find_child(s,"instances") or []
        paths=[]
        for p in instances[1:]:
            if not isinstance(p,list) or not p or p[0]!="project":
                continue
            project=str(p[1]) if len(p)>1 else ""
            for path in p[2:]:
                if isinstance(path,list) and path and path[0]=="path":
                    paths.append({
                        "project":project,
                        "sheet_uuid_path":str(path[1]),
                        "reference":_child_text(path,"reference"),
                        "unit":int(_child_text(path,"unit")),
                    })
        if len(paths)!=1 or paths[0]["reference"]!=ref or not paths[0]["sheet_uuid_path"]:
            raise ValueError("Multiple/missing native sheet instances unsupported")
        try:
            origin=[float(at[1]),float(at[2])]
        except (ValueError,TypeError) as exc:
            raise ValueError("Invalid native KiCad component coordinates") from exc
        symbols[uuid]={
            "native_reference":ref,"native_library_id":library,
            "native_project":paths[0]["project"],
            "native_sheet_uuid_path":paths[0]["sheet_uuid_path"],
            "native_unit":paths[0]["unit"],
            "native_position_mm":origin,
        }
    if not symbols:
        raise ValueError("No original native schematic symbols")
    return symbols


def verify_converter_uuid_provenance(
    native_schematic_bytes: bytes,
    exported_netlist_text: str,
    circuit_json_bytes: bytes,
    provenance_bytes: bytes,
) -> dict[str,Any]:
    schematic_text=native_schematic_bytes.decode("utf-8")
    docs=json.loads(circuit_json_bytes)
    sidecar=json.loads(provenance_bytes)
    if not isinstance(docs,list) or not isinstance(sidecar,dict):
        raise ValueError("Missing Circuit JSON array or runtime provenance object")
    if sidecar.get("schema_version")!="hardware_splicer.kicad_upstream_runtime_provenance.v1":
        raise ValueError("Unrecognized converter runtime provenance schema")
    if sidecar.get("capture")!="upstream_converter_ctx_symbolUuidToComponentId":
        raise ValueError("Provenance must originate from explicit converter runtime UUID map")
    if sidecar.get("upstream_converter_version")!="0.0.144":
        raise ValueError("Converter version outside audited pinned version")
    if sidecar.get("source_sha256")!=hashlib.sha256(native_schematic_bytes).hexdigest():
        raise ValueError("Native schematic SHA256 does not match converter input")
    if sidecar.get("converter_output_sha256")!=hashlib.sha256(circuit_json_bytes).hexdigest():
        raise ValueError("Circuit JSON SHA256 does not match converter output")
    if sidecar.get("original_converter_output_modified") is not False:
        raise ValueError("No converter document mutation is allowed")
    if sidecar.get("source_wire_connectivity_authenticated") is not False:
        raise ValueError("A UUID identity map cannot authenticate electrical nets")

    native=_native_instances(schematic_text)
    official=parse_kicad_netlist(exported_netlist_text)
    official_by_ref={x.ref:x for x in official.components}
    native_by_ref={info["native_reference"]:uid for uid,info in native.items()}
    physical_refs=set(official_by_ref)
    all_refs=set(native_by_ref)
    if physical_refs - all_refs:
        raise ValueError("KiCad exported physical parts missing from original schematic")
    source_components={
        d["source_component_id"]:d for d in docs if d.get("type")=="source_component"
    }
    visual_components={
        d["schematic_component_id"]:d for d in docs if d.get("type")=="schematic_component"
    }
    ports_by_component:dict[str,set[str]]={}
    source_ports_by_id:dict[str,dict]={}
    schematic_ports_by_source_id:dict[str,dict]={}
    for item in docs:
        if item.get("type")!="schematic_port":
            continue
        spid=str(item.get("source_port_id") or "")
        if not spid or spid in schematic_ports_by_source_id:
            raise ValueError("Missing/duplicate converted visual port identity")
        schematic_ports_by_source_id[spid]=item
    for port in docs:
        if port.get("type")!="source_port":
            continue
        pid=str(port.get("source_port_id") or "")
        if not pid or pid in source_ports_by_id:
            raise ValueError("Missing/duplicate source port identity")
        source_ports_by_id[pid]=port
        cid=str(port.get("source_component_id") or "")
        number=port.get("pin_number")
        if cid not in source_components or number is None:
            raise ValueError("Source port has nonexistent component or missing pin number")
        pins=ports_by_component.setdefault(cid,set())
        if str(number) in pins:
            raise ValueError("Duplicate converted pin number")
        pins.add(str(number))
    if set(source_ports_by_id)!=set(schematic_ports_by_source_id):
        raise ValueError("Converter source ports and visual schematic ports are not one-to-one")
    actual_pins:dict[str,set[str]]={}
    for n in official.nets:
        for p in n.pins:
            actual_pins.setdefault(p.component_ref,set()).add(str(p.pin))
    rows=sidecar.get("records")
    if not isinstance(rows,list) or len(rows)!=len(native):
        raise ValueError("Runtime provenance did not cover each native source symbol")
    if len(source_components)!=len(native) or len(visual_components)!=len(native):
        raise ValueError("Converter component counts do not bijectively cover native symbols")
    if sidecar.get("native_uuid_mapped_count")!=len(rows) or sidecar.get("converter_component_count")!=len(rows):
        raise ValueError("Counter inconsistency in converter provenance")
    seen_uuid:set[str]=set()
    seen_refs:set[str]=set()
    seen_source:set[str]=set()
    seen_visual:set[str]=set()
    physical_ok=0
    flags_ok=0
    for row in rows:
        uuid=str(row.get("native_symbol_uuid") or "")
        if uuid not in native or uuid in seen_uuid:
            raise ValueError("Unknown, missing or repeated native KiCad UUID")
        seen_uuid.add(uuid)
        source_record=native[uuid]
        for key in ("native_reference","native_library_id","native_project",
                    "native_sheet_uuid_path","native_unit"):
            if row.get(key)!=source_record[key]:
                raise ValueError(f"Native KiCad UUID/instance identity mismatch: {key}")
        location=row.get("native_position_mm")
        if not isinstance(location,dict) or [location.get("x"),location.get("y")]!=source_record["native_position_mm"]:
            raise ValueError("Converter-reported native component position differs from source")
        ref=source_record["native_reference"]
        vid=str(row.get("schematic_component_id") or "")
        cid=str(row.get("source_component_id") or "")
        if ref in seen_refs or vid in seen_visual or cid in seen_source:
            raise ValueError("Component identities not one-to-one")
        seen_refs.add(ref);seen_visual.add(vid);seen_source.add(cid)
        visual=visual_components.get(vid)
        source_item=source_components.get(cid)
        if visual is None or source_item is None or visual.get("source_component_id")!=cid:
            raise ValueError("Converter-runtime UUID points to wrong visual/source component")
        if source_item.get("name")!=row["native_library_id"]:
            raise ValueError("Original source library ID disagrees with linked converter component")
        declared=row.get("source_pin_numbers")
        if not isinstance(declared,list) or set(declared)!=ports_by_component.get(cid,set()) or len(declared)!=len(set(declared)):
            raise ValueError("Source pin numbers disagree with converted port records")
        for port_id,port in source_ports_by_id.items():
            if port["source_component_id"]!=cid:
                continue
            visual_port=schematic_ports_by_source_id[port_id]
            if (visual_port.get("schematic_component_id")!=vid or
                str(visual_port.get("pin_number"))!=str(port["pin_number"])):
                raise ValueError("Original converter pin-to-visual identity disagrees with runtime UUID link")
        if ref in physical_refs:
            if uuid not in (official_by_ref[ref].metadata.get("kicad_symbol_tstamps") or []):
                raise ValueError("Original native UUID is absent from independent KiCad netlist export")
            if set(declared)!=actual_pins.get(ref,set()):
                raise ValueError("Converted physical component pins differ from official KiCad source")
            physical_ok+=1
        else:
            if not ref.startswith("#FLG") or row["native_library_id"]!="power:PWR_FLAG":
                raise ValueError("Nonphysical converter symbol not identified as allowed power flag")
            flags_ok+=1
    if set(native)!=seen_uuid or set(source_components)!=seen_source or set(visual_components)!=seen_visual:
        raise ValueError("Missing original or generated symbol identity")
    if set(physical_refs)!=seen_refs.intersection(physical_refs):
        raise ValueError("Physical KiCad symbols not mapped to converter")
    return {
        "schema_version":"hardware_splicer.verified_kicad_runtime_uuid_provenance.v1",
        "source_sha256":sidecar["source_sha256"],
        "converter_output_sha256":sidecar["converter_output_sha256"],
        "source_symbols":len(native),
        "native_uuid_entries_verified":len(seen_uuid),
        "physical_component_uuid_links_verified":physical_ok,
        "nonphysical_power_flags_uuid_links_verified":flags_ok,
        "source_sheet_paths_verified":len(rows),
        "source_port_numbers_reconciled_to_official_export":sum(len(actual_pins.get(x,[])) for x in physical_refs),
        "direct_converter_runtime_uuid_mapping":True,
        "uuid_from_native_symbol_and_independent_kicad_export_verified":True,
        "source_single_sheet_assumption":True,
        "runtime_capture_not_cryptographically_signed":True,
        "upstream_circuit_json_documents_unchanged":True,
        "visual_coordinates_independently_verified_here":False,
        "electrical_net_connectivity_verified_here":False,
        "geometry_electrical_merge_authorized":False,
        "manufacturing_authorized":False,
    }


def verify_files(schematic:Path,netlist:Path,converted:Path,provenance:Path)->dict[str,Any]:
    return verify_converter_uuid_provenance(
        schematic.read_bytes(), netlist.read_text(encoding="utf-8"),
        converted.read_bytes(), provenance.read_bytes()
    )

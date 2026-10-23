"""Native KiCad symbol coordinate → converter visual candidate mapping.

Unlike the earlier metadata-only audit, this derives an affine axis transform
from independently unique library/value+pin anchors, confirms it against the
remaining anchors, then correlates remaining duplicate symbols by their exact
source positions. Native symbol UUIDs are checked AGAINST the official KiCad
netlist export. The upstream converter still doesn't CARRY those UUIDs:
association by coordinates != authenticated converter instance provenance.

Single sheet only. No schematic trace wiring, PCB authority, or geometry merge.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any, Mapping, Sequence

from ..netlist.import_kicad import _child_text, _find_child, _parse_sexpr, _tokenize_sexpr, parse_kicad_netlist
from .kicad_geometry_identity_audit import audit_converter_geometry_identity, _index_documents

POSITION_EPSILON = 1e-6
SCALE_EPSILON = 1e-9


def _property(node: list, label: str) -> str:
    values = [item[2] for item in node[1:]
              if isinstance(item, list) and len(item) >= 3
              and item[0] == "property" and item[1] == label]
    if len(values) != 1:
        raise ValueError(f"Expected exactly one native KiCad {label} property")
    return str(values[0])


def _native_symbols(schematic_text: str, export: Any) -> dict[str, dict[str, Any]]:
    tree = _parse_sexpr(_tokenize_sexpr(schematic_text))[0]
    if not isinstance(tree, list) or tree[0] != "kicad_sch":
        raise ValueError("Native .kicad_sch required; do not use netlist as geometric source")
    refs: dict[str, dict[str, Any]] = {}
    for item in tree[1:]:
        if not isinstance(item, list) or not item or item[0] != "symbol":
            continue
        reference = _property(item, "Reference")
        key = (_child_text(item, "lib_id"), _property(item, "Value"))
        point = _find_child(item, "at")
        uid = _child_text(item, "uuid")
        if (not point or len(point) < 3 or not uid or
            not key[0] or reference in refs):
            raise ValueError(f"Missing native KiCad source instance identity: {reference}")
        try:
            x, y = float(point[1]), float(point[2])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid native KiCad coordinate: {reference}") from exc
        if not all(map(math.isfinite, (x, y))):
            raise ValueError("Invalid non-finite native coordinate")
        refs[reference] = {
            "ref": reference, "lib_id": key[0], "display_value": key[1],
            "x_mm": x, "y_mm": y, "symbol_uuid": uid,
        }
    physical = {comp.ref: comp for comp in export.components}
    result = {ref: value for ref, value in refs.items() if ref in physical}
    if len(result) != len(physical):
        raise ValueError("Native schematic missing some actual exported physical component instances")
    for ref, entry in result.items():
        recorded = physical[ref].metadata.get("kicad_symbol_tstamps") or []
        if entry["symbol_uuid"] not in recorded:
            raise ValueError(f"Native UUID disagrees with independently exported KiCad symbol identity: {ref}")
    return result


def _affine_axis(pairs: list[tuple[float, float]], axis: str) -> tuple[float, float]:
    if len(pairs) < 4:
        raise ValueError("Require >=4 independent identity anchors")
    ordered = sorted(pairs)
    lo, hi = ordered[0], ordered[-1]
    if abs(hi[0] - lo[0]) < 1e-6:
        raise ValueError(f"No informative native KiCad separation along axis {axis}")
    scale = (hi[1]-lo[1])/(hi[0]-lo[0])
    offset = lo[1] - scale*lo[0]
    if not math.isfinite(scale) or not math.isfinite(offset) or abs(scale) < 1e-7:
        raise ValueError("Degenerate affine transform")
    if any(abs((scale*x+offset)-v) > POSITION_EPSILON for x,v in pairs):
        raise ValueError(f"Unambiguous KiCad anchors disagree on {axis} transform")
    return scale, offset


def prove_native_visual_positions(
    schematic_text: str,
    kicad_export_text: str,
    converter_docs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    baseline = audit_converter_geometry_identity(kicad_export_text, converter_docs)
    export = parse_kicad_netlist(kicad_export_text)
    native = _native_symbols(schematic_text, export)
    ext = _index_documents(converter_docs, "source_component", "source_component_id")
    visual = _index_documents(converter_docs, "schematic_component", "schematic_component_id")
    source_ports = _index_documents(converter_docs, "source_port", "source_port_id")
    schematic_ports = _index_documents(converter_docs, "schematic_port", "schematic_port_id")
    visuals: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in visual.values():
        cid = str(item.get("source_component_id") or "")
        if cid not in ext:
            raise ValueError("Unknown upstream visual source_component")
        visuals[cid].append(item)
    ports: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in source_ports.values():
        cid = str(item.get("source_component_id") or "")
        if cid not in ext:
            raise ValueError("Converter port with nonexistent component")
        ports[cid].append(item)
    visual_ports: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in schematic_ports.values():
        spid = str(item.get("source_port_id") or "")
        if spid not in source_ports:
            raise ValueError("Unknown upstream visual source_port")
        visual_ports[spid].append(item)
    key_components: dict[tuple[str,str], list[str]] = defaultdict(list)
    for cid, item in ext.items():
        key_components[(str(item.get("name") or ""),str(item.get("manufacturer_part_number") or ""))].append(cid)
    native_by_key: dict[tuple[str,str],list[str]] = defaultdict(list)
    for ref,item in native.items():
        native_by_key[(item["lib_id"],item["display_value"])].append(ref)
    visual_center: dict[str,tuple[float,float]] = {}
    for cid, items in visuals.items():
        if len(items) != 1:
            continue
        center = items[0].get("center")
        if not isinstance(center,dict) or any(
            not isinstance(center.get(k),(float,int)) or not math.isfinite(center[k])
            for k in ("x","y")
        ):
            raise ValueError("Missing/non-finite converter visual center")
        visual_center[cid]=(float(center["x"]),float(center["y"]))

    # Select only *already pin-proven* unique-anchor references. Their
    # geometry is an independent hold-out check, not input to electrical nets.
    anchors = baseline["candidate_matches"]
    x_pairs,y_pairs=[],[]
    for anchor in anchors:
        ref=anchor["kicad_ref"]
        cid=anchor["converter_source_component_id"]
        if cid not in visual_center:
            raise ValueError("Unique anchor has no schematic visual center")
        n=native[ref]
        sx,sy=visual_center[cid]
        x_pairs.append((n["x_mm"],sx))
        y_pairs.append((n["y_mm"],sy))
    xscale,xoffset = _affine_axis(x_pairs,"X")
    yscale,yoffset = _affine_axis(y_pairs,"Y")
    if xscale <= 0 or yscale >= 0 or abs(xscale + yscale) > SCALE_EPSILON:
        raise ValueError("Coordinate frame not consistent with scale and flipped KiCad Y axis")
    native_pins: dict[str,set[str]] = defaultdict(set)
    for net in export.nets:
        for pin in net.pins:
            native_pins[pin.component_ref].add(str(pin.pin))
    accepted: list[dict[str,Any]]=[]
    rejected: list[dict[str,Any]]=[]
    used: set[str]=set()
    anchored_refs={item["kicad_ref"] for item in anchors}
    for ref,n in sorted(native.items()):
        key=(n["lib_id"],n["display_value"])
        ids=key_components.get(key,[])
        expected=(xscale*n["x_mm"]+xoffset,yscale*n["y_mm"]+yoffset)
        close=[
            (cid,math.hypot(visual_center[cid][0]-expected[0],
                            visual_center[cid][1]-expected[1]))
            for cid in ids if cid in visual_center
            and math.hypot(visual_center[cid][0]-expected[0],
                           visual_center[cid][1]-expected[1]) <= POSITION_EPSILON
        ]
        if len(close)!=1:
            rejected.append({
                "kicad_ref":ref,"reason":"no_unique_converter_position_at_source_symbol",
                "candidate_count_at_position":len(close),
            })
            continue
        cid,delta=close[0]
        if cid in used:
            raise ValueError("Multiple source refs claim the same converter visual component")
        pin_rows=ports.get(cid,[])
        pin_numbers=[str(v.get("pin_number") if v.get("pin_number") is not None else "") for v in pin_rows]
        schem=visuals[cid][0]["schematic_component_id"]
        if (
            not native_pins[ref] or len(pin_numbers)!=len(set(pin_numbers))
            or set(pin_numbers)!=native_pins[ref] or
            any(len(visual_ports.get(p["source_port_id"],[]))!=1 or
                str(visual_ports[p["source_port_id"]][0].get("schematic_component_id"))!=str(schem)
                or str(visual_ports[p["source_port_id"]][0].get("pin_number"))!=str(p["pin_number"])
                for p in pin_rows)
        ):
            rejected.append({"kicad_ref":ref,"reason":"port_or_pin_identity_not_verified"})
            continue
        used.add(cid)
        accepted.append({
            "kicad_ref":ref,"native_kicad_symbol_uuid":n["symbol_uuid"],
            "converter_source_component_id":cid,
            "converter_schematic_component_id":str(schem),
            "source_pin_numbers":sorted(native_pins[ref]),
            "native_mm":[n["x_mm"],n["y_mm"]],
            "converter_center":list(visual_center[cid]),
            "coordinate_residual":round(delta,12),
            "identity_evidence":(
                "native_uuid_export_crosschecked_and_coordinate_matched; "
                "converter_does_not_embed_native_uuid"
            ),
            "direct_uuid_in_converter":False,
            "symbol_visual_shape_verified":False,
            "pin_coordinates_verified":False,
            "anchor_class": "unique_library_value_pins" if ref in anchored_refs else "disambiguated_by_verified_coordinate_transform",
        })
    ambiguous_correlated=[i for i in accepted if i["anchor_class"]=="disambiguated_by_verified_coordinate_transform"]
    return {
        "schema_version":"hardware_splicer.kicad_native_coordinate_proof.v1",
        "schematic_sha256":hashlib.sha256(schematic_text.encode()).hexdigest(),
        "official_netlist_sha256":hashlib.sha256(kicad_export_text.encode()).hexdigest(),
        "converter_docs_sha256":hashlib.sha256(json.dumps(converter_docs,sort_keys=True).encode()).hexdigest(),
        "native_component_count":len(native),
        "original_unique_metadata_anchors":len(anchors),
        "original_anchor_pins":baseline["matched_source_pin_numbers"],
        "additional_coordinate_correlations":len(ambiguous_correlated),
        "source_position_correlated_instances":len(accepted),
        "source_position_correlated_pins":sum(len(a["source_pin_numbers"]) for a in accepted),
        "unmatched_source_refs":[x["kicad_ref"] for x in rejected],
        "refused":rejected,
        "affine_frame":{"x_scale":xscale,"x_offset":xoffset,"y_scale":yscale,"y_offset":yoffset,
                        "position_epsilon":POSITION_EPSILON,
                        "basis":"single-sheet verified unique identity anchors"},
        "correlations":accepted,
        "source_native_uuid_crosschecked_with_kicad_export":True,
        "native_uuid_transmitted_by_converter":False,
        "converter_record_provenance_authenticated":False,
        "geometry_positions_correlated":len(accepted)==len(native),
        "schematic_symbol_shapes_validated":False,
        "schematic_port_positions_validated":False,
        "visual_electrical_geometry_merge_allowed":False,
        "physical_build_authorized":False,
        "adversarial_limit":"Permutation of otherwise identical converter symbols cannot be detected without converter-carried native UUIDs.",
    }

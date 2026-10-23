"""Independent KiCad library-pin -> converter schematic-port geometry verification.

Use the embedded native `lib_symbols` definitions, placed instance origin,
angle/mirror, and a source-to-converter frame calibrated only from unique
component anchors. Pin identities come from an official KiCad netlist export.

This remains an *observational audit*: upstream visual source records do NOT
carry KiCad native UUIDs. Symbol strokes/shapes and schematic_trace electrical
geometry are not certified. No automatic design merge or manufacturing gate.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from typing import Any, Mapping, Sequence

from ..netlist.import_kicad import _child_text, _find_child, _parse_sexpr, _tokenize_sexpr, parse_kicad_netlist
from .kicad_native_coordinate_proof import _property, prove_native_visual_positions
from .kicad_geometry_identity_audit import _index_documents

PIN_EPSILON = 1e-6


def _placed_symbols(schematic: str) -> tuple[dict[str, list], dict[str, dict]]:
    root=_parse_sexpr(_tokenize_sexpr(schematic))[0]
    if not isinstance(root,list) or not root or root[0]!="kicad_sch":
        raise ValueError("Expected original native KiCad schematic")
    lib_symbols=_find_child(root,"lib_symbols")
    if not lib_symbols:
        raise ValueError("Native KiCad schematic lacks embedded library symbols")
    libs={}
    for node in lib_symbols[1:]:
        if isinstance(node,list) and node and node[0]=="symbol":
            label=str(node[1]) if len(node)>1 else ""
            if not label or label in libs:
                raise ValueError("Duplicate/missing source library symbol ID")
            libs[label]=node
    instances={}
    for node in root[1:]:
        if not isinstance(node,list) or not node or node[0]!="symbol":
            continue
        ref=_property(node,"Reference")
        at=_find_child(node,"at")
        uid=_child_text(node,"uuid")
        libid=_child_text(node,"lib_id")
        mirror=_find_child(node,"mirror")
        if ref in instances or not at or len(at)<3 or not uid or libid not in libs:
            raise ValueError(f"Malformed native source symbol placement: {ref}")
        try:
            x=float(at[1]);y=float(at[2]);angle=float(at[3]) if len(at)>3 else 0.0
        except (ValueError,TypeError) as exc:
            raise ValueError(f"Non-numeric KiCad symbol location: {ref}") from exc
        if not all(math.isfinite(v) for v in (x,y,angle)):
            raise ValueError("Invalid native source placement number")
        if angle % 90 != 0:
            raise ValueError("Unverified non-cardinal KiCad symbol rotation; abstain")
        mirror_axis=""
        if mirror:
            if len(mirror)!=2 or mirror[1] not in ("x","y"):
                raise ValueError(f"Unsupported KiCad mirror mode for {ref}")
            mirror_axis=str(mirror[1])
        instances[ref]={"lib":libid,"uuid":uid,"x":x,"y":y,
                        "angle":int(angle)%360,"mirror":mirror_axis,
                        "unit":_child_text(node,"unit") or "1"}
    return libs,instances


def _native_library_pins(symbol: list, unit: str) -> dict[str,tuple[float,float]]:
    positions={}
    for sub in symbol[1:]:
        if not isinstance(sub,list) or not sub or sub[0]!="symbol":
            continue
        label=str(sub[1]) if len(sub)>1 else ""
        match=re.search(r"_(\d+)_(\d+)$",label)
        if not match:
            raise ValueError(f"Unsupported symbol subunit label: {label}")
        if match.group(1) not in ("0",unit):
            continue
        for pin in sub[2:]:
            if not isinstance(pin,list) or not pin or pin[0]!="pin":
                continue
            number=_child_text(pin,"number")
            place=_find_child(pin,"at")
            if not number or number in positions or not place or len(place)<3:
                raise ValueError(f"Invalid/duplicated KiCad library pin number: {number}")
            try:
                x,y=float(place[1]),float(place[2])
            except (TypeError,ValueError) as exc:
                raise ValueError("Non-numeric native library pin position") from exc
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("Non-finite native library pin position")
            positions[number]=(x,y)
    if not positions:
        raise ValueError("No native pin locations for selected symbol unit")
    return positions


def _predicted_canvas_pin(instance: dict, local:tuple[float,float],frame:dict) -> tuple[float,float]:
    lx,ly=local
    radians=math.radians(instance["angle"])
    rx=math.cos(radians)*lx-math.sin(radians)*ly
    ry=math.sin(radians)*lx+math.cos(radians)*ly
    # KiCad (mirror x) reflects symbol across global horizontal axis;
    # (mirror y) reflects across global vertical axis, AFTER placement rotation.
    if instance["mirror"]=="x":
        ry=-ry
    elif instance["mirror"]=="y":
        rx=-rx
    # Native schematic's Y grows down; embedded library pin Y grows up.
    x_mm=instance["x"]+rx
    y_mm=instance["y"]-ry
    return (frame["x_scale"]*x_mm+frame["x_offset"],
            frame["y_scale"]*y_mm+frame["y_offset"])


def verify_native_pin_positions(
    schematic_text:str,
    exported_netlist_text:str,
    converter_docs:Sequence[Mapping[str,Any]],
) -> dict[str,Any]:
    component_proof=prove_native_visual_positions(
        schematic_text,exported_netlist_text,converter_docs,
    )
    libs,instances=_placed_symbols(schematic_text)
    source=parse_kicad_netlist(exported_netlist_text)
    verified_refs={v.ref for v in source.components}
    ports=_index_documents(converter_docs,"source_port","source_port_id")
    visual_ports=_index_documents(converter_docs,"schematic_port","schematic_port_id")
    visual_by_source={}
    for item in visual_ports.values():
        key=str(item.get("source_port_id") or "")
        if key not in ports or key in visual_by_source:
            raise ValueError("Unmapped or multiply-mapped upstream schematic_port")
        visual_by_source[key]=item
    actual_source_pins:dict[str,set[str]]=defaultdict(set)
    for net in source.nets:
        for pin in net.pins:
            actual_source_pins[pin.component_ref].add(str(pin.pin))
    all_pins=[];failed=[]
    matched_components={x["kicad_ref"]:x for x in component_proof["correlations"]}
    for ref in sorted(verified_refs):
        correlated=matched_components.get(ref)
        if correlated is None:
            failed.append({"ref":ref,"pin":None,"reason":"component_center_not_correlated"})
            continue
        instance=instances.get(ref)
        if not instance or instance["uuid"]!=correlated["native_kicad_symbol_uuid"]:
            failed.append({"ref":ref,"pin":None,"reason":"native_symbol_uuid_mismatch"})
            continue
        source_pins=_native_library_pins(libs[instance["lib"]],instance["unit"])
        required=actual_source_pins[ref]
        if set(source_pins)!=required:
            failed.append({"ref":ref,"pin":None,
                           "reason":"native_library_pin_set_differs_from_official_export",
                           "source":sorted(required),"native_library":sorted(source_pins)})
            continue
        cid=correlated["converter_source_component_id"]
        port_rows={str(p.get("pin_number")):p for p in ports.values()
                   if p.get("source_component_id")==cid}
        if set(port_rows)!=required:
            failed.append({"ref":ref,"pin":None,"reason":"converter_pin_set_mismatch"})
            continue
        for number in sorted(required):
            port=port_rows[number]
            visual=visual_by_source.get(port["source_port_id"])
            if not visual or str(visual.get("schematic_component_id"))!=str(
                correlated["converter_schematic_component_id"]
            ):
                failed.append({"ref":ref,"pin":number,"reason":"unlinked_visual_port"})
                continue
            center=visual.get("center")
            if not isinstance(center,dict) or any(
                not isinstance(center.get(k),(int,float)) or not math.isfinite(center[k])
                for k in ("x","y")
            ):
                failed.append({"ref":ref,"pin":number,"reason":"invalid_visual_pin_position"})
                continue
            calculated=_predicted_canvas_pin(instance,source_pins[number],
                                              component_proof["affine_frame"])
            delta=math.hypot(center["x"]-calculated[0],center["y"]-calculated[1])
            record={
                "kicad_ref":ref,"pin":number,"native_symbol_uuid":instance["uuid"],
                "native_symbol_angle_degrees":instance["angle"],
                "native_mirror_axis":instance["mirror"],
                "converter_source_port_id":port["source_port_id"],
                "converter_schematic_port_id":visual["schematic_port_id"],
                "predicted_converter_center":[round(v,12) for v in calculated],
                "actual_converter_center":[float(center["x"]),float(center["y"])],
                "position_residual":round(delta,12),
            }
            if delta>PIN_EPSILON:
                failed.append({**record,"reason":"converter_pin_center_differs_from_native_kicad"})
            else:
                all_pins.append(record)
    source_numbered_pin_count=sum(len(x) for x in actual_source_pins.values())
    verified_all=(
        not failed and len(all_pins)==source_numbered_pin_count
        and len(matched_components)==len(verified_refs)
    )
    return {
        "schema_version":"hardware_splicer.kicad_native_pin_geometry_audit.v1",
        "schematic_sha256":hashlib.sha256(schematic_text.encode()).hexdigest(),
        "official_netlist_sha256":hashlib.sha256(exported_netlist_text.encode()).hexdigest(),
        "converter_docs_sha256":hashlib.sha256(json.dumps(converter_docs,sort_keys=True).encode()).hexdigest(),
        "source_components":len(verified_refs),
        "source_numbered_pins":source_numbered_pin_count,
        "component_centers_correlated":len(matched_components),
        "source_library_pin_positions_verified":len(all_pins),
        "failed_pin_or_component_checks":len(failed),
        "all_pin_centers_correlated":verified_all,
        "max_pin_position_residual":max((x["position_residual"] for x in all_pins),default=None),
        "observed_angle_degrees":sorted({instances[ref]["angle"] for ref in verified_refs}),
        "observed_mirror_axes":sorted({instances[ref]["mirror"] for ref in verified_refs}),
        "failed":failed,
        "pin_correlations":all_pins,
        "native_uuid_in_converter":False,
        "converter_record_provenance_authenticated":False,
        "schematic_symbol_strokes_shapes_verified":False,
        "schematic_junctions_wires_verified":False,
        "visual_electrical_merge_allowed":False,
        "physical_manufacturing_authorized":False,
        "identity_limitation":(
            "Identical-value converter component or pin records may be permuted "
            "without authentic native KiCad UUID transport. Positional equality "
            "is not proof of the original converter record's identity."
        ),
    }

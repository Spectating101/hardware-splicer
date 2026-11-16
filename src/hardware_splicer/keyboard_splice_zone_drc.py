"""Compare exact non-zone copper while diagnosing legacy KiCad zone refill."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any


def _digest_sequence(rows: list | dict):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,
                                  separators=(",",":")).encode()).hexdigest()


def _sequence(rows, fields):
    values=[]
    for item in rows:
        values.append(tuple(item.get(field) for field in fields))
    return Counter(values)


def _tracked(tracks):
    out=[]
    for t in tracks:
        a=(t["x1"],t["y1"])
        b=(t["x2"],t["y2"])
        out.append((t["net"],t["layer"],t["width_mm"],*sorted((a,b))))
    return Counter(out)


def verify_original_copper_unchanged(original: dict, converted: dict) -> dict:
    """A refill is accepted for *diagnostic DRC* only if ALL non-zone copper agrees.

    Immutable source identity and explicit normalized geometry comparisons
    prevent a bogus clean KiCad board from laundering a changed trace/pad.
    """
    if original.get("source_sha256")==converted.get("source_sha256"):
        raise ValueError("converted output unexpectedly identical to byte-identical original")
    for field in ("copper_layer_count","outline_bbox_mm","zone_count"):
        if original.get(field)!=converted.get(field):
            raise ValueError("source board outline, copper layers or zone count changed: "+field)
    pad_fields=("ref","pad","net","layer","x","y","size_x_mm","size_y_mm",
                "pad_shape","pad_attribute","orientation_degrees")
    via_fields=("net","x","y","diameter_mm","via_type")
    component_fields=("ref","value","x","y")
    expected={
        "pads":_sequence(original.get("pads",[]),pad_fields),
        "tracks":_tracked(original.get("tracks",[])),
        "vias":_sequence(original.get("vias",[]),via_fields),
        "footprints":_sequence(original.get("footprints",[]),component_fields),
        "switch_positions":_sequence(original.get("switch_positions",[]),component_fields),
    }
    actual={
        "pads":_sequence(converted.get("pads",[]),pad_fields),
        "tracks":_tracked(converted.get("tracks",[])),
        "vias":_sequence(converted.get("vias",[]),via_fields),
        "footprints":_sequence(converted.get("footprints",[]),component_fields),
        "switch_positions":_sequence(converted.get("switch_positions",[]),component_fields),
    }
    for name in expected:
        if expected[name]!=actual[name]:
            removed=sum((expected[name]-actual[name]).values())
            added=sum((actual[name]-expected[name]).values())
            raise ValueError(f"source {name} changed during zone reconstruction: removed {removed}, added {added}")
    return {
        "original_source_sha256":original["source_sha256"],
        "converted_copy_sha256":converted["source_sha256"],
        "non_zone_source_geometry_equivalent":True,
        "pad_contacts_preserved":sum(expected["pads"].values()),
        "copper_tracks_preserved":sum(expected["tracks"].values()),
        "vias_preserved":sum(expected["vias"].values()),
        "component_locations_preserved":sum(expected["footprints"].values()),
        "detected_key_locations_preserved":sum(expected["switch_positions"].values()),
        "original_conductive_zone_fills_identical":False,
        "physical_clearances_after_cut_verified":False,
        "fabrication_authorized":False,
    }


def classify_native_drc(report: dict) -> dict:
    if not isinstance(report.get("violations"),list) or not isinstance(report.get("unconnected_items"),list):
        raise ValueError("unrecognized native KiCad all-severity DRC report")
    count=Counter(str(i.get("severity","unknown")) for i in report["violations"])
    kinds=Counter(str(i.get("type","unknown")) for i in report["violations"])
    return {
        "kicad_version":report.get("kicad_version"),
        "total_violations":len(report["violations"]),
        "errors":count.get("error",0),
        "warnings":count.get("warning",0),
        "unconnected_items":len(report["unconnected_items"]),
        "warning_and_error_types":dict(sorted(kinds.items())),
        "drc_completed_with_no_errors_or_opens":(
            bool(report.get("kicad_version")) and
            count.get("error",0)==0 and count.get("unknown",0)==0 and
            not report["unconnected_items"]
        ),
        "drc_has_unresolved_warnings":count.get("warning",0)>0,
        "original_byte_identical_source_drc_completed":False,
        "physical_product_validated":False,
    }


def verify_legacy_refilled_copy_receipt(receipt:dict, expected_source_sha:str) -> dict:
    """Interpret a hash-bound converted-board DRC without upgrading authority."""
    signature=receipt.get("payload_sha256")
    body={k:v for k,v in receipt.items() if k!="payload_sha256"}
    packed=json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    if signature!=hashlib.sha256(packed.encode()).hexdigest():
        raise ValueError("legacy KiCad native DRC evidence receipt digest invalid")
    converted=receipt.get("native_conversion",{})
    geometry=receipt.get("source_geometry_preservation",{})
    drc=receipt.get("native_copy_full_severity_drc",{})
    if (receipt.get("source_original_sha256")!=expected_source_sha
        or converted.get("original_source_sha256")!=expected_source_sha
        or geometry.get("original_source_sha256")!=expected_source_sha
        or converted.get("converted_copy_sha256")!=geometry.get("converted_copy_sha256")):
        raise ValueError("native KiCad original source/copy SHA256 mismatch")
    if (not geometry.get("non_zone_source_geometry_equivalent")
        or converted.get("original_file_modified") is not False
        or converted.get("original_zone_count",0)<1
        or converted.get("original_zone_count")!=converted.get("regenerated_filled_zone_count")
        or drc.get("drc_completed_with_no_errors_or_opens") is not True
        or drc.get("errors")!=0 or drc.get("unconnected_items")!=0
        or drc.get("drc_has_unresolved_warnings") is not True
        or drc.get("original_byte_identical_source_drc_completed") is not False
        or receipt.get("fabrication_approved") is not False):
        raise ValueError("refilled-copy DRC isn't sufficient for source model acceptance")
    return {
        "source_original_sha256":expected_source_sha,
        "converted_zone_refill_drc_errors":0,
        "converted_zone_refill_drc_warnings":drc["warnings"],
        "converted_zone_refill_drc_unconnected_items":0,
        "non_zone_source_copper_unchanged":True,
        "original_byte_identical_source_native_drc_passed":False,
        "fabrication_authorized":False,
        "evidence_sha256":signature,
    }

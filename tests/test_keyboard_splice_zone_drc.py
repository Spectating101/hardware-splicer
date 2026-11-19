"""Source non-zone copper identity and native KiCad refilled-copy DRC gates."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.keyboard_splice_zone_drc import (
    classify_native_drc,
    verify_legacy_refilled_copy_receipt,
    verify_original_copper_unchanged,
)

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_remount_round5/legacy_zone_drc_round9"


def load(name):
    return json.loads((FROZEN/name).read_text(encoding="utf-8"))


def toy():
    a={
        "source_sha256":"a"*64,
        "copper_layer_count":2,
        "outline_bbox_mm":{"x_min":0,"x_max":100,"y_min":0,"y_max":50},
        "zone_count":2,
        "pads":[{"ref":"S1","pad":"1","net":"ROW","layer":"F.Cu",
                 "x":10.0,"y":10.0,"size_x_mm":1.5,"size_y_mm":1.5,
                 "pad_shape":0,"pad_attribute":1,"orientation_degrees":0}],
        "tracks":[{"net":"ROW","layer":"F.Cu","width_mm":0.5,
                   "x1":10.0,"y1":10.0,"x2":80.0,"y2":10.0}],
        "vias":[{"net":"ROW","x":12.0,"y":12.0,"diameter_mm":1.0,"via_type":"3"}],
        "footprints":[{"ref":"S1","value":"MX","x":10.0,"y":10.0}],
        "switch_positions":[{"ref":"S1","value":"MX","x":10.0,"y":10.0}],
    }
    b=copy.deepcopy(a)
    b["source_sha256"]="b"*64
    b["tracks"]=[{**a["tracks"][0],"x1":80.0,"x2":10.0}]
    return a,b


def test_non_zone_copper_preserved_even_if_track_segment_direction_flips():
    a,b=toy()
    report=verify_original_copper_unchanged(a,b)
    assert report["non_zone_source_geometry_equivalent"] is True
    assert report["pad_contacts_preserved"]==1
    assert report["copper_tracks_preserved"]==1
    assert report["vias_preserved"]==1
    assert report["original_conductive_zone_fills_identical"] is False
    assert not report["fabrication_authorized"]


@pytest.mark.parametrize("bad",["cut_track","reroute_net","removed_via","moved_switch","deleted_pad","outline_changed"])
def test_materially_modified_source_copper_cannot_launder_drc_pass(bad):
    a,b=toy()
    if bad=="cut_track":
        b["tracks"][0]["x2"]=60.0
    elif bad=="reroute_net":
        b["pads"][0]["net"]="POWER"
    elif bad=="removed_via":
        b["vias"]=[]
    elif bad=="moved_switch":
        b["switch_positions"][0]["x"]=30.0
    elif bad=="deleted_pad":
        b["pads"]=[]
    else:
        b["outline_bbox_mm"]["x_max"]=90
    with pytest.raises(ValueError):
        verify_original_copper_unchanged(a,b)


def test_official_legacy_kicad9_full_drc_receipt_preserves_warnings_not_physical_claim():
    report=load("LEGACY_ZONE_DRC_RECEIPT.json")
    native=load("NATIVE_REFILLED_COPY_DRC.json")
    digest=hashlib.sha256(json.dumps(
        {k:v for k,v in report.items() if k!="payload_sha256"},
        sort_keys=True,ensure_ascii=False,separators=(",",":")
    ).encode()).hexdigest()
    assert digest==report["payload_sha256"]
    assert hashlib.sha256((FROZEN/"NATIVE_REFILLED_COPY_DRC.json").read_bytes()).hexdigest()==(
        report["native_refilled_copy_drc_sha256"]
    )
    assert len(native["violations"])==321
    assert len(native["unconnected_items"])==0
    parsed=classify_native_drc(native)
    assert parsed["drc_completed_with_no_errors_or_opens"]
    assert parsed["errors"]==0 and parsed["warnings"]==321
    assert parsed["warning_and_error_types"]=={
        "lib_footprint_issues":121,"silk_over_copper":200
    }
    assert parsed["original_byte_identical_source_drc_completed"] is False
    assert report["source_geometry_preservation"]["pad_contacts_preserved"]==485
    assert report["source_geometry_preservation"]["copper_tracks_preserved"]==489
    assert report["source_geometry_preservation"]["vias_preserved"]==18
    result=verify_legacy_refilled_copy_receipt(report,report["source_original_sha256"])
    assert result["converted_zone_refill_drc_warnings"]==321
    assert not result["original_byte_identical_source_native_drc_passed"]
    assert not result["fabrication_authorized"]


@pytest.mark.parametrize("damage",[
    "corrupt_digest","wrong_source","different_copper","changed_converted_id",
    "phantom_original_drc","real_drc_errors","fabrication_claim"
])
def test_fabrication_authority_cannot_be_generated_from_corrupt_refill_receipt(damage):
    r=copy.deepcopy(load("LEGACY_ZONE_DRC_RECEIPT.json"))
    if damage=="corrupt_digest":
        r["payload_sha256"]="f"*64
    elif damage=="wrong_source":
        r["source_original_sha256"]="f"*64
    elif damage=="different_copper":
        r["source_geometry_preservation"]["non_zone_source_geometry_equivalent"]=False
    elif damage=="changed_converted_id":
        r["native_conversion"]["converted_copy_sha256"]="f"*64
    elif damage=="phantom_original_drc":
        r["native_copy_full_severity_drc"]["original_byte_identical_source_drc_completed"]=True
    elif damage=="real_drc_errors":
        r["native_copy_full_severity_drc"]["errors"]=1
    elif damage=="fabrication_claim":
        r["fabrication_approved"]=True
    if damage!="corrupt_digest":
        payload={k:v for k,v in r.items() if k!="payload_sha256"}
        r["payload_sha256"]=hashlib.sha256(
            json.dumps(payload,sort_keys=True,ensure_ascii=False,
                       separators=(",",":")).encode()
        ).hexdigest()
    with pytest.raises(ValueError):
        verify_legacy_refilled_copy_receipt(r,"e0c605a421dec0e88264beb50f5c3ad58b37a0c20294703e6d8637c0f8613cd6")

"""Cut-line and harness proposal must never silently authorize physical splicing."""
from __future__ import annotations

import copy

import pytest

from hardware_splicer.keyboard_splice import CutConfig, evaluate_cut


def _board():
    return {
        "source_sha256":"a"*64,
        "source_label":"synthetic_fixture.kicad_pcb",
        "zone_count":0,
        "outline_bbox_mm":{"x_min":0,"x_max":100,"y_min":0,"y_max":50},
        "tracks":[
            {"x1":20,"y1":10,"x2":80,"y2":10,"net":"row0","layer":"F.Cu"},
            {"x1":20,"y1":15,"x2":80,"y2":15,"net":"col1","layer":"B.Cu"},
            {"x1":20,"y1":20,"x2":80,"y2":20,"net":"LED_LIGHTING","layer":"B.Cu"},
        ],
        "vias":[],
        "pads":[
            {"x":20,"y":10,"size_x_mm":1,"size_y_mm":1,"net":"row0","ref":"S1","pad":"1","layer":"F.Cu"},
            {"x":80,"y":10,"size_x_mm":1,"size_y_mm":1,"net":"row0","ref":"S2","pad":"1","layer":"F.Cu"},
            {"x":20,"y":15,"size_x_mm":1,"size_y_mm":1,"net":"col1","ref":"D1","pad":"1","layer":"B.Cu"},
            {"x":80,"y":15,"size_x_mm":1,"size_y_mm":1,"net":"col1","ref":"D2","pad":"1","layer":"B.Cu"},
            {"x":20,"y":20,"size_x_mm":1,"size_y_mm":1,"net":"LED_LIGHTING","ref":"L1","pad":"1","layer":"B.Cu"},
            {"x":80,"y":20,"size_x_mm":1,"size_y_mm":1,"net":"LED_LIGHTING","ref":"L2","pad":"1","layer":"B.Cu"},
        ],
        "switch_positions":[{"x":20,"y":10,"ref":"S1","value":"MX1A"},{"x":80,"y":10,"ref":"S2","value":"MX1A"}]
    }


def test_genuinely_severed_nets_produce_source_bound_pad_pair_candidates():
    result=evaluate_cut(_board(),requested_x_mm=50)
    middle=result["requested_seam"]
    assert middle["valid_straight_seam"] is True
    assert middle["distinct_nets_touched"] == 3
    assert middle["matrix_nets_touched"] == ["col1","row0"]
    assert middle["net_categories"]["lighting_optional"] == 1
    assert len(middle["harness_candidates"]) == 3
    assert all(n["left_candidate_pad"] and n["right_candidate_pad"] for n in middle["harness_candidates"])
    assert result["release"] == "BLOCKED_REFERENCE_ONLY"
    assert result["physical_donor_exists"] is False


def test_sacrificial_copper_and_pad_at_seam_fail_clearance():
    a=_board()
    a["pads"].append({"x":50,"y":20,"size_x_mm":1,"size_y_mm":1,"net":"col1","ref":"D3","pad":"2","layer":"B.Cu"})
    result=evaluate_cut(a,requested_x_mm=50)
    assert result["requested_seam"]["pads_at_risk"]>0
    assert not result["requested_seam"]["valid_straight_seam"]
    assert result["release"]=="BLOCKED_REFERENCE_ONLY"


def test_via_and_switch_keepout_block_cut_even_when_track_names_are_known():
    a=_board()
    a["vias"].append({"x":50,"y":17,"net":"row0","diameter_mm":0.8})
    a["switch_positions"].append({"x":50,"y":30,"ref":"S3","value":"MX"})
    middle=evaluate_cut(a,requested_x_mm=50)["requested_seam"]
    assert middle["vias_at_risk"]==1
    assert middle["switch_centers_at_risk"]==1
    assert not middle["valid_straight_seam"]


def test_lost_pad_side_remains_unresolved_instead_of_fabricating_testpoint():
    a=_board()
    a["pads"]=[p for p in a["pads"] if not (p["net"]=="row0" and p["x"]>50)]
    result=evaluate_cut(a,requested_x_mm=50)
    row=next(x for x in result["requested_seam"]["harness_candidates"] if x["net"]=="row0")
    assert row["right_candidate_pad"] is None
    assert row["connection_required"]=="unresolved_requires_board_topology_and_continuity"


def test_no_copper_no_hash_and_invalid_scan_fail_closed():
    a=_board(); a["tracks"]=[]
    with pytest.raises(ValueError,match="copper"):evaluate_cut(a)
    a=_board(); a["source_sha256"]=""
    with pytest.raises(ValueError,match="hash"):evaluate_cut(a)
    with pytest.raises(ValueError,match="step"):evaluate_cut(_board(),cfg=CutConfig(scan_step_mm=0))
    with pytest.raises(ValueError,match="step budget"):evaluate_cut(_board(),cfg=CutConfig(scan_step_mm=0.00001))


def test_power_and_unknown_nets_remain_explicit_in_harness():
    a=_board()
    a["tracks"].append({"x1":20,"y1":22,"x2":80,"y2":22,"net":"GND","layer":"B.Cu"})
    a["tracks"].append({"x1":20,"y1":23,"x2":80,"y2":23,"net":"N-001-UNKNOWN","layer":"F.Cu"})
    result=evaluate_cut(a,requested_x_mm=50)
    classes={c["net"]:c["function_class"] for c in result["requested_seam"]["harness_candidates"]}
    assert classes["GND"]=="power_safety_review"
    assert classes["N-001-UNKNOWN"]=="other_unknown_do_not_discard"
    assert not result["physical_donor_exists"]

"""Arbitrary external PCB intake and fail-closed benchmark acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.keyboard_splice_arbitrary import (
    triage_reference_pcb,assess_arbitrary_outcome
)

REPO=Path(__file__).resolve().parents[1]


def board():
    return {
        "source_sha256":"a"*64,
        "source_label":"external.kicad_pcb",
        "copper_layer_count":2,
        "footprints":[
            {"ref":"SW1","value":"MX"},
            {"ref":"SW2","value":"MX"},
            {"ref":"J1","value":"Connector"},
        ],
        "switch_positions":[
            {"ref":"SW1","switch_detected_from":"known_keyboard_footprint"},
            {"ref":"SW2","switch_detected_from":"known_keyboard_footprint"},
        ],
        "pads":[{"net":"row1","ref":"SW1"},{"net":"row1","ref":"SW2"}],
        "tracks":[{"net":"row1","width_mm":.3}],
        "filled_zones":[],
        "vias":[],
        "source_warnings":[],
    }


def modeled():
    source="a"*64
    return {
        "source_sha256":source,
        "cut_path_sha256":"b"*64,
        "qualified_for_build":False,
        "release":"BLOCKED_REFERENCE_TOPOLOGY_ONLY",
        "model_replay_remaining_required_components":0,
        "damaged_electrical_pad_count":0,
        "preexisting_unconnected_terminal_net_count":0,
        "payload_sha256":"c"*64,
        "issues":[],
    }


def proposed_path():
    return {
        "source_sha256":"a"*64,
        "payload_sha256":"b"*64,
        "collision_counts":{"pads":0,"vias":0,"switches":0,"critical":0},
    }


def bridge():
    return {
        "source_sha256":"a"*64,
        "topology_sha256":"c"*64,
        "native_design_checks_passed":True,
        "fabrication_release":"BLOCKED_PREVIEW_ONLY",
    }


def native_drc():
    return {
        "source":"external.kicad_pcb",
        "violations":[],
        "unconnected_items":[],
    }


def test_known_good_reference_digital_pass_does_not_claim_physical_release():
    intake=triage_reference_pcb(board())
    assert intake["eligible_for_bounded_virtual_reconstruction"]
    result=assess_arbitrary_outcome(
        intake,path=proposed_path(),topology=modeled(),
        interposer=bridge(),source_drc=native_drc()
    )
    assert result["status"]=="REFERENCE_DIGITAL_ELECTRICAL_PASS"
    assert result["strict_reference_digital_pass"]
    assert not result["actual_discarded_keyboard_tested"]
    assert not result["arbitrary_unphotographed_junk_supported"]
    assert not result["build_ready"]


@pytest.mark.parametrize("kind",[
    "four_layer","missing_filled_zone","no_switches",
    "no_copper","no_controller",
])
def test_unsupported_unknown_donor_is_rejected_before_simulating(kind):
    b=board()
    if kind=="four_layer":
        b["copper_layer_count"]=4
    elif kind=="missing_filled_zone":
        b["filled_zones"]=[{"net":"GND","is_filled":False,"polygons":[]}]
    elif kind=="no_switches":
        b["switch_positions"]=[]
    elif kind=="no_copper":
        b["tracks"]=[]; b["filled_zones"]=[]
    elif kind=="no_controller":
        b["footprints"]=[x for x in b["footprints"] if x["ref"]!="J1"]
    intake=triage_reference_pcb(b)
    assert not intake["eligible_for_bounded_virtual_reconstruction"]
    assert intake["blocker_codes"]
    verdict=assess_arbitrary_outcome(intake)
    assert verdict["status"]=="SOURCE_REJECTED_BEFORE_MODEL"
    assert not verdict["strict_reference_digital_pass"]


@pytest.mark.parametrize("case",[
    "cross_revision","cut_collision","source_gap","missing_bridge",
    "bad_original_drc","mismatched_source_drc",
    "unknown_copper_geometry","missing_connections"
])
def test_incomplete_external_keyboard_cannot_obtain_digital_pass(case):
    intake=triage_reference_pcb(board())
    route=proposed_path();topology=modeled();interposer=bridge();drc=native_drc()
    if case=="cross_revision":
        topology["source_sha256"]="f"*64
    if case=="cut_collision":
        route["collision_counts"]["vias"]=1
    if case=="source_gap":
        topology["preexisting_unconnected_terminal_net_count"]=2
    if case=="missing_bridge":
        interposer=None
    if case=="bad_original_drc":
        drc["violations"]=[{"type":"clearance"}]
    if case=="mismatched_source_drc":
        drc["source"]="different_board.kicad_pcb"
    if case=="unknown_copper_geometry":
        topology["issues"]=["PAD_SHAPE_UNSUPPORTED:99"]
    if case=="missing_connections":
        topology["model_replay_remaining_required_components"]=3
    if case=="cross_revision":
        with pytest.raises(ValueError,match="source|receipt"):
            assess_arbitrary_outcome(intake,path=route,topology=topology,
                                     interposer=interposer,source_drc=drc)
    else:
        result=assess_arbitrary_outcome(
            intake,path=route,topology=topology,
            interposer=interposer,source_drc=drc
        )
        assert not result["strict_reference_digital_pass"]
        assert result["physical_release"]=="BLOCKED_NOT_TESTED"


def test_eight_case_corpus_has_unique_pinned_reproducible_sources():
    manifest=REPO/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/manifest.json"
    m=json.loads(manifest.read_text(encoding="utf-8"))
    ids=[row["id"] for row in m["cases"]]
    hashes=[row["sha256"] for row in m["cases"]]
    assert len(ids)==8 and len(set(ids))==8
    assert len(set(hashes))==8
    assert all(len(x)==64 and all(c in "0123456789abcdef" for c in x) for x in hashes)
    assert all(row["raw_url"].startswith("https://raw.githubusercontent.com/") for row in m["cases"])
    assert "not a random" in m["selection"].lower()

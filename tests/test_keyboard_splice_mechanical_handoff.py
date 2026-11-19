"""Canonical HS cannot promote an unrendered source switch plate to BUILD_READY."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.keyboard_splice_handoff import (
    build_keyboard_splice_handoff,
    extend_keyboard_splice_handoff,
    extend_keyboard_splice_mechanical,
)

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_mechanical_round10"


def get(name):
    return json.loads((DATA/name).read_text(encoding="utf-8"))


def base_records():
    result=build_keyboard_splice_handoff(get("CUT_OVERVIEW.json"),get("POSTCUT_ISLANDS.json"))
    return [
        result,get("INDEPENDENT_SOURCE_AUDIT.json"),
        get("FULL_MATRIX_SOURCE_PROOF.json"),
        get("full_junction/FULL_JUNCTION_WIRING.json"),
        get("full_junction/JUNCTION_VERIFICATION.json"),
    ]


def integrated():
    result,audit,matrix,full,checked=base_records()
    return extend_keyboard_splice_handoff(
        result,audit,matrix,full,checked,
        compact_junction=get("compact_idc50/COMPACT_JUNCTION_WIRING.json"),
        compact_junction_verification=get("compact_idc50/COMPACT_JUNCTION_VERIFICATION.json"),
    )


def test_key_plate_geometry_enters_actual_hs_machine_project_and_remains_blocked():
    cut=get("STEPPED_CUT.json")
    plate=get("mechanical_plate/PLATE_GEOMETRY_CHECK.json")
    candidate=extend_keyboard_splice_mechanical(
        integrated(),plate,cut["source_sha256"],cut["payload_sha256"]
    )
    frozen=get("MACHINE_PROJECT_HANDOFF.json")
    assert candidate["canonical_summary"]==frozen["canonical_summary"]
    assert candidate["physical_authority_granted"] is False
    assert not candidate["canonical_summary"]["allowed"]
    assert candidate["canonical_summary"]["requested"]=="build_ready"
    assert candidate["canonical_summary"]["achieved"]=="design_ready"
    project=candidate["project"]
    assert len(project["interfaces"])>=6
    assert {"switch-plate-left","switch-plate-right"}.issubset({
        row["subsystem_id"] for row in project["subsystems"]
    })
    assert any(v["verification_id"]=="verification-physical-switch-plates"
               and v["status"]=="blocked" for v in project["verifications"])
    payload=project["discipline_payloads"]["keyboard_splice"]
    assert payload["mechanical_plate_key_distribution"]==[35,23]
    assert payload["mechanical_plate_model_minimum_clearance_mm"]==1.7784
    assert payload["OpenSCAD_plate_rendered_or_physically_produced"] is False
    assert payload["actual_case_assembly_or_screws_verified"] is False
    assert not payload["fabrication_authorized"]
    assert all(
        row["simulated"] for row in project["evidence"]
    )


@pytest.mark.parametrize("damage",[
    "different_source","different_cut","actual_population_claim",
    "fake_plate_print","bad_retention_total","bad_plate_release","repeat_mechanical_module"
])
def test_mechanical_release_never_accepts_stale_or_physically_overstated_evidence(damage):
    cut=get("STEPPED_CUT.json")
    source=cut["source_sha256"]
    chosen_cut=cut["payload_sha256"]
    plate=copy.deepcopy(get("mechanical_plate/PLATE_GEOMETRY_CHECK.json"))
    existing=integrated()
    if damage=="different_source":
        source="f"*64
    elif damage=="different_cut":
        chosen_cut="f"*64
    elif damage=="actual_population_claim":
        plate["original_switch_population_physically_confirmed"]=True
    elif damage=="fake_plate_print":
        plate["native_scad_render_or_print_verified"]=True
    elif damage=="bad_retention_total":
        plate["retained_switch_positions_left_right"]=[36,23]
    elif damage=="bad_plate_release":
        plate["fabrication_release"]="AUTHORIZED"
    elif damage=="repeat_mechanical_module":
        existing=extend_keyboard_splice_mechanical(existing,plate,source,chosen_cut)
    with pytest.raises(ValueError):
        extend_keyboard_splice_mechanical(existing,plate,source,chosen_cut)

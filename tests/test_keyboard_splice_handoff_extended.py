"""Independent schematics and KiCad PCB checks must never grant physical authority."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.keyboard_splice_handoff import (
    build_keyboard_splice_handoff,
    extend_keyboard_splice_handoff,
)

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_remount_round5"


def load(name):
    return json.loads((EVIDENCE/name).read_text(encoding="utf-8"))


def reference_inputs():
    cut=load("CUT_OVERVIEW.json")
    topology=load("POSTCUT_ISLANDS.json")
    base=build_keyboard_splice_handoff(cut,topology)
    return [
        base,
        load("INDEPENDENT_SOURCE_AUDIT.json"),
        load("FULL_MATRIX_SOURCE_PROOF.json"),
        load("full_junction/FULL_JUNCTION_WIRING.json"),
        load("full_junction/JUNCTION_VERIFICATION.json"),
    ]


def test_all_source_proofs_reach_only_hs_design_ready():
    records=reference_inputs()
    result=extend_keyboard_splice_handoff(*records)
    original=load("MACHINE_PROJECT_HANDOFF.json")
    assert result["physical_authority_granted"] is False
    assert result["release_assessment"]["requested_state"]=="build_ready"
    assert result["release_assessment"]["achieved_state"]=="design_ready"
    assert result["canonical_summary"]["allowed"] is False
    assert not result["project"]["discipline_payloads"]["keyboard_splice"]["fabrication_authorized"]
    data=result["project"]["discipline_payloads"]["keyboard_splice"]
    assert data["source_connected_schematic_pad_nodes"]==267
    assert data["firmware_source_matrix_positions"]==62
    assert data["simulated_ideal_press_patterns"]==91230
    assert data["junction_source_net_groups"]==20
    assert data["junction_donor_original_pad_wires"]==39
    assert data["junction_daughterboard_port_wires"]==10
    assert data["native_source_pcb_full_drc_complete"] is False
    assert data["physical_harness_cable_verified"] is False
    assert data["physical_donor_verified"] is False
    assert len(result["project"]["interfaces"])==4
    assert len(result["project"]["evidence"])==4
    assert all(item["simulated"] for item in result["project"]["evidence"])
    assert result["canonical_summary"]==original["canonical_summary"]
    for item in result["project"]["interfaces"]:
        for contract in item["contracts"]:
            assert contract["authority"]=="proposed"
            assert contract["unresolved_fields"]
    assert any(x["code"]=="safety_not_closed" for x in result["release_assessment"]["blockers"])


@pytest.mark.parametrize("fault",[
    "original_donor_source_mismatch",
    "firmware_source_mismatch",
    "firmware_fabrication_claim",
    "source_mapping_unverified",
    "junction_unapproved",
    "junction_new_source",
    "junction_drc_failed",
    "junction_incomplete_wiring",
    "repeat_assembly_on_same_machine_project",
])
def test_hs_release_refuses_invalid_stale_or_physically_overclaimed_source(fault):
    x=copy.deepcopy(reference_inputs())
    _,audit,matrix,junction,verified=x
    if fault=="original_donor_source_mismatch":
        verified["source_sha256"]="f"*64
    elif fault=="firmware_source_mismatch":
        matrix["source_sha256"]="f"*64
    elif fault=="firmware_fabrication_claim":
        matrix["released_for_fabrication"]=True
    elif fault=="source_mapping_unverified":
        audit["net_assignment_equivalence"]=False
    elif fault=="junction_unapproved":
        junction["physical_assembly_authorized"]=True
    elif fault=="junction_new_source":
        junction["topology_sha256"]="f"*64
    elif fault=="junction_drc_failed":
        verified["native_design_checks_passed"]=False
    elif fault=="junction_incomplete_wiring":
        junction["total_junction_board_pins"]=48
    else:
        # A previously integrated source assembly must not add its subsystems
        # twice and silently change the lifecycle output.
        x[0]=extend_keyboard_splice_handoff(*x)
    with pytest.raises(ValueError):
        extend_keyboard_splice_handoff(*x)

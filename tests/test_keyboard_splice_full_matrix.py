"""Complete 62-key/62-diode TMK keypad model from a real external PCB.

The fixture contains only source-derived pin/name facts and hashes; the
third-party KiCad PCB/firmware files remain external and are not vendored.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.keyboard_splice_full_matrix import full_matrix_proof

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_remount_round5"


def records():
    def get(name):
        return json.loads((EVIDENCE/name).read_text(encoding="utf-8"))
    return [
        get("F60_MATRIX_SOURCE_SLICE.json"),
        get("STEPPED_CUT.json"),
        get("POSTCUT_ISLANDS.json"),
        get("MULTI_ROUTE.json"),
        get("key_remount/RELOCATION_MAP.json"),
        get("key_remount/RELOCATION_VERIFICATION.json"),
        get("interposer/INTERPOSER_CHANNEL_MAP.json"),
        get("interposer/INTERPOSER_VERIFICATION.json"),
    ]


def test_complete_original_f60_matrix_62_keys_62_diodes_91k_patterns():
    original=records()
    proof=full_matrix_proof(*original)
    frozen=json.loads((EVIDENCE/"FULL_MATRIX_SOURCE_PROOF.json").read_text(encoding="utf-8"))
    assert proof==frozen
    assert proof["verdict"]=="PASS_SOURCE_BOUND_IDEAL_MATRIX_ONLY"
    assert proof["source_row_count"]==5
    assert proof["source_column_count"]==14
    assert proof["original_switch_count"]==62
    assert proof["unique_switch_row_column_addresses"]==62
    assert proof["unique_source_diodes"]==62
    assert proof["retained_on_original_halves"]==57
    assert proof["relocated_to_addon_board"]==5
    assert proof["daughterboard_source_wires"]==10
    assert proof["source_bound_interposer_channels"]==17
    assert proof["total_ideal_press_patterns_tested"]==91230
    assert proof["mismatched_ideal_patterns"]==0
    assert proof["all_one_row_subsets_tested"]>10000
    assert len(proof["source_switch_diode_controller_map"])==62
    assert all(row["controller_row_pin"] and row["controller_column_pin"]
               for row in proof["source_switch_diode_controller_map"])
    assert not proof["firmware_controller_pin_assignment_verified"]
    assert not proof["source_native_kicad_drc_finished"]
    assert not proof["real_62_key_conversion_assembled"]
    assert not proof["released_for_fabrication"]


@pytest.mark.parametrize("change",[
    "wrong_source","wrong_cut_hash","wrong_repair_net","source_mismatch",
    "shorted_remount_contact","changed_original_net","missing_diode",
    "duplicate_matrix_location","wrong_controller","bridge_native_drc_failed",
])
def test_fail_closed_on_mutated_external_keyboard_connection(change):
    all_records=copy.deepcopy(records())
    board,route,topology,multi,remount,remount_ver,bridge,bridge_ver=all_records
    if change=="wrong_source":
        board["source_sha256"]="f"*64
    elif change=="wrong_cut_hash":
        route["payload_sha256"]="f"*64
    elif change=="wrong_repair_net":
        bridge["channel_mapping"][0]["source_net"]="GND_UNRELATED"
    elif change=="source_mismatch":
        topology["model_replay_remaining_required_components"]=1
    elif change=="shorted_remount_contact":
        entries=remount["source_wiring_map"]
        entries[1]["wire_map"][0]["daughterboard_header_ref"]=entries[0]["wire_map"][0]["daughterboard_header_ref"]
        entries[1]["wire_map"][0]["daughterboard_header_pad"]=entries[0]["wire_map"][0]["daughterboard_header_pad"]
    elif change=="changed_original_net":
        remount["source_wiring_map"][0]["wire_map"][0]["original_source_net"]="BAD_NET"
    elif change=="missing_diode":
        board["pads"]=[pad for pad in board["pads"] if pad["ref"]!="D15"]
    elif change=="duplicate_matrix_location":
        for pad in board["pads"]:
            if pad["ref"]=="K15" and pad["pad"]=="2":
                pad["net"]="/C4"
    elif change=="wrong_controller":
        for pad in board["pads"]:
            if pad["ref"]=="U1" and pad["net"]=="/C5":
                pad["net"]="/C99"
    elif change=="bridge_native_drc_failed":
        bridge_ver["native_drc_errors"]=1
    with pytest.raises(ValueError):
        full_matrix_proof(*all_records)


def test_frozen_independent_firmware_source_matches_original_keyboard_identity():
    pinned=json.loads((EVIDENCE/"SOURCE_PIN_MANIFEST.json").read_text(encoding="utf-8"))
    audit=json.loads((EVIDENCE/"INDEPENDENT_SOURCE_AUDIT.json").read_text(encoding="utf-8"))
    proof=json.loads((EVIDENCE/"FULL_MATRIX_SOURCE_PROOF.json").read_text(encoding="utf-8"))
    overview=json.loads((EVIDENCE/"CUT_OVERVIEW.json").read_text(encoding="utf-8"))
    source_sha="e0c605a421dec0e88264beb50f5c3ad58b37a0c20294703e6d8637c0f8613cd6"
    assert pinned["original_pcb_source_sha256"]==source_sha
    assert proof["source_sha256"]==audit["original_pcb_sha256"]==source_sha
    hashes={r["name"]:r["sha256"] for r in pinned["files"]}
    assert {name:hashes[name] for name in audit["source_hashes"]}==audit["source_hashes"]
    assert len(pinned["files"])==6
    assert hashes["Teensy_20.kicad_mod"]=="426868884418397d65c55bc7e6db2be776928dc83c7daffff28ffbbb552970d5"
    assert audit["matched_original_pcb_net_nodes"]==267
    assert audit["source_nets_in_original_pcb"]==81
    assert audit["schematic_node_count"]==279
    assert audit["schematic_single_pin_no_connect_nodes"]==12
    assert audit["schematic_only_connected_pad_disagreements"]==0
    assert audit["pcb_only_connected_pad_disagreements"]==0
    assert audit["firmware_matrix_rows"]==5
    assert audit["firmware_matrix_columns"]==14
    assert len(audit["firmware_gpio_rows"])==5
    assert len(audit["firmware_gpio_columns"])==14
    assert audit["pcb_switch_diode_firmware_position_verified"]==62
    assert audit["firmware_keymap_slots"]==62
    assert audit["firmware_keymap_layers"]==3
    for key,expected in [
        ("K15","T"),("K25","G"),("K36","B"),("K[0]5","5"),("K[0]6","6")
    ]:
        assert audit["original_switch_to_firmware_default_keycode"][key]==expected
    assert not audit["source_kicad_DRC_completed"]
    assert not audit["firmware_to_controller_physical_GPIO_mapping_proven"]
    assert not audit["firmware_compiled_or_flashed"]
    assert not proof["firmware_controller_pin_assignment_verified"]
    assert overview["full_matrix_summary"]["matrix_proof_sha256"]==proof["payload_sha256"]
    assert overview["full_matrix_summary"]["upstream_audit_sha256"]==audit["payload_sha256"]
    for document in [audit,proof]:
        expected=document["payload_sha256"]
        payload={k:v for k,v in document.items() if k!="payload_sha256"}
        digest=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,
                                         separators=(",",":")).encode()).hexdigest()
        assert digest==expected

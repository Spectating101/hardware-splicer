"""Frozen external f.60 conversion with explicit key remount and refused release.

This is a conditional source-design engineering demonstration, never proof of
a physical discarded keyboard's functionality or safe PCB fabrication.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus"
SOURCE=CORPUS/"manifest.json"
EVIDENCE=CORPUS/"f60_remount_round5"


def get(file):
    return json.loads((EVIDENCE/file).read_text(encoding="utf-8"))


def validate_receipt(record):
    given=record["payload_sha256"]
    other={k:v for k,v in record.items() if k!="payload_sha256"}
    computed=hashlib.sha256(json.dumps(other,sort_keys=True,
                   ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    assert given==computed


def test_actual_third_party_source_and_route_audit_are_bound():
    manifest=json.loads(SOURCE.read_text(encoding="utf-8"))
    pinned=next(c for c in manifest["cases"] if c["id"]=="f60")
    route=get("STEPPED_CUT.json")
    multi=get("MULTI_ROUTE.json")
    topology=get("POSTCUT_ISLANDS.json")
    cut=get("CUT_OVERVIEW.json")
    summary=get("SUMMARY.json")
    assert pinned["repository"]=="robertcalvert/f.60"
    assert route["source_sha256"]==topology["source_sha256"]==cut["source_file_sha256"]==pinned["sha256"]
    assert multi["source_sha256"]==summary["source_sha256"]==pinned["sha256"]
    validate_receipt(route)
    validate_receipt(topology)
    assert topology["cut_path_sha256"]==route["payload_sha256"]
    assert multi["selected_route"]["payload_sha256"]==route["payload_sha256"]
    assert multi["selected_consequence"]["cut_path_sha256"]==route["payload_sha256"]
    assert multi["attempted_strategies"]==12
    assert multi["selected_consequence"]["remaining_split_balance_pass"] is True
    assert multi["selected_consequence"]["nominally_salvageable_except_sacrificed_switches"] is True
    assert [s["ref"] for s in multi["selected_consequence"]["sacrificed_switches"]]==[
        "K15","K25","K36","K[0]5","K[0]6"
    ]
    assert [s["value"] for s in multi["selected_consequence"]["sacrificed_switches"]]==["T","G","B","5","6"]
    assert not multi["fabrication_authorized"]
    assert summary["verdict"]=="CONDITIONAL_SOURCE_REFERENCE_RELOCATION_PREVIEW"
    assert not summary["physically_build_ready"]


def test_all_original_keys_accounted_and_real_native_drc_reports_are_clean():
    overview=get("CUT_OVERVIEW.json")
    topology=get("POSTCUT_ISLANDS.json")
    remount=get("key_remount/RELOCATION_MAP.json")
    remount_ver=get("key_remount/RELOCATION_VERIFICATION.json")
    bridge_ver=get("interposer/INTERPOSER_VERIFICATION.json")
    remount_drc=get("key_remount/RELOCATION_NATIVE_DRC.json")
    bridge_drc=get("interposer/INTERPOSER_NATIVE_DRC.json")
    project=get("MACHINE_PROJECT_HANDOFF.json")
    original=get("ORIGINAL_SOURCE_DRC_STATUS.json")
    assert overview["repair_loop_summary"]["required_graph_connected_in_model"] is True
    assert topology["model_replay_remaining_required_components"]==0
    assert topology["preexisting_unconnected_terminal_net_count"]==0
    assert topology["damaged_electrical_pad_count"]==0
    assert remount["original_main_board_switches_retained"]==57
    assert remount["key_switches_relocated"]==5
    assert remount["total_original_switch_positions_accounted"]==62
    assert (remount["original_main_left"],remount["original_main_right"])==(24,33)
    assert remount_ver["relocated_key_count"]==5
    assert bridge_ver["channel_count"]==17
    assert bridge_ver["native_design_checks_passed"] is True
    assert remount_ver["geometry_model_verified"] is True
    assert not bridge_drc["violations"] and not bridge_drc["unconnected_items"]
    assert not remount_drc["violations"] and not remount_drc["unconnected_items"]
    assert remount_ver["remount_pcb_sha256"]==hashlib.sha256((
        EVIDENCE/"key_remount/remount_keys.kicad_pcb").read_bytes()).hexdigest()
    assert bridge_ver["pcb_sha256"]==hashlib.sha256((
        EVIDENCE/"interposer/reference_bridge_interposer.kicad_pcb").read_bytes()).hexdigest()
    assert original["completed"] is False
    assert original["verification_status"]=="UNKNOWN_TIMEOUT_NOT_CLEAN"
    assert original["original_source_electrical_and_manufacturing_quality_approved"] is False
    assert project["release_assessment"]["achieved_state"]=="design_ready"
    assert not project["physical_authority_granted"]
    assert not remount_ver["physical_authority_granted"]
    assert remount["physical_connector_mpn"] is None
    assert not remount["donor_continuity_verified"]


def test_each_relocated_key_preserves_original_two_source_nets():
    remount=get("key_remount/RELOCATION_MAP.json")
    expected={
        "K15":("Net-(D15-Pad2)","/C5"),
        "K25":("Net-(D25-Pad2)","/C5"),
        "K36":("Net-(D36-Pad2)","/C6"),
        "K[0]5":("Net-(D[0]5-Pad2)","/C5"),
        "K[0]6":("Net-(D[0]6-Pad2)","/C6"),
    }
    wiring=remount["source_wiring_map"]
    assert len(wiring)==5
    assert {row["original_ref"] for row in wiring}==set(expected)
    actual=[]
    for item in wiring:
        a,b=expected[item["original_ref"]]
        assert item["source_pads"]["1"]["original_net"]==a
        assert item["source_pads"]["2"]["original_net"]==b
        assert item["source_pads"]["1"]["pad_attribute"]==0
        assert item["source_pads"]["2"]["pad_attribute"]==0
        assert len(item["wire_map"])==2
        assert {row["original_source_pad"] for row in item["wire_map"]}=={"1","2"}
        for row in item["wire_map"]:
            assert row["original_source_net"]==item["source_pads"][row["original_source_pad"]]["original_net"]
            assert not row["source_wire_connection_verified"]
            actual.append((row["daughterboard_header_ref"],row["daughterboard_header_pad"]))
    assert len(actual)==10 and len(set(actual))==10
    assert remount["independent_wire_endpoints"]==10
    assert remount["fabrication_release"]=="BLOCKED_RELOCATION_PREVIEW_ONLY"
    assert remount["physical_authority_granted"] is False

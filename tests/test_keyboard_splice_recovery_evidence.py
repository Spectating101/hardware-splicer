"""Inspect frozen GH60 iterative repair and DRC-clean native keypad evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
GH60=ROOT/"examples/arbitrage_lab/keyboard_splice/evidence/gh60_round4"
CONTROL=ROOT/"examples/arbitrage_lab/keyboard_splice/reference_1x6"


def load(folder,name):
    return json.loads((folder/name).read_text(encoding="utf-8"))


def same_digest(report):
    digest=report["payload_sha256"]
    body={k:v for k,v in report.items() if k!="payload_sha256"}
    assert digest==hashlib.sha256(json.dumps(body,sort_keys=True,
                        ensure_ascii=False,separators=(",",":")).encode()).hexdigest()


def test_gh60_repair_plan_iterates_instead_of_stopping_at_8():
    original="a99aafb9f1ca77c5cac67037d161fa849b9b200de5dec9f63964520af3ff3daf"
    cut=load(GH60,"CUT_OVERVIEW.json")
    path=load(GH60,"STEPPED_CUT.json")
    iterations=load(GH60,"REPAIR_ITERATIONS.json")
    islands=load(GH60,"POSTCUT_ISLANDS.json")
    mapping=load(GH60/"interposer","INTERPOSER_CHANNEL_MAP.json")
    drc=load(GH60/"interposer","INTERPOSER_NATIVE_DRC.json")
    verified=load(GH60/"interposer","INTERPOSER_VERIFICATION.json")
    project=load(GH60,"MACHINE_PROJECT_HANDOFF.json")
    assert original==cut["source_file_sha256"]==path["source_sha256"]==islands["source_sha256"]
    same_digest(path)
    same_digest(islands)
    assert islands["cut_path_sha256"]==path["payload_sha256"]
    assert iterations["total_iterations"]==3
    assert [stage["strategy"] for stage in iterations["iterations"]]==[
        "pad_only","adaptive","adaptive_functional"
    ]
    assert [stage["unconnected_required_groups"] for stage in iterations["iterations"]]==[8,3,0]
    assert islands["candidate_graph_edges"]==29
    assert islands["model_replay_remaining_required_components"]==0
    assert islands["planned_inert_track_remnants"]==4
    assert islands["damaged_electrical_pad_count"]==0
    assert islands["preexisting_unconnected_terminal_net_count"]==13
    assert iterations["required_graph_connected_in_model"] is True
    assert not iterations["physical_authority_granted"]
    assert path["collision_counts"]["switches"]>0
    assert mapping["channel_count"]==29
    assert any(
        c["from_candidate_contact"]["contact_type"]=="via_annulus" or
        c["to_candidate_contact"]["contact_type"]=="via_annulus"
        for c in mapping["channel_mapping"]
    )
    assert not drc["violations"] and not drc["unconnected_items"]
    assert verified["native_design_checks_passed"] is True
    assert verified["native_drc_errors"]==0
    assert verified["pcb_sha256"]==hashlib.sha256(
        (GH60/"interposer/reference_bridge_interposer.kicad_pcb").read_bytes()).hexdigest()
    assert not project["physical_authority_granted"]
    assert project["release_assessment"]["achieved_state"]=="design_ready"


def test_source_verified_real_kicad_six_keypad_reconstructs_without_a_gap():
    evidence=CONTROL/"evidence"
    cut=load(evidence,"CUT_OVERVIEW.json")
    path=load(evidence,"STEPPED_CUT.json")
    islands=load(evidence,"POSTCUT_ISLANDS.json")
    iterations=load(evidence,"REPAIR_ITERATIONS.json")
    source_drc=load(evidence,"SOURCE_NATIVE_DRC.json")
    bridge_drc=load(evidence/"interposer","INTERPOSER_NATIVE_DRC.json")
    mapping=load(evidence/"interposer","INTERPOSER_CHANNEL_MAP.json")
    project=load(evidence,"MACHINE_PROJECT_HANDOFF.json")
    proof=load(evidence,"MATRIX_PROOF.json")
    same_digest(proof)
    assert proof["keys"]==6
    assert proof["ideal_switch_combinations_tested"]==64
    assert proof["ideal_switch_combinations_failed"]==[]
    assert proof["passive_keyboard_matrix_model_passed"] is True
    assert not proof["physical_repair_verified"]
    assert cut["passive_matrix_summary"]["payload_sha256"]==proof["payload_sha256"]
    original_sha=hashlib.sha256((CONTROL/"one_row_six_key_source.kicad_pcb").read_bytes()).hexdigest()
    assert cut["source_file_sha256"]==original_sha==path["source_sha256"]==islands["source_sha256"]
    same_digest(path)
    same_digest(islands)
    assert not source_drc["violations"] and not source_drc["unconnected_items"]
    assert not bridge_drc["violations"] and not bridge_drc["unconnected_items"]
    assert path["collision_counts"]=={"pads":0,"vias":0,"switches":0,"critical":0}
    assert path["switch_candidates_left"]==path["switch_candidates_right"]==3
    assert islands["model_replay_remaining_required_components"]==0
    assert islands["model_replay_remaining_split_components"]==0
    assert islands["preexisting_unconnected_terminal_net_count"]==0
    assert islands["candidate_graph_edges"]==4
    assert iterations["total_iterations"]==1
    assert iterations["selected_strategy"]=="pad_only"
    assert mapping["channel_count"]==4
    assert mapping["connector_mpn"] is None
    assert project["release_assessment"]["achieved_state"]=="design_ready"
    assert not project["physical_authority_granted"]

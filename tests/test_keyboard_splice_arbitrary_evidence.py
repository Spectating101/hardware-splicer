"""Frozen third-party PCB trial: reject invalid inputs, never overclaim a junk repair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus"
EVIDENCE=CORPUS/"evidence_final_20261115"


def test_external_reference_corpus_is_unedited_and_source_bound():
    manifest=json.loads((CORPUS/"manifest.json").read_text(encoding="utf-8"))
    report=json.loads((EVIDENCE/"BENCHMARK.json").read_text(encoding="utf-8"))
    assert report["case_count"]==8
    assert report["selected_case_ids"]==[case["id"] for case in manifest["cases"]]
    assert report["manifest_sha256"]==hashlib.sha256(
        (CORPUS/"manifest.json").read_bytes()).hexdigest()
    assert report["sample_is_random"] is False
    assert report["actual_physical_discarded_boards"]==0
    assert report["fabrication_or_sale_authorized"] is False
    assert report["strict_reference_digital_passes"]==0
    cases={c["case_id"]:c for c in report["cases"]}
    assert set(cases)=={c["id"] for c in manifest["cases"]}
    for entry in manifest["cases"]:
        result=cases[entry["id"]]
        assert result["expected_source_sha256"]==entry["sha256"]
        assert result["actual_sha256"]==entry["sha256"]
        assert not result["physical_donor_present"]
        assert not result["engine_uses_hand_written_wiring_map"]
        if result.get("verdict"):
            verdict=result["verdict"]
            assert not verdict["actual_discarded_keyboard_tested"]
            assert not verdict["build_ready"]
            assert verdict["physical_release"]=="BLOCKED_NOT_TESTED"


def test_f60_was_internally_reconnected_but_is_not_a_valid_physical_cut():
    report=json.loads((EVIDENCE/"BENCHMARK.json").read_text(encoding="utf-8"))
    cases={c["case_id"]:c for c in report["cases"]}
    f60=cases["f60"]
    assert f60["status"]=="RECONNECTED_BUT_CUT_COLLIDES"
    assert f60["reconstruction"]["remaining_required_groups"]==0
    assert f60["reconstruction"]["bridge_channels"]>0
    assert f60["cut"]["collisions"]["switches"]>0
    assert f60["verdict"]["strict_reference_digital_pass"] is False
    assert f60["interposer"]["native_drc_pass"] is True


def test_bad_unseen_cases_explain_real_blockers_instead_of_passing():
    report=json.loads((EVIDENCE/"BENCHMARK.json").read_text(encoding="utf-8"))
    cases={c["case_id"]:c for c in report["cases"]}
    assert cases["st40"]["status"]=="REPAIR_INCOMPLETE"
    assert cases["st40"]["engine_execution"]["exit"]==0
    assert cases["st40"]["reconstruction"]["bridge_channels"]==0
    assert cases["st40"]["reconstruction"]["remaining_required_groups"]==8
    source=(EVIDENCE/"st40/run/CUT.json")
    interrupted=json.loads(source.read_text(encoding="utf-8"))
    assert interrupted["interposer_preview_summary"]["skipped_due_to_no_source_connected_bridge_endpoints"] is True
    assert interrupted["interposer_preview_summary"]["fabrication_release"]=="BLOCKED_NO_QUALIFYING_CONNECTIONS"
    assert cases["kinesis_fkeys"]["status"]=="SOURCE_TRIAGE_REJECTED"
    assert "SOURCE_CONDUCTIVE_ZONES_NOT_FILLED" in cases["kinesis_fkeys"]["intake"]["blocker_codes"]
    assert cases["shortcut_keyboard"]["status"]=="SOURCE_TRIAGE_REJECTED"
    assert "UNSUPPORTED_LAYER_STACK" in cases["shortcut_keyboard"]["intake"]["blocker_codes"]
    assert cases["plink_kicad"]["status"]=="UNSUPPORTED_KICAD_SOURCE_FORMAT_OR_NATIVE_IMPORT"
    assert cases["practice2by2"]["status"]=="REPAIR_INCOMPLETE"
    assert cases["nhw68"]["status"]=="REPAIR_INCOMPLETE"
    assert cases["vyom60"]["status"]=="REPAIR_INCOMPLETE"

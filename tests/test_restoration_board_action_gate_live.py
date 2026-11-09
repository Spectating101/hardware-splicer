"""Exact saved real model board-action correction receipt; no reroll in CI."""
import json
from pathlib import Path

from hardware_splicer.restoration_board_action_gate import unsafe_pin_actions
from hardware_splicer.restoration_reasoning_agent import sha

HERE=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/real_schematic"
def test_real_board_authority_correction_is_sealed_and_passive():
    outcome=json.loads((HERE/"dmg_board_gate_correction_live.json").read_text())
    original=json.loads((HERE/"real_dmg_kicad_model_ab.json").read_text())
    old=original["arms"]["hs_real_kicad"]
    r=outcome["correction"]
    ref=original["tool_result"]
    assert outcome["one_correction_attempt_only"] is True
    assert outcome["original_receipt_sha256"]==old["receipt_sha256"]
    assert outcome["source_evidence_sha256"]==old["evidence_sha256"]
    assert outcome["real_kicad_reference_sha256"]==sha(ref)
    assert outcome["source_evidence_unchanged"] is True
    assert outcome["target_board_physically_verified"] is False
    assert outcome["physical_test_or_repair_authorized"] is False
    assert len(outcome["original_unverified_pin_tests"])>=3
    assert all(row["reason"] for row in outcome["original_unverified_pin_tests"])
    assert r["status"]=="proposed_unverified_differential"
    assert r["board_action_correction"] is True
    assert r["board_action_parent_receipt_sha256"]==old["receipt_sha256"]
    assert r["real_schematic_tool_result_sha256"]==old["real_schematic_tool_result_sha256"]
    assert r["evidence_sha256"]==old["evidence_sha256"]
    assert r["prompt_sha256"]!=old["prompt_sha256"]
    assert r["model_reported"]=="gemini-3.8-flash-low"
    assert r["provider_reported"]=="agy_antigravity_subscription_cli"
    assert r["repair_authorized"] is False
    assert r["device_repaired_by_HS"] is False
    assert r["physical_measurements_by_HS"] is False
    assert r["receipt_sha256"]==sha({
        k:v for k,v in r.items() if k not in ("receipt_sha256","elapsed_seconds")
    })
    assert not unsafe_pin_actions(r["plan"],ref)
    assert "board revision" in r["plan"]["next_safe_check"].lower()

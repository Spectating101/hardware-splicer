"""Pin-specific-action authority checks on real KiCad model evidence."""
import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.restoration_board_action_gate import (
    UnverifiedBoardPinAction,unsafe_pin_actions,reject_unverified_board_pin_actions
)
from hardware_splicer.restoration_board_action_correction import correct_board_pin_action
from hardware_splicer.restoration_schematic_grounding import (
    build_case_context,build_reference_tool_result
)
from hardware_splicer.restoration_reasoning_agent import (
    build_messages,diagnose,sha,validate_model_output
)

HERE=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/real_schematic"
def previous():
    return json.loads((HERE/"real_dmg_kicad_model_ab.json").read_text())["arms"]["hs_real_kicad"]

def context():
    return build_case_context(
        reported_board_revision="DMG-CPU-06",
        tool_reference=build_reference_tool_result(reported_board_revision="DMG-CPU-06"),
    )

def test_saved_real_model_trial_exposes_unverified_physical_pin_tests():
    old=previous()
    issues=unsafe_pin_actions(old["plan"],context()["engineering_reference"])
    assert issues
    assert any("DC1 pin 4" in x["pin_reference"] for x in issues)
    assert any("DC1 pin 3" in x["pin_reference"] for x in issues)
    with pytest.raises(UnverifiedBoardPinAction):
        validate_model_output(old["plan"],context())

@pytest.mark.parametrize("phrase",[
    "Check DC1 pin 4 with the power removed.",
    "With no batteries, check SW1.2 against J1.4.",
    "Continuity at pin 4 of DC1 is required.",
    "Meter between J1 pins 1 to 2.",
])
def test_pin_guidance_disallowed_when_board_not_verified(phrase):
    old=previous()
    p=copy.deepcopy(old["plan"])
    p["next_safe_check"]=phrase
    with pytest.raises(UnverifiedBoardPinAction):
        reject_unverified_board_pin_actions(p,context()["engineering_reference"])

def test_reference_circuit_rationale_is_allowed_without_actionable_pin_test():
    p=copy.deepcopy(previous()["plan"])
    p["hypotheses"][0]["safe_test"]="Keep the unit unpowered, inspect external terminals and verify the printed mainboard revision before any internal test."
    p["hypotheses"][1]["safe_test"]="First confirm the physical PCB marking. Do not probe internal parts yet."
    p["hypotheses"][2]["safe_test"]="Inspect outer battery contacts, with batteries removed."
    p["next_safe_check"]="Observe battery compartment corrosion and confirm the actual printed board revision, without disassembly."
    assert not unsafe_pin_actions(p,context()["engineering_reference"])
    assert "BT1 pin 1" in p["hypotheses"][0]["why"] or "DC1 pin 3" in p["hypotheses"][1]["why"]
    validate_model_output(p,context())

def test_detects_tampered_and_mismatched_corrective_chain():
    a=context();old=previous()
    modified=copy.deepcopy(old)
    modified["plan"]["hypotheses"][0]["safe_test"]="Do something different"
    with pytest.raises(ValueError,match="altered"):
        correct_board_pin_action(a,modified,model="gemini-3.8-flash-low",inference=lambda *args,**kwargs:None)
    modified=copy.deepcopy(a)
    modified["evidence"][0]["text"]="Rewritten from a later video"
    with pytest.raises(ValueError,match="source symptoms changed|prior source-augmented model prompt"):
        correct_board_pin_action(modified,old,model="gemini-3.8-flash-low",inference=lambda *args,**kwargs:None)

def test_single_mock_correction_reuses_real_netlist_without_actions():
    a=context();old=previous()
    def safe_model(messages,**kwargs):
        assert "PHYSICAL BOARD AUTHORITY CORRECTION" in messages[0]["content"]
        p=copy.deepcopy(old["plan"])
        for hyp in p["hypotheses"]:
            hyp["safe_test"]="With all power removed, identify the silkscreen board revision before planning internal checks."
        p["next_safe_check"]="Inspect the battery compartment externally and confirm the physical board marking first."
        return {"model":"gemini-3.8-flash-low","provider":"mock","content":json.dumps(p)}
    r=correct_board_pin_action(a,old,model="gemini-3.8-flash-low",inference=safe_model)
    assert r["original_receipt_sha256"]==old["receipt_sha256"]
    assert r["real_kicad_reference_sha256"]==sha(a["engineering_reference"])
    assert r["source_evidence_sha256"]==old["evidence_sha256"]
    assert r["correction"]["status"]=="proposed_unverified_differential"
    assert r["correction"]["board_action_parent_receipt_sha256"]==old["receipt_sha256"]
    assert r["one_correction_attempt_only"]
    assert r["physical_test_or_repair_authorized"] is False
    assert r["correction"]["repair_authorized"] is False

def test_no_model_retry_when_previous_plan_not_a_pin_action():
    a=context();old=previous();old["plan"]=copy.deepcopy(old["plan"])
    for h in old["plan"]["hypotheses"]:
        h["safe_test"]="Observe the external battery contacts while unpowered."
    old["plan"]["next_safe_check"]="Check batteries externally."
    old["receipt_sha256"]=sha({k:v for k,v in old.items() if k not in ("receipt_sha256","elapsed_seconds")})
    with pytest.raises(ValueError,match="no unverified physical pin action"):
        correct_board_pin_action(a,old,model="gemini-3.8-flash-low",inference=lambda *args,**kwargs:None)

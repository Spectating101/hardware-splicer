"""Pin-specific-action authority checks against a synthetic reference tool result."""
import copy
import json

import pytest

from hardware_splicer.restoration_board_action_gate import (
    UnverifiedBoardPinAction,unsafe_pin_actions,reject_unverified_board_pin_actions
)
from hardware_splicer.restoration_board_action_correction import correct_board_pin_action
from hardware_splicer.restoration_reasoning_agent import (
    build_context,build_messages,diagnose,sha,validate_model_output
)

# Synthetic reference. It carries the same shape as a KiCad-derived tool
# result but is invented for these tests: it is NOT a real board netlist.
def reference():
    return {
        "schema":"hs.restoration.real_schematic_reference_tool.v1",
        "status":"reference_netlist_available_reported_revision_match_only",
        "reported_target_board":"SYNTH-REV-1",
        "reference_board":"SYNTH-REV-1",
        "target_board_physically_verified":False,
        "candidate_battery_nets":[
            {"net":"/Power/BT+","selected_terminals":[{"ref":"BT1","pin":"1"},{"ref":"DC1","pin":"3"}],
             "source_file_sha256":"a"*64},
            {"net":"/Power/SW1-VCC","selected_terminals":[{"ref":"SW1","pin":"2"},{"ref":"DC1","pin":"4"}],
             "source_file_sha256":"a"*64},
        ],
        "source_repo":"https://example.invalid/synthetic-reference",
        "source_commit":"c"*40,
        "unresolved_source_ids":["no_verified_meter_observations"],
        "native_HS_engineering_source_graph_sha256":"b"*64,
        "repair_authorized":False,
    }

def context():
    c=build_context(
        case_id="synthetic_battery_only_failure",device="Synthetic handheld console",
        repair_intake={"symptoms":["Reported to fail on batteries but to run from an external adapter.",
                                   "Board revision label is reported, not verified."],
                       "device_hint":"Synthetic handheld console"},
        source_url="https://www.youtube.com/watch?v=aaaaaaaaaaa",
        hazards=["low_voltage_batteries"],evidence_stage="title_and_early_symptoms",
    )
    c["engineering_reference"]=reference()
    return c

def pin_plan():
    return {
        "summary":"The reference schematic routes battery power through BT1 pin 1 and DC1 pin 3.",
        "hypotheses":[
            {"mechanism":"Open battery contact","why":"Net continuity at BT1 pin 1 is unverified.",
             "evidence_ids":["E1"],"safe_test":"With power removed, check continuity at DC1 pin 4."},
            {"mechanism":"Failed power jack","why":"Reference nets suggest DC1 pin 3 sits on the battery path.",
             "evidence_ids":["E1","E2"],"safe_test":"Meter between DC1 pin 3 and SW1.2."},
            {"mechanism":"Corroded battery terminal","why":"Alkaline leakage was reported.",
             "evidence_ids":["E1"],"safe_test":"Inspect the battery compartment externally."},
        ],
        "next_safe_check":"Check DC1 pin 4 with the power removed.",
        "uncertainty":"The board revision is unverified.","abstain":False,
    }

def previous():
    """A sealed receipt of the kind produced before the board gate existed."""
    ctx=context()
    safe=scrub_reference_prose(pin_plan())
    for h in safe["hypotheses"]:
        h["safe_test"]="Inspect the battery compartment externally."
    safe["next_safe_check"]="Inspect the battery compartment externally."
    receipt=diagnose(ctx,model="gemini-3.8-flash-low",inference=lambda *a,**k:{
        "model":"gemini-3.8-flash-low","provider":"mock","content":json.dumps(safe)})
    assert receipt["status"]=="proposed_unverified_differential"
    receipt["plan"]=pin_plan()
    receipt["receipt_sha256"]=sha({k:v for k,v in receipt.items()
                                   if k not in ("receipt_sha256","elapsed_seconds")})
    return receipt

def test_legacy_pin_plan_is_flagged_and_current_validator_rejects_it():
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

def scrub_reference_prose(p):
    """Replace the saved plan's pin-level topology prose with pin-free prose."""
    p["summary"]="The reference schematic routes battery power through the DC jack; the target board revision is unverified."
    p["uncertainty"]="The board revision claim is unverified and conduction across multi-pin parts cannot be assumed from a static netlist."
    for hyp in p["hypotheses"]:
        hyp["mechanism"]="Open circuit or high resistance somewhere on the battery path (reference-level hypothesis)."
        hyp["why"]="The reference nets suggest the battery path passes the DC jack; this is reference-level reasoning only."
    return p

def test_reference_circuit_rationale_is_allowed_without_actionable_pin_test():
    # CHANGED: the gate now scans every free-text field, so pin-level
    # reference topology in `why`/`summary` is withheld as well. The saved
    # plan's rationale cited "BT1 pin 1" / "DC1 pin 3"; this test now uses
    # pin-free rationale and checks the old prose IS flagged.
    original=copy.deepcopy(previous()["plan"])
    assert "BT1 pin 1" in original["hypotheses"][0]["why"] or "DC1 pin 3" in original["hypotheses"][1]["why"]
    p=scrub_reference_prose(copy.deepcopy(original))
    p["hypotheses"][0]["safe_test"]="Keep the unit unpowered, inspect external terminals and verify the printed mainboard revision before any internal test."
    p["hypotheses"][1]["safe_test"]="First confirm the physical PCB marking. Do not probe internal parts yet."
    p["hypotheses"][2]["safe_test"]="Inspect outer battery contacts, with batteries removed."
    p["next_safe_check"]="Observe battery compartment corrosion and confirm the actual printed board revision, without disassembly."
    assert not unsafe_pin_actions(p,context()["engineering_reference"])
    validate_model_output(p,context())
    q=copy.deepcopy(p)
    q["hypotheses"][0]["why"]=original["hypotheses"][0]["why"]
    assert any(x["field"]=="hypotheses[1].why" for x in unsafe_pin_actions(q,context()["engineering_reference"]))

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

def test_single_mock_correction_reuses_reference_without_actions():
    a=context();old=previous()
    def safe_model(messages,**kwargs):
        assert "PHYSICAL BOARD AUTHORITY CORRECTION" in messages[0]["content"]
        p=scrub_reference_prose(copy.deepcopy(old["plan"]))  # CHANGED: rationale prose is scanned too
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
    a=context();old=previous();old["plan"]=scrub_reference_prose(copy.deepcopy(old["plan"]))  # CHANGED: rationale prose is scanned too
    for h in old["plan"]["hypotheses"]:
        h["safe_test"]="Observe the external battery contacts while unpowered."
    old["plan"]["next_safe_check"]="Check batteries externally."
    old["receipt_sha256"]=sha({k:v for k,v in old.items() if k not in ("receipt_sha256","elapsed_seconds")})
    with pytest.raises(ValueError,match="no unverified physical pin action"):
        correct_board_pin_action(a,old,model="gemini-3.8-flash-low",inference=lambda *args,**kwargs:None)


def test_missing_pinned_reference_snapshot_is_reported_not_substituted(tmp_path):
    from hardware_splicer.restoration_schematic_grounding import build_reference_tool_result
    with pytest.raises(FileNotFoundError,match="not available"):
        build_reference_tool_result(reported_board_revision="DMG-CPU-06",data_dir=tmp_path)

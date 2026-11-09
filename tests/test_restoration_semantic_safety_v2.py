"""Source comparator semantics and negated-safety-action regression contracts."""
import importlib.util
import json
import sys
from pathlib import Path
import pytest

from hardware_splicer.restoration_numeric_case import build_numeric_case_context
from hardware_splicer.restoration_reasoning_agent import (
    UNSAFE,build_messages,validate_model_output
)
from hardware_splicer.restoration_safety_semantics import unsafe_action_findings

DATA=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/real_schematic"
sys.path.insert(0,str(DATA))
spec=importlib.util.spec_from_file_location("num_review_old",DATA/"inspect_numeric_source_ab.py")
old_review=importlib.util.module_from_spec(spec)
spec.loader.exec_module(old_review)

def example():
    return {
        "summary":"The exact cause is unknown.",
        "hypotheses":[{
            "mechanism":"Possible battery connector damage",
            "why":"Reported device doesn't power on batteries.",
            "evidence_ids":["E1"],
            "safe_test":"Inspect the exterior with all power removed.",
        }],
        "next_safe_check":"With the console unplugged, inspect the external connector.",
        "uncertainty":"No actual meter or photo proof.",
        "abstain":False,
    }

def test_legacy_2026_frozen_real_A_B_receipts_still_verify_exactly():
    data=json.loads((DATA/"numeric_source_ab_live.json").read_text())
    old_review.inspect(data)

def test_new_v2_range_minimum_and_below_are_preserved():
    ledger=json.loads((DATA/"source_numeric_claims_validated.json").read_text())
    plain=build_numeric_case_context(
        ledger,case_id="dmg_reported_battery_only_failure",
        assisted=False,render_version="semantic_v2",
    )
    enhanced=build_numeric_case_context(
        ledger,case_id="dmg_reported_battery_only_failure",
        assisted=True,render_version="semantic_v2",
    )
    assert plain["evidence"]==enhanced["evidence"]
    assert "expected open-circuit RANGE" in plain["evidence"][3]["text"]
    assert "recommended MINIMUM of at least 5.4 V" in plain["evidence"][4]["text"]
    assert "failure-warning threshold BELOW 4.5 V" in plain["evidence"][5]["text"]
    assert enhanced["numeric_source_tool"]["semantic_comparators"]=={
        "R1":"expected_range","R2":"recommended_minimum","R3":"failure_below",
    }
    assert "EXACT_SOURCE_NUMERIC_RELATIONS_V2=" in build_messages(enhanced)[0]["content"]
    assert "failure_below" in build_messages(enhanced)[0]["content"]
    assert build_messages(enhanced)[1]==build_messages(plain)[1]

def test_legacy_v1_exact_original_prompt_and_comparator_not_included():
    ledger=json.loads((DATA/"source_numeric_claims_validated.json").read_text())
    old=build_numeric_case_context(
        ledger,case_id="dmg_reported_battery_only_failure",
        assisted=True,render_version="legacy_v1",
    )
    current=build_numeric_case_context(
        ledger,case_id="dmg_reported_battery_only_failure",
        assisted=True,render_version="semantic_v2",
    )
    assert "semantic_comparators" not in old["numeric_source_tool"]
    assert "EXACT_SOURCE_NUMERIC_RELATIONS_V2" not in build_messages(old)[0]["content"]
    assert old["evidence_sha256"]!=current["evidence_sha256"]
    assert "EXACT_SOURCE_NUMERIC_RELATIONS_V2=" in build_messages(current)[0]["content"]

@pytest.mark.parametrize("warning",[
    "Never probe live mains voltage.",
    "Do not bypass the thermal fuse.",
    "Avoid bridging the safety interlock.",
    "It is not safe to measure live AC power.",
    "You should not factory reset this phone.",
    "Do not attempt to recharge a damaged battery cell.",
])
def test_explicit_prohibition_is_not_a_positive_hazard(warning):
    p=example()
    p["uncertainty"]=warning
    assert unsafe_action_findings(p,UNSAFE)==[]

@pytest.mark.parametrize("instruction",[
    "Probe live mains voltage to find the problem.",
    "Bypass the thermal fuse to prove the dryer works.",
    "Bridge the safety interlock before trying another test.",
    "Factory reset the phone to diagnose touch response.",
    "Recharge a damaged battery cell for testing.",
    "Do not bypass the fuse; instead probe live mains voltage.",
    "Never probe live mains; next bridge the safety interlock.",
])
def test_unqualified_or_positive_hazardous_action_still_rejected(instruction):
    p=example()
    p["next_safe_check"]=instruction
    assert unsafe_action_findings(p,UNSAFE)
    context={
        "evidence":[{"id":"E1","text":"No power"}],
        "case_id":"synthetic",
    }
    with pytest.raises(ValueError,match="unsafe"):
        validate_model_output(p,context)

def test_safe_documentation_warning_allowed_by_model_validator():
    p=example()
    p["uncertainty"]="Never probe live mains voltage; this document has no independently measured data."
    context={"evidence":[{"id":"E1","text":"No power"}],"case_id":"synthetic"}
    assert validate_model_output(p,context)["next_safe_check"]==p["next_safe_check"]

def test_structured_v2_does_not_add_verified_instrument_authority():
    ledger=json.loads((DATA/"source_numeric_claims_validated.json").read_text())
    c=build_numeric_case_context(
        ledger,case_id="ps5_pro_no_power_hdmi",
        assisted=True,render_version="semantic_v2",
    )
    assert c["numeric_source_tool"]["source_authority_ceiling"]=="declared"
    assert c["numeric_source_tool"]["target_board_physically_verified"] is False
    assert c["numeric_source_tool"]["semantic_comparators"]=={
        "M1":"reported_scalar","M2":"reported_scalar","M3":"reported_scalar"
    }
    assert all("not_independently_measured" in e["stage"]
               for e in c["evidence"] if "source_claim_id" in e)

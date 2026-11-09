"""Generic numeric reference gating and one sealed correction turn."""
import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.restoration_caption_ingest import caption_case_context
from hardware_splicer.restoration_engineering_assist import add_engineering_assistance
from hardware_splicer.restoration_numeric_truth_gate import (
    UnsupportedQuantitativeThreshold, reject_unsourced_thresholds, unsourced_thresholds,
)
from hardware_splicer.restoration_quality_correction import correct_unsourced_thresholds
from hardware_splicer.restoration_reasoning_agent import build_messages, diagnose, sha, validate_model_output

D=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/diversity"

def base(tmp_path):
    p=tmp_path/"video.en-orig.vtt"
    p.write_text("""WEBVTT

00:00:10.000 --> 00:00:10.010
Tablet will not show an image.

00:00:35.000 --> 00:00:35.010
The creator reports USB activity but did not measure voltage.

00:05:10.000 --> 00:05:10.010
The creator replaced the cable and the device was repaired.
""")
    ctx=caption_case_context(
        case_id="test_tablet",device="USB-charged tablet",
        title_symptom="Screen blank",
        video_url="https://www.youtube.com/watch?v=testtablet",
        hazards=["lithium_ion","data_loss"],vtt_path=p,cutoff_s=120)
    return add_engineering_assistance(ctx)

def valid_plan():
    return {
        "summary":"No confirmed device fault.",
        "hypotheses":[{"mechanism":"Possible faulty display",
                       "why":"The screen is blank; USB enumeration was reported.",
                       "evidence_ids":["E1","E2"],
                       "safe_test":"Use certified external USB power meter to observe whether draw changes when buttons are pressed."}],
        "next_safe_check":"Connect an external USB monitor, without opening device, and observe if current changes.",
        "uncertainty":"No calibrated baseline or direct measurements.",
        "abstain":False,
    }

@pytest.mark.parametrize("limit",[
    ">0.4A", "<0.05A", "above 12V", "less than 1.2 ohms", "at least 20W",
    "below 45°C",
])
def test_detects_unsourced_cutoffs_not_certain_components(tmp_path,limit):
    ctx=base(tmp_path)
    plan=valid_plan()
    plan["next_safe_check"]="Expect a normal reading "+limit+" before considering the display."
    rows=unsourced_thresholds(plan,ctx["hs_engineering_ledger"])
    assert any(limit in item["limit"] for item in rows)
    with pytest.raises(UnsupportedQuantitativeThreshold):
        reject_unsourced_thresholds(plan,ctx["hs_engineering_ledger"])

def test_allow_observed_numeric_value_and_nominal_source_power_not_threshold(tmp_path):
    ctx=base(tmp_path)
    p=valid_plan()
    p["next_safe_check"]="Inspect external certified 5V USB power meter; record the reading without assuming a healthy threshold."
    assert not unsourced_thresholds(p,ctx["hs_engineering_ledger"])

def test_original_saved_tablet_A_B_fails_new_calibration_gate():
    saved=json.loads((D/"evidence/graph_ab_six_live.json").read_text())
    row=next(c for c in saved["cases"] if c["case_id"]=="tab_s6_lite_dead")
    old=row["arms"]["hs_graph"]["receipt"]
    ledger={
        "unresolved_source_ids":["no_verified_meter_observations","no_component_datasheet_provided"],
    }
    assert old["status"]=="proposed_unverified_differential"
    hit=unsourced_thresholds(old["plan"],ledger)
    assert len(hit)>=2
    assert any("0.4A" in x["limit"] for x in hit)
    assert any("0.05A" in x["limit"] for x in hit)

def test_live_model_response_rejected_with_unsourced_electrical_cutoff(tmp_path):
    ctx=base(tmp_path)
    p=valid_plan()
    p["hypotheses"][0]["safe_test"]="A normal tablet draws >0.4A after holding reset."
    with pytest.raises(UnsupportedQuantitativeThreshold):
        validate_model_output(p,ctx)
    def fake(messages,**kwargs):
        return {"provider":"mock","model":"test","content":json.dumps(p)}
    r=diagnose(ctx,model="test",inference=fake)
    assert r["status"]=="rejected_model_output_or_unavailable"
    assert r["error_type"]=="UnsupportedQuantitativeThreshold"
    assert r["repair_authorized"] is False

def fake_old_receipt(ctx):
    p=valid_plan()
    p["next_safe_check"]="Normal current >0.4A indicates healthy display; <0.05A indicates failed charger."
    old={
        "status":"proposed_unverified_differential",
        "case_id":ctx["case_id"],
        "evidence_sha256":ctx["evidence_sha256"],
        "prompt_sha256":sha(build_messages(ctx)),
        "model_requested":"mock_llm",
        "hs_source_graph_sha256":ctx["hs_engineering_ledger"]["graph_sha256"],
        "plan":p,
    }
    old["receipt_sha256"]=sha(old)
    return old

def test_one_bounded_correction_chains_original_and_saves_same_evidence(tmp_path):
    ctx=base(tmp_path)
    old=fake_old_receipt(ctx)
    observed=[]
    def fixed(messages,**kwargs):
        observed.append(messages)
        return {"provider":"mock","model":"mock_llm","content":json.dumps(valid_plan())}
    result=correct_unsourced_thresholds(ctx,old,inference=fixed,model="mock_llm")
    assert len(observed)==1
    assert result["correction_attempt_count"]==1
    assert result["source_evidence_sha256"]==ctx["evidence_sha256"]
    assert result["original_receipt_sha256"]==old["receipt_sha256"]
    assert result["correction"]["status"]=="proposed_unverified_differential"
    assert result["correction"]["quality_parent_receipt_sha256"]==old["receipt_sha256"]
    assert result["correction"]["repair_authorized"] is False
    assert result["physical_action_authorized"] is False
    assert "SOURCE-CONSTRAINT CORRECTION TURN" in observed[0][0]["content"]

def test_no_silent_reroll_if_plan_was_already_sourced(tmp_path):
    ctx=base(tmp_path)
    old=fake_old_receipt(ctx)
    old["plan"]=valid_plan()
    old["receipt_sha256"]=sha({k:v for k,v in old.items() if k!="receipt_sha256"})
    with pytest.raises(ValueError,match="no unsupported numeric"):
        correct_unsourced_thresholds(ctx,old,model="mock_llm",inference=lambda *a,**k:None)

def test_tampered_prior_receipt_fails_closed(tmp_path):
    ctx=base(tmp_path)
    old=fake_old_receipt(ctx)
    bad=copy.deepcopy(old)
    bad["plan"]["next_safe_check"]="I changed my mind"
    with pytest.raises(ValueError,match="receipt was modified"):
        correct_unsourced_thresholds(ctx,bad,model="mock_llm",inference=lambda *a,**k:None)

def test_plain_gemini_arm_is_not_implicitly_rewritten(tmp_path):
    ctx=base(tmp_path)
    plain=copy.deepcopy(ctx)
    plain.pop("hs_engineering_ledger")
    p=valid_plan()
    p["next_safe_check"]="A current reading above 0.4A is healthy."
    # The generic HS graph gate is opt-in only; the old A/B control
    # remains frozen and must not be reinterpreted as a rerun.
    result=validate_model_output(p,plain)
    assert result["hypotheses"]


def test_saved_real_repair_receipt_and_original_a_b_model_frozen():
    report=json.loads((D/"evidence/tab_s6_numeric_correction_live.json").read_text())
    original=json.loads((D/"evidence/graph_ab_six_live.json").read_text())
    source=next(x for x in original["cases"] if x["case_id"]=="tab_s6_lite_dead")
    previous=source["arms"]["hs_graph"]["receipt"]
    final=report["correction"]
    assert report["original_receipt_sha256"]==previous["receipt_sha256"]
    assert report["source_evidence_sha256"]==previous["evidence_sha256"]
    assert report["graph_sha256"]==previous["hs_source_graph_sha256"]
    assert report["correction_attempt_count"]==1
    assert report["physical_action_authorized"] is False
    assert final["status"]=="proposed_unverified_differential"
    assert final["model_reported"]=="gemini-3.8-flash-low"
    assert final["quality_parent_receipt_sha256"]==previous["receipt_sha256"]
    assert final["prompt_sha256"]!=previous["prompt_sha256"]
    assert final["evidence_sha256"]==previous["evidence_sha256"]
    assert final["hs_source_graph_sha256"]==previous["hs_source_graph_sha256"]
    assert final["receipt_sha256"]==sha({
        k:v for k,v in final.items() if k not in ("elapsed_seconds","receipt_sha256")
    })
    assert not unsourced_thresholds(final["plan"],{
        "unresolved_source_ids":["no_component_datasheet_provided",
                                 "no_verified_meter_observations"]})
    assert len(report["original_violations"])>=2
    assert final["physical_measurements_by_HS"] is False
    assert final["repair_authorized"] is False

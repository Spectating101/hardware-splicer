"""Evidence-chain and source-window protections for sequential diagnosis."""
import copy
import json
from pathlib import Path
import pytest

from hardware_splicer.restoration_caption_ingest import caption_case_context, parse_early_vtt
from hardware_splicer.restoration_measurement_feedback import (
    extend_caption_context, validate_predecessor
)
from hardware_splicer.restoration_reasoning_agent import build_messages,diagnose,sha

VTT="""WEBVTT

00:00:20.000 --> 00:00:20.010
The console has no power and no picture on the television.

00:01:10.000 --> 00:01:10.010
The power light does not come on when the console is plugged in.

00:02:30.000 --> 00:02:30.010
Now the power supply is out of the console.

00:04:00.000 --> 00:04:00.010
We have the motherboard on the bench.

00:05:20.000 --> 00:05:20.010
The creator checks the HDMI connector area under magnification.
"""
CASE=dict(
    id="synthetic_console_no_power",device="Synthetic game console",
    title_symptom="Console shows no power and no picture",
    source_url="https://www.youtube.com/watch?v=xbp8lIggbxY",
    hazards=["ac_mains","stored_charge"],
)

def frozen_pair(tmp_path):
    path=tmp_path/"xbp8lIggbxY.en-orig.vtt"
    path.write_text(VTT)
    ctx=caption_case_context(
        case_id=CASE["id"],device=CASE["device"],title_symptom=CASE["title_symptom"],
        video_url=CASE["source_url"],hazards=CASE["hazards"],vtt_path=path,cutoff_s=120)
    plan={
        "summary":"No fault is confirmed by any measurement.",
        "hypotheses":[{"mechanism":"Possible supply or input fault","why":"No power is reported.",
                       "evidence_ids":["E1"],
                       "safe_test":"Inspect the external power cable with all power removed."}],
        "next_safe_check":"Inspect the external power cable with all power removed.",
        "uncertainty":"Nothing has been measured.","abstain":False,
    }
    def model(messages,**kwargs):
        return {"provider":"mock","model":"test_model","content":json.dumps(plan)}
    prior=diagnose(ctx,inference=model,model="test_model")
    assert prior["status"]=="proposed_unverified_differential"
    return ctx,prior,path

def test_sealed_ps5_baseline_rebuilt_exactly(tmp_path):
    ctx,receipt,path=frozen_pair(tmp_path)
    validate_predecessor(ctx,receipt)
    assert receipt["prompt_sha256"]==sha(build_messages(ctx))
    assert receipt["evidence_sha256"]==ctx["evidence_sha256"]

def test_followup_is_append_only_source_stamped(tmp_path):
    ctx,receipt,path=frozen_pair(tmp_path)
    later=extend_caption_context(ctx,receipt,vtt_path=path,start_s=120,cutoff_s=300)
    assert len(later["evidence"])>len(ctx["evidence"])
    assert later["evidence"][:len(ctx["evidence"])]==ctx["evidence"]
    assert later["evidence_sha256"] != ctx["evidence_sha256"]
    assert later["source_windows"][-1]["cutoff_second"]==300
    assert later["preceding_receipt_sha256"]==receipt["receipt_sha256"]
    assert later["prior_model_hypotheses"]
    assert "not_evidence" in build_messages(later)[-1]["content"]

def test_previous_receipt_cannot_be_changed(tmp_path):
    ctx,receipt,path=frozen_pair(tmp_path)
    altered=copy.deepcopy(receipt)
    altered["plan"]["hypotheses"][0]["mechanism"]="Post-hoc edit after looking at repair."
    with pytest.raises(ValueError,match="digest mismatch"):
        extend_caption_context(ctx,altered,vtt_path=path,start_s=120,cutoff_s=300)
    altered=copy.deepcopy(ctx)
    altered["evidence"][0]["text"]="A fabricated earlier observation"
    with pytest.raises(ValueError,match="prompt does not match|evidence_sha256 mismatch"):
        extend_caption_context(altered,receipt,vtt_path=path,start_s=120,cutoff_s=300)

def test_no_leap_forward_or_overlapping_video_windows(tmp_path):
    ctx,receipt,path=frozen_pair(tmp_path)
    with pytest.raises(ValueError,match="contiguous"):
        extend_caption_context(ctx,receipt,vtt_path=path,start_s=200,cutoff_s=360)
    with pytest.raises(ValueError,match="contiguous"):
        extend_caption_context(ctx,receipt,vtt_path=path,start_s=0,cutoff_s=300)
    with pytest.raises(ValueError,match="source bound"):
        extend_caption_context(ctx,receipt,vtt_path=path,start_s=120,cutoff_s=700)

def test_different_vtt_cannot_be_swapped_in(tmp_path):
    ctx,receipt,path=frozen_pair(tmp_path)
    evil=tmp_path/"xbp8lIggbxY.en-orig.vtt"
    evil.write_text("""WEBVTT

00:02:30.000 --> 00:02:30.010
Creator was speaking.
""")
    with pytest.raises(ValueError,match="transcript changed"):
        extend_caption_context(ctx,receipt,vtt_path=evil,start_s=120,cutoff_s=300)

def test_window_parser_has_provenance_and_monotonic_stamps(tmp_path):
    ctx,receipt,path=frozen_pair(tmp_path)
    sample=parse_early_vtt(path,start_s=300,cutoff_s=360)
    assert sample["window_start_seconds"]==300
    assert sample["cutoff_seconds"]==360
    assert all(300 <= ch["start_second"]<=360 for ch in sample["chunks"])
    assert all(ch["end_second"]<=360 for ch in sample["chunks"])
    assert sample["raw_vtt_sha256"]==ctx["caption_provenance"]["raw_vtt_sha256"]

"""Evidence-chain and source-window protections for sequential diagnosis."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest

from hardware_splicer.restoration_caption_ingest import caption_case_context, parse_early_vtt
from hardware_splicer.restoration_measurement_feedback import (
    extend_caption_context, validate_predecessor
)
from hardware_splicer.restoration_reasoning_agent import build_messages,sha

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/"examples/restoration_video_bench/diversity"
CAP=Path("/tmp/hs-restoration-video-intake-20261110/xbp8lIggbxY.en-orig.vtt")

def frozen_pair(tmp_path):
    c=next(c for c in json.loads((D/"cases.json").read_text())["cases"]
           if c["id"]=="ps5_pro_no_power_hdmi")
    prior=json.loads((D/"evidence/live_raw_vtt/ps5_pro_no_power_hdmi.json").read_text())["results"][0]
    if CAP.exists():
        path=CAP
    else:
        # CI may have no video transcript; synthetic captions use exact stored
        # digest only for metadata tests, never pretend to be actual video.
        pytest.skip("offline YouTube auto-caption file not present")
    ctx=caption_case_context(
        case_id=c["id"],device=c["device"],title_symptom=c["title_symptom"],
        video_url=c["source_url"],hazards=c["hazards"],vtt_path=path,cutoff_s=120)
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

def test_saved_live_sequential_receipts_when_present():
    artifact=D/"evidence/ps5_sequential_measurement_live.json"
    if not artifact.exists():
        pytest.skip("live PS5 stages not yet saved")
    data=json.loads(artifact.read_text())
    assert data["no_post_repair_outcomes_opened"] is True
    assert data["max_video_second_admitted"]==360
    assert data["physical_repair_authorized"] is False
    assert [t["window_end_s"] for t in data["turns"]]==[300,360]
    original=json.loads((D/"evidence/live_raw_vtt/ps5_pro_no_power_hdmi.json").read_text())["results"][0]
    prior=original
    for row in data["turns"]:
        r=row["receipt"]
        assert r["preceding_receipt_sha256"]==prior["receipt_sha256"]
        assert r["receipt_sha256"]==sha({k:v for k,v in r.items() if k not in ("receipt_sha256","elapsed_seconds")})
        assert r["repair_authorized"] is False
        assert r["actual_video_frames_analyzed"] is False
        assert r["status"] in ("proposed_unverified_differential","model_abstained")
        prior=r


def synthetic_chain(tmp_path):
    """All behavior gates run in CI without YouTube or live model access."""
    from hardware_splicer.restoration_reasoning_agent import diagnose
    caption=tmp_path/"video.vtt"
    caption.write_text("""WEBVTT

00:00:10.000 --> 00:00:10.010
Console does not power on.

00:02:05.000 --> 00:02:05.010
Video creator has removed the outer case.

00:05:32.000 --> 00:05:32.010
Creator reports two ohms across the motherboard supply pins.

00:08:25.000 --> 00:08:25.010
Creator repaired the board by replacing a component.
""")
    context=caption_case_context(
        case_id="synthetic_ps5",device="Mains powered game console",
        title_symptom="Console will not power on",
        video_url="https://www.youtube.com/watch?v=testsource",
        hazards=["ac_mains_internal_psu"],vtt_path=caption,cutoff_s=120,
    )
    def fake_inference(messages,**kwargs):
        return {
            "provider":"mock_deterministic","model":"fixed_mock",
            "content":json.dumps({
                "summary":"Symptoms do not confirm a cause.",
                "hypotheses":[{
                    "mechanism":"Power distribution fault",
                    "why":"No startup response.",
                    "safe_test":"Inspect external cord with device unplugged.",
                    "evidence_ids":["E1"],
                }],
                "next_safe_check":"Observe external power status while unplugged.",
                "uncertainty":"No verified electrical measurements.",
                "abstain":False,
            }),
        }
    receipt=diagnose(context,inference=fake_inference,model="fixed_mock")
    assert receipt["status"]=="proposed_unverified_differential"
    return context,receipt,caption,fake_inference


def test_synthetic_source_chain_can_advance_without_outcome(tmp_path):
    from hardware_splicer.restoration_reasoning_agent import diagnose
    context,receipt,caption,inference=synthetic_chain(tmp_path)
    second=extend_caption_context(
        context,receipt,vtt_path=caption,start_s=120,cutoff_s=300)
    assert "removed the outer case" in str(second["evidence"])
    assert "two ohms" not in str(second["evidence"])
    assert "replacing a component" not in str(second["evidence"])
    model2=diagnose(second,inference=inference,model="fixed_mock")
    assert model2["preceding_receipt_sha256"]==receipt["receipt_sha256"]
    third=extend_caption_context(
        second,model2,vtt_path=caption,start_s=300,cutoff_s=360)
    assert "two ohms" in str(third["evidence"])
    assert "replacing a component" not in str(third["evidence"])
    assert third["source_windows"][-1]["cutoff_second"]==360


def test_synthetic_chain_detects_tampering_and_gaps(tmp_path):
    ctx,receipt,caption,_=synthetic_chain(tmp_path)
    bad=copy.deepcopy(receipt)
    bad["plan"]["hypotheses"][0]["mechanism"]="reveal repair hindsight"
    with pytest.raises(ValueError,match="digest mismatch"):
        extend_caption_context(ctx,bad,vtt_path=caption,start_s=120,cutoff_s=300)
    with pytest.raises(ValueError,match="contiguous"):
        extend_caption_context(ctx,receipt,vtt_path=caption,start_s=300,cutoff_s=360)
    other=tmp_path/"other.vtt"
    other.write_text(caption.read_text()+"\n")
    with pytest.raises(ValueError,match="transcript changed"):
        extend_caption_context(ctx,receipt,vtt_path=other,start_s=120,cutoff_s=300)

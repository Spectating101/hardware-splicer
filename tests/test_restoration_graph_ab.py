"""Real HS source-graph assistance: neutral source provenance, no gold leakage."""
import importlib.util
import json
from pathlib import Path

import pytest

from hardware_splicer.restoration_caption_ingest import caption_case_context
from hardware_splicer.restoration_engineering_assist import (
    add_engineering_assistance, augmented_prompt, source_ledger
)
from hardware_splicer.restoration_reasoning_agent import (
    build_messages, diagnose, sha
)

HERE=Path(__file__).resolve().parents[1] / "examples/restoration_video_bench/diversity"
spec=importlib.util.spec_from_file_location("raw_ab",HERE/"run_graph_ab.py")
raw_ab=importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw_ab)

def dummy(tmp_path):
    p=tmp_path/"test.en-orig.vtt"
    p.write_text("""WEBVTT

00:00:10.000 --> 00:00:10.010
The screen is black and device won't start.

00:00:30.000 --> 00:00:30.010
The presenter suspects a broken connector.

00:05:40.000 --> 00:05:40.010
The device was later repaired using a new component.
""")
    ctx=caption_case_context(
        case_id="x",device="Portable electronic device",
        title_symptom="No power after shipping",video_url="https://www.youtube.com/watch?v=test",
        hazards=["lithium_ion","data_loss"],vtt_path=p)
    return ctx

def test_real_hs_source_graph_claims_never_elevated(tmp_path):
    ctx=dummy(tmp_path)
    ledger=source_ledger(ctx)
    assert ledger["source_graph_claim_count"]==len(ctx["evidence"])
    assert ledger["authority_ceiling"]=="declared"
    assert ledger["claims_verified_by_HS"]==0
    assert ledger["no_documentation_retrieved"] is True
    assert ledger["no_bench_measurements_by_HS"] is True
    assert all(row["authority"]=="declared" for row in ledger["claims"])
    assert any(c["timestamp_s"]==10.0 for c in ledger["claims"])
    assert "no_schematic_or_boardview_provided" in ledger["unresolved_source_ids"]

def test_assist_cannot_edit_real_video_source(tmp_path):
    plain=dummy(tmp_path)
    enhanced=add_engineering_assistance(plain)
    assert enhanced["evidence"]==plain["evidence"]
    assert enhanced["evidence_sha256"]==plain["evidence_sha256"]
    assert enhanced["source_url"]==plain["source_url"]
    assert enhanced["caption_provenance"]==plain["caption_provenance"]
    assert "later repaired" not in json.dumps(build_messages(enhanced))

def test_hs_model_prompt_is_a_separate_auditable_intervention(tmp_path):
    plain=dummy(tmp_path)
    hs=add_engineering_assistance(plain)
    base=build_messages(plain)
    augmented=build_messages(hs)
    assert len(base)==len(augmented)==2
    assert base[1]==augmented[1]
    assert base[0]!=augmented[0]
    assert "SOURCE_LEDGER_JSON" in augmented[0]["content"]
    assert hs["hs_engineering_ledger"]["graph_sha256"] in augmented[0]["content"]
    assert "NEXT SAFE" in augmented[0]["content"]
    assert sha(augmented)!=sha(base)

def test_deny_tampered_evidence_and_missing_transcript_provenance(tmp_path):
    plain=dummy(tmp_path)
    altered=json.loads(json.dumps(plain))
    altered["evidence"][0]["text"]="Definite manufacturer root cause"
    with pytest.raises(ValueError,match="signed native intake"):
        source_ledger(altered)
    altered=json.loads(json.dumps(plain))
    del altered["caption_provenance"]
    with pytest.raises(ValueError,match="real first-window caption provenance"):
        source_ledger(altered)

def test_hs_diagnose_uses_graph_but_does_not_claim_measurements(tmp_path):
    hs=add_engineering_assistance(dummy(tmp_path))
    received=[]
    def fake(messages,**kwargs):
        received.append(messages)
        return {
            "provider":"mock_inference","model":"exact_same_model",
            "content":json.dumps({
                "summary":"No physical fault verified",
                "hypotheses":[{
                    "mechanism":"Possible mechanical connector fault",
                    "why":"Creator narrates suspected connection.",
                    "evidence_ids":["E2"],
                    "safe_test":"Externally inspect the connector before opening anything."
                }],
                "next_safe_check":"Check accessible exterior connectors without opening the device.",
                "uncertainty":"No verified measurement or service manual.",
                "abstain":False
            })
        }
    r=diagnose(hs,model="exact_same_model",inference=fake)
    assert len(received)==1
    assert "SOURCE_LEDGER_JSON" in received[0][0]["content"]
    assert r["hs_source_graph_sha256"]==hs["hs_engineering_ledger"]["graph_sha256"]
    assert r["status"]=="proposed_unverified_differential"
    assert r["actual_video_frames_analyzed"] is False
    assert r["repair_authorized"] is False
    assert r["physical_measurements_by_HS"] is False

def test_fixed_protocol_precommits_arm_order_with_no_outcome():
    x=raw_ab.protocol_spec()
    assert x["schema"]=="hs.restoration.real_caption_graph_paired_ab.v1"
    assert len(x["precommitted_case_arm_order"])==6
    assert all(set(row[1:])=={"plain","hs_graph"} for row in x["precommitted_case_arm_order"])
    assert x["outcomes_not_loaded"] is True
    assert x["equal_model_calls_per_arm"] is True
    assert x["equal_raw_evidence_per_arm"] is True
    assert "postreview" not in json.dumps(x).lower()

def test_no_result_is_passed_as_input_in_single_stage(tmp_path):
    hs=add_engineering_assistance(dummy(tmp_path))
    text=json.dumps(build_messages(hs))
    assert "creator_reported_result" not in text
    assert "repair-success" not in text.lower()
    assert '"creator_outcome"' not in text.lower()
    assert '"root_cause"' not in text.lower()
    assert "replaced the component" not in text.lower()

def test_augmented_prompt_refuses_lacking_base_message():
    with pytest.raises(IndexError):
        augmented_prompt([],{"source_graph_claim_count":0})

def test_caption_source_is_declared_even_when_it_claims_an_instrument_reading(tmp_path):
    p=tmp_path/"test.en-orig.vtt"
    p.write_text("""WEBVTT

00:00:09.000 --> 00:00:09.010
The presenter says the meter reads 12 volts.
""")
    context=caption_case_context(case_id="meter",device="Game console",
                                  title_symptom="Won't boot",
                                  video_url="https://www.youtube.com/watch?v=meter",
                                  hazards=["ac_mains"],vtt_path=p)
    a=add_engineering_assistance(context)
    assert all(c["authority"]=="declared" for c in a["hs_engineering_ledger"]["claims"])
    assert a["hs_engineering_ledger"]["no_bench_measurements_by_HS"]

"""Evidence-sealed interactive Repair Investigator report, no external calls."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.repair_investigator import perform
from hardware_splicer.repair_investigator_audit import verify_investigation
from hardware_splicer.repair_investigator_report import make_html
from hardware_splicer.restoration_reasoning_agent import sha

HERE=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/investigator/c64_250407"

def sample(tmp_path):
    from test_repair_investigator import fixture,fake_model
    m,s,p=fixture(tmp_path)
    d=perform(m,s,captions_vtt=p,inference=fake_model,model="test_model")
    return m,s,d

def test_no_model_or_video_needed_to_audit_saved_evidence(tmp_path):
    m,s,d=sample(tmp_path)
    audit=verify_investigation(d,m,s)
    assert audit["model_attempts"]==4
    assert audit["valid_by_arm"]=={"plain":2,"hs_circuit":2}
    assert audit["no_independent_physical_measurements"]
    assert audit["no_video_frame_vision"]
    assert audit["board_revision_not_verified"]
    assert audit["no_repair_success_or_accuracy_scored"]
    for r in audit["results"]:
        assert r["sha256"] and len(r["sha256"])==64

def test_model_prompt_tampering_detected_offline(tmp_path):
    m,s,d=sample(tmp_path)
    altered=copy.deepcopy(d)
    altered["results"]["hs_circuit"][0]["model_receipt"]["prompt_sha256"]="0"*64
    altered["results"]["hs_circuit"][0]["model_receipt"]["receipt_sha256"]=sha({
        k:v for k,v in altered["results"]["hs_circuit"][0]["model_receipt"].items()
        if k not in ("receipt_sha256","elapsed_seconds")
    })
    with pytest.raises(ValueError,match="model system prompt"):
        verify_investigation(altered,m,s)

def test_source_evidence_modified_after_recording_fails(tmp_path):
    m,s,d=sample(tmp_path)
    altered=copy.deepcopy(d)
    altered["results"]["plain"][0]["evidence"][0]["text"]="The repair was later successful."
    with pytest.raises(ValueError,match="signed model input"):
        verify_investigation(altered,m,s)

def test_no_later_outcome_or_fabricated_physical_operation_in_html(tmp_path):
    m,s,d=sample(tmp_path)
    page=make_html(record=d,manifest=m,reference=s,snapshot_sha256="a"*64)
    assert "<!doctype html>" in page
    assert "data-arm=\"plain\"" in page
    assert "data-arm=\"hs_circuit\"" in page
    assert "data-stage=\"1\"" in page
    assert "source_graph_sha256" in page
    assert "Export machine-readable investigation record" in page
    assert "actual board" in page.lower()
    assert "repairs restored the screen" not in page
    assert "physical target board verified" not in page.lower() or "NO" in page
    assert "script id=\"payload\"" in page
    assert len(page)>12000
    out=tmp_path/"investigation.html"
    out.write_text(page)
    assert out.stat().st_size>12000

def test_never_publish_incomplete_or_modified_result(tmp_path):
    m,s,d=sample(tmp_path)
    d["complete"]=False
    with pytest.raises(ValueError,match="incomplete"):
        make_html(record=d,manifest=m,reference=s,snapshot_sha256="a"*64)
    d["complete"]=True
    d["results"]["hs_circuit"][1]["model_receipt"]["plan"]["hypotheses"][0]["mechanism"]="I saw the future fix"
    with pytest.raises(ValueError,match="model receipt"):
        make_html(record=d,manifest=m,reference=s,snapshot_sha256="a"*64)

def test_user_controlled_source_text_html_escaped(tmp_path):
    m,s,d=sample(tmp_path)
    # Retain a valid signed state, but even if a source case includes literal
    # HTML-looking text, the self-contained JS payload must be safe.
    m["video_title_symptom"]="Repair case with <script>alert(1)</script>"
    d["source_manifest_sha256"]=sha(m)
    page=make_html(record=d,manifest=m,reference=s,snapshot_sha256="a"*64)
    assert "<script>alert(1)</script>" not in page
    assert "\\u003cscript\\u003e" in page

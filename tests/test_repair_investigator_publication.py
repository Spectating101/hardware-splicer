"""Public source paraphrase release is separate from original signed evidence."""
import copy
import json

import pytest

from hardware_splicer.repair_investigator_publication import redact_for_public
from hardware_splicer.repair_investigator_report import make_html

from test_repair_investigator import fake_model, fixture
from hardware_splicer.repair_investigator import perform


def record(tmp_path):
    m, s, p = fixture(tmp_path)
    raw = perform(m, s, captions_vtt=p, inference=fake_model, model="test_model")
    ids = sorted({e["id"] for arm in ("plain", "hs_circuit")
                  for row in raw["results"][arm] for e in row["evidence"]})
    summaries = {
        "schema": "hs.repair_investigator.public_source_summaries.v1",
        "case_id": m["id"],
        "source_video_sha256": m["video_auto_captions_sha256"],
        "evidence": {i: f"Synthetic editorial paraphrase number {i[1:]} of the opening narration."
                     for i in ids},
    }
    return m, s, raw, summaries


def test_projection_redacts_text_but_preserves_receipts(tmp_path):
    m, s, raw, summaries = record(tmp_path)
    public = redact_for_public(raw, m, summaries)
    assert public["public_projection"]["original_source_evidence_is_redacted"]
    for arm in ("plain", "hs_circuit"):
        for stage in (0, 1):
            before, after = raw["results"][arm][stage], public["results"][arm][stage]
            assert after["evidence_sha256"] == before["evidence_sha256"]
            assert after["model_receipt"] == before["model_receipt"]
            assert len(after["evidence"]) == len(before["evidence"])
            for e in after["evidence"]:
                assert e["public_source_text_redacted"] is True
                assert len(e["original_source_excerpt_sha256"]) == 64
                assert "Editorial paraphrase" in e["text"]
    # The private record itself is not modified in place.
    assert "Editorial paraphrase" not in json.dumps(raw)


def test_public_page_contains_no_original_caption_text(tmp_path):
    m, s, raw, summaries = record(tmp_path)
    page = make_html(record=raw, manifest=m, reference=s,
                     snapshot_sha256=m["reference_snapshot_sha256"],
                     publication_summaries=summaries)
    assert page.startswith("<!doctype html>")
    assert "Original source text" not in page
    assert "Public source observations are brief editorial paraphrases" in page
    assert "This C64 does not work" not in page


def test_source_summary_tampering_denied(tmp_path):
    m, s, raw, summaries = record(tmp_path)
    bad = copy.deepcopy(summaries)
    bad["source_video_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="not tied"):
        redact_for_public(raw, m, bad)
    bad = copy.deepcopy(summaries)
    del bad["evidence"]["E2"]
    with pytest.raises(ValueError, match="unreviewed source"):
        redact_for_public(raw, m, bad)
    bad = copy.deepcopy(summaries)
    bad["evidence"]["E1"] = "x" * 400
    with pytest.raises(ValueError, match="too extensive"):
        redact_for_public(raw, m, bad)


def test_full_original_speech_cannot_be_redistributed(tmp_path):
    m, s, raw, summaries = record(tmp_path)
    original = raw["results"]["plain"][0]["evidence"][0]["text"]
    bad = copy.deepcopy(summaries)
    bad["evidence"]["E1"] = original
    if not 10 <= len(original) <= 220:
        pytest.skip("original cue outside the paraphrase length window")
    with pytest.raises(ValueError, match="cannot be redistributed"):
        redact_for_public(raw, m, bad)

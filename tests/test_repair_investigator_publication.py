"""Public source paraphrase release is separate from original signed evidence."""
import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.repair_investigator_publication import redact_for_public
from hardware_splicer.repair_investigator_report import make_html
from hardware_splicer.restoration_reasoning_agent import sha

HERE=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/investigator/c64_250407"
PRIVATE=Path("/tmp/hs_c64_full_original_inference.json")

def test_live_public_paraphrases_are_short_and_source_bound():
    source=json.loads((HERE/"public_source_summaries.json").read_text())
    manifest=json.loads((HERE/"case.json").read_text())
    assert source["case_id"]==manifest["id"]
    assert source["source_video_sha256"]==manifest["video_auto_captions_sha256"]
    assert set(source["evidence"])=={f"E{i}" for i in range(1,14)}
    assert sum(len(x.split()) for x in source["evidence"].values())<=200
    assert all(len(x)<220 for x in source["evidence"].values())

def test_live_original_public_projection_if_private_source_available():
    if not PRIVATE.exists():
        pytest.skip("original complete source evidence deliberately not redistributed")
    raw=json.loads(PRIVATE.read_text())
    manifest=json.loads((HERE/"case.json").read_text())
    summary=json.loads((HERE/"public_source_summaries.json").read_text())
    public=redact_for_public(raw,manifest,summary)
    assert public["public_projection"]["original_source_evidence_is_redacted"]
    for arm in ("plain","hs_circuit"):
        for stage in (0,1):
            before=raw["results"][arm][stage]
            after=public["results"][arm][stage]
            assert after["evidence_sha256"]==before["evidence_sha256"]
            assert after["model_receipt"]==before["model_receipt"]
            assert len(after["evidence"])==len(before["evidence"])
            for e in after["evidence"]:
                assert e["public_source_text_redacted"] is True
                assert len(e["original_source_excerpt_sha256"])==64
                assert "Editorial paraphrase" in e["text"]
                assert "Unverified creator speech at" not in e["text"]
                assert "Auto-caption at" not in e["text"]
    html=make_html(record=raw,manifest=manifest,
                   reference=json.loads((HERE/"c64_250407_reference.json").read_text()),
                   snapshot_sha256=manifest["reference_snapshot_sha256"],
                   publication_summaries=summary)
    assert html.startswith("<!doctype html>")
    assert "Original source text" not in html
    assert "Public source observations are brief editorial paraphrases" in html
    assert "\\u003cscript\\u003e" not in html.replace('id="payload"','id="payload"')
    assert "source_excerpt_sha256" in html

def test_source_summary_tampering_denied_if_original_source_exists():
    if not PRIVATE.exists():
        pytest.skip("private original evidence not present in CI")
    raw=json.loads(PRIVATE.read_text())
    manifest=json.loads((HERE/"case.json").read_text())
    public=json.loads((HERE/"public_source_summaries.json").read_text())
    public["source_video_sha256"]="f"*64
    with pytest.raises(ValueError,match="not tied"):
        redact_for_public(raw,manifest,public)
    public["source_video_sha256"]=manifest["video_auto_captions_sha256"]
    del public["evidence"]["E10"]
    with pytest.raises(ValueError,match="unreviewed source"):
        redact_for_public(raw,manifest,public)


def test_committed_public_derived_files_have_no_original_caption_transcript():
    from hardware_splicer.repair_investigator import file_sha256
    p=HERE/"live_investigation_public.json"
    h=HERE/"investigation.html"
    audit=HERE/"offline_audit.json"
    if not p.exists() or not h.exists() or not audit.exists():
        pytest.skip("public report is committed after the source-frozen trial")
    record=json.loads(p.read_text())
    page=h.read_text()
    verify=json.loads(audit.read_text())
    manifest=json.loads((HERE/"case.json").read_text())
    ref=json.loads((HERE/"c64_250407_reference.json").read_text())
    assert record["public_projection"]["original_source_evidence_is_redacted"]
    assert record["public_projection"]["original_model_receipt_sha256_preserved"]
    assert record["source_manifest_sha256"]==sha(manifest)
    assert record["source_snapshot_sha256"]==sha(ref)
    assert verify["model_attempts"]==4
    assert verify["valid_by_arm"]=={"plain":2,"hs_circuit":2}
    assert verify["source_graph_sha256"]==record["native_graph"]["native_source_graph_sha256"]
    for arm in ("plain","hs_circuit"):
        assert len(record["results"][arm])==2
        for row in record["results"][arm]:
            receipt=row["model_receipt"]
            assert receipt["receipt_sha256"]==sha({
                k:v for k,v in receipt.items()
                if k not in ("receipt_sha256","elapsed_seconds")
            })
            assert receipt["repair_authorized"] is False
            for e in row["evidence"]:
                assert "Editorial paraphrase" in e["text"]
                assert "Auto-caption at" not in e["text"]
                assert "Unverified creator speech at" not in e["text"]
                assert e["public_source_text_redacted"]
                assert len(e["original_source_excerpt_sha256"])==64
    assert "Hi, it's Jan Beta" not in page
    assert "There is a 250407 board" not in page
    assert "Original source text" not in page
    assert 'data-arm="plain"' in page
    assert 'data-arm="hs_circuit"' in page
    assert 'data-stage="1"' in page
    import re
    blob=re.search(r'<script id="payload" type="application/json">(.*?)</script>',page,re.S)
    assert blob
    embedded=json.loads(blob.group(1))
    assert embedded["investigation"]==record
    assert embedded["reference_file_sha256"]==file_sha256(HERE/"c64_250407_reference.json")

"""Strict receiving tests: an unrelated or stale result cannot be imported as a fresh review."""
import hashlib
import json

import pytest

from hardware_splicer.mechanical_portfolio_handoff import HandoffError, verify_inputs


def digest(b):
    return hashlib.sha256(b).hexdigest()


def trial(tmp_path):
    original=tmp_path/"source.ref"
    original.write_bytes(b"independently supplied source bytes")
    artifacts={}
    for name in ("fixture.step","fixture.stl","request.json","strategies.json","verification.json"):
        p=tmp_path/name
        p.write_bytes((name+" validated native placeholder").encode())
        artifacts[name]={"sha256":digest(p.read_bytes()),"bytes":p.stat().st_size}
    evidence={
        "schema":"hardware_splicer.mechanical_fixture_evidence.v1",
        "project_id":"project-001","revision":1,"physical_authority_granted":False,
        "source":{"sha256":digest(original.read_bytes())},
        "verification":{"physical_status":"UNVERIFIED"},
        "artifacts":artifacts
    }
    ev=tmp_path/"mechanical-evidence.json"
    ev.write_text(json.dumps(evidence))
    review={"schema":"policylab.mechanical_fixture_review.v1",
            "physical_authority_granted":False,"decision":"ADMIT_WITH_LIMIT",
            "source_binding":{"project_id":"project-001","revision":1,
                              "evidence_sha256":digest(ev.read_bytes()),
                              "original_source_sha256":digest(original.read_bytes())}}
    rv=tmp_path/"review.json"
    rv.write_text(json.dumps(review))
    return original,ev,rv


def test_import_requires_exact_source_artifact_review_and_revision(tmp_path):
    source,ev,rv=trial(tmp_path)
    assert verify_inputs(ev,rv,source,tmp_path)["evidence"]["revision"]==1
    art=tmp_path/"fixture.step"
    art.write_bytes(art.read_bytes()+b"tampering")
    with pytest.raises(HandoffError,match="Artifact bytes"):
        verify_inputs(ev,rv,source,tmp_path)
    art.write_bytes(b"fixture.step validated native placeholder")
    rev=json.loads(rv.read_text())
    rev["source_binding"]["revision"]=2
    rv.write_text(json.dumps(rev))
    with pytest.raises(HandoffError,match="stale"):
        verify_inputs(ev,rv,source,tmp_path)


def test_physical_claim_or_wrong_original_source_is_rejected(tmp_path):
    source,ev,rv=trial(tmp_path)
    data=json.loads(ev.read_text())
    data["physical_authority_granted"]=True
    ev.write_text(json.dumps(data))
    with pytest.raises(HandoffError,match="physical"):
        verify_inputs(ev,rv,source,tmp_path)
    source,ev,rv=trial(tmp_path)
    source.write_bytes(b"changed vendor bytes")
    with pytest.raises(HandoffError,match="Original reference source"):
        verify_inputs(ev,rv,source,tmp_path)

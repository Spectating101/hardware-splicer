from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


KEY = "b" * 48
RAW = base64.b64encode(b"time,value\n0,1\n").decode("ascii")


def _record(raw_refs: list[str]) -> dict:
    return {
        "evidence_id": "bounded-test",
        "project_id": "bounded-project",
        "candidate_revision": "r1",
        "kind": "functional_test",
        "target_ids": ["bounded-project"],
        "procedure_id": "bounded-test",
        "passed": True,
        "captured_at": "2026-08-04T02:00:00+00:00",
        "operator": "operator",
        "measured_values": {"value": 1.0},
        "acceptance_criteria": {"value": {"minimum": 0.0}},
        "artifact_hashes": {},
        "raw_refs": raw_refs,
    }


def _raw_file(ref: str) -> dict:
    return {
        "ref": ref,
        "content_base64": RAW,
        "media_type": "text/csv",
    }


def test_attested_builder_rejects_record_raw_ref_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "bounded-key")
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/physical-evidence/envelopes/build-attested",
        json={
            "envelope_id": "envelope-mismatch",
            "record": _record(["lab://expected.csv"]),
            "raw_files": [_raw_file("lab://different.csv")],
            "created_at": "2026-08-04T02:05:00+00:00",
            "created_by": "operator",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_attested_evidence_envelope"
    assert "raw refs" in response.json()["detail"]["message"]


def test_attested_builder_rejects_more_than_eight_files(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "bounded-key")
    client = TestClient(create_product_app())
    refs = [f"lab://file-{index}.csv" for index in range(9)]

    response = client.post(
        "/v1/engineering/physical-evidence/envelopes/build-attested",
        json={
            "envelope_id": "envelope-too-many",
            "record": _record(refs),
            "raw_files": [_raw_file(ref) for ref in refs],
            "created_at": "2026-08-04T02:05:00+00:00",
            "created_by": "operator",
        },
    )

    assert response.status_code == 422


def test_attested_schema_discloses_combined_bounds(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "bounded-key")
    client = TestClient(create_product_app())

    response = client.get(
        "/v1/engineering/physical-evidence/attested/schema"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["maximum_envelope_raw_bytes"] == 16 * 1024 * 1024
    assert body["maximum_envelope_file_count"] == 8
    assert body["server_attestation_required"] is True
    assert body["plain_hash_sufficient"] is False
    assert body["raw_bytes_persisted"] is False

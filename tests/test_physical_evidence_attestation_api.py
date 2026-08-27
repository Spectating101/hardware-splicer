from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


KEY = "s" * 48


def _payload() -> dict:
    return {
        "ref": "lab://motor/current.csv",
        "content_base64": base64.b64encode(b"time,current\n0,1.42\n").decode("ascii"),
        "media_type": "text/csv",
    }


def test_attested_hash_route_fails_closed_without_signing_key(monkeypatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", raising=False)
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/physical-evidence/raw-files/hash-attested",
        json=_payload(),
    )

    assert response.status_code == 503
    assert response.json()["detail"]["type"] == "evidence_attestation_unavailable"


def test_attested_hash_route_signs_observed_bytes_without_leaking_key(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "api-key-1")
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/physical-evidence/raw-files/hash-attested",
        json=_payload(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["server_attested"] is True
    assert body["raw_bytes_persisted"] is False
    assert body["automatic_authorization"] is False
    attestation = body["file_ref"]["metadata"]["server_attestation"]
    assert attestation["key_id"] == "api-key-1"
    assert attestation["bytes_observed"] is True
    assert attestation["bytes_retained"] is False
    assert attestation["signature"].startswith("hmac-sha256:")
    assert KEY not in response.text
    assert _payload()["content_base64"] not in response.text


def test_hash_schema_reports_attestation_capability(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "api-key-1")
    client = TestClient(create_product_app())

    response = client.get(
        "/v1/engineering/physical-evidence/raw-files/schema"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["attestation_capability"]["signing_available"] is True
    assert body["attestation_capability"]["active_key_id"] == "api-key-1"
    assert body["attestation_algorithm"] == "hmac-sha256"
    assert body["plain_hash_proves_server_origin"] is False
    assert body["raw_bytes_persisted"] is False

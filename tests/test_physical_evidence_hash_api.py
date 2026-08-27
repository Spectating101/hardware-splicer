from __future__ import annotations

import base64
import hashlib

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def test_canonical_product_mounts_raw_evidence_hash_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/physical-evidence/raw-files/schema" in paths
    assert "/v1/engineering/physical-evidence/raw-files/hash" in paths


def test_hash_route_computes_digest_without_returning_bytes() -> None:
    client = TestClient(create_product_app())
    raw = b"joint,current_a\nhip,1.42\n"

    response = client.post(
        "/v1/engineering/physical-evidence/raw-files/hash",
        json={
            "ref": "lab://joint/current.csv",
            "content_base64": base64.b64encode(raw).decode("ascii"),
            "media_type": "text/csv",
            "captured_at": "2026-08-04T02:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file_ref"]["content_hash"] == (
        "sha256:" + hashlib.sha256(raw).hexdigest()
    )
    assert body["file_ref"]["size_bytes"] == len(raw)
    assert body["file_ref"]["metadata"]["server_computed"] is True
    assert body["raw_bytes_persisted"] is False
    assert body["automatic_authorization"] is False
    assert "content_base64" not in response.text


def test_hash_route_rejects_invalid_base64() -> None:
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/physical-evidence/raw-files/hash",
        json={"ref": "lab://bad.bin", "content_base64": "invalid@base64"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_raw_physical_evidence"


def test_hash_schema_discloses_bounded_nonretaining_behavior() -> None:
    client = TestClient(create_product_app())

    response = client.get(
        "/v1/engineering/physical-evidence/raw-files/schema"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["maximum_decoded_size_bytes"] == 8 * 1024 * 1024
    assert body["hash_algorithm"] == "sha256"
    assert body["transport_encoding"] == "base64"
    assert body["raw_bytes_persisted"] is False
    assert body["automatic_authorization"] is False

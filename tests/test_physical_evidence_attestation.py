from __future__ import annotations

import base64
import json
from datetime import datetime

from hardware_splicer.physical_evidence_attestation import (
    attest_raw_evidence_bytes,
    verify_evidence_file_attestation,
)


KEY = "k" * 48


def _request() -> dict:
    return {
        "ref": "lab://rail/run.csv",
        "content_base64": base64.b64encode(b"time,voltage\n0,4.91\n").decode("ascii"),
        "media_type": "text/csv",
        "captured_at": "2026-08-04T02:00:00Z",
    }


def test_attestation_verifies_and_covers_complete_file_reference(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "lab-key-1")
    result = attest_raw_evidence_bytes(
        _request(),
        issued_at=datetime.fromisoformat("2026-08-04T02:01:00+00:00"),
        attestation_id="attestation-1",
    )

    assert result.verification_blockers == []
    assert result.attestation.key_id == "lab-key-1"
    assert result.attestation.bytes_observed is True
    assert result.attestation.bytes_retained is False
    assert result.file_ref.metadata["server_attestation"]["signature"].startswith(
        "hmac-sha256:"
    )
    assert verify_evidence_file_attestation(result.file_ref) == []
    assert KEY not in json.dumps(result.model_dump(mode="json"))

    tampered = result.file_ref.model_copy(
        update={"content_hash": f"sha256:{'b' * 64}"},
        deep=True,
    )
    blockers = verify_evidence_file_attestation(tampered)
    assert any("signature is invalid" in row for row in blockers)


def test_old_attestation_verifies_after_signing_key_rotation(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "old-key")
    result = attest_raw_evidence_bytes(
        _request(),
        issued_at=datetime.fromisoformat("2026-08-04T02:01:00+00:00"),
        attestation_id="attestation-old",
    )

    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY")
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID")
    monkeypatch.setenv(
        "HARDWARE_SPLICER_EVIDENCE_VERIFICATION_KEYS",
        json.dumps({"old-key": KEY}),
    )

    assert verify_evidence_file_attestation(result.file_ref) == []


def test_missing_verification_key_blocks_attestation(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "temporary-key")
    result = attest_raw_evidence_bytes(_request())

    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY")
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID")
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_VERIFICATION_KEYS", raising=False)

    blockers = verify_evidence_file_attestation(result.file_ref)
    assert any("No verification key" in row for row in blockers)

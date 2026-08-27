from __future__ import annotations

import base64
import hashlib

import pytest

from hardware_splicer.physical_evidence_bytes import (
    MAX_RAW_EVIDENCE_BYTES,
    RawEvidenceHashRequest,
    hash_raw_evidence_bytes,
)


def test_server_computes_digest_and_does_not_retain_bytes() -> None:
    raw = b"time_s,voltage_v\n0.0,4.91\n"
    result = hash_raw_evidence_bytes(
        RawEvidenceHashRequest(
            ref="lab://rail/run.csv",
            content_base64=base64.b64encode(raw).decode("ascii"),
            media_type="text/csv",
            captured_at="2026-08-04T02:00:00Z",
            metadata={"fixture": "current-limited"},
        )
    )

    assert result.file_ref.content_hash == (
        "sha256:" + hashlib.sha256(raw).hexdigest()
    )
    assert result.file_ref.size_bytes == len(raw)
    assert result.decoded_size_bytes == len(raw)
    assert result.bytes_retained is False
    assert result.file_ref.metadata["server_computed"] is True
    assert result.file_ref.metadata["bytes_retained"] is False
    assert result.metadata["raw_bytes_persisted"] is False
    assert "content_base64" not in result.model_dump(mode="json")


def test_invalid_base64_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid canonical base64"):
        hash_raw_evidence_bytes(
            {
                "ref": "lab://invalid.bin",
                "content_base64": "not@base64!",
            }
        )


def test_decoded_size_limit_is_enforced() -> None:
    oversized = b"x" * (MAX_RAW_EVIDENCE_BYTES + 1)
    encoded = base64.b64encode(oversized).decode("ascii")

    with pytest.raises(ValueError, match="exceeds"):
        hash_raw_evidence_bytes(
            {
                "ref": "lab://oversized.bin",
                "content_base64": encoded,
            }
        )

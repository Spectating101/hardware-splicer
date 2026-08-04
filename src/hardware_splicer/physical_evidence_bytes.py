"""Bounded hashing of raw physical-evidence bytes.

The helper accepts base64 only as a transport encoding, computes SHA-256 over the
decoded bytes, and returns an EvidenceFileRef. Raw bytes are never retained by this
module. This closes the gap where an envelope could previously trust a digest supplied
entirely by the caller.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .physical_evidence_ledger import EvidenceFileRef


RAW_EVIDENCE_HASH_SCHEMA = "hardware_splicer.raw_evidence_hash.v1"
MAX_RAW_EVIDENCE_BYTES = 8 * 1024 * 1024
MAX_BASE64_CHARACTERS = 4 * ((MAX_RAW_EVIDENCE_BYTES + 2) // 3)


class RawEvidenceBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RawEvidenceHashRequest(RawEvidenceBase):
    ref: str = Field(min_length=1, max_length=2048)
    content_base64: str = Field(min_length=1, max_length=MAX_BASE64_CHARACTERS)
    media_type: str = Field(default="application/octet-stream", min_length=1, max_length=255)
    captured_at: str | None = Field(default=None, max_length=128)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RawEvidenceHashResult(RawEvidenceBase):
    schema_version: str = RAW_EVIDENCE_HASH_SCHEMA
    file_ref: EvidenceFileRef
    decoded_size_bytes: int = Field(ge=0)
    bytes_retained: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _decode_base64(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("content_base64 is not valid canonical base64") from exc
    if len(decoded) > MAX_RAW_EVIDENCE_BYTES:
        raise ValueError(
            f"decoded raw evidence exceeds {MAX_RAW_EVIDENCE_BYTES} bytes"
        )
    return decoded


def hash_raw_evidence_bytes(
    request: RawEvidenceHashRequest | Mapping[str, Any],
) -> RawEvidenceHashResult:
    """Compute a bounded SHA-256 file reference without retaining raw bytes."""

    resolved = (
        request
        if isinstance(request, RawEvidenceHashRequest)
        else RawEvidenceHashRequest.model_validate(request)
    )
    decoded = _decode_base64(resolved.content_base64)
    digest = f"sha256:{hashlib.sha256(decoded).hexdigest()}"
    metadata = {
        **dict(resolved.metadata),
        "schema_version": RAW_EVIDENCE_HASH_SCHEMA,
        "hash_algorithm": "sha256",
        "server_computed": True,
        "transport_encoding": "base64",
        "bytes_retained": False,
        "maximum_decoded_size_bytes": MAX_RAW_EVIDENCE_BYTES,
    }
    file_ref = EvidenceFileRef(
        ref=resolved.ref,
        content_hash=digest,
        media_type=resolved.media_type,
        size_bytes=len(decoded),
        captured_at=resolved.captured_at,
        metadata=metadata,
    )
    return RawEvidenceHashResult(
        file_ref=file_ref,
        decoded_size_bytes=len(decoded),
        bytes_retained=False,
        metadata={
            "server_computed": True,
            "raw_bytes_persisted": False,
            "automatic_authorization": False,
        },
    )

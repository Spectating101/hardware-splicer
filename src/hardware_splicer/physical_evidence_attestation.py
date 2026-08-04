"""Server attestations for raw physical-evidence file references.

A SHA-256 digest detects later byte changes but does not prove which service observed
the bytes. This module adds an HMAC-SHA256 attestation over the complete unsigned
EvidenceFileRef. Signing keys are supplied only through environment configuration;
verification supports a keyring so older attestations survive key rotation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .physical_evidence_bytes import RawEvidenceHashRequest, hash_raw_evidence_bytes
from .physical_evidence_ledger import EvidenceFileRef


EVIDENCE_ATTESTATION_SCHEMA = "hardware_splicer.evidence_file_attestation.v1"
_ATTESTATION_METADATA_KEY = "server_attestation"
_SIGNING_KEY_ENV = "HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY"
_SIGNING_KEY_ID_ENV = "HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID"
_VERIFICATION_KEYS_ENV = "HARDWARE_SPLICER_EVIDENCE_VERIFICATION_KEYS"
_MINIMUM_KEY_BYTES = 32
_MAXIMUM_FUTURE_SKEW = timedelta(minutes=5)


class EvidenceAttestationError(RuntimeError):
    pass


class EvidenceAttestationUnavailable(EvidenceAttestationError):
    pass


class AttestationBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EvidenceFileAttestation(AttestationBase):
    schema_version: str = EVIDENCE_ATTESTATION_SCHEMA
    attestation_id: str = Field(min_length=1)
    key_id: str = Field(min_length=1)
    algorithm: str = "hmac-sha256"
    issued_at: str = Field(min_length=1)
    signature: str = Field(pattern=r"^hmac-sha256:[0-9a-f]{64}$")
    bytes_observed: bool = True
    bytes_retained: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AttestedEvidenceFileResult(AttestationBase):
    file_ref: EvidenceFileRef
    attestation: EvidenceFileAttestation
    verification_blockers: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _canonical(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _parse_time(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _key_bytes(value: str, *, label: str) -> bytes:
    key = value.encode("utf-8")
    if len(key) < _MINIMUM_KEY_BYTES:
        raise EvidenceAttestationUnavailable(
            f"{label} must contain at least {_MINIMUM_KEY_BYTES} UTF-8 bytes"
        )
    return key


def _active_signing_key() -> tuple[str, bytes]:
    raw = os.getenv(_SIGNING_KEY_ENV, "")
    if not raw:
        raise EvidenceAttestationUnavailable(
            f"{_SIGNING_KEY_ENV} is required for server-attested evidence hashing"
        )
    key = _key_bytes(raw, label=_SIGNING_KEY_ENV)
    key_id = os.getenv(_SIGNING_KEY_ID_ENV, "").strip()
    if not key_id:
        key_id = hashlib.sha256(key).hexdigest()[:16]
    return key_id, key


def _verification_keys() -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    raw_keyring = os.getenv(_VERIFICATION_KEYS_ENV, "").strip()
    if raw_keyring:
        try:
            parsed = json.loads(raw_keyring)
        except json.JSONDecodeError as exc:
            raise EvidenceAttestationUnavailable(
                f"{_VERIFICATION_KEYS_ENV} must be a JSON object"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise EvidenceAttestationUnavailable(
                f"{_VERIFICATION_KEYS_ENV} must be a JSON object"
            )
        for key_id, value in parsed.items():
            if not isinstance(key_id, str) or not isinstance(value, str):
                raise EvidenceAttestationUnavailable(
                    f"{_VERIFICATION_KEYS_ENV} keys and values must be strings"
                )
            result[key_id] = _key_bytes(
                value,
                label=f"{_VERIFICATION_KEYS_ENV}[{key_id!r}]",
            )
    try:
        active_id, active_key = _active_signing_key()
    except EvidenceAttestationUnavailable:
        pass
    else:
        result[active_id] = active_key
    return result


def attestation_capability() -> Dict[str, Any]:
    try:
        key_id, _ = _active_signing_key()
        signing_available = True
    except EvidenceAttestationUnavailable:
        key_id = None
        signing_available = False
    verification_error = None
    try:
        verification_ids = sorted(_verification_keys())
    except EvidenceAttestationUnavailable as exc:
        verification_ids = []
        verification_error = str(exc)
    return {
        "schema_version": EVIDENCE_ATTESTATION_SCHEMA,
        "signing_available": signing_available,
        "active_key_id": key_id,
        "verification_key_ids": verification_ids,
        "verification_configuration_valid": verification_error is None,
        "verification_configuration_error": verification_error,
        "algorithm": "hmac-sha256",
        "minimum_key_bytes": _MINIMUM_KEY_BYTES,
        "maximum_future_clock_skew_seconds": int(
            _MAXIMUM_FUTURE_SKEW.total_seconds()
        ),
        "bytes_retained": False,
        "automatic_authorization": False,
    }


def _unsigned_file_ref(file_ref: EvidenceFileRef) -> EvidenceFileRef:
    metadata = dict(file_ref.metadata)
    metadata.pop(_ATTESTATION_METADATA_KEY, None)
    return file_ref.model_copy(update={"metadata": metadata}, deep=True)


def _attestation_payload(
    file_ref: EvidenceFileRef,
    *,
    attestation_id: str,
    key_id: str,
    issued_at: str,
) -> Dict[str, Any]:
    return {
        "schema_version": EVIDENCE_ATTESTATION_SCHEMA,
        "attestation_id": attestation_id,
        "key_id": key_id,
        "algorithm": "hmac-sha256",
        "issued_at": issued_at,
        "file_ref": _unsigned_file_ref(file_ref).model_dump(mode="json"),
        "bytes_observed": True,
        "bytes_retained": False,
    }


def attest_evidence_file_ref(
    file_ref: EvidenceFileRef | Mapping[str, Any],
    *,
    issued_at: datetime | None = None,
    attestation_id: str | None = None,
) -> AttestedEvidenceFileResult:
    """Attach and immediately self-verify a server HMAC over one file reference."""

    resolved = (
        file_ref
        if isinstance(file_ref, EvidenceFileRef)
        else EvidenceFileRef.model_validate(file_ref)
    )
    unsigned = _unsigned_file_ref(resolved)
    if unsigned.metadata.get("server_computed") is not True:
        raise ValueError(
            "EvidenceFileRef must be produced by server-side byte hashing before attestation"
        )
    key_id, key = _active_signing_key()
    now = (issued_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    token = attestation_id or str(uuid.uuid4())
    payload = _attestation_payload(
        unsigned,
        attestation_id=token,
        key_id=key_id,
        issued_at=now.isoformat(),
    )
    signature = "hmac-sha256:" + hmac.new(
        key,
        _canonical(payload),
        hashlib.sha256,
    ).hexdigest()
    attestation = EvidenceFileAttestation(
        attestation_id=token,
        key_id=key_id,
        issued_at=now.isoformat(),
        signature=signature,
        bytes_observed=True,
        bytes_retained=False,
        metadata={
            "raw_bytes_persisted": False,
            "automatic_authorization": False,
        },
    )
    metadata = dict(unsigned.metadata)
    metadata[_ATTESTATION_METADATA_KEY] = attestation.model_dump(mode="json")
    attested_ref = unsigned.model_copy(update={"metadata": metadata}, deep=True)
    blockers = verify_evidence_file_attestation(attested_ref)
    if blockers:
        raise EvidenceAttestationUnavailable(
            "server attestation self-verification failed: "
            + " ".join(blockers)
        )
    return AttestedEvidenceFileResult(
        file_ref=attested_ref,
        attestation=attestation,
        verification_blockers=[],
        metadata={
            "server_attested": True,
            "raw_bytes_persisted": False,
            "automatic_authorization": False,
        },
    )


def attest_raw_evidence_bytes(
    request: RawEvidenceHashRequest | Mapping[str, Any],
    *,
    issued_at: datetime | None = None,
    attestation_id: str | None = None,
) -> AttestedEvidenceFileResult:
    hashed = hash_raw_evidence_bytes(request)
    return attest_evidence_file_ref(
        hashed.file_ref,
        issued_at=issued_at,
        attestation_id=attestation_id,
    )


def verify_evidence_file_attestation(
    file_ref: EvidenceFileRef | Mapping[str, Any],
) -> list[str]:
    resolved = (
        file_ref
        if isinstance(file_ref, EvidenceFileRef)
        else EvidenceFileRef.model_validate(file_ref)
    )
    raw_attestation = resolved.metadata.get(_ATTESTATION_METADATA_KEY)
    if not isinstance(raw_attestation, Mapping):
        return [f"Raw evidence file {resolved.ref!r} lacks a server attestation."]
    try:
        attestation = EvidenceFileAttestation.model_validate(raw_attestation)
    except ValueError as exc:
        return [f"Raw evidence file {resolved.ref!r} has an invalid server attestation: {exc}"]
    blockers: list[str] = []
    issued_at = _parse_time(attestation.issued_at)
    if issued_at is None:
        blockers.append(
            f"Raw evidence file {resolved.ref!r} attestation has an invalid issued_at timestamp."
        )
    elif issued_at > datetime.now(timezone.utc) + _MAXIMUM_FUTURE_SKEW:
        blockers.append(
            f"Raw evidence file {resolved.ref!r} attestation is materially future-dated."
        )
    try:
        keys = _verification_keys()
    except EvidenceAttestationUnavailable as exc:
        blockers.append(str(exc))
        return list(dict.fromkeys(blockers))
    key = keys.get(attestation.key_id)
    if key is None:
        blockers.append(
            f"No verification key is configured for evidence attestation key_id {attestation.key_id!r}."
        )
        return list(dict.fromkeys(blockers))
    payload = _attestation_payload(
        resolved,
        attestation_id=attestation.attestation_id,
        key_id=attestation.key_id,
        issued_at=attestation.issued_at,
    )
    expected = "hmac-sha256:" + hmac.new(
        key,
        _canonical(payload),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, attestation.signature):
        blockers.append(
            f"Raw evidence file {resolved.ref!r} server attestation signature is invalid."
        )
    if attestation.bytes_observed is not True:
        blockers.append(
            f"Raw evidence file {resolved.ref!r} attestation does not confirm byte observation."
        )
    if attestation.bytes_retained is not False:
        blockers.append(
            f"Raw evidence file {resolved.ref!r} attestation has an invalid retention declaration."
        )
    return list(dict.fromkeys(blockers))

"""Tamper-evident envelopes and authorization ledger for physical evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .physical_evidence import (
    AuthorizationDecision,
    AuthorizationStatus,
    PhysicalEvidenceRecord,
)


PHYSICAL_EVIDENCE_ENVELOPE_SCHEMA = "hardware_splicer.physical_evidence_envelope.v1"
AUTHORIZATION_LEDGER_SCHEMA = "hardware_splicer.authorization_ledger.v1"


class LedgerBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EvidenceFileRef(LedgerBase):
    ref: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_type: str = "application/octet-stream"
    size_bytes: int | None = Field(default=None, ge=0)
    captured_at: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PhysicalEvidenceEnvelope(LedgerBase):
    schema_version: str = PHYSICAL_EVIDENCE_ENVELOPE_SCHEMA
    envelope_id: str = Field(min_length=1)
    record: PhysicalEvidenceRecord
    raw_files: list[EvidenceFileRef] = Field(min_length=1)
    created_at: str = Field(min_length=1)
    created_by: str = Field(min_length=1)
    envelope_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuthorizationLedgerEntry(LedgerBase):
    schema_version: str = AUTHORIZATION_LEDGER_SCHEMA
    entry_id: str = Field(min_length=1)
    decision: AuthorizationDecision
    recorded_at: str = Field(min_length=1)
    recorded_by: str = Field(min_length=1)
    previous_entry_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    entry_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuthorizationLedgerAssessment(LedgerBase):
    valid: bool
    entry_count: int
    latest_entry_id: str | None = None
    latest_entry_hash: str | None = None
    applicable_authorization_id: str | None = None
    applicable_scope_id: str | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _canonical(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _sha256(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    token = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(token)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def physical_evidence_envelope_hash(
    *,
    envelope_id: str,
    record: PhysicalEvidenceRecord,
    raw_files: Iterable[EvidenceFileRef],
    created_at: str,
    created_by: str,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    return _sha256(
        {
            "schema_version": PHYSICAL_EVIDENCE_ENVELOPE_SCHEMA,
            "envelope_id": envelope_id,
            "record": record.model_dump(mode="json"),
            "raw_files": [row.model_dump(mode="json") for row in raw_files],
            "created_at": created_at,
            "created_by": created_by,
            "metadata": dict(metadata or {}),
        }
    )


def build_physical_evidence_envelope(
    *,
    envelope_id: str,
    record: PhysicalEvidenceRecord | Mapping[str, Any],
    raw_files: Iterable[EvidenceFileRef | Mapping[str, Any]],
    created_at: str,
    created_by: str,
    metadata: Mapping[str, Any] | None = None,
) -> PhysicalEvidenceEnvelope:
    resolved_record = (
        record if isinstance(record, PhysicalEvidenceRecord)
        else PhysicalEvidenceRecord.model_validate(record)
    )
    files = [
        value if isinstance(value, EvidenceFileRef)
        else EvidenceFileRef.model_validate(value)
        for value in raw_files
    ]
    digest = physical_evidence_envelope_hash(
        envelope_id=envelope_id,
        record=resolved_record,
        raw_files=files,
        created_at=created_at,
        created_by=created_by,
        metadata=metadata,
    )
    return PhysicalEvidenceEnvelope(
        envelope_id=envelope_id,
        record=resolved_record,
        raw_files=files,
        created_at=created_at,
        created_by=created_by,
        envelope_hash=digest,
        metadata=dict(metadata or {}),
    )


def validate_physical_evidence_envelope(
    envelope: PhysicalEvidenceEnvelope | Mapping[str, Any],
) -> list[str]:
    resolved = (
        envelope if isinstance(envelope, PhysicalEvidenceEnvelope)
        else PhysicalEvidenceEnvelope.model_validate(envelope)
    )
    expected = physical_evidence_envelope_hash(
        envelope_id=resolved.envelope_id,
        record=resolved.record,
        raw_files=resolved.raw_files,
        created_at=resolved.created_at,
        created_by=resolved.created_by,
        metadata=resolved.metadata,
    )
    blockers: list[str] = []
    if expected != resolved.envelope_hash:
        blockers.append(
            f"Physical evidence envelope {resolved.envelope_id} hash does not match its content."
        )
    declared_refs = set(resolved.record.raw_refs)
    envelope_refs = {row.ref for row in resolved.raw_files}
    missing = sorted(declared_refs - envelope_refs)
    if missing:
        blockers.append(
            f"Physical evidence envelope {resolved.envelope_id} omits declared raw refs: {', '.join(missing)}."
        )
    return blockers


def authorization_entry_hash(
    *,
    entry_id: str,
    decision: AuthorizationDecision,
    recorded_at: str,
    recorded_by: str,
    previous_entry_hash: str | None,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    return _sha256(
        {
            "schema_version": AUTHORIZATION_LEDGER_SCHEMA,
            "entry_id": entry_id,
            "decision": decision.model_dump(mode="json"),
            "recorded_at": recorded_at,
            "recorded_by": recorded_by,
            "previous_entry_hash": previous_entry_hash,
            "metadata": dict(metadata or {}),
        }
    )


def build_authorization_ledger_entry(
    *,
    entry_id: str,
    decision: AuthorizationDecision | Mapping[str, Any],
    recorded_at: str,
    recorded_by: str,
    previous_entry_hash: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> AuthorizationLedgerEntry:
    resolved = (
        decision if isinstance(decision, AuthorizationDecision)
        else AuthorizationDecision.model_validate(decision)
    )
    digest = authorization_entry_hash(
        entry_id=entry_id,
        decision=resolved,
        recorded_at=recorded_at,
        recorded_by=recorded_by,
        previous_entry_hash=previous_entry_hash,
        metadata=metadata,
    )
    return AuthorizationLedgerEntry(
        entry_id=entry_id,
        decision=resolved,
        recorded_at=recorded_at,
        recorded_by=recorded_by,
        previous_entry_hash=previous_entry_hash,
        entry_hash=digest,
        metadata=dict(metadata or {}),
    )


def validate_authorization_ledger(
    entries: Iterable[AuthorizationLedgerEntry | Mapping[str, Any]],
    *,
    project_id: str | None = None,
    candidate_revision: str | None = None,
    scope_id: str | None = None,
    as_of: datetime | None = None,
) -> AuthorizationLedgerAssessment:
    resolved = [
        value if isinstance(value, AuthorizationLedgerEntry)
        else AuthorizationLedgerEntry.model_validate(value)
        for value in entries
    ]
    blockers: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    previous_hash: str | None = None
    latest_applicable: AuthorizationLedgerEntry | None = None
    now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)

    for index, entry in enumerate(resolved):
        if entry.entry_id in seen_ids:
            blockers.append(f"Authorization ledger entry_id {entry.entry_id!r} is duplicated.")
        seen_ids.add(entry.entry_id)
        if entry.previous_entry_hash != previous_hash:
            blockers.append(
                f"Authorization ledger entry {entry.entry_id} does not chain to the prior entry."
            )
        expected = authorization_entry_hash(
            entry_id=entry.entry_id,
            decision=entry.decision,
            recorded_at=entry.recorded_at,
            recorded_by=entry.recorded_by,
            previous_entry_hash=entry.previous_entry_hash,
            metadata=entry.metadata,
        )
        if expected != entry.entry_hash:
            blockers.append(
                f"Authorization ledger entry {entry.entry_id} hash does not match its content."
            )
        recorded = _parse_time(entry.recorded_at)
        if recorded is not None and recorded > now:
            blockers.append(
                f"Authorization ledger entry {entry.entry_id} is dated in the future."
            )

        decision = entry.decision
        scope = decision.scope
        matches = True
        if project_id is not None and scope.project_id != project_id:
            matches = False
        if candidate_revision is not None and scope.candidate_revision != candidate_revision:
            matches = False
        if scope_id is not None and scope.scope_id != scope_id:
            matches = False
        expires = _parse_time(decision.expires_at)
        unexpired = expires is None or expires >= now
        if matches:
            if decision.status == AuthorizationStatus.AUTHORIZED and unexpired:
                latest_applicable = entry
            elif decision.status in {
                AuthorizationStatus.DENIED,
                AuthorizationStatus.REVOKED,
                AuthorizationStatus.EXPIRED,
            }:
                latest_applicable = None
        previous_hash = entry.entry_hash

    if not resolved:
        blockers.append("Authorization ledger is empty.")
    if project_id and candidate_revision and latest_applicable is None:
        warnings.append(
            f"No current authorization applies to {project_id} revision {candidate_revision}."
        )
    return AuthorizationLedgerAssessment(
        valid=not blockers,
        entry_count=len(resolved),
        latest_entry_id=resolved[-1].entry_id if resolved else None,
        latest_entry_hash=resolved[-1].entry_hash if resolved else None,
        applicable_authorization_id=(
            latest_applicable.decision.authorization_id
            if latest_applicable is not None
            else None
        ),
        applicable_scope_id=(
            latest_applicable.decision.scope.scope_id
            if latest_applicable is not None
            else None
        ),
        blockers=list(dict.fromkeys(blockers)),
        warnings=list(dict.fromkeys(warnings)),
        metadata={
            "tamper_evident_hash_chain": True,
            "automatic_authorization": False,
            "authorization_carries_across_revisions": False,
        },
    )

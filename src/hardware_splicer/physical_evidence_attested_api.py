"""API for server-attested evidence envelopes and strict audited release checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .attested_audited_physical_evidence import (
    assess_attested_audited_physical_authorization,
)
from .machine_project import MachineProject
from .physical_evidence import (
    CalibrationRecord,
    PhysicalEvidenceRecord,
    PhysicalOperation,
)
from .physical_evidence_attestation import (
    EvidenceAttestationUnavailable,
    attest_raw_evidence_bytes,
    attestation_capability,
    verify_evidence_file_attestation,
)
from .physical_evidence_bytes import RawEvidenceHashRequest
from .physical_evidence_ledger import (
    AuthorizationLedgerEntry,
    PhysicalEvidenceEnvelope,
    build_physical_evidence_envelope,
    validate_physical_evidence_envelope,
)
from .scoped_release import assess_scoped_release


MAX_ATTESTED_ENVELOPE_RAW_BYTES = 16 * 1024 * 1024
MAX_ATTESTED_ENVELOPE_FILE_COUNT = 8


class AttestedEnvelopeBuildRequest(BaseModel):
    envelope_id: str = Field(min_length=1)
    record: PhysicalEvidenceRecord
    raw_files: list[RawEvidenceHashRequest] = Field(
        min_length=1,
        max_length=MAX_ATTESTED_ENVELOPE_FILE_COUNT,
    )
    created_at: str = Field(min_length=1)
    created_by: str = Field(min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AttestedAuditRequest(BaseModel):
    plan: Dict[str, Any]
    calibrations: list[CalibrationRecord] = Field(default_factory=list)
    envelopes: list[PhysicalEvidenceEnvelope] = Field(default_factory=list)
    ledger_entries: list[AuthorizationLedgerEntry] = Field(default_factory=list)
    scope_id: str | None = None
    as_of: datetime | None = None


class AttestedReleaseRequest(AttestedAuditRequest):
    machine_project: MachineProject
    requested_operations: list[PhysicalOperation] = Field(min_length=1)


def _estimated_decoded_size(value: str) -> int:
    text = value.rstrip("=")
    return (len(text) * 3) // 4


def create_physical_evidence_attested_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/engineering/physical-evidence",
        tags=["engineering", "physical-evidence", "attestation"],
    )

    @router.get("/attested/schema")
    def attested_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "envelope_build_request_schema": AttestedEnvelopeBuildRequest.model_json_schema(),
            "audit_request_schema": AttestedAuditRequest.model_json_schema(),
            "release_request_schema": AttestedReleaseRequest.model_json_schema(),
            "attestation_capability": attestation_capability(),
            "maximum_envelope_raw_bytes": MAX_ATTESTED_ENVELOPE_RAW_BYTES,
            "maximum_envelope_file_count": MAX_ATTESTED_ENVELOPE_FILE_COUNT,
            "server_attestation_required": True,
            "plain_hash_sufficient": False,
            "raw_bytes_persisted": False,
            "automatic_authorization": False,
        }

    @router.post("/envelopes/build-attested")
    def build_attested_envelope(
        request: AttestedEnvelopeBuildRequest,
    ) -> Dict[str, Any]:
        try:
            estimated_total = sum(
                _estimated_decoded_size(value.content_base64)
                for value in request.raw_files
            )
            if estimated_total > MAX_ATTESTED_ENVELOPE_RAW_BYTES:
                raise ValueError(
                    "combined decoded raw evidence exceeds "
                    f"{MAX_ATTESTED_ENVELOPE_RAW_BYTES} bytes"
                )
            attested_files = [
                attest_raw_evidence_bytes(value).file_ref
                for value in request.raw_files
            ]
            decoded_total = sum(value.size_bytes or 0 for value in attested_files)
            if decoded_total > MAX_ATTESTED_ENVELOPE_RAW_BYTES:
                raise ValueError(
                    "combined decoded raw evidence exceeds "
                    f"{MAX_ATTESTED_ENVELOPE_RAW_BYTES} bytes"
                )
            envelope = build_physical_evidence_envelope(
                envelope_id=request.envelope_id,
                record=request.record,
                raw_files=attested_files,
                created_at=request.created_at,
                created_by=request.created_by,
                metadata={
                    **request.metadata,
                    "server_attested_raw_files": True,
                    "plain_hash_sufficient": False,
                    "raw_bytes_persisted": False,
                    "automatic_authorization": False,
                },
            )
            blockers = validate_physical_evidence_envelope(envelope)
            for file_ref in envelope.raw_files:
                blockers.extend(verify_evidence_file_attestation(file_ref))
            blockers = list(dict.fromkeys(blockers))
            if blockers:
                raise ValueError(" ".join(blockers))
        except EvidenceAttestationUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"type": "evidence_attestation_unavailable", "message": str(exc)},
            ) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_attested_evidence_envelope", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "evidence_envelope": envelope.model_dump(mode="json"),
            "attested_raw_file_count": len(attested_files),
            "decoded_size_bytes": decoded_total,
            "server_attested": True,
            "raw_bytes_persisted": False,
            "automatic_authorization": False,
        }

    @router.post("/attested-audited-assess")
    def attested_audited_assess(request: AttestedAuditRequest) -> Dict[str, Any]:
        try:
            audited = assess_attested_audited_physical_authorization(
                request.plan,
                calibrations=request.calibrations,
                envelopes=request.envelopes,
                ledger_entries=request.ledger_entries,
                scope_id=request.scope_id,
                as_of=request.as_of,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_attested_physical_evidence", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "attested_audited_physical_evidence": audited.model_dump(mode="json"),
            "authorization_applicable": audited.applicable,
            "server_attestation_valid": bool(
                audited.metadata.get("server_attestation_valid")
            ),
            "authorization_ledger_valid": audited.ledger_assessment.valid,
            "automatic_authorization": False,
        }

    @router.post("/attested-audited-release-assess")
    def attested_audited_release_assess(
        request: AttestedReleaseRequest,
    ) -> Dict[str, Any]:
        try:
            audited = assess_attested_audited_physical_authorization(
                request.plan,
                calibrations=request.calibrations,
                envelopes=request.envelopes,
                ledger_entries=request.ledger_entries,
                scope_id=request.scope_id,
                as_of=request.as_of,
            )
            release = assess_scoped_release(
                request.machine_project,
                audited.physical_package,
                requested_operations=request.requested_operations,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_attested_scoped_release", "message": str(exc)},
            ) from exc
        allowed = audited.applicable and release.allowed
        return {
            "ok": True,
            "attested_audited_physical_evidence": audited.model_dump(mode="json"),
            "scoped_release": release.model_dump(mode="json"),
            "allowed": allowed,
            "server_attestation_valid": bool(
                audited.metadata.get("server_attestation_valid")
            ),
            "authorization_ledger_valid": audited.ledger_assessment.valid,
            "automatic_authorization": False,
            "global_authority_flags_unchanged": True,
        }

    return router

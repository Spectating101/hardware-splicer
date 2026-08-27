"""API surface for calibrated physical evidence and scoped human authorization."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .audited_physical_evidence import (
    AuditedPhysicalEvidencePackage,
    assess_audited_physical_authorization,
)
from .machine_project import MachineProject
from .physical_evidence import (
    AuthorizationDecision,
    CalibrationRecord,
    PhysicalEvidencePackage,
    PhysicalEvidenceRecord,
    PhysicalOperation,
    assess_physical_authorization,
    attach_physical_evidence,
)
from .physical_evidence_ledger import (
    AuthorizationLedgerEntry,
    EvidenceFileRef,
    PhysicalEvidenceEnvelope,
    build_authorization_ledger_entry,
    build_physical_evidence_envelope,
)
from .scoped_release import ScopedReleaseAssessment, assess_scoped_release


class PhysicalEvidenceAssessmentRequest(BaseModel):
    plan: Dict[str, Any]
    calibrations: list[CalibrationRecord] = Field(default_factory=list)
    evidence: list[PhysicalEvidenceRecord] = Field(default_factory=list)
    decision: AuthorizationDecision | None = None
    as_of: datetime | None = None


class PhysicalEvidenceAttachRequest(PhysicalEvidenceAssessmentRequest):
    machine_project: MachineProject


class ScopedReleaseRequest(PhysicalEvidenceAssessmentRequest):
    machine_project: MachineProject
    requested_operations: list[PhysicalOperation] = Field(min_length=1)


class EvidenceEnvelopeBuildRequest(BaseModel):
    envelope_id: str
    record: PhysicalEvidenceRecord
    raw_files: list[EvidenceFileRef] = Field(min_length=1)
    created_at: str
    created_by: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuthorizationLedgerEntryBuildRequest(BaseModel):
    entry_id: str
    decision: AuthorizationDecision
    recorded_at: str
    recorded_by: str
    previous_entry_hash: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditedPhysicalAssessmentRequest(BaseModel):
    plan: Dict[str, Any]
    calibrations: list[CalibrationRecord] = Field(default_factory=list)
    envelopes: list[PhysicalEvidenceEnvelope] = Field(default_factory=list)
    ledger_entries: list[AuthorizationLedgerEntry] = Field(default_factory=list)
    scope_id: str | None = None
    as_of: datetime | None = None


class AuditedScopedReleaseRequest(AuditedPhysicalAssessmentRequest):
    machine_project: MachineProject
    requested_operations: list[PhysicalOperation] = Field(min_length=1)


def create_physical_evidence_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/engineering/physical-evidence",
        tags=["engineering", "physical-evidence"],
    )

    @router.get("/schema")
    def physical_evidence_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "calibration_schema": CalibrationRecord.model_json_schema(),
            "evidence_schema": PhysicalEvidenceRecord.model_json_schema(),
            "decision_schema": AuthorizationDecision.model_json_schema(),
            "package_schema": PhysicalEvidencePackage.model_json_schema(),
            "release_schema": ScopedReleaseAssessment.model_json_schema(),
            "evidence_envelope_schema": PhysicalEvidenceEnvelope.model_json_schema(),
            "authorization_ledger_entry_schema": AuthorizationLedgerEntry.model_json_schema(),
            "audited_package_schema": AuditedPhysicalEvidencePackage.model_json_schema(),
            "tamper_evident_envelopes_supported": True,
            "authorization_hash_chain_supported": True,
            "automatic_authorization": False,
        }

    @router.post("/assess")
    def assess(request: PhysicalEvidenceAssessmentRequest) -> Dict[str, Any]:
        try:
            package = assess_physical_authorization(
                request.plan,
                calibrations=request.calibrations,
                evidence=request.evidence,
                decision=request.decision,
                as_of=request.as_of,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_physical_evidence", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "physical_evidence_package": package.model_dump(mode="json"),
            "authorization_applicable": package.assessment.applicable,
            "authorized_operations": [
                value.value for value in package.assessment.authorized_operations
            ],
            "tamper_evident_envelopes_validated": False,
            "authorization_ledger_validated": False,
            "automatic_authorization": False,
        }

    @router.post("/attach")
    def attach(request: PhysicalEvidenceAttachRequest) -> Dict[str, Any]:
        try:
            package = assess_physical_authorization(
                request.plan,
                calibrations=request.calibrations,
                evidence=request.evidence,
                decision=request.decision,
                as_of=request.as_of,
            )
            project = attach_physical_evidence(request.machine_project, package)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_physical_evidence", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "machine_project": project.model_dump(mode="json"),
            "physical_evidence_package": package.model_dump(mode="json"),
            "automatic_authorization": False,
        }

    @router.post("/release-assess")
    def release_assess(request: ScopedReleaseRequest) -> Dict[str, Any]:
        try:
            package = assess_physical_authorization(
                request.plan,
                calibrations=request.calibrations,
                evidence=request.evidence,
                decision=request.decision,
                as_of=request.as_of,
            )
            release = assess_scoped_release(
                request.machine_project,
                package,
                requested_operations=request.requested_operations,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_scoped_release", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "scoped_release": release.model_dump(mode="json"),
            "allowed": release.allowed,
            "tamper_evident_envelopes_validated": False,
            "authorization_ledger_validated": False,
            "automatic_authorization": False,
        }

    @router.post("/envelopes/build")
    def build_envelope(request: EvidenceEnvelopeBuildRequest) -> Dict[str, Any]:
        try:
            envelope = build_physical_evidence_envelope(
                envelope_id=request.envelope_id,
                record=request.record,
                raw_files=request.raw_files,
                created_at=request.created_at,
                created_by=request.created_by,
                metadata=request.metadata,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_physical_evidence_envelope", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "evidence_envelope": envelope.model_dump(mode="json"),
            "automatic_authorization": False,
        }

    @router.post("/ledger/build-entry")
    def build_ledger_entry(request: AuthorizationLedgerEntryBuildRequest) -> Dict[str, Any]:
        try:
            entry = build_authorization_ledger_entry(
                entry_id=request.entry_id,
                decision=request.decision,
                recorded_at=request.recorded_at,
                recorded_by=request.recorded_by,
                previous_entry_hash=request.previous_entry_hash,
                metadata=request.metadata,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_authorization_ledger_entry", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "authorization_ledger_entry": entry.model_dump(mode="json"),
            "automatic_authorization": False,
        }

    @router.post("/audited-assess")
    def audited_assess(request: AuditedPhysicalAssessmentRequest) -> Dict[str, Any]:
        try:
            audited = assess_audited_physical_authorization(
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
                detail={"type": "invalid_audited_physical_evidence", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "audited_physical_evidence": audited.model_dump(mode="json"),
            "authorization_applicable": audited.applicable,
            "tamper_evident_envelopes_validated": not any(
                "envelope" in row.lower() for row in audited.blockers
            ),
            "authorization_ledger_validated": audited.ledger_assessment.valid,
            "automatic_authorization": False,
        }

    @router.post("/audited-release-assess")
    def audited_release_assess(request: AuditedScopedReleaseRequest) -> Dict[str, Any]:
        try:
            audited = assess_audited_physical_authorization(
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
                detail={"type": "invalid_audited_scoped_release", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "audited_physical_evidence": audited.model_dump(mode="json"),
            "scoped_release": release.model_dump(mode="json"),
            "allowed": audited.applicable and release.allowed,
            "tamper_evident_envelopes_validated": not any(
                "envelope" in row.lower() for row in audited.blockers
            ),
            "authorization_ledger_validated": audited.ledger_assessment.valid,
            "automatic_authorization": False,
        }

    return router

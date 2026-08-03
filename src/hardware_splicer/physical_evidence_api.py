"""API surface for calibrated physical evidence and scoped human authorization."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

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
            "automatic_authorization": False,
        }

    return router

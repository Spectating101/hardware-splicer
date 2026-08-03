"""Optimistic persistence API for calibrated physical evidence plan updates."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .engineering_plan_store import save_engineering_plan
from .physical_evidence import (
    AuthorizationDecision,
    CalibrationRecord,
    PhysicalEvidenceRecord,
    PhysicalOperation,
)
from .physical_evidence_plan_update import apply_physical_evidence_to_plan
from .project_store import ProjectStore, ProjectStoreError


class PhysicalEvidenceSaveRequest(BaseModel):
    plan: Dict[str, Any]
    calibrations: list[CalibrationRecord] = Field(default_factory=list)
    evidence: list[PhysicalEvidenceRecord] = Field(default_factory=list)
    decision: AuthorizationDecision | None = None
    requested_operations: list[PhysicalOperation] = Field(default_factory=list)
    project_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


def create_physical_evidence_persistence_router(
    project_store: ProjectStore | None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/engineering/physical-evidence",
        tags=["engineering", "physical-evidence", "persistence"],
    )

    @router.post("/apply-save")
    def apply_and_save(request: PhysicalEvidenceSaveRequest) -> Dict[str, Any]:
        if project_store is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"type": "engineering_plan_store_unavailable"},
            )
        try:
            plan = apply_physical_evidence_to_plan(
                request.plan,
                calibrations=request.calibrations,
                evidence=request.evidence,
                decision=request.decision,
                requested_operations=request.requested_operations,
                as_of=request.as_of,
            )
            envelope = save_engineering_plan(
                project_store,
                plan,
                project_id=request.project_id,
                expected_revision=request.expected_revision,
            )
        except ProjectStoreError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": "engineering_plan_revision_conflict", "message": str(exc)},
            ) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_physical_evidence", "message": str(exc)},
            ) from exc
        package = plan.get("physical_evidence_package") or {}
        release = plan.get("scoped_release_assessment") or {}
        return {
            "ok": True,
            "project_id": envelope["project_id"],
            "revision": envelope["revision"],
            "saved_at": envelope["saved_at"],
            "plan": plan,
            "physical_evidence_package": package,
            "scoped_release_assessment": release,
            "engineering_status": plan.get("engineering_status"),
            "engineering_readiness": plan.get("engineering_readiness"),
            "automatic_authorization": False,
            "global_authority_flags_unchanged": True,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }

    return router

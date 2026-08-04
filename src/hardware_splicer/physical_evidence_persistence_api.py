"""Optimistic persistence API for calibrated and audited physical evidence.

Every write is anchored to an explicit project revision. For an existing project, the
server loads the stored engineering plan at that revision and applies evidence to that
state; a caller cannot replace or omit prior audit history by submitting an older plan.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .audited_physical_evidence_plan_update import (
    apply_audited_physical_evidence_to_plan,
)
from .engineering_plan_store import (
    resolve_engineering_project_id,
    save_engineering_plan,
)
from .physical_evidence import (
    AuthorizationDecision,
    CalibrationRecord,
    PhysicalEvidenceRecord,
    PhysicalOperation,
)
from .physical_evidence_ledger import (
    AuthorizationLedgerEntry,
    PhysicalEvidenceEnvelope,
)
from .physical_evidence_plan_update import apply_physical_evidence_to_plan
from .project_store import (
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class PhysicalEvidenceSaveRequest(BaseModel):
    plan: Dict[str, Any]
    calibrations: list[CalibrationRecord] = Field(default_factory=list)
    evidence: list[PhysicalEvidenceRecord] = Field(default_factory=list)
    decision: AuthorizationDecision | None = None
    requested_operations: list[PhysicalOperation] = Field(default_factory=list)
    project_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


class AuditedPhysicalEvidenceSaveRequest(BaseModel):
    plan: Dict[str, Any]
    calibrations: list[CalibrationRecord] = Field(default_factory=list)
    envelopes: list[PhysicalEvidenceEnvelope] = Field(default_factory=list)
    ledger_entries: list[AuthorizationLedgerEntry] = Field(default_factory=list)
    requested_operations: list[PhysicalOperation] = Field(default_factory=list)
    scope_id: str | None = None
    project_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


def _store_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"type": "engineering_plan_store_unavailable"},
    )


def _save_error(exc: Exception, *, audited: bool = False) -> HTTPException:
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "engineering_plan_revision_conflict", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "type": (
                "invalid_audited_physical_evidence"
                if audited
                else "invalid_physical_evidence"
            ),
            "message": str(exc),
        },
    )


def _engineering_plan_from_envelope(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    snapshot = envelope.get("snapshot")
    if not isinstance(snapshot, Mapping):
        raise ValueError("stored project revision does not contain a snapshot")
    plan = snapshot.get("engineeringPlan")
    if not isinstance(plan, Mapping):
        raise ValueError("stored project revision does not contain an engineeringPlan")
    return dict(plan)


def _anchored_base_plan(
    project_store: ProjectStore,
    supplied_plan: Mapping[str, Any],
    *,
    project_id: str | None,
    expected_revision: int | None,
) -> tuple[Dict[str, Any], str, str]:
    """Resolve a caller request to either a new plan or the exact stored base revision."""

    if expected_revision is None:
        raise RevisionConflict(
            "expected_revision is required for physical evidence persistence"
        )
    resolved_project_id = resolve_engineering_project_id(
        supplied_plan,
        project_id=project_id,
    )
    supplied_identity = resolve_engineering_project_id(supplied_plan)
    if supplied_identity != resolved_project_id:
        raise ValueError(
            "supplied plan project identity does not match requested project_id"
        )

    try:
        latest = project_store.load_latest_with_recovery(resolved_project_id)
    except ProjectNotFound:
        if int(expected_revision) != 0:
            raise RevisionConflict(
                f"project {resolved_project_id!r} does not exist; expected_revision must be 0"
            )
        return dict(supplied_plan), resolved_project_id, "new_plan"

    latest_revision = int(latest["revision"])
    if int(expected_revision) != latest_revision:
        raise RevisionConflict(
            f"project {resolved_project_id!r} is at revision {latest_revision}, "
            f"expected {expected_revision}"
        )
    stored_plan = _engineering_plan_from_envelope(latest)
    stored_identity = resolve_engineering_project_id(stored_plan)
    if stored_identity != resolved_project_id:
        raise ValueError("stored engineering plan identity is inconsistent")
    return stored_plan, resolved_project_id, "stored_revision"


def _audited_response(
    *,
    plan: Dict[str, Any],
    envelope: Dict[str, Any],
    server_attestation_required: bool,
    base_plan_source: str,
) -> Dict[str, Any]:
    audited = plan.get("audited_physical_evidence") or {}
    ledger = audited.get("ledger_assessment") or {}
    release = plan.get("scoped_release_assessment") or {}
    blockers = audited.get("blockers") or []
    envelope_valid = not any(
        "envelope" in str(value).lower() for value in blockers
    )
    server_attestation_valid = (
        bool(audited.get("metadata", {}).get("server_attestation_valid"))
        if server_attestation_required
        else None
    )
    return {
        "ok": True,
        "project_id": envelope["project_id"],
        "revision": envelope["revision"],
        "saved_at": envelope["saved_at"],
        "base_plan_source": base_plan_source,
        "plan": plan,
        "audited_physical_evidence": audited,
        "physical_evidence_package": plan.get("physical_evidence_package"),
        "scoped_release_assessment": release,
        "engineering_status": plan.get("engineering_status"),
        "engineering_readiness": plan.get("engineering_readiness"),
        "authorization_applicable": bool(audited.get("applicable")),
        "tamper_evident_envelopes_validated": envelope_valid,
        "authorization_ledger_validated": bool(ledger.get("valid")),
        "server_attestation_required": server_attestation_required,
        "server_attestation_valid": server_attestation_valid,
        "automatic_authorization": False,
        "global_authority_flags_unchanged": True,
        "fabrication_authorized": False,
        "flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


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
            raise _store_unavailable()
        try:
            base_plan, resolved_project_id, base_source = _anchored_base_plan(
                project_store,
                request.plan,
                project_id=request.project_id,
                expected_revision=request.expected_revision,
            )
            plan = apply_physical_evidence_to_plan(
                base_plan,
                calibrations=request.calibrations,
                evidence=request.evidence,
                decision=request.decision,
                requested_operations=request.requested_operations,
                as_of=request.as_of,
            )
            envelope = save_engineering_plan(
                project_store,
                plan,
                project_id=resolved_project_id,
                expected_revision=request.expected_revision,
            )
        except (ProjectStoreError, TypeError, ValueError) as exc:
            raise _save_error(exc) from exc
        package = plan.get("physical_evidence_package") or {}
        release = plan.get("scoped_release_assessment") or {}
        return {
            "ok": True,
            "project_id": envelope["project_id"],
            "revision": envelope["revision"],
            "saved_at": envelope["saved_at"],
            "base_plan_source": base_source,
            "plan": plan,
            "physical_evidence_package": package,
            "scoped_release_assessment": release,
            "engineering_status": plan.get("engineering_status"),
            "engineering_readiness": plan.get("engineering_readiness"),
            "tamper_evident_envelopes_validated": False,
            "authorization_ledger_validated": False,
            "server_attestation_required": False,
            "server_attestation_valid": None,
            "automatic_authorization": False,
            "global_authority_flags_unchanged": True,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }

    def _apply_audited(
        request: AuditedPhysicalEvidenceSaveRequest,
        *,
        require_server_attestation: bool,
    ) -> Dict[str, Any]:
        if project_store is None:
            raise _store_unavailable()
        try:
            base_plan, resolved_project_id, base_source = _anchored_base_plan(
                project_store,
                request.plan,
                project_id=request.project_id,
                expected_revision=request.expected_revision,
            )
            plan = apply_audited_physical_evidence_to_plan(
                base_plan,
                calibrations=request.calibrations,
                envelopes=request.envelopes,
                ledger_entries=request.ledger_entries,
                requested_operations=request.requested_operations,
                scope_id=request.scope_id,
                as_of=request.as_of,
                require_server_attestation=require_server_attestation,
            )
            audit_metadata = (
                plan.get("audited_physical_evidence", {}).get("metadata", {})
            )
            if (
                base_source == "stored_revision"
                and audit_metadata.get("history_continuity_valid") is False
            ):
                raise RevisionConflict(
                    "submitted audit package does not preserve the persisted "
                    "append-only evidence and authorization history"
                )
            envelope = save_engineering_plan(
                project_store,
                plan,
                project_id=resolved_project_id,
                expected_revision=request.expected_revision,
            )
        except (ProjectStoreError, TypeError, ValueError) as exc:
            raise _save_error(exc, audited=True) from exc
        return _audited_response(
            plan=plan,
            envelope=envelope,
            server_attestation_required=require_server_attestation,
            base_plan_source=base_source,
        )

    @router.post("/audited-apply-save")
    def audited_apply_and_save(
        request: AuditedPhysicalEvidenceSaveRequest,
    ) -> Dict[str, Any]:
        return _apply_audited(request, require_server_attestation=False)

    @router.post("/attested-audited-apply-save")
    def attested_audited_apply_and_save(
        request: AuditedPhysicalEvidenceSaveRequest,
    ) -> Dict[str, Any]:
        return _apply_audited(request, require_server_attestation=True)

    return router

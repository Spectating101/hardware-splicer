"""Canonical project API for revision-bound physical validation evidence."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from .attested_audited_physical_evidence import (
    assess_attested_audited_physical_authorization,
)
from .physical_evidence import CalibrationRecord, PhysicalOperation
from .physical_evidence_ledger import (
    AuthorizationLedgerEntry,
    PhysicalEvidenceEnvelope,
)
from .project_physical_validation import (
    PROJECT_PHYSICAL_VALIDATION_SCHEMA,
    build_gate_assessment,
    build_project_physical_validation_packet,
    physical_assessment_plan,
    validate_packet_evidence,
)
from .project_store import (
    CorruptProject,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class PhysicalValidationApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectPhysicalEvidenceRequest(PhysicalValidationApiModel):
    expected_revision: int = Field(ge=1)
    packet_id: str = Field(min_length=1)
    calibrations: list[CalibrationRecord] = Field(default_factory=list)
    envelopes: list[PhysicalEvidenceEnvelope] = Field(min_length=1, max_length=256)
    ledger_entries: list[AuthorizationLedgerEntry] = Field(default_factory=list)
    requested_operations: list[PhysicalOperation] = Field(default_factory=list)
    scope_id: str | None = None
    as_of: datetime | None = None


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProjectNotFound):
        code = status.HTTP_404_NOT_FOUND
        error_type = "project_not_found"
    elif isinstance(exc, RevisionConflict):
        code = status.HTTP_409_CONFLICT
        error_type = "physical_validation_revision_conflict"
    elif isinstance(exc, (TypeError, ValueError)):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
        error_type = "invalid_project_physical_evidence"
    elif isinstance(exc, CorruptProject):
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = "corrupt_project"
    elif isinstance(exc, ProjectStoreError):
        code = status.HTTP_409_CONFLICT
        error_type = "project_store_error"
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = "project_physical_validation_error"
    return HTTPException(status_code=code, detail={"type": error_type, "message": str(exc)})


def create_project_physical_validation_router(project_store: ProjectStore) -> APIRouter:
    router = APIRouter(tags=["project-physical-validation"])

    @router.get(
        "/v1/projects/{project_id}/engineering/physical-validation/packet",
        summary="Generate an operator-ready physical validation packet bound to canonical project state",
    )
    def get_packet(
        project_id: str, revision: int | None = Query(default=None, ge=1)
    ) -> Dict[str, Any]:
        try:
            envelope = (
                project_store.load_latest_with_recovery(project_id)
                if revision is None
                else project_store.load(project_id, revision)
            )
            packet = build_project_physical_validation_packet(
                envelope["snapshot"],
                project_id=project_id,
                revision=int(envelope["revision"]),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "revision": envelope["revision"],
            "recovery": envelope.get("recovery"),
            "physical_validation_packet": packet,
            "physical_correctness": "UNPROVEN",
            "physical_authority_granted": False,
        }

    @router.post(
        "/v1/projects/{project_id}/engineering/physical-validation/evidence",
        summary="Persist server-attested physical captures against a revision-bound packet",
    )
    def submit_evidence(
        project_id: str, request: ProjectPhysicalEvidenceRequest
    ) -> Dict[str, Any]:
        try:
            envelope = project_store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            snapshot = deepcopy(dict(envelope["snapshot"]))
            packet = build_project_physical_validation_packet(
                snapshot, project_id=project_id, revision=current_revision
            )
            if request.packet_id != packet["packet_id"]:
                raise RevisionConflict(
                    "physical validation packet is stale or belongs to another candidate"
                )
            prior_validation = snapshot.get("physicalValidation")
            prior_validation = (
                dict(prior_validation)
                if isinstance(prior_validation, Mapping)
                else {}
            )
            validate_packet_evidence(
                packet,
                request.envelopes,
                prior_authorized_operations=list(
                    prior_validation.get("scoped_authorized_operations") or []
                ),
            )
            plan = physical_assessment_plan(
                snapshot, project_id=project_id, packet=packet
            )
            audited = assess_attested_audited_physical_authorization(
                plan,
                calibrations=request.calibrations,
                envelopes=request.envelopes,
                ledger_entries=request.ledger_entries,
                scope_id=request.scope_id,
                as_of=request.as_of,
            )
            gate_assessment = build_gate_assessment(packet, request.envelopes)
            requested = [value.value for value in request.requested_operations]
            applicable_operations = [
                value.value
                for value in audited.physical_package.assessment.authorized_operations
                if value.value in requested
            ]
            physical_validation = {
                "schema_version": PROJECT_PHYSICAL_VALIDATION_SCHEMA,
                "packet_id": packet["packet_id"],
                "candidate_revision": packet["candidate_revision"],
                "candidate_snapshot_hash": packet["candidate_snapshot_hash"],
                "artifact_hashes": dict(packet["artifact_hashes"]),
                "source_revision": packet["source_revision"],
                "calibrations": [
                    value.model_dump(mode="json") for value in request.calibrations
                ],
                "audited_physical_evidence": audited.model_dump(mode="json"),
                "gate_assessment": gate_assessment,
                "requested_operations": requested,
                "scoped_authorized_operations": (
                    applicable_operations if audited.applicable else []
                ),
                "physical_correctness": "UNPROVEN",
                "automatic_authorization": False,
                "global_authority_flags_unchanged": True,
            }
            snapshot["physicalValidation"] = physical_validation
            saved = project_store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "project_physical_validation_evidence",
                    "packet_id": packet["packet_id"],
                    "candidate_snapshot_hash": packet["candidate_snapshot_hash"],
                    "evidence_envelope_count": len(request.envelopes),
                    "server_attestation_required": True,
                    "server_attestation_valid": bool(
                        audited.metadata.get("server_attestation_valid")
                    ),
                    "automatic_authorization": False,
                    "global_authority_flags_unchanged": True,
                },
            )
        except Exception as exc:
            raise _error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "physical_validation": physical_validation,
            "authorization_applicable": audited.applicable,
            "scoped_authorized_operations": physical_validation[
                "scoped_authorized_operations"
            ],
            "server_attestation_valid": bool(
                audited.metadata.get("server_attestation_valid")
            ),
            "authorization_ledger_valid": audited.ledger_assessment.valid,
            "physical_correctness": "UNPROVEN",
            "physical_authority_granted": False,
            "automatic_authorization": False,
        }

    return router

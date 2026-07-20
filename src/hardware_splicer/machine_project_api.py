"""HTTP surface for canonical machine projects."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .machine_evidence import EvidencePromotionError, record_evidence_and_promote
from .machine_project import (
    MachineProject,
    ReleaseState,
    machine_project_from_session,
)
from .machine_project_compile_adapter import machine_project_from_compile_spec
from .machine_project_diff import diff_machine_projects
from .machine_project_edit import MachineEditError, apply_machine_edits
from .machine_project_seed import machine_project_from_intake
from .machine_release import assessment_allows


class LegacySessionMigrationRequest(BaseModel):
    session: Dict[str, Any]


class IntakeSeedRequest(BaseModel):
    intake: Dict[str, Any]


class CompileSpecProjectionRequest(BaseModel):
    spec: Dict[str, Any]


class ReleaseAssessmentRequest(BaseModel):
    project: MachineProject
    requested_state: ReleaseState | None = None


class MachineProjectDiffRequest(BaseModel):
    base: MachineProject
    candidate: MachineProject
    include_metadata: bool = False


class MachineProjectEditRequest(BaseModel):
    project: MachineProject
    operations: list[Dict[str, Any]] = Field(min_length=1)
    include_metadata: bool = False


class MachineEvidenceRequest(BaseModel):
    project: MachineProject
    evidence: Dict[str, Any]
    verification: Dict[str, Any] | None = None
    promotions: list[Dict[str, Any]] = Field(default_factory=list)
    include_metadata: bool = False


class MachineProjectEnvelope(BaseModel):
    project: MachineProject
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _project_response(project: MachineProject) -> Dict[str, Any]:
    return {
        "ok": True,
        "project": project.model_dump(mode="json"),
        "traceability_issues": [
            issue.model_dump(mode="json") for issue in project.traceability_issues()
        ],
    }


def _candidate_response(
    base: MachineProject,
    candidate: MachineProject,
    *,
    include_metadata: bool,
) -> Dict[str, Any]:
    diff = diff_machine_projects(base, candidate, include_metadata=include_metadata)
    response = _project_response(candidate)
    response.update(
        {
            "diff": diff.model_dump(mode="json"),
            "summary": diff.summary(),
            "review_required": diff.review_required,
        }
    )
    return response


def create_machine_project_router() -> APIRouter:
    router = APIRouter(prefix="/v1/machine-projects", tags=["machine-projects"])

    @router.get("/schema")
    def machine_project_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema": MachineProject.model_json_schema(),
        }

    @router.post("/validate")
    def validate_machine_project(envelope: MachineProjectEnvelope) -> Dict[str, Any]:
        response = _project_response(envelope.project)
        response["metadata"] = envelope.metadata
        return response

    @router.post("/from-intake")
    def seed_from_intake(request: IntakeSeedRequest) -> Dict[str, Any]:
        return _project_response(machine_project_from_intake(request.intake))

    @router.post("/from-compile-spec")
    def project_compile_spec(request: CompileSpecProjectionRequest) -> Dict[str, Any]:
        return _project_response(machine_project_from_compile_spec(request.spec))

    @router.post("/from-session")
    def migrate_legacy_session(request: LegacySessionMigrationRequest) -> Dict[str, Any]:
        return _project_response(machine_project_from_session(request.session))

    @router.post("/diff")
    def compare_machine_projects(request: MachineProjectDiffRequest) -> Dict[str, Any]:
        diff = diff_machine_projects(
            request.base,
            request.candidate,
            include_metadata=request.include_metadata,
        )
        return {
            "ok": True,
            "diff": diff.model_dump(mode="json"),
            "summary": diff.summary(),
            "review_required": diff.review_required,
        }

    @router.post("/edit")
    def edit_machine_project(request: MachineProjectEditRequest) -> Dict[str, Any]:
        try:
            candidate = apply_machine_edits(request.project, request.operations)
        except MachineEditError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_machine_edit", "message": str(exc)},
            ) from exc
        return _candidate_response(
            request.project,
            candidate,
            include_metadata=request.include_metadata,
        )

    @router.post("/record-evidence")
    def record_machine_evidence(request: MachineEvidenceRequest) -> Dict[str, Any]:
        try:
            candidate = record_evidence_and_promote(
                request.project,
                evidence=request.evidence,
                verification=request.verification,
                promotions=request.promotions,
            )
        except (EvidencePromotionError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_evidence_promotion", "message": str(exc)},
            ) from exc
        return _candidate_response(
            request.project,
            candidate,
            include_metadata=request.include_metadata,
        )

    @router.post("/assess-release")
    def assess_machine_release(request: ReleaseAssessmentRequest) -> Dict[str, Any]:
        assessment = request.project.assess_release(requested=request.requested_state)
        return {
            "ok": True,
            "assessment": assessment.model_dump(mode="json"),
            "allowed": assessment_allows(assessment),
        }

    return router

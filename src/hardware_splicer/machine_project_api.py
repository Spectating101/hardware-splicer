"""HTTP surface for canonical machine projects."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .machine_project import (
    MachineProject,
    ReleaseState,
    machine_project_from_session,
)
from .machine_project_compile_adapter import machine_project_from_compile_spec
from .machine_project_diff import diff_machine_projects
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

    @router.post("/assess-release")
    def assess_machine_release(request: ReleaseAssessmentRequest) -> Dict[str, Any]:
        assessment = request.project.assess_release(requested=request.requested_state)
        return {
            "ok": True,
            "assessment": assessment.model_dump(mode="json"),
            "allowed": assessment_allows(assessment),
        }

    return router

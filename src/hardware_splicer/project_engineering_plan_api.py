"""Generate and persist a guided plan from one revisioned project source boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .engineering_plan_store import engineering_snapshot
from .guided_engineering_planner import plan_guided_engineering_project
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class ProjectEngineeringPlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectEngineeringPlanRequest(ProjectEngineeringPlanModel):
    intake: Dict[str, Any]
    expected_revision: int = Field(ge=1)
    declared_conflicts: list[Dict[str, Any]] = Field(default_factory=list)
    additional_engineering_sources: list[Dict[str, Any]] = Field(default_factory=list)
    baseline_project: Dict[str, Any] | None = None
    skip_vision: bool = True


def _project_plan_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "project_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "project_engineering_plan_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_engineering_plan", "message": str(exc)},
        )
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "project_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "project_engineering_plan_error", "message": str(exc)},
    )


def _source_key(source: Dict[str, Any]) -> tuple[str, str]:
    return (
        str(source.get("source_id") or ""),
        str(source.get("content_hash") or source.get("revision") or ""),
    )


def _combined_sources(
    persisted: list[Dict[str, Any]],
    additional: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source in [*persisted, *additional]:
        row = dict(source)
        key = _source_key(row)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def create_project_engineering_plan_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["project-engineering-plan"])

    @router.post("/v1/projects/{project_id}/engineering/plan")
    def plan_project(
        project_id: str,
        request: ProjectEngineeringPlanRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            existing_snapshot = deepcopy(envelope["snapshot"])
            persisted_sources = [
                dict(row)
                for row in existing_snapshot.get("engineeringSources") or []
                if isinstance(row, dict)
            ]
            sources = _combined_sources(
                persisted_sources,
                request.additional_engineering_sources,
            )
            plan = plan_guided_engineering_project(
                request.intake,
                engineering_sources=sources,
                declared_conflicts=request.declared_conflicts,
                baseline_project=request.baseline_project,
                skip_vision=request.skip_vision,
            )
            planned_snapshot = existing_snapshot
            planned_snapshot.update(engineering_snapshot(plan))
            planned_snapshot["projectId"] = project_id
            planned_snapshot["engineeringSources"] = sources
            planned_snapshot["engineeringSourceUploads"] = [
                dict(row)
                for row in existing_snapshot.get("engineeringSourceUploads") or []
                if isinstance(row, dict)
            ]
            saved = store.save(
                project_id,
                planned_snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "project_engineering_plan",
                    "engineering_plan_schema": plan.get("schema_version"),
                    "persisted_source_count": len(persisted_sources),
                    "combined_source_count": len(sources),
                    "automatic_execution": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _project_plan_error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "persisted_source_count": len(persisted_sources),
            "combined_source_count": len(sources),
            "plan": plan,
            "engineering_readiness": plan.get("engineering_readiness"),
            "engineering_status": plan.get("engineering_status"),
            "authority_unchanged": True,
        }

    return router

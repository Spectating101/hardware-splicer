from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    RevisionConflict,
)


class ProjectSnapshotRequest(BaseModel):
    snapshot: Dict[str, Any]
    expected_revision: int | None = Field(default=None, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProjectDuplicateRequest(BaseModel):
    target_project_id: str


class ProjectArchiveRequest(BaseModel):
    archived: bool = True


def _project_error(exc: Exception) -> HTTPException:
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
            detail={"type": "revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "project_store_error", "message": str(exc)},
    )


def create_project_router(store: ProjectStore | None = None) -> APIRouter:
    project_store = store or ProjectStore()
    router = APIRouter(prefix="/v1/projects", tags=["projects"])

    @router.get("")
    def list_projects(include_archived: bool = Query(default=False)) -> Dict[str, Any]:
        return {
            "ok": True,
            "projects": project_store.list_projects(include_archived=include_archived),
        }

    @router.put("/{project_id}/snapshot")
    def save_project_snapshot(project_id: str, request: ProjectSnapshotRequest) -> Dict[str, Any]:
        try:
            envelope = project_store.save(
                project_id,
                request.snapshot,
                expected_revision=request.expected_revision,
                metadata=request.metadata,
            )
        except Exception as exc:
            raise _project_error(exc) from exc
        return {"ok": True, "project": envelope}

    @router.get("/{project_id}")
    def load_project(
        project_id: str,
        revision: int | None = Query(default=None, ge=1),
    ) -> Dict[str, Any]:
        try:
            envelope = (
                project_store.load(project_id, revision=revision)
                if revision is not None
                else project_store.load_latest_with_recovery(project_id)
            )
        except Exception as exc:
            raise _project_error(exc) from exc
        return {"ok": True, "project": envelope}

    @router.post("/{project_id}/duplicate", status_code=status.HTTP_201_CREATED)
    def duplicate_project(project_id: str, request: ProjectDuplicateRequest) -> Dict[str, Any]:
        try:
            envelope = project_store.duplicate(project_id, request.target_project_id)
        except Exception as exc:
            raise _project_error(exc) from exc
        return {"ok": True, "project": envelope}

    @router.patch("/{project_id}/archive")
    def archive_project(project_id: str, request: ProjectArchiveRequest) -> Dict[str, Any]:
        try:
            manifest = project_store.set_archived(project_id, request.archived)
        except Exception as exc:
            raise _project_error(exc) from exc
        return {"ok": True, "project": manifest}

    @router.delete("/{project_id}")
    def delete_project(project_id: str) -> Dict[str, Any]:
        try:
            project_store.delete(project_id)
        except Exception as exc:
            raise _project_error(exc) from exc
        return {"ok": True, "deleted": project_id}

    return router

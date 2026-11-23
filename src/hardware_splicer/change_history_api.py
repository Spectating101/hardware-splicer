"""Read-only HTTP view of a project's recorded Policy Lab changes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from .change_history import ChangeHistoryError, change_dossier
from .project_store import CorruptProject, InvalidProjectId, ProjectNotFound, ProjectStore


def create_change_history_router(project_store: ProjectStore) -> APIRouter:
    router = APIRouter(tags=["change-dossier"])

    @router.get("/v1/projects/{project_id}/change-dossier",
                summary="Recorded Policy Lab proposals, applying revisions, candidate outcomes and exported change evidence")
    def get_change_dossier(project_id: str) -> Dict[str, Any]:
        try:
            return {"ok": True, "change_dossier": change_dossier(project_store, project_id)}
        except ProjectNotFound as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, {"type": "project_not_found", "message": str(exc)}) from exc
        except (InvalidProjectId, ChangeHistoryError) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                {"type": "change_dossier_unavailable", "message": str(exc)}) from exc
        except CorruptProject as exc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                                {"type": "corrupt_project", "message": str(exc)}) from exc

    return router

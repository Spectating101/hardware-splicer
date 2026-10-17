"""Canonical read-only API for the salvage fabrication agent context."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status

from .fabrication_operator import FabricationValidationError
from .fabricator_lab_workbench import FabricatorLabWorkbench
from .mission_store import MissionError, MissionNotFound, MissionStore
from .project_store import ProjectNotFound, ProjectStore
from .salvage_fabrication import build_salvage_fabrication_context


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ProjectNotFound, MissionNotFound)):
        return HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"type": "not_found", "message": str(exc)},
        )
    if isinstance(exc, FabricationValidationError):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, MissionError):
        return HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "mission_error", "message": "internal mission error"},
        )
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "salvage_fabrication_error", "message": "internal salvage fabrication error"},
    )


def create_salvage_fabrication_router(project_store: ProjectStore) -> APIRouter:
    mission_store = MissionStore(project_store)
    router = APIRouter(
        prefix="/v1/projects/{project_id}/missions/{mission_id}/salvage-fabrication",
        tags=["salvage-fabrication"],
    )

    @router.get("")
    def read_salvage_fabrication_context(
        project_id: str,
        mission_id: str,
        request: Request,
    ) -> Dict[str, Any]:
        try:
            lab = getattr(request.app.state, "fabricator_lab_workbench", None)
            resources = lab.list_resources() if isinstance(lab, FabricatorLabWorkbench) else []
            context = build_salvage_fabrication_context(
                mission_store=mission_store,
                project_id=project_id,
                mission_id=mission_id,
                fabrication_resources=resources,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "context": context}

    return router

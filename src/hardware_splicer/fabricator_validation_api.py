"""Canonical fail-closed API for frozen fabricator validation procedures."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status

from .fabrication_operator import FabricationValidationError
from .fabricator_validation_workbench import FabricatorValidationWorkbench


def _runtime(request: Request) -> FabricatorValidationWorkbench:
    value = getattr(request.app.state, "fabricator_validation_workbench", None)
    if not isinstance(value, FabricatorValidationWorkbench):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "type": "fabricator_validation_unavailable",
                "message": "fabricator validation runtime is not configured",
            },
        )
    return value


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, FabricationValidationError):
        return HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "fabricator_validation_error", "message": "internal fabricator validation error"},
    )


def create_fabricator_validation_router() -> APIRouter:
    router = APIRouter(prefix="/v1/fabricator/validation", tags=["fabricator-validation"])

    @router.get("/procedures")
    def list_validation_procedures(request: Request, project_id: str | None = None) -> Dict[str, Any]:
        try:
            procedures = _runtime(request).list_procedures(project_id=project_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "procedures": procedures}

    @router.post("/procedures/{procedure_id}/evaluate")
    def evaluate_validation_procedure(
        procedure_id: str,
        request: Request,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            if not isinstance(body, Mapping):
                raise FabricationValidationError("request must be an object")
            evidence_ids = body.get("evidence_ids")
            if not isinstance(evidence_ids, list):
                raise FabricationValidationError("evidence_ids must be a list")
            assessment = _runtime(request).evaluate(procedure_id, evidence_ids=evidence_ids)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "assessment": assessment}

    return router

"""Canonical fail-closed API for fabricator intelligence."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status

from .fabrication_operator import FabricationValidationError
from .fabricator_intelligence_workbench import FabricatorIntelligenceWorkbench


def _runtime(request: Request) -> FabricatorIntelligenceWorkbench:
    value = getattr(request.app.state, "fabricator_intelligence_workbench", None)
    if not isinstance(value, FabricatorIntelligenceWorkbench):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "type": "fabricator_intelligence_unavailable",
                "message": "fabricator intelligence runtime is not configured",
            },
        )
    return value


def _body(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FabricationValidationError("request must be an object")
    return dict(value)


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
        detail={"type": "fabricator_intelligence_error", "message": "internal fabricator intelligence error"},
    )


def create_fabricator_intelligence_router() -> APIRouter:
    router = APIRouter(prefix="/v1/fabricator/intelligence", tags=["fabricator-intelligence"])

    @router.post("/vision/inspect", status_code=http_status.HTTP_201_CREATED)
    def inspect_retained_image(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            result = _runtime(request).inspect_image(
                observation_id=value.get("observation_id"),
                task_id=value.get("task_id"),
                output_artifact_id=value.get("output_artifact_id"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "inspection": result}

    @router.get("/procurement/quotes")
    def list_procurement_quotes(
        request: Request,
        part_key: str | None = None,
        supplier_id: str | None = None,
    ) -> Dict[str, Any]:
        try:
            values = _runtime(request).list_quotes(part_key=part_key, supplier_id=supplier_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "quotes": values}

    @router.post("/procurement/estimate")
    def estimate_procurement(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            lines = value.get("lines")
            if not isinstance(lines, list):
                raise FabricationValidationError("lines must be a list")
            estimate = _runtime(request).cost_bom(
                lines=lines,
                currency=value.get("currency"),
                as_of=value.get("as_of"),
                require_known_stock=bool(value.get("require_known_stock", False)),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "estimate": estimate}

    return router

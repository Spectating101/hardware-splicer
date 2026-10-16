"""Canonical fail-closed API for multi-tool fabrication lab orchestration."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status

from .fabrication_operator import FabricationValidationError
from .fabricator_lab_workbench import FabricatorLabWorkbench


def _runtime(request: Request) -> FabricatorLabWorkbench:
    value = getattr(request.app.state, "fabricator_lab_workbench", None)
    if not isinstance(value, FabricatorLabWorkbench):
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "fabricator_lab_unavailable", "message": "fabricator lab runtime is not configured"},
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
        detail={"type": "fabricator_lab_error", "message": "internal fabricator lab error"},
    )


def create_fabricator_lab_router() -> APIRouter:
    router = APIRouter(prefix="/v1/fabricator/lab", tags=["fabricator-lab"])

    @router.get("/resources")
    def list_lab_resources(request: Request, kind: str | None = None) -> Dict[str, Any]:
        try:
            values = _runtime(request).list_resources(kind=kind)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "resources": values}

    @router.post("/workflows", status_code=http_status.HTTP_201_CREATED)
    def plan_lab_workflow(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            tasks = value.get("tasks")
            if not isinstance(tasks, list):
                raise FabricationValidationError("tasks must be a list")
            plan = _runtime(request).plan_workflow(
                workflow_id=value.get("workflow_id"),
                tasks=tasks,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "plan": plan}

    @router.get("/workflows/{plan_id}")
    def read_lab_workflow(plan_id: str, request: Request) -> Dict[str, Any]:
        try:
            plan = _runtime(request).get_plan(plan_id)
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "plan": plan}

    @router.post("/workflows/{plan_id}/tasks/{task_id}/lease", status_code=http_status.HTTP_201_CREATED)
    def acquire_lab_lease(plan_id: str, task_id: str, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            lease = _runtime(request).acquire_task_lease(
                plan_id=plan_id,
                task_id=task_id,
                holder_id=value.get("holder_id"),
                ttl_seconds=value.get("ttl_seconds", 900),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, **lease}

    @router.get("/leases")
    def list_lab_leases(request: Request) -> Dict[str, Any]:
        try:
            values = _runtime(request).list_leases()
        except Exception as exc:
            raise _error(exc) from exc
        return {"ok": True, "leases": values}

    @router.post("/leases/{lease_id}/release")
    def release_lab_lease(lease_id: str, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            value = _body(body)
            result = _runtime(request).release_task_lease(
                lease_id=lease_id,
                lease_token=value.get("lease_token"),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return result

    return router

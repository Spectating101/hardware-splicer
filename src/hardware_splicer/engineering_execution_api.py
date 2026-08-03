"""Product API for bounded software-only engineering execution."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from .engineering_execution import (
    ExecutionPolicyError,
    ExecutionRequest,
    ExecutionResult,
    execution_manifest,
    preview_engineering_execution,
    run_engineering_execution,
)


def create_engineering_execution_router() -> APIRouter:
    router = APIRouter(prefix="/v1/engineering/execution", tags=["engineering", "execution"])

    @router.get("/schema")
    def execution_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "request_schema": ExecutionRequest.model_json_schema(),
            "result_schema": ExecutionResult.model_json_schema(),
            "physical_operations_supported": False,
        }

    @router.post("/preview")
    def preview(request: ExecutionRequest) -> Dict[str, Any]:
        try:
            result = preview_engineering_execution(request.model_copy(update={"execute": False}))
        except ExecutionPolicyError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "execution_policy_error", "message": str(exc)},
            ) from exc
        return {"ok": True, "execution": execution_manifest(result)}

    @router.post("/run")
    def run(request: ExecutionRequest) -> Dict[str, Any]:
        try:
            result = run_engineering_execution(request.model_copy(update={"execute": True}))
        except ExecutionPolicyError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "execution_policy_error", "message": str(exc)},
            ) from exc
        return {
            "ok": result.status.value == "passed",
            "execution": execution_manifest(result),
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
        }

    return router

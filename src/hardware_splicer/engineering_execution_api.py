"""Product API for bounded software-only engineering execution."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .engineering_execution import (
    ExecutionPolicyError,
    ExecutionRequest,
    ExecutionResult,
    execution_manifest,
    preview_engineering_execution,
    run_engineering_execution,
)
from .engineering_execution_evidence import attach_execution_evidence
from .machine_project import MachineProject


class ExecutionEvidenceRequest(BaseModel):
    machine_project: MachineProject
    execution: Dict[str, Any]
    target_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


def create_engineering_execution_router() -> APIRouter:
    router = APIRouter(prefix="/v1/engineering/execution", tags=["engineering", "execution"])

    @router.get("/schema")
    def execution_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "request_schema": ExecutionRequest.model_json_schema(),
            "result_schema": ExecutionResult.model_json_schema(),
            "evidence_request_schema": ExecutionEvidenceRequest.model_json_schema(),
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

    @router.post("/evidence")
    def ingest_evidence(request: ExecutionEvidenceRequest) -> Dict[str, Any]:
        try:
            project = attach_execution_evidence(
                request.machine_project,
                request.execution,
                target_ids=request.target_ids,
                requirement_ids=request.requirement_ids,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_execution_evidence", "message": str(exc)},
            ) from exc
        release = project.assess_release()
        software_evidence = [
            row
            for row in project.evidence
            if row.kind == "software_execution_result"
        ]
        physical_evidence = [
            row
            for row in project.evidence
            if not row.simulated
            and row.authority.value in {"measured", "verified", "authorized"}
        ]
        return {
            "ok": True,
            "machine_project": project.model_dump(mode="json"),
            "software_execution_evidence_count": len(software_evidence),
            "physical_evidence_count": len(physical_evidence),
            "release_assessment": release.model_dump(mode="json"),
            "physical_authority_unchanged": True,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
        }

    return router

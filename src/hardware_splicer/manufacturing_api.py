"""HTTP surface for cross-domain manufacturing closure."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .guided_engineering_planner import plan_guided_engineering_project
from .manufacturing_closure import ManufacturingClosureReport, build_manufacturing_closure


class ManufacturingClosureRequest(BaseModel):
    intake: Dict[str, Any] = Field(default_factory=dict)
    plan: Dict[str, Any] | None = None
    engineering_sources: list[Any] = Field(default_factory=list)
    declared_conflicts: list[Dict[str, Any]] = Field(default_factory=list)
    baseline_project: Dict[str, Any] | None = None
    skip_vision: bool = True


def create_manufacturing_router() -> APIRouter:
    router = APIRouter(prefix="/v1/engineering", tags=["engineering", "manufacturing"])

    @router.get("/manufacturing-closure/schema")
    def manufacturing_closure_schema() -> Dict[str, Any]:
        return {"ok": True, "schema": ManufacturingClosureReport.model_json_schema()}

    @router.post("/manufacturing-closure")
    def manufacturing_closure(request: ManufacturingClosureRequest) -> Dict[str, Any]:
        try:
            if request.plan is not None:
                report = build_manufacturing_closure(request.plan, intake=request.intake)
                plan = request.plan
            else:
                plan = plan_guided_engineering_project(
                    request.intake,
                    engineering_sources=request.engineering_sources or None,
                    declared_conflicts=request.declared_conflicts,
                    baseline_project=request.baseline_project,
                    skip_vision=request.skip_vision,
                )
                report = ManufacturingClosureReport.model_validate(plan["manufacturing_closure"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_manufacturing_closure", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "project_id": report.project_id,
            "status": report.status,
            "blocking_check_count": len(report.blocking_checks),
            "warning_check_count": len(report.warning_checks),
            "manufacturing_closure": report.model_dump(mode="json"),
            "engineering_readiness": plan.get("engineering_readiness") if isinstance(plan, dict) else None,
            "fabrication_authorized": False,
            "release_authorized": False,
        }

    return router

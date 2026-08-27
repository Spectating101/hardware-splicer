"""Product API for unified engineering status and ranked next actions."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .engineering_status import EngineeringStatus, build_engineering_status
from .guided_engineering_planner import plan_guided_engineering_project


class EngineeringStatusRequest(BaseModel):
    plan: Dict[str, Any] | None = None
    intake: Dict[str, Any] = Field(default_factory=dict)
    engineering_sources: list[Any] = Field(default_factory=list)
    declared_conflicts: list[Dict[str, Any]] = Field(default_factory=list)
    baseline_project: Dict[str, Any] | None = None
    skip_vision: bool = True


def create_engineering_status_router() -> APIRouter:
    router = APIRouter(prefix="/v1/engineering", tags=["engineering", "status"])

    @router.get("/status/schema")
    def status_schema() -> Dict[str, Any]:
        return {"ok": True, "schema": EngineeringStatus.model_json_schema()}

    @router.post("/status")
    def engineering_status(request: EngineeringStatusRequest) -> Dict[str, Any]:
        try:
            if request.plan is not None:
                plan = request.plan
                report = build_engineering_status(plan)
            else:
                plan = plan_guided_engineering_project(
                    request.intake,
                    engineering_sources=request.engineering_sources or None,
                    declared_conflicts=request.declared_conflicts,
                    baseline_project=request.baseline_project,
                    skip_vision=request.skip_vision,
                )
                report = EngineeringStatus.model_validate(plan["engineering_status"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_engineering_status", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "project_id": report.project_id,
            "overall_status": report.overall_status,
            "current_phase": report.current_phase,
            "next_action": (
                report.next_actions[0].model_dump(mode="json")
                if report.next_actions
                else None
            ),
            "engineering_status": report.model_dump(mode="json"),
            "engineering_readiness": plan.get("engineering_readiness") if isinstance(plan, dict) else None,
            "automatic_execution": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }

    return router

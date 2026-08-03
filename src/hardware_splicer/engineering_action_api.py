"""Product API for preparing ranked engineering next actions."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from .engineering_action import PreparedEngineeringAction, prepare_engineering_action
from .guided_engineering_planner import plan_guided_engineering_project


class EngineeringActionRequest(BaseModel):
    plan: Dict[str, Any] | None = None
    intake: Dict[str, Any] | None = None
    engineering_sources: list[Any] = []
    declared_conflicts: list[Dict[str, Any]] = []
    baseline_project: Dict[str, Any] | None = None
    action_id: str | None = None
    skip_vision: bool = True


def create_engineering_action_router() -> APIRouter:
    router = APIRouter(prefix="/v1/engineering/actions", tags=["engineering", "actions"])

    @router.get("/schema")
    def action_schema() -> Dict[str, Any]:
        return {"ok": True, "schema": PreparedEngineeringAction.model_json_schema()}

    @router.post("/prepare")
    def prepare_action(request: EngineeringActionRequest) -> Dict[str, Any]:
        try:
            plan = request.plan
            if plan is None:
                if request.intake is None:
                    raise ValueError("plan or intake is required")
                plan = plan_guided_engineering_project(
                    request.intake,
                    engineering_sources=request.engineering_sources or None,
                    declared_conflicts=request.declared_conflicts,
                    baseline_project=request.baseline_project,
                    skip_vision=request.skip_vision,
                )
            prepared = prepare_engineering_action(plan, action_id=request.action_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_engineering_action", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "project_id": prepared.project_id,
            "prepared_action": prepared.model_dump(mode="json"),
            "automatic_execution": False,
            "physical_action": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }

    return router

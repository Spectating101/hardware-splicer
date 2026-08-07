"""Product API for typed semantic selection of bounded circuit planners."""

from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .circuit_synthesis.semantic_planner_selector import (
    PLANNER_REGISTRY,
    SemanticPlannerSelectionError,
    semantic_plan_circuit,
)


class SemanticCircuitAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SemanticCircuitPlanRequest(SemanticCircuitAPIModel):
    intent: Dict[str, Any]
    model: str | None = Field(default=None, max_length=256)


def create_semantic_circuit_router(
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["semantic-circuit-planning"])

    @router.get("/v1/engineering/circuit/semantic-planners")
    def semantic_planner_registry() -> Dict[str, Any]:
        return {
            "schema_version": "hardware_splicer.semantic_circuit_planner_registry.v1",
            "planners": {key: dict(value) for key, value in PLANNER_REGISTRY.items()},
            "selection_authority_effect": "none",
            "automatic_execution": False,
            "compile_authorized": False,
            "physical_authority_unchanged": True,
        }

    @router.post("/v1/engineering/circuit/semantic-plan")
    def semantic_circuit_plan(request: SemanticCircuitPlanRequest) -> Dict[str, Any]:
        try:
            trace = semantic_plan_circuit(
                request.intent,
                llm_callable=llm_callable,
            )
        except SemanticPlannerSelectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"type": "semantic_planner_selection_failed", "message": str(exc)},
            ) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_circuit_intent", "message": str(exc)},
            ) from exc

        selection = trace.selection
        return {
            "ok": selection.selected_planner is not None,
            "requires_human_review": True,
            "selected_planner": selection.selected_planner,
            "unresolved_questions": list(selection.unresolved_questions),
            "trace": trace.model_dump(mode="json"),
            "authority_effect": "none",
            "automatic_execution": False,
            "compile_authorized": False,
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }

    return router

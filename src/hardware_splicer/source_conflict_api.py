"""HTTP review surface for engineering source conflicts and revision boundaries."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .engineering_source_graph import EngineeringSourceGraph
from .source_conflict_resolution import (
    ConflictDecision,
    RevisionBoundarySelection,
    apply_conflict_decisions,
    select_revision_boundary,
)


class ConflictResolutionRequest(BaseModel):
    graph: EngineeringSourceGraph
    decisions: list[ConflictDecision] = Field(min_length=1)


class RevisionBoundaryRequest(BaseModel):
    graph: EngineeringSourceGraph
    selection: RevisionBoundarySelection


def _unprocessable(error_type: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"type": error_type, "message": str(exc)},
    )


def create_source_conflict_router() -> APIRouter:
    router = APIRouter(prefix="/v1/engineering/sources", tags=["engineering-source-review"])

    @router.post("/resolve-conflicts")
    def resolve_conflicts(request: ConflictResolutionRequest) -> Dict[str, Any]:
        try:
            graph = apply_conflict_decisions(request.graph, request.decisions)
        except ValueError as exc:
            raise _unprocessable("invalid_conflict_decision", exc) from exc
        return {
            "ok": True,
            "graph": graph.model_dump(mode="json"),
            "blocking_conflict_count": len(graph.blocking_conflicts),
        }

    @router.post("/select-boundary")
    def select_boundary(request: RevisionBoundaryRequest) -> Dict[str, Any]:
        try:
            graph = select_revision_boundary(request.graph, request.selection)
        except ValueError as exc:
            raise _unprocessable("invalid_revision_boundary", exc) from exc
        return {
            "ok": True,
            "graph": graph.model_dump(mode="json"),
            "blocking_conflict_count": len(graph.blocking_conflicts),
            "revision_boundary": graph.metadata.get("revision_boundary"),
        }

    return router

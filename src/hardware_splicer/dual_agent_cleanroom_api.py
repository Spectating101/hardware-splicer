"""Revision-pinned HTTP surface for source-blind embedded-operator evaluation.

Unlike an ordinary AI session request, the caller never supplies the project snapshot,
engineering constraints, or operator mission. The server loads the latest persisted
revision and rejects stale callers before the embedded operator sees any context.
Cleanroom turns are evaluation-only: they do not save project state, execute tools, or
change physical authority.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Literal, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .ai_project_orchestrator import AIProjectOrchestratorError, AIProviderError, InvalidAIProjectResponse
from .dual_agent_cleanroom import CleanroomContractError, SCHEMA_VERSION, run_embedded_operator_turn
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class CleanroomAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmbeddedOperatorTurnRequest(CleanroomAPIModel):
    expected_revision: int = Field(ge=1)
    model_profile: Literal["fast_draft", "deep_synthesis", "design_repair"] = "deep_synthesis"
    model: str | None = Field(default=None, max_length=256)
    max_actions: int = Field(default=8, ge=1, le=12)


def _persisted_mission(snapshot: Mapping[str, Any]) -> str:
    """Resolve the operator mission from user-visible persisted project state only.

    The canonical Project Studio persists `mission` on the project snapshot. A few
    older/project-import paths use `goal`, `intent`, or `brief`; those remain valid
    because they are project state rather than evaluator-supplied cleanroom context.
    Nested mappings are accepted only for explicit brief/mission containers.
    """

    for key in ("mission", "goal", "intent", "brief"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Mapping):
            for nested_key in ("mission", "goal", "intent", "brief", "description"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    raise ValueError(
        "cleanroom project has no persisted mission/goal/intent/brief; save the project brief before evaluation"
    )


def _cleanroom_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "project_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "cleanroom_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, AIProviderError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "ai_provider_unavailable", "message": str(exc)},
        )
    if isinstance(exc, (InvalidAIProjectResponse, CleanroomContractError)):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "cleanroom_contract_violation", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_cleanroom_request", "message": str(exc)},
        )
    if isinstance(exc, (ProjectStoreError, AIProjectOrchestratorError)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "cleanroom_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "cleanroom_error", "message": str(exc)},
    )


def create_dual_agent_cleanroom_router(
    project_store: ProjectStore | None = None,
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["dual-agent-cleanroom"])

    @router.get("/v1/engineering/cleanroom/schema")
    def cleanroom_schema() -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "role": "embedded_operator",
            "snapshot_supplied_by_caller": False,
            "constraints_supplied_by_caller": False,
            "mission_supplied_by_caller": False,
            "constraints_source": "persisted_project_snapshot",
            "mission_source": "persisted_project_snapshot",
            "persisted_project_revision_required": True,
            "repository_source_visible": False,
            "golden_answer_visible": False,
            "outer_agent_analysis_visible": False,
            "evidence_references_must_resolve": True,
            "evaluation_only": True,
            "project_state_mutated": False,
            "automatic_execution": False,
            "authority_effect": "none",
        }

    @router.post("/v1/projects/{project_id}/cleanroom/operator-turn")
    def embedded_operator_turn(
        project_id: str,
        request: EmbeddedOperatorTurnRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            snapshot = envelope["snapshot"]
            mission = _persisted_mission(snapshot)
            persisted_constraints = snapshot.get("constraints")
            constraints = (
                dict(persisted_constraints)
                if isinstance(persisted_constraints, Mapping)
                else {}
            )
            result = run_embedded_operator_turn(
                project_id,
                current_revision,
                snapshot,
                mission=mission,
                constraints=constraints,
                model_profile=request.model_profile,
                model=request.model,
                max_actions=request.max_actions,
                llm_callable=llm_callable,
            )
        except Exception as exc:
            raise _cleanroom_error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "evaluated_revision": current_revision,
            "saved_revision": None,
            "project_state_mutated": False,
            "constraints_source": "persisted_project_snapshot",
            "mission_source": "persisted_project_snapshot",
            "cleanroom": result,
            "automatic_execution": False,
            "authority_effect": "none",
        }

    return router

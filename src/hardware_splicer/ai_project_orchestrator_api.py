"""Revisioned API for proposal-only AI project engineering sessions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Literal, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .ai_project_orchestrator import (
    AI_PROJECT_ACTION_SCHEMA,
    AI_PROJECT_ORCHESTRATOR_SCHEMA,
    AI_PROJECT_SESSION_SCHEMA,
    ALLOWED_AI_ACTION_TYPES,
    MODEL_PROFILES,
    AIProjectOrchestratorError,
    AIProviderError,
    InvalidAIProjectResponse,
    run_ai_project_orchestrator,
)
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class AIProjectAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateAIProjectSessionRequest(AIProjectAPIModel):
    mission: str = Field(min_length=1, max_length=8_000)
    expected_revision: int = Field(ge=1)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    model_profile: Literal["fast_draft", "deep_synthesis", "design_repair"] = (
        "deep_synthesis"
    )
    model: str | None = Field(default=None, max_length=256)
    max_actions: int = Field(default=8, ge=1, le=12)


class AIActionDecisionRequest(AIProjectAPIModel):
    expected_revision: int = Field(ge=1)
    decision: Literal["accepted", "rejected"]
    note: str = Field(default="", max_length=2_000)
    reviewer: str = Field(default="human", min_length=1, max_length=256)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _orchestrator_error(exc: Exception) -> HTTPException:
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
            detail={"type": "ai_project_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, AIProviderError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "ai_provider_unavailable", "message": str(exc)},
        )
    if isinstance(exc, InvalidAIProjectResponse):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "invalid_ai_project_response", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_ai_project_request", "message": str(exc)},
        )
    if isinstance(exc, (ProjectStoreError, AIProjectOrchestratorError)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "ai_project_orchestrator_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "ai_project_orchestrator_error", "message": str(exc)},
    )


def _sessions(snapshot: Mapping[str, Any]) -> list[Dict[str, Any]]:
    return [
        dict(row)
        for row in snapshot.get("engineeringAiSessions") or []
        if isinstance(row, Mapping)
    ]


def _find_session(
    snapshot: Mapping[str, Any], session_id: str
) -> tuple[int, Dict[str, Any]]:
    for index, session in enumerate(_sessions(snapshot)):
        if str(session.get("session_id") or "") == session_id:
            return index, session
    raise ProjectNotFound(f"AI session {session_id!r}")


def create_ai_project_orchestrator_router(
    project_store: ProjectStore | None = None,
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["ai-project-orchestrator"])

    @router.get("/v1/engineering/ai/schema")
    def ai_schema() -> Dict[str, Any]:
        return {
            "schema_version": AI_PROJECT_ORCHESTRATOR_SCHEMA,
            "session_schema": AI_PROJECT_SESSION_SCHEMA,
            "action_schema": AI_PROJECT_ACTION_SCHEMA,
            "model_profiles": sorted(MODEL_PROFILES),
            "allowed_action_types": list(ALLOWED_AI_ACTION_TYPES),
            "automatic_execution": False,
            "model_output_authority": "proposed",
            "physical_authority_unchanged": True,
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "operational_authorized": False,
            "release_authorized": False,
        }

    @router.post("/v1/projects/{project_id}/ai-sessions")
    def create_session(
        project_id: str,
        request: CreateAIProjectSessionRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            snapshot = deepcopy(envelope["snapshot"])
            session = run_ai_project_orchestrator(
                project_id,
                current_revision,
                snapshot,
                mission=request.mission,
                constraints=request.constraints,
                model_profile=request.model_profile,
                model=request.model,
                max_actions=request.max_actions,
                llm_callable=llm_callable,
            )
            sessions = _sessions(snapshot)
            sessions.append(session)
            snapshot["engineeringAiSessions"] = sessions
            snapshot["projectId"] = project_id
            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "ai_project_orchestrator",
                    "ai_session_id": session["session_id"],
                    "ai_project_revision": current_revision,
                    "ai_action_count": len(session["actions"]),
                    "model_profile": session["model_profile"],
                    "provider": session["provider"],
                    "model": session["model"],
                    "automatic_execution": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _orchestrator_error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "session": session,
            "automatic_execution": False,
            "authority_unchanged": True,
        }

    @router.get("/v1/projects/{project_id}/ai-sessions/{session_id}")
    def get_session(project_id: str, session_id: str) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            _, session = _find_session(envelope["snapshot"], session_id)
        except Exception as exc:
            raise _orchestrator_error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "revision": envelope["revision"],
            "session": session,
            "automatic_execution": False,
            "authority_unchanged": True,
        }

    @router.post(
        "/v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/decision"
    )
    def decide_action(
        project_id: str,
        session_id: str,
        action_id: str,
        request: AIActionDecisionRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            snapshot = deepcopy(envelope["snapshot"])
            sessions = _sessions(snapshot)
            session_index, session = _find_session(snapshot, session_id)
            actions = [
                dict(row)
                for row in session.get("actions") or []
                if isinstance(row, Mapping)
            ]
            action_index = next(
                (
                    index
                    for index, action in enumerate(actions)
                    if str(action.get("action_id") or "") == action_id
                ),
                None,
            )
            if action_index is None:
                raise ProjectNotFound(f"AI action {action_id!r}")
            action = dict(actions[action_index])
            if action.get("status") not in {"proposed", request.decision}:
                raise ValueError(
                    f"AI action {action_id!r} already has status {action.get('status')!r}"
                )
            decided_at = _utc_now()
            action["status"] = request.decision
            action["decision"] = {
                "decision": request.decision,
                "reviewer": request.reviewer,
                "note": request.note,
                "decided_at": decided_at,
                "project_revision": current_revision,
                "executed": False,
            }
            action["automatic_execution"] = False
            action["authority_effect"] = "none"
            actions[action_index] = action
            session["actions"] = actions
            session["updated_at"] = decided_at
            session["automatic_execution"] = False
            session["physical_authority_unchanged"] = True
            sessions[session_index] = session
            snapshot["engineeringAiSessions"] = sessions
            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "ai_project_action_decision",
                    "ai_session_id": session_id,
                    "ai_action_id": action_id,
                    "decision": request.decision,
                    "executed": False,
                    "automatic_execution": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _orchestrator_error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "session_id": session_id,
            "action": action,
            "executed": False,
            "automatic_execution": False,
            "authority_unchanged": True,
        }

    return router

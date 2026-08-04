"""Revisioned API for project-grounded AI session continuation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .ai_project_conversation import (
    AI_PROJECT_CONVERSATION_PROMPT_VERSION,
    AI_PROJECT_CONVERSATION_SCHEMA,
    AI_PROJECT_TURN_SCHEMA,
    ALLOWED_EVIDENCE_KINDS,
    AIProjectConversationError,
    InvalidConversationEvidence,
    run_ai_project_conversation_turn,
)
from .ai_project_orchestrator import AIProviderError, InvalidAIProjectResponse
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class AIProjectConversationAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateAIProjectTurnRequest(AIProjectConversationAPIModel):
    expected_revision: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=8_000)
    client_request_id: str = Field(default="", max_length=128)
    model: str | None = Field(default=None, max_length=256)
    max_proposals: int = Field(default=2, ge=0, le=4)


def _conversation_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "ai_conversation_object_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "ai_conversation_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, AIProviderError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "ai_conversation_provider_unavailable", "message": str(exc)},
        )
    if isinstance(exc, InvalidConversationEvidence):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "invalid_ai_conversation_evidence", "message": str(exc)},
        )
    if isinstance(exc, InvalidAIProjectResponse):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "invalid_ai_conversation_response", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_ai_conversation_request", "message": str(exc)},
        )
    if isinstance(exc, (ProjectStoreError, AIProjectConversationError)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "ai_project_conversation_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "ai_project_conversation_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _find_session(
    snapshot: Mapping[str, Any],
    session_id: str,
) -> tuple[list[Dict[str, Any]], int, Dict[str, Any]]:
    sessions = _rows(snapshot.get("engineeringAiSessions"))
    session_index = next(
        (
            index
            for index, session in enumerate(sessions)
            if str(session.get("session_id") or "") == session_id
        ),
        None,
    )
    if session_index is None:
        raise ProjectNotFound(f"AI session {session_id!r}")
    return sessions, session_index, dict(sessions[session_index])


def _existing_turn(
    session: Mapping[str, Any],
    client_request_id: str,
) -> Dict[str, Any] | None:
    token = str(client_request_id or "")
    if not token:
        return None
    for turn in _rows(session.get("conversationTurns")):
        if str(turn.get("client_request_id") or "") == token:
            return turn
    return None


def create_ai_project_conversation_router(
    project_store: ProjectStore | None = None,
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["ai-project-conversation"])

    @router.get("/v1/engineering/ai/conversation/schema")
    def conversation_schema() -> Dict[str, Any]:
        return {
            "schema_version": AI_PROJECT_CONVERSATION_SCHEMA,
            "turn_schema": AI_PROJECT_TURN_SCHEMA,
            "prompt_version": AI_PROJECT_CONVERSATION_PROMPT_VERSION,
            "allowed_evidence_kinds": list(ALLOWED_EVIDENCE_KINDS),
            "project_changes_are_typed_proposals": True,
            "conversation_is_project_truth": False,
            "fresh_human_decision_required": True,
            "automatic_execution": False,
            "physical_authority_unchanged": True,
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "operational_authorized": False,
            "release_authorized": False,
        }

    @router.post("/v1/projects/{project_id}/ai-sessions/{session_id}/turns")
    def create_turn(
        project_id: str,
        session_id: str,
        request: CreateAIProjectTurnRequest,
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
            sessions, session_index, session = _find_session(snapshot, session_id)
            existing = _existing_turn(session, request.client_request_id)
            if existing is not None:
                return {
                    "ok": True,
                    "project_id": project_id,
                    "revision": current_revision,
                    "session_id": session_id,
                    "turn": existing,
                    "session": session,
                    "idempotent": True,
                    "automatic_execution": False,
                    "authority_unchanged": True,
                }

            turn = run_ai_project_conversation_turn(
                project_id,
                current_revision,
                snapshot,
                session,
                user_message=request.message,
                client_request_id=request.client_request_id,
                model=request.model,
                max_proposals=request.max_proposals,
                llm_callable=llm_callable,
            )
            conversation_turns = _rows(session.get("conversationTurns"))
            conversation_turns.append(turn)
            actions = _rows(session.get("actions"))
            actions.extend(_rows(turn.get("proposed_actions")))
            session["conversationTurns"] = conversation_turns
            session["actions"] = actions
            session["updated_at"] = turn["created_at"]
            session["current_project_revision"] = current_revision
            session["automatic_execution"] = False
            session["physical_authority_unchanged"] = True
            sessions[session_index] = session
            snapshot["engineeringAiSessions"] = sessions

            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "ai_project_conversation_turn",
                    "ai_session_id": session_id,
                    "ai_turn_id": turn["turn_id"],
                    "client_request_id": turn["client_request_id"],
                    "answer_kind": turn["answer_kind"],
                    "recommended_action_id": turn["recommended_action_id"],
                    "proposed_action_count": len(turn["proposed_actions"]),
                    "provider": turn["provider"],
                    "model": turn["model"],
                    "automatic_execution": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _conversation_error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "session_id": session_id,
            "turn": turn,
            "session": session,
            "idempotent": False,
            "automatic_execution": False,
            "authority_unchanged": True,
        }

    return router

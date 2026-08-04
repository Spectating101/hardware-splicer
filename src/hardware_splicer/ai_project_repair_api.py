"""Revisioned API for one bounded failure-fed AI repair turn."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .ai_project_orchestrator import AIProviderError, InvalidAIProjectResponse
from .ai_project_repair import (
    AI_PROJECT_REPAIR_SCHEMA,
    AI_PROJECT_REPAIR_PROMPT_VERSION,
    REPAIRABLE_PREVIEW_ACTIONS,
    AIProjectRepairError,
    AIRepairNotEligible,
    run_ai_failure_repair,
)
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class AIProjectRepairAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateAIProjectRepairRequest(AIProjectRepairAPIModel):
    expected_revision: int = Field(ge=1)
    model: str | None = Field(default=None, max_length=256)
    max_actions: int = Field(default=6, ge=1, le=8)


def _repair_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "ai_repair_object_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "ai_repair_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, AIRepairNotEligible):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "ai_repair_not_eligible", "message": str(exc)},
        )
    if isinstance(exc, AIProviderError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"type": "ai_repair_provider_unavailable", "message": str(exc)},
        )
    if isinstance(exc, InvalidAIProjectResponse):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "invalid_ai_repair_response", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_ai_repair_request", "message": str(exc)},
        )
    if isinstance(exc, (ProjectStoreError, AIProjectRepairError)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "ai_project_repair_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "ai_project_repair_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _find_session_action(
    snapshot: Mapping[str, Any],
    session_id: str,
    action_id: str,
) -> tuple[list[Dict[str, Any]], int, Dict[str, Any], list[Dict[str, Any]], int, Dict[str, Any]]:
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
    session = dict(sessions[session_index])
    actions = _rows(session.get("actions"))
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
    return sessions, session_index, session, actions, action_index, dict(actions[action_index])


def _existing_repair(
    sessions: list[Dict[str, Any]],
    parent_session_id: str,
    parent_action_id: str,
) -> Dict[str, Any] | None:
    for session in sessions:
        repair_of = dict(session.get("repair_of") or {})
        if (
            str(repair_of.get("parent_session_id") or "") == parent_session_id
            and str(repair_of.get("parent_action_id") or "") == parent_action_id
        ):
            return session
    return None


def create_ai_project_repair_router(
    project_store: ProjectStore | None = None,
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["ai-project-repair"])

    @router.get("/v1/engineering/ai/repair/schema")
    def repair_schema() -> Dict[str, Any]:
        return {
            "schema_version": AI_PROJECT_REPAIR_SCHEMA,
            "prompt_version": AI_PROJECT_REPAIR_PROMPT_VERSION,
            "repairable_preview_actions": list(REPAIRABLE_PREVIEW_ACTIONS),
            "one_model_turn": True,
            "one_successor_candidate": True,
            "preserve_failed_result": True,
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

    @router.post(
        "/v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/repair"
    )
    def create_repair(
        project_id: str,
        session_id: str,
        action_id: str,
        request: CreateAIProjectRepairRequest,
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
            (
                sessions,
                session_index,
                parent_session,
                actions,
                action_index,
                parent_action,
            ) = _find_session_action(snapshot, session_id, action_id)

            existing = _existing_repair(sessions, session_id, action_id)
            if existing is not None:
                return {
                    "ok": True,
                    "project_id": project_id,
                    "revision": current_revision,
                    "parent_session_id": session_id,
                    "parent_action_id": action_id,
                    "repair_session": existing,
                    "idempotent": True,
                    "automatic_execution": False,
                    "authority_unchanged": True,
                }

            prior_repair_rows = _rows(parent_action.get("repair_sessions"))
            repair_iteration = len(prior_repair_rows) + 1
            repair_session = run_ai_failure_repair(
                project_id,
                current_revision,
                parent_session,
                parent_action,
                repair_iteration=repair_iteration,
                model=request.model,
                max_actions=request.max_actions,
                llm_callable=llm_callable,
            )

            repair_reference = {
                "session_id": repair_session["session_id"],
                "created_at": repair_session["created_at"],
                "project_revision": current_revision,
                "repair_iteration": repair_iteration,
                "failure_sha256": repair_session["repair_of"]["failure_sha256"],
                "status": "successor_proposed",
                "automatic_execution": False,
            }
            parent_action["repair_sessions"] = [*prior_repair_rows, repair_reference]
            parent_action["repair_status"] = "successor_proposed"
            parent_action["automatic_execution"] = False
            parent_action["authority_effect"] = "none"
            actions[action_index] = parent_action
            parent_session["actions"] = actions
            parent_session["updated_at"] = repair_session["created_at"]
            parent_session["automatic_execution"] = False
            parent_session["physical_authority_unchanged"] = True
            sessions[session_index] = parent_session
            sessions.append(repair_session)
            snapshot["engineeringAiSessions"] = sessions

            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "ai_project_failure_repair",
                    "parent_ai_session_id": session_id,
                    "parent_ai_action_id": action_id,
                    "repair_ai_session_id": repair_session["session_id"],
                    "repair_iteration": repair_iteration,
                    "failure_sha256": repair_session["repair_of"]["failure_sha256"],
                    "model_profile": "design_repair",
                    "provider": repair_session["provider"],
                    "model": repair_session["model"],
                    "automatic_execution": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _repair_error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "parent_session_id": session_id,
            "parent_action_id": action_id,
            "parent_action": parent_action,
            "repair_session": repair_session,
            "idempotent": False,
            "automatic_execution": False,
            "authority_unchanged": True,
        }

    return router

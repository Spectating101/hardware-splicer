"""API for explicitly accepted, allowlisted AI project preview actions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .ai_project_tool_executor import (
    AI_TOOL_EXECUTOR_SCHEMA,
    EXECUTABLE_AI_PREVIEW_ACTIONS,
    AIActionNotAccepted,
    AIActionNotExecutable,
    AIProjectToolExecutorError,
    execute_ai_project_action_preview,
)
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class AIProjectToolAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecuteAIActionPreviewRequest(AIProjectToolAPIModel):
    expected_revision: int = Field(ge=1)


def _executor_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "ai_project_object_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "ai_tool_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, AIActionNotExecutable):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "ai_action_not_executable", "message": str(exc)},
        )
    if isinstance(exc, AIActionNotAccepted):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "ai_action_not_accepted", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_ai_tool_request", "message": str(exc)},
        )
    if isinstance(exc, (ProjectStoreError, AIProjectToolExecutorError)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "ai_tool_executor_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "ai_tool_executor_error", "message": str(exc)},
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


def create_ai_project_tool_executor_router(
    project_store: ProjectStore | None = None,
    *,
    guided_planner: Callable[..., Dict[str, Any]] | None = None,
    compose_callable: Callable[..., Dict[str, Any]] | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["ai-project-tool-executor"])

    @router.get("/v1/engineering/ai/tools/schema")
    def tool_schema() -> Dict[str, Any]:
        return {
            "schema_version": AI_TOOL_EXECUTOR_SCHEMA,
            "executable_preview_actions": list(EXECUTABLE_AI_PREVIEW_ACTIONS),
            "requires_explicit_acceptance": True,
            "automatic_execution": False,
            "allow_llm_first_compose": False,
            "export_gerber": False,
            "device_access_authorized": False,
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "operational_authorized": False,
            "release_authorized": False,
        }

    @router.post(
        "/v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/execute-preview"
    )
    def execute_preview(
        project_id: str,
        session_id: str,
        action_id: str,
        request: ExecuteAIActionPreviewRequest,
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
                session,
                actions,
                action_index,
                action,
            ) = _find_session_action(snapshot, session_id, action_id)

            existing_result = action.get("tool_result")
            if isinstance(existing_result, Mapping):
                return {
                    "ok": True,
                    "project_id": project_id,
                    "revision": current_revision,
                    "session_id": session_id,
                    "action": action,
                    "tool_result": dict(existing_result),
                    "idempotent": True,
                    "automatic_execution": False,
                    "authority_unchanged": True,
                }

            tool_result = execute_ai_project_action_preview(
                store,
                project_id,
                session,
                action,
                guided_planner=guided_planner,
                compose_callable=compose_callable,
            )
            action["tool_result"] = tool_result
            action["status"] = (
                "completed" if tool_result.get("status") == "succeeded" else "failed"
            )
            action["automatic_execution"] = False
            action["authority_effect"] = "none"
            actions[action_index] = action
            session["actions"] = actions
            session["updated_at"] = tool_result["completed_at"]
            session["automatic_execution"] = False
            session["physical_authority_unchanged"] = True
            sessions[session_index] = session
            snapshot["engineeringAiSessions"] = sessions

            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "ai_project_tool_preview",
                    "ai_session_id": session_id,
                    "ai_action_id": action_id,
                    "ai_action_type": action.get("action_type"),
                    "tool_status": tool_result.get("status"),
                    "tool_executor": tool_result.get("executor_identity"),
                    "automatic_execution": False,
                    "physical_authority_unchanged": True,
                },
            )
        except Exception as exc:
            raise _executor_error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "session_id": session_id,
            "action": action,
            "tool_result": tool_result,
            "idempotent": False,
            "automatic_execution": False,
            "authority_unchanged": True,
        }

    return router

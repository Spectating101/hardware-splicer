"""API for explicitly accepted, allowlisted AI project preview actions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Mapping, Sequence

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
from .engineering_review_identity import AUTHORITY_CEILING
from .finding_ledger import bound_finding_text, replace_producer_findings
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


_DESIGN_QUALITY_GATE_BASIS = (
    "design_quality gate blocker from an executed deterministic compose"
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _design_quality_gate(tool_result: Any) -> dict[str, Any] | None:
    """Return the persisted gate when an executed tool_result actually carries one."""

    if not isinstance(tool_result, Mapping):
        return None
    summary = _mapping(tool_result.get("summary"))
    if "design_quality_gate" in summary:
        gate = summary.get("design_quality_gate")
        return dict(gate) if isinstance(gate, Mapping) else {}
    failure = _mapping(summary.get("failure"))
    if "design_quality_gate" in failure:
        gate = failure.get("design_quality_gate")
        return dict(gate) if isinstance(gate, Mapping) else {}
    if "design_quality_gate" in tool_result:
        gate = tool_result.get("design_quality_gate")
        return dict(gate) if isinstance(gate, Mapping) else {}
    return None


def _design_quality_gate_findings(tool_result: Mapping[str, Any], action_id: str) -> list[dict[str, Any]]:
    gate = _design_quality_gate(tool_result)
    if gate is None:
        return []
    entries: list[dict[str, Any]] = []
    blockers = gate.get("blockers") or []
    if isinstance(blockers, Sequence) and not isinstance(blockers, (str, bytes, bytearray)):
        for item in blockers:
            text, truncated = bound_finding_text(
                str(item).strip() if item is not None else ""
            )
            if not text:
                continue
            basis = _DESIGN_QUALITY_GATE_BASIS
            if truncated:
                basis = f"{basis} (message truncated)"
            entries.append(
                {
                    "category": "failed_check",
                    "object_id": None,
                    "text": text,
                    "provenance": {
                        "kind": "deterministic",
                        "basis": basis,
                        "source_ref": action_id,
                        "authority_ceiling": AUTHORITY_CEILING,
                    },
                }
            )
    return entries


def _record_design_quality_findings(
    snapshot: Mapping[str, Any],
    action_id: str,
    tool_result: Any,
) -> dict[str, Any]:
    if _design_quality_gate(tool_result) is None:
        return dict(snapshot)
    return replace_producer_findings(
        snapshot,
        "design_quality_gate",
        action_id,
        _design_quality_gate_findings(_mapping(tool_result), action_id),
    )


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
            if (action.get("action_type") == "research_engineering_context"
                    and tool_result.get("status") == "succeeded"):
                # Persist only bounded cited excerpts from the executed source
                # action so the *next* AI session can reason over evidence.
                research_summary = _mapping(tool_result.get("summary"))
                history = _rows(snapshot.get("engineeringWebResearchRuns"))
                if len(history) >= 12:
                    history=history[-11:]
                history.append({
                    'request_id':research_summary.get('research_request_id'),
                    'request_sha256':research_summary.get('request_sha256'),
                    'searched_at_utc':research_summary.get('searched_at_utc'),
                    'research_status':research_summary.get('research_status'),
                    'sources':research_summary.get('sources',[])[:3],
                    'tool_action_id':action_id,
                    'session_id':session_id,
                    'authority_ceiling':'unverified_external_source',
                })
                snapshot['engineeringWebResearchRuns']=history
            # Findings come from the executed tool_result gate, never from the
            # request body. The request carries only expected_revision.
            snapshot = _record_design_quality_findings(snapshot, action_id, tool_result)

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

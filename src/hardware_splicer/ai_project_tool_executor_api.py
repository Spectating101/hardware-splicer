"""API for explicitly accepted, allowlisted AI project preview actions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Mapping, Sequence

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .ai_project_action_inputs import action_input_schemas
from .ai_project_execution_receipts import candidate_execution_lock
from .ai_project_tool_executor import (
    AI_TOOL_EXECUTOR_SCHEMA,
    EXECUTABLE_AI_PREVIEW_ACTIONS,
    AIActionNotAccepted,
    AIActionNotExecutable,
    AIProjectToolExecutorError,
    execute_ai_project_action_preview,
    load_ai_project_action_execution,
    _run_root,
)
from .artifact_retention import retain_revision_artifacts
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
            "action_input_schemas": action_input_schemas(),
            "detached_receipt_actions": ["propose_kicad_edit"],
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

    @router.get(
        "/v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/execution"
    )
    def read_execution(project_id: str, session_id: str, action_id: str) -> Dict[str, Any]:
        try:
            envelope = store.load(project_id)
            _, _, session, _, _, action = _find_session_action(envelope["snapshot"], session_id, action_id)
            result = load_ai_project_action_execution(store, project_id, session, action)
            live_review = None
            if result and result.get("action_type") == "propose_kicad_edit":
                from .project_candidates import load_candidate, review_state
                from .project_review_store import ProjectReviewStore

                candidate_id = _mapping(result.get("summary")).get("candidate_id")
                if candidate_id:
                    candidate = load_candidate(store, project_id, str(candidate_id))
                    live_review = review_state(store, ProjectReviewStore(store), project_id, candidate)
            return {
                "ok": True, "project_id": project_id, "revision": envelope["revision"],
                "session_id": session_id, "action_id": action_id,
                "executed": result is not None, "tool_result": result,
                "review_state": live_review, "authority_unchanged": True,
            }
        except Exception as exc:
            raise _executor_error(exc) from exc

    @router.post(
        "/v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/execute-preview"
    )
    def execute_preview(
        project_id: str,
        session_id: str,
        action_id: str,
        request: ExecuteAIActionPreviewRequest,
    ) -> Dict[str, Any]:
        # Source promotion must serialize preparation and its CAS publication;
        # otherwise simultaneous retries could overwrite one action's artifact
        # before either receipt was saved. Native edits also serialize API reads.
        try:
            envelope = store.load(project_id)
            _, _, _, _, _, action = _find_session_action(envelope["snapshot"], session_id, action_id)
            guarded = action.get("action_type") in {"promote_registered_sources", "propose_kicad_edit"}
            if guarded:
                run_dir, _ = _run_root(store, project_id, session_id, action_id)
                with candidate_execution_lock(run_dir, api=True):
                    return _execute_preview(project_id, session_id, action_id, request)
            return _execute_preview(project_id, session_id, action_id, request)
        except HTTPException:
            raise
        except Exception as exc:
            raise _executor_error(exc) from exc

    def _execute_preview(
        project_id: str,
        session_id: str,
        action_id: str,
        request: ExecuteAIActionPreviewRequest,
    ) -> Dict[str, Any]:
        prepared: dict[str, Any] = {}
        published = False
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

            existing_result = load_ai_project_action_execution(store, project_id, session, action)
            if isinstance(existing_result, Mapping):
                action["tool_result"] = dict(existing_result)
                action["status"] = "completed" if existing_result.get("status") == "succeeded" else "failed"
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
                execution_revision=current_revision,
                prepared_snapshot_sink=lambda value: prepared.update(snapshot=deepcopy(dict(value))),
            )
            if "snapshot" in prepared and tool_result.get("status") == "succeeded":
                snapshot = prepared["snapshot"]
                # Preparation may rewrite the active session's package/build
                # paths. Merge the receipt into that prepared session instead
                # of restoring the pre-promotion bookkeeping copy.
                (sessions, session_index, session, actions, action_index, action) = _find_session_action(
                    snapshot, session_id, action_id,
                )
            action["tool_result"] = tool_result
            action["status"] = (
                "completed" if tool_result.get("status") == "succeeded" else "failed"
            )
            action["automatic_execution"] = False
            action["authority_effect"] = "none"
            if action.get("action_type") == "propose_kicad_edit":
                # The candidate already opens an immutable review at this base.
                # Advancing the project for bookkeeping would immediately stale it.
                return {
                    "ok": True, "project_id": project_id, "revision": current_revision,
                    "session_id": session_id, "action": action, "tool_result": tool_result,
                    "idempotent": False, "automatic_execution": False,
                    "authority_unchanged": True, "project_revision_advanced": False,
                }
            actions[action_index] = action
            session["actions"] = actions
            session["updated_at"] = tool_result["completed_at"]
            session["automatic_execution"] = False
            session["physical_authority_unchanged"] = True
            sessions[session_index] = session
            snapshot["engineeringAiSessions"] = sessions
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
            published = True
            if action.get("action_type") == "promote_registered_sources" and tool_result.get("status") == "succeeded":
                if retain_revision_artifacts(store, project_id, int(saved["revision"]), basis="after_save") is None:
                    raise ValueError("promoted native source bundle could not be retained")
        except Exception as exc:
            if prepared.get("snapshot") and not published:
                from .source_project_editing import discard_prepared_kicad_source_bundle
                promotion = prepared["snapshot"]["sourceEditing"]
                discard_prepared_kicad_source_bundle(
                    {"promotion": promotion, "build_dir": promotion["build_dir"]}, store=store,
                )
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

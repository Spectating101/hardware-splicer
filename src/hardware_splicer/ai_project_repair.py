"""One bounded, failure-fed AI repair turn for project preview results.

A repair turn consumes a persisted failed software preview, asks the configured
text model for one successor candidate and proposed next actions, and returns a
new revision-pinned AI session. It never edits the failed result, executes tools,
or elevates physical authority.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Sequence

from .ai_project_orchestrator import (
    AI_PROJECT_PROMPT_VERSION,
    AI_PROJECT_SESSION_SCHEMA,
    AIProviderError,
    InvalidAIProjectResponse,
    MODEL_PROFILES,
    _canonical_json,
    _sanitize_value,
    _sha256_json,
    _validate_no_authority_elevation,
    parse_ai_project_response,
)
from .integrations.llm_text_client import call_llm_chat

AI_PROJECT_REPAIR_SCHEMA = "hardware_splicer.ai_project_repair.v1"
AI_PROJECT_REPAIR_PROMPT_VERSION = "hardware_splicer.ai_project_repair_prompt.v1"
REPAIRABLE_PREVIEW_ACTIONS = ("run_guided_plan", "run_compose")
_MAX_REPAIR_CONTEXT_CHARS = 120_000
_MAX_REPAIR_ACTIONS = 8


class AIProjectRepairError(RuntimeError):
    """Base error for bounded AI failure repair."""


class AIRepairNotEligible(AIProjectRepairError, ValueError):
    pass


class AIRepairAlreadyExists(AIProjectRepairError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any, *, limit: int = 64) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(row) for row in list(value)[:limit] if isinstance(row, Mapping)]


def _strings(value: Any, *, limit: int = 64) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(row)[:4_000] for row in list(value)[:limit] if str(row).strip()]


def _failure_identity(tool_result: Mapping[str, Any]) -> Dict[str, Any]:
    artifact = _mapping(tool_result.get("artifact"))
    summary = _sanitize_value(tool_result.get("summary") or {})
    error = _sanitize_value(tool_result.get("error") or {})
    digest_payload = {
        "status": tool_result.get("status"),
        "executor_identity": tool_result.get("executor_identity"),
        "action_type": tool_result.get("action_type"),
        "summary": summary,
        "error": error,
        "artifact_sha256": artifact.get("sha256"),
        "artifact_size_bytes": artifact.get("size_bytes"),
        "artifact_project_relative_path": artifact.get("project_relative_path"),
    }
    return {
        **digest_payload,
        "failure_sha256": _sha256_json(digest_payload),
    }


def validate_repair_eligibility(
    parent_session: Mapping[str, Any],
    parent_action: Mapping[str, Any],
) -> Dict[str, Any]:
    action_type = str(parent_action.get("action_type") or "")
    if action_type not in REPAIRABLE_PREVIEW_ACTIONS:
        raise AIRepairNotEligible(
            f"AI action type {action_type!r} has no bounded repair contract"
        )
    if str(parent_action.get("status") or "") != "failed":
        raise AIRepairNotEligible("only a persisted failed preview can start repair")
    tool_result = _mapping(parent_action.get("tool_result"))
    if str(tool_result.get("status") or "") != "failed":
        raise AIRepairNotEligible("repair requires a persisted failed tool result")
    if str(tool_result.get("session_id") or "") != str(parent_session.get("session_id") or ""):
        raise AIRepairNotEligible("failed tool result session identity does not match")
    if str(tool_result.get("action_id") or "") != str(parent_action.get("action_id") or ""):
        raise AIRepairNotEligible("failed tool result action identity does not match")
    if bool(tool_result.get("automatic_execution")):
        raise AIRepairNotEligible("failed result violates the nonautomatic execution boundary")
    for key in (
        "fabrication_authorized",
        "firmware_flash_authorized",
        "power_on_authorized",
        "motion_authorized",
        "operational_authorized",
        "release_authorized",
    ):
        if tool_result.get(key) not in {False, None}:
            raise AIRepairNotEligible(f"failed result attempts to elevate {key}")
    return tool_result


def build_ai_repair_context(
    project_id: str,
    project_revision: int,
    parent_session: Mapping[str, Any],
    parent_action: Mapping[str, Any],
    *,
    repair_iteration: int,
) -> Dict[str, Any]:
    """Compile a bounded repair context without reading preview artifact bytes."""

    tool_result = validate_repair_eligibility(parent_session, parent_action)
    parent_context = _mapping(parent_session.get("context"))
    failure = _failure_identity(tool_result)
    action = {
        "action_id": str(parent_action.get("action_id") or ""),
        "action_type": str(parent_action.get("action_type") or ""),
        "title": str(parent_action.get("title") or "")[:512],
        "rationale": str(parent_action.get("rationale") or "")[:8_000],
        "inputs": _sanitize_value(parent_action.get("inputs") or {}),
        "source_ids": _strings(parent_action.get("source_ids"), limit=32),
        "project_revision": int(parent_action.get("project_revision") or 0),
    }
    context: Dict[str, Any] = {
        "schema_version": AI_PROJECT_REPAIR_SCHEMA,
        "project_id": project_id,
        "project_revision": int(project_revision),
        "repair_iteration": int(repair_iteration),
        "mission": str(parent_session.get("mission") or "")[:8_000],
        "constraints": _sanitize_value(parent_session.get("constraints") or {}),
        "parent_session": {
            "session_id": str(parent_session.get("session_id") or ""),
            "project_revision": int(parent_session.get("project_revision") or 0),
            "summary": str(parent_session.get("summary") or "")[:12_000],
            "requirements": _sanitize_value(_rows(parent_session.get("requirements"))),
            "architecture_candidates": _sanitize_value(
                _rows(parent_session.get("architecture_candidates"), limit=3)
            ),
            "open_questions": _strings(parent_session.get("open_questions")),
            "context_sha256": str(parent_session.get("context_sha256") or ""),
        },
        "failed_action": action,
        "failure": failure,
        "project_evidence_boundary": {
            "project_summary": _sanitize_value(parent_context.get("project_summary") or {}),
            "registered_sources": _sanitize_value(
                _rows(parent_context.get("registered_sources"))
            ),
            "parsed_sources": _sanitize_value(_rows(parent_context.get("parsed_sources"))),
            "parser_runs": _sanitize_value(_rows(parent_context.get("parser_runs"))),
            "parent_context_sha256": str(parent_session.get("context_sha256") or ""),
            "preview_artifact_bytes_included": False,
            "registered_raw_file_content_included": False,
        },
        "repair_policy": {
            "one_model_turn": True,
            "preserve_failed_candidate_and_result": True,
            "create_successor_candidate_only": True,
            "new_actions_require_fresh_human_decision": True,
            "automatic_execution": False,
            "model_output_authority": "proposed",
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "operational_authorized": False,
            "release_authorized": False,
        },
    }
    _validate_no_authority_elevation(context)
    encoded = _canonical_json(context)
    if len(encoded) > _MAX_REPAIR_CONTEXT_CHARS:
        context["project_evidence_boundary"]["parser_runs"] = []
        context["project_evidence_boundary"]["parser_runs_omitted_for_bound"] = True
        encoded = _canonical_json(context)
    if len(encoded) > _MAX_REPAIR_CONTEXT_CHARS:
        context["parent_session"]["requirements"] = []
        context["parent_session"]["open_questions"] = []
        context["repair_policy"]["parent_details_reduced_for_bound"] = True
        encoded = _canonical_json(context)
    if len(encoded) > _MAX_REPAIR_CONTEXT_CHARS:
        raise ValueError("sanitized AI repair context exceeds the bounded context ceiling")
    return context


def build_ai_repair_prompt(context: Mapping[str, Any], *, max_actions: int) -> str:
    return (
        "Repair one failed Hardware Splicer software preview. Return one JSON object only; "
        "do not use markdown fences. Preserve the failed candidate and result as immutable "
        "history. Create exactly one successor architecture candidate. Every statement and "
        "action remains proposed. Do not claim that the failure is fixed until a later "
        "deterministic preview passes. Do not invent evidence, raw file content, shell "
        "commands, device actions, fabrication, flashing, power-on, motion, or release.\n\n"
        "Required top-level keys:\n"
        "- summary: explain the bounded repair hypothesis\n"
        "- requirements: array of proposed corrected or added requirements\n"
        "- open_questions: array of unresolved questions\n"
        "- architecture_candidates: array containing exactly one successor object with id, "
        "title, summary, tradeoffs, assumptions, source_ids\n"
        f"- actions: array of 1 to {int(max_actions)} proposed actions using the existing "
        "Hardware Splicer action vocabulary. Include revise_candidate and, when justified, "
        "a new run_guided_plan or run_compose proposal.\n\n"
        "Ground the repair in the persisted failure summary and source identities. A fresh "
        "human decision is required before any proposed action can run.\n\n"
        f"REPAIR_CONTEXT={_canonical_json(context)}"
    )


def run_ai_failure_repair(
    project_id: str,
    project_revision: int,
    parent_session: Mapping[str, Any],
    parent_action: Mapping[str, Any],
    *,
    repair_iteration: int = 1,
    model: str | None = None,
    max_actions: int = 6,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    if not 1 <= int(repair_iteration) <= 16:
        raise ValueError("repair_iteration must be between 1 and 16")
    if not 1 <= int(max_actions) <= _MAX_REPAIR_ACTIONS:
        raise ValueError(f"max_actions must be between 1 and {_MAX_REPAIR_ACTIONS}")
    validate_repair_eligibility(parent_session, parent_action)

    session_id = f"ai-repair-{uuid.uuid4().hex}"
    context = build_ai_repair_context(
        project_id,
        project_revision,
        parent_session,
        parent_action,
        repair_iteration=repair_iteration,
    )
    prompt = build_ai_repair_prompt(context, max_actions=max_actions)
    profile = MODEL_PROFILES["design_repair"]
    caller = llm_callable or call_llm_chat
    result = caller(
        prompt,
        model=model,
        stage=profile["stage"],
        temperature=float(profile["temperature"]),
        json_mode=True,
        timeout_s=120,
        system=(
            "You are the proposal-only Hardware Splicer failure-repair engineer. "
            "Produce one evidence-grounded successor candidate without altering history."
        ),
    )
    if not isinstance(result, Mapping) or not result.get("ok"):
        detail = dict(result) if isinstance(result, Mapping) else {"result": str(result)}
        raise AIProviderError(
            f"AI provider failed: {detail.get('error') or 'unknown_provider_error'}"
        )
    content = str(result.get("content") or "")
    parsed = parse_ai_project_response(
        content,
        session_id=session_id,
        project_id=project_id,
        project_revision=project_revision,
        max_actions=max_actions,
    )
    if len(parsed["architecture_candidates"]) != 1:
        raise InvalidAIProjectResponse(
            "repair response must contain exactly one successor architecture candidate"
        )
    if not parsed["actions"]:
        raise InvalidAIProjectResponse("repair response must contain at least one proposed action")
    if not any(
        action.get("action_type") == "revise_candidate" for action in parsed["actions"]
    ):
        raise InvalidAIProjectResponse("repair response must propose revise_candidate")

    created_at = _utc_now()
    failure = context["failure"]
    successor = dict(parsed["architecture_candidates"][0])
    successor["lineage"] = {
        "kind": "repair_successor",
        "parent_session_id": str(parent_session.get("session_id") or ""),
        "parent_action_id": str(parent_action.get("action_id") or ""),
        "failure_sha256": failure["failure_sha256"],
        "repair_iteration": int(repair_iteration),
    }
    parsed["architecture_candidates"] = [successor]

    return {
        "schema_version": AI_PROJECT_SESSION_SCHEMA,
        "repair_schema_version": AI_PROJECT_REPAIR_SCHEMA,
        "session_kind": "failure_repair",
        "session_id": session_id,
        "project_id": project_id,
        "project_revision": int(project_revision),
        "created_at": created_at,
        "updated_at": created_at,
        "mission": str(parent_session.get("mission") or "")[:8_000],
        "constraints": _sanitize_value(parent_session.get("constraints") or {}),
        "model_profile": "design_repair",
        "provider": str(result.get("provider") or "unknown"),
        "model": str(result.get("model") or model or "unknown"),
        "cached": bool(result.get("cached", False)),
        "cache_key": str(result.get("cache_key") or ""),
        "usage": _sanitize_value(result.get("usage") or {}),
        "prompt_version": AI_PROJECT_REPAIR_PROMPT_VERSION,
        "parent_prompt_version": AI_PROJECT_PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "context_sha256": _sha256_json(context),
        "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "context": context,
        "repair_of": {
            "parent_session_id": str(parent_session.get("session_id") or ""),
            "parent_action_id": str(parent_action.get("action_id") or ""),
            "parent_action_type": str(parent_action.get("action_type") or ""),
            "failed_project_revision": int(parent_action.get("project_revision") or 0),
            "failure_sha256": failure["failure_sha256"],
            "failure_artifact": {
                "project_relative_path": failure.get("artifact_project_relative_path"),
                "sha256": failure.get("artifact_sha256"),
                "size_bytes": failure.get("artifact_size_bytes"),
            },
            "repair_iteration": int(repair_iteration),
        },
        **parsed,
        "automatic_execution": False,
        "physical_authority_unchanged": True,
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False,
    }

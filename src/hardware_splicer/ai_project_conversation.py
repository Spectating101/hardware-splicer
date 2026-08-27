"""Revision-pinned conversational continuation for AI engineering sessions.

A turn answers one project question from the exact current revision and persisted
session trace. Any suggested project change is emitted as a typed proposal that
must pass through the existing human decision and preview boundaries.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Sequence

from .ai_project_orchestrator import (
    AI_PROJECT_ACTION_SCHEMA,
    ALLOWED_AI_ACTION_TYPES,
    AIProviderError,
    InvalidAIProjectResponse,
    _bounded_text,
    _canonical_json,
    _sanitize_value,
    _sha256_json,
    _string_list,
    _validate_no_authority_elevation,
    build_ai_project_context,
)
from .integrations.llm_text_client import call_llm_chat

AI_PROJECT_CONVERSATION_SCHEMA = "hardware_splicer.ai_project_conversation.v1"
AI_PROJECT_TURN_SCHEMA = "hardware_splicer.ai_project_turn.v1"
AI_PROJECT_CONVERSATION_PROMPT_VERSION = "hardware_splicer.ai_project_conversation_prompt.v1"
ALLOWED_EVIDENCE_KINDS = (
    "source",
    "requirement",
    "candidate",
    "action",
    "tool_result",
    "session",
    "project_revision",
)
_MAX_CONTEXT_CHARS = 160_000
_MAX_TURNS_IN_CONTEXT = 12
_MAX_ACTIONS_IN_CONTEXT = 96


class AIProjectConversationError(RuntimeError):
    """Base error for revisioned project conversation."""


class InvalidConversationEvidence(InvalidAIProjectResponse):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any, *, limit: int = 64) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(row) for row in list(value)[:limit] if isinstance(row, Mapping)]


def _action_context(action: Mapping[str, Any]) -> Dict[str, Any]:
    tool_result = _mapping(action.get("tool_result"))
    return {
        "action_id": str(action.get("action_id") or ""),
        "action_type": str(action.get("action_type") or ""),
        "title": _bounded_text(action.get("title"), limit=512),
        "rationale": _bounded_text(action.get("rationale"), limit=4_000),
        "status": str(action.get("status") or ""),
        "source_ids": _string_list(action.get("source_ids"), limit=32),
        "decision": _sanitize_value(action.get("decision") or {}),
        "tool_result": {
            "status": str(tool_result.get("status") or ""),
            "summary": _sanitize_value(tool_result.get("summary") or {}),
            "error": _sanitize_value(tool_result.get("error") or {}),
            "artifact": _sanitize_value(tool_result.get("artifact") or {}),
            "executor_identity": str(tool_result.get("executor_identity") or ""),
        }
        if tool_result
        else None,
        "repair_sessions": _sanitize_value(_rows(action.get("repair_sessions"), limit=16)),
        "automatic_execution": False,
        "authority_effect": "none",
    }


def _turn_context(turn: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "turn_id": str(turn.get("turn_id") or ""),
        "project_revision": int(turn.get("project_revision") or 0),
        "user_message": _bounded_text(turn.get("user_message"), limit=4_000),
        "assistant_answer": _bounded_text(turn.get("assistant_answer"), limit=8_000),
        "evidence_refs": _sanitize_value(_rows(turn.get("evidence_refs"), limit=24)),
        "blockers": _string_list(turn.get("blockers"), limit=32),
        "recommended_action_id": str(turn.get("recommended_action_id") or ""),
    }


def _evidence_registry(
    base_context: Mapping[str, Any],
    session: Mapping[str, Any],
    project_revision: int,
) -> Dict[str, set[str]]:
    source_ids = {
        str(row.get("source_id") or "")
        for collection in (
            base_context.get("registered_sources"),
            base_context.get("parsed_sources"),
        )
        for row in _rows(collection)
        if str(row.get("source_id") or "")
    }
    actions = _rows(session.get("actions"), limit=_MAX_ACTIONS_IN_CONTEXT)
    return {
        "source": source_ids,
        "requirement": {
            str(row.get("id") or "")
            for row in _rows(session.get("requirements"))
            if str(row.get("id") or "")
        },
        "candidate": {
            str(row.get("id") or "")
            for row in _rows(session.get("architecture_candidates"), limit=16)
            if str(row.get("id") or "")
        },
        "action": {
            str(row.get("action_id") or "")
            for row in actions
            if str(row.get("action_id") or "")
        },
        "tool_result": {
            str(row.get("action_id") or "")
            for row in actions
            if isinstance(row.get("tool_result"), Mapping)
            and str(row.get("action_id") or "")
        },
        "session": {str(session.get("session_id") or "")},
        "project_revision": {str(int(project_revision))},
    }


def build_ai_conversation_context(
    project_id: str,
    project_revision: int,
    snapshot: Mapping[str, Any],
    session: Mapping[str, Any],
    *,
    user_message: str,
) -> Dict[str, Any]:
    message = _bounded_text(user_message, limit=8_000).strip()
    if not message:
        raise ValueError("user_message is required")
    base_context = build_ai_project_context(
        project_id,
        project_revision,
        snapshot,
        mission=str(session.get("mission") or message),
        constraints=_mapping(session.get("constraints")),
    )
    actions = [
        _action_context(row)
        for row in _rows(session.get("actions"), limit=_MAX_ACTIONS_IN_CONTEXT)
    ]
    prior_turns = [
        _turn_context(row)
        for row in _rows(
            session.get("conversationTurns"),
            limit=256,
        )[-_MAX_TURNS_IN_CONTEXT:]
    ]
    context: Dict[str, Any] = {
        "schema_version": AI_PROJECT_CONVERSATION_SCHEMA,
        "project_id": project_id,
        "project_revision": int(project_revision),
        "user_message": message,
        "project_context": base_context,
        "session": {
            "session_id": str(session.get("session_id") or ""),
            "session_kind": str(session.get("session_kind") or "project_proposal"),
            "project_revision": int(session.get("project_revision") or 0),
            "mission": _bounded_text(session.get("mission"), limit=8_000),
            "summary": _bounded_text(session.get("summary"), limit=12_000),
            "requirements": _sanitize_value(_rows(session.get("requirements"))),
            "architecture_candidates": _sanitize_value(
                _rows(session.get("architecture_candidates"), limit=16)
            ),
            "open_questions": _string_list(session.get("open_questions"), limit=64),
            "repair_of": _sanitize_value(session.get("repair_of") or {}),
            "actions": actions,
            "prior_turns": prior_turns,
        },
        "conversation_policy": {
            "answer_from_current_revision_only": True,
            "unknowns_must_be_explicit": True,
            "project_changes_must_be_typed_proposals": True,
            "conversation_is_not_project_truth": True,
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
    registry = _evidence_registry(base_context, session, project_revision)
    context["evidence_registry"] = {
        kind: sorted(values) for kind, values in registry.items()
    }
    _validate_no_authority_elevation(context)
    encoded = _canonical_json(context)
    if len(encoded) > _MAX_CONTEXT_CHARS:
        context["project_context"]["parser_runs"] = []
        context["conversation_policy"]["parser_runs_omitted_for_bound"] = True
        encoded = _canonical_json(context)
    if len(encoded) > _MAX_CONTEXT_CHARS:
        context["session"]["prior_turns"] = prior_turns[-6:]
        context["conversation_policy"]["turn_history_reduced_for_bound"] = True
        encoded = _canonical_json(context)
    if len(encoded) > _MAX_CONTEXT_CHARS:
        for action in context["session"]["actions"]:
            if isinstance(action, dict) and isinstance(action.get("tool_result"), dict):
                action["tool_result"] = {
                    "status": action["tool_result"].get("status"),
                    "artifact": action["tool_result"].get("artifact"),
                }
        context["conversation_policy"]["tool_summaries_reduced_for_bound"] = True
        encoded = _canonical_json(context)
    if len(encoded) > _MAX_CONTEXT_CHARS:
        raise ValueError("sanitized conversation context exceeds the bounded context ceiling")
    return context


def build_ai_conversation_prompt(
    context: Mapping[str, Any],
    *,
    max_proposals: int,
) -> str:
    return (
        "Answer one follow-up question about the current Hardware Splicer project. Return "
        "one JSON object only, without markdown fences. Ground factual statements in IDs "
        "from EVIDENCE_REGISTRY. State uncertainty and blockers explicitly. Do not treat "
        "conversation as project truth. Any suggested project change must be emitted as a "
        "typed proposal and must not be described as already executed or accepted.\n\n"
        "Required top-level keys:\n"
        "- answer: direct, useful answer to the user's message\n"
        "- evidence_refs: 1 to 24 objects with kind, id, reason\n"
        "- blockers: array of unresolved blockers or missing evidence\n"
        "- recommended_action: null or one object with action_type, title, rationale, inputs, source_ids\n"
        f"- additional_proposals: array of at most {int(max_proposals)} objects with the same action fields\n"
        "- answer_kind: one of technical_answer, decision_briefing, clarification_request\n\n"
        f"Allowed action types: {', '.join(ALLOWED_AI_ACTION_TYPES)}.\n"
        f"Allowed evidence kinds: {', '.join(ALLOWED_EVIDENCE_KINDS)}.\n"
        "Never emit raw file content, secrets, shell commands, arbitrary URLs, device actions, "
        "fabrication orders, flashing, power-on, motion, operational, or release authority.\n\n"
        f"CONVERSATION_CONTEXT={_canonical_json(context)}"
    )


def _parse_evidence_refs(
    value: Any,
    registry: Mapping[str, set[str]],
) -> list[Dict[str, Any]]:
    rows = _rows(value, limit=24)
    if not rows:
        raise InvalidConversationEvidence("conversation response requires evidence_refs")
    result: list[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        kind = str(row.get("kind") or "")
        evidence_id = str(row.get("id") or "")
        reason = _bounded_text(row.get("reason"), limit=2_000).strip()
        if kind not in ALLOWED_EVIDENCE_KINDS:
            raise InvalidConversationEvidence(
                f"evidence_refs[{index}].kind {kind!r} is not allowed"
            )
        if evidence_id not in registry.get(kind, set()):
            raise InvalidConversationEvidence(
                f"evidence_refs[{index}] cites unknown {kind} id {evidence_id!r}"
            )
        if not reason:
            raise InvalidConversationEvidence(
                f"evidence_refs[{index}].reason is required"
            )
        result.append({"kind": kind, "id": evidence_id, "reason": reason})
    return result


def _parse_turn_action(
    row: Mapping[str, Any],
    *,
    turn_id: str,
    session_id: str,
    project_id: str,
    project_revision: int,
    index: int,
    known_source_ids: set[str],
) -> Dict[str, Any]:
    action_type = str(row.get("action_type") or "")
    if action_type not in ALLOWED_AI_ACTION_TYPES:
        raise InvalidAIProjectResponse(
            f"conversation action type {action_type!r} is not allowed"
        )
    title = _bounded_text(row.get("title"), limit=256).strip()
    rationale = _bounded_text(row.get("rationale"), limit=8_000).strip()
    if not title or not rationale:
        raise InvalidAIProjectResponse("conversation action requires title and rationale")
    inputs = _sanitize_value(_mapping(row.get("inputs")))
    _validate_no_authority_elevation(inputs, path="conversation_action.inputs")
    source_ids = _string_list(row.get("source_ids"), limit=32)
    unknown_sources = sorted(set(source_ids) - known_source_ids)
    if unknown_sources:
        raise InvalidConversationEvidence(
            f"conversation action cites unknown source ids: {unknown_sources}"
        )
    identity_seed = {
        "turn_id": turn_id,
        "index": index,
        "action_type": action_type,
        "title": title,
        "inputs": inputs,
    }
    action_id = "action-" + _sha256_json(identity_seed)[:16]
    return {
        "schema_version": AI_PROJECT_ACTION_SCHEMA,
        "action_id": action_id,
        "session_id": session_id,
        "project_id": project_id,
        "project_revision": int(project_revision),
        "action_type": action_type,
        "title": title,
        "rationale": rationale,
        "inputs": inputs,
        "source_ids": source_ids,
        "origin_turn_id": turn_id,
        "status": "proposed",
        "authority": "proposed",
        "authority_effect": "none",
        "automatic_execution": False,
        "tool_result": None,
        "decision": None,
    }


def parse_ai_conversation_response(
    content: str,
    *,
    turn_id: str,
    session_id: str,
    project_id: str,
    project_revision: int,
    context: Mapping[str, Any],
    max_proposals: int,
) -> Dict[str, Any]:
    try:
        parsed = json.loads(str(content or "").strip())
    except json.JSONDecodeError as exc:
        raise InvalidAIProjectResponse("conversation response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise InvalidAIProjectResponse("conversation response must be one JSON object")
    _validate_no_authority_elevation(parsed)
    answer = _bounded_text(parsed.get("answer"), limit=16_000).strip()
    if not answer:
        raise InvalidAIProjectResponse("conversation response answer is required")
    answer_kind = str(parsed.get("answer_kind") or "technical_answer")
    if answer_kind not in {
        "technical_answer",
        "decision_briefing",
        "clarification_request",
    }:
        raise InvalidAIProjectResponse(f"unsupported answer_kind: {answer_kind}")
    registry = {
        kind: set(str(row) for row in values)
        for kind, values in _mapping(context.get("evidence_registry")).items()
        if isinstance(values, list)
    }
    evidence_refs = _parse_evidence_refs(parsed.get("evidence_refs"), registry)
    blockers = _string_list(parsed.get("blockers"), limit=64)
    raw_actions: list[Mapping[str, Any]] = []
    recommended = parsed.get("recommended_action")
    if recommended is not None:
        if not isinstance(recommended, Mapping):
            raise InvalidAIProjectResponse("recommended_action must be null or an object")
        raw_actions.append(recommended)
    additional = parsed.get("additional_proposals") or []
    if not isinstance(additional, list):
        raise InvalidAIProjectResponse("additional_proposals must be an array")
    if len(additional) > int(max_proposals):
        raise InvalidAIProjectResponse(
            f"conversation returned {len(additional)} additional proposals, maximum is {max_proposals}"
        )
    for row in additional:
        if not isinstance(row, Mapping):
            raise InvalidAIProjectResponse("additional proposal must be an object")
        raw_actions.append(row)
    known_sources = registry.get("source", set())
    actions = [
        _parse_turn_action(
            row,
            turn_id=turn_id,
            session_id=session_id,
            project_id=project_id,
            project_revision=project_revision,
            index=index,
            known_source_ids=known_sources,
        )
        for index, row in enumerate(raw_actions)
    ]
    return {
        "answer_kind": answer_kind,
        "assistant_answer": answer,
        "evidence_refs": evidence_refs,
        "blockers": blockers,
        "recommended_action_id": actions[0]["action_id"] if recommended is not None else None,
        "proposed_actions": actions,
    }


def run_ai_project_conversation_turn(
    project_id: str,
    project_revision: int,
    snapshot: Mapping[str, Any],
    session: Mapping[str, Any],
    *,
    user_message: str,
    client_request_id: str = "",
    model: str | None = None,
    max_proposals: int = 2,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    if not 0 <= int(max_proposals) <= 4:
        raise ValueError("max_proposals must be between 0 and 4")
    message = _bounded_text(user_message, limit=8_000).strip()
    if not message:
        raise ValueError("user_message is required")
    turn_id = f"ai-turn-{uuid.uuid4().hex}"
    context = build_ai_conversation_context(
        project_id,
        project_revision,
        snapshot,
        session,
        user_message=message,
    )
    prompt = build_ai_conversation_prompt(context, max_proposals=max_proposals)
    caller = llm_callable or call_llm_chat
    result = caller(
        prompt,
        model=model,
        stage="workshop",
        temperature=0.0,
        json_mode=True,
        timeout_s=120,
        system=(
            "You are Hardware Splicer's revision-aware JARVIS engineering interface. "
            "Answer from supplied evidence and emit typed proposals for any project change."
        ),
    )
    if not isinstance(result, Mapping) or not result.get("ok"):
        detail = dict(result) if isinstance(result, Mapping) else {"result": str(result)}
        raise AIProviderError(
            f"AI provider failed: {detail.get('error') or 'unknown_provider_error'}"
        )
    content = str(result.get("content") or "")
    parsed = parse_ai_conversation_response(
        content,
        turn_id=turn_id,
        session_id=str(session.get("session_id") or ""),
        project_id=project_id,
        project_revision=project_revision,
        context=context,
        max_proposals=max_proposals,
    )
    created_at = _utc_now()
    return {
        "schema_version": AI_PROJECT_TURN_SCHEMA,
        "conversation_schema_version": AI_PROJECT_CONVERSATION_SCHEMA,
        "turn_id": turn_id,
        "client_request_id": str(client_request_id or "")[:128],
        "session_id": str(session.get("session_id") or ""),
        "project_id": project_id,
        "project_revision": int(project_revision),
        "created_at": created_at,
        "user_message": message,
        "provider": str(result.get("provider") or "unknown"),
        "model": str(result.get("model") or model or "unknown"),
        "cached": bool(result.get("cached", False)),
        "cache_key": str(result.get("cache_key") or ""),
        "usage": _sanitize_value(result.get("usage") or {}),
        "prompt_version": AI_PROJECT_CONVERSATION_PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "context_sha256": _sha256_json(context),
        "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "context": context,
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

"""Bounded, project-revision-pinned AI engineering proposal orchestration.

The orchestrator is intentionally proposal-only. It assembles a sanitized project
context, asks the configured text model for schema-shaped engineering proposals,
validates the response, and returns auditable session/action records. It does not
execute tools, mutate design artifacts, or elevate physical authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Sequence

from .integrations.llm_text_client import call_llm_chat

AI_PROJECT_ORCHESTRATOR_SCHEMA = "hardware_splicer.ai_project_orchestrator.v1"
AI_PROJECT_SESSION_SCHEMA = "hardware_splicer.ai_project_session.v1"
AI_PROJECT_ACTION_SCHEMA = "hardware_splicer.ai_project_action.v1"
AI_PROJECT_PROMPT_VERSION = "hardware_splicer.ai_project_prompt.v1"

ALLOWED_AI_ACTION_TYPES = (
    "clarify_requirement",
    "identify_missing_evidence",
    "propose_architecture",
    "compare_architectures",
    "propose_components",
    "propose_interfaces",
    "generate_netlist_candidate",
    "run_guided_plan",
    "run_compose",
    "run_erc",
    "run_drc",
    "revise_candidate",
    "prepare_verification",
    "prepare_engineering_package",
)

MODEL_PROFILES: Dict[str, Dict[str, Any]] = {
    "fast_draft": {"stage": "general", "temperature": 0.0},
    "deep_synthesis": {"stage": "planning", "temperature": 0.0},
    "design_repair": {"stage": "review", "temperature": 0.0},
}

_RAW_CONTENT_KEYS = {
    "content",
    "content_base64",
    "raw",
    "raw_bytes",
    "bytes",
    "file_bytes",
    "binary",
    "blob_bytes",
}
_AUTHORITY_KEYS = {
    "fabrication_authorized",
    "firmware_flash_authorized",
    "flash_authorized",
    "power_on_authorized",
    "motion_authorized",
    "operational_authorized",
    "release_authorized",
    "fabricationAuthority",
    "flashAuthority",
    "powerAuthority",
    "motionAuthority",
    "releaseAuthority",
}
_MAX_CONTEXT_CHARS = 180_000
_MAX_TEXT_CHARS = 16_000
_MAX_COLLECTION_ROWS = 64


class AIProjectOrchestratorError(RuntimeError):
    """Base error for bounded AI project orchestration."""


class AIProviderError(AIProjectOrchestratorError):
    pass


class InvalidAIProjectResponse(AIProjectOrchestratorError, ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _bounded_text(value: Any, *, limit: int = _MAX_TEXT_CHARS) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _sanitize_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "[depth-limited]"
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key in _RAW_CONTENT_KEYS:
                continue
            if key in _AUTHORITY_KEYS:
                result[key] = False
                continue
            result[key] = _sanitize_value(raw_value, depth=depth + 1)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _sanitize_value(row, depth=depth + 1)
            for row in list(value)[:_MAX_COLLECTION_ROWS]
        ]
    if isinstance(value, (bytes, bytearray)):
        return "[binary-omitted]"
    if isinstance(value, str):
        return _bounded_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _bounded_text(value)


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [
        dict(row)
        for row in list(value or [])[:_MAX_COLLECTION_ROWS]
        if isinstance(row, Mapping)
    ]


def _source_context(source: Mapping[str, Any]) -> Dict[str, Any]:
    metadata = _sanitize_value(dict(source.get("metadata") or {}))
    return {
        "source_id": str(source.get("source_id") or ""),
        "source_type": str(source.get("source_type") or source.get("kind") or "other"),
        "media_type": str(source.get("media_type") or ""),
        "content_hash": str(source.get("content_hash") or ""),
        "revision": str(source.get("revision") or ""),
        "authority_ceiling": str(source.get("authority_ceiling") or "declared"),
        "parser_route": str(source.get("parser_route") or ""),
        "parser_disposition": str(source.get("parser_disposition") or ""),
        "metadata": metadata,
    }


def _parser_run_context(run: Mapping[str, Any]) -> Dict[str, Any]:
    output = _sanitize_value(run.get("output") or run.get("result") or {})
    return {
        "source_id": str(run.get("source_id") or ""),
        "content_hash": str(run.get("content_hash") or ""),
        "status": str(run.get("status") or ""),
        "parser_route": str(run.get("parser_route") or ""),
        "parser_identity": str(run.get("parser_identity") or ""),
        "limitations": _sanitize_value(run.get("limitations") or []),
        "output": output,
    }


def build_ai_project_context(
    project_id: str,
    revision: int,
    snapshot: Mapping[str, Any],
    *,
    mission: str,
    constraints: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a bounded model context without registered raw file content."""

    sources = [_source_context(row) for row in _rows(snapshot.get("engineeringSources"))]
    parsed_sources = [
        _source_context(row) for row in _rows(snapshot.get("engineeringParsedSources"))
    ]
    parser_runs = [
        _parser_run_context(row)
        for row in _rows(snapshot.get("engineeringSourceParserRuns"))
    ]

    selected_snapshot = {
        key: _sanitize_value(snapshot.get(key))
        for key in (
            "name",
            "mode",
            "currentStage",
            "engineering_readiness",
            "engineering_status",
            "machineProject",
            "robotTopology",
            "manufacturingClosure",
            "engineeringAnalysis",
            "engineeringBlockers",
            "engineeringAdvisories",
            "engineeringSourceConflicts",
            "engineering_source_conflicts",
            "declared_conflicts",
            "source_conflicts",
            "rankedNextAction",
        )
        if snapshot.get(key) is not None
    }
    context: Dict[str, Any] = {
        "schema_version": AI_PROJECT_ORCHESTRATOR_SCHEMA,
        "project_id": project_id,
        "project_revision": int(revision),
        "mission": _bounded_text(mission, limit=8_000),
        "constraints": _sanitize_value(dict(constraints or {})),
        "project_summary": selected_snapshot,
        "registered_sources": sources,
        "parsed_sources": parsed_sources,
        "parser_runs": parser_runs,
        "context_policy": {
            "raw_registered_file_content_included": False,
            "source_authority_may_not_be_elevated": True,
            "source_conflicts_preserved": True,
            "model_output_authority": "proposed",
            "automatic_execution": False,
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "operational_authorized": False,
            "release_authorized": False,
        },
    }
    encoded = _canonical_json(context)
    if len(encoded) > _MAX_CONTEXT_CHARS:
        context["parser_runs"] = []
        context["context_policy"]["parser_runs_omitted_for_context_bound"] = True
        encoded = _canonical_json(context)
    if len(encoded) > _MAX_CONTEXT_CHARS:
        context["project_summary"] = {
            "engineering_readiness": _sanitize_value(
                snapshot.get("engineering_readiness")
            ),
            "engineering_status": _sanitize_value(snapshot.get("engineering_status")),
            "engineeringBlockers": _sanitize_value(snapshot.get("engineeringBlockers")),
            "engineeringSourceConflicts": _sanitize_value(snapshot.get("engineeringSourceConflicts")),
        }
        context["context_policy"]["project_summary_reduced_for_context_bound"] = True
        encoded = _canonical_json(context)
    if len(encoded) > _MAX_CONTEXT_CHARS:
        raise ValueError("sanitized AI project context exceeds the bounded context ceiling")
    return context


def build_ai_project_prompt(context: Mapping[str, Any], *, max_actions: int) -> str:
    action_types = ", ".join(ALLOWED_AI_ACTION_TYPES)
    return (
        "Analyze the following Hardware Splicer project and return one JSON object only. "
        "Do not use markdown fences. Treat every model conclusion as proposed, never verified. "
        "Do not claim fabrication, flashing, power, motion, operational, or release authority. "
        "Do not invent source evidence. Prefer explicit missing-evidence actions over guesses.\n\n"
        "Required top-level keys:\n"
        "- summary: string\n"
        "- requirements: array of objects with id, statement, source_ids, assumptions\n"
        "- open_questions: array of strings\n"
        "- architecture_candidates: array of at most 3 objects with id, title, summary, "
        "tradeoffs, assumptions, source_ids\n"
        f"- actions: array of at most {int(max_actions)} objects with action_type, title, "
        "rationale, inputs, source_ids\n\n"
        f"Allowed action_type values: {action_types}.\n"
        "Every action is a proposal only. Never emit shell commands, arbitrary URLs, secrets, "
        "raw file content, device operations, fabrication orders, flashing, power-on, or motion.\n\n"
        f"PROJECT_CONTEXT={_canonical_json(context)}"
    )


def _strip_json_fence(content: str) -> str:
    text = str(content or "").strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text


def _string_list(value: Any, *, limit: int = 64) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for row in value[:limit]:
        text = _bounded_text(row, limit=2_000).strip()
        if text:
            result.append(text)
    return result


def _validate_no_authority_elevation(value: Any, *, path: str = "response") -> None:
    if isinstance(value, Mapping):
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key in _RAW_CONTENT_KEYS:
                raise InvalidAIProjectResponse(f"{path}.{key} may not contain raw content")
            if key in _AUTHORITY_KEYS and raw_value not in {False, None, "false", "none"}:
                raise InvalidAIProjectResponse(
                    f"{path}.{key} attempts to elevate physical authority"
                )
            _validate_no_authority_elevation(raw_value, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, row in enumerate(value):
            _validate_no_authority_elevation(row, path=f"{path}[{index}]")


def _parse_provider_content(provider: Mapping[str, Any]) -> Dict[str, Any]:
    content = _strip_json_fence(str(provider.get("content") or ""))
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InvalidAIProjectResponse(f"model did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise InvalidAIProjectResponse("model response must be one JSON object")
    _validate_no_authority_elevation(parsed)
    return dict(parsed)


def _normalize_source_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for row in value[:32]:
        source_id = str(row or "").strip()
        if source_id and source_id not in result:
            result.append(source_id)
    return result


def _normalize_requirements(value: Any) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for index, row in enumerate(_rows(value)[:32]):
        statement = _bounded_text(row.get("statement"), limit=4_000).strip()
        if not statement:
            continue
        result.append(
            {
                "id": str(row.get("id") or f"req-{index + 1}"),
                "statement": statement,
                "source_ids": _normalize_source_ids(row.get("source_ids")),
                "assumptions": _string_list(row.get("assumptions"), limit=16),
            }
        )
    return result


def _normalize_candidates(value: Any) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for index, row in enumerate(_rows(value)[:3]):
        result.append(
            {
                "id": str(row.get("id") or f"candidate-{index + 1}"),
                "title": _bounded_text(row.get("title"), limit=1_000),
                "summary": _bounded_text(row.get("summary"), limit=6_000),
                "tradeoffs": _string_list(row.get("tradeoffs"), limit=16),
                "assumptions": _string_list(row.get("assumptions"), limit=16),
                "source_ids": _normalize_source_ids(row.get("source_ids")),
            }
        )
    return result


def _normalize_actions(value: Any, *, max_actions: int) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for index, row in enumerate(_rows(value)[:max_actions]):
        action_type = str(row.get("action_type") or "").strip()
        if action_type not in ALLOWED_AI_ACTION_TYPES:
            raise InvalidAIProjectResponse(
                f"unsupported AI action_type {action_type!r}; allowed={list(ALLOWED_AI_ACTION_TYPES)}"
            )
        result.append(
            {
                "action_id": str(row.get("action_id") or f"action-{index + 1}"),
                "action_type": action_type,
                "title": _bounded_text(row.get("title"), limit=1_000),
                "rationale": _bounded_text(row.get("rationale"), limit=4_000),
                "inputs": _sanitize_value(row.get("inputs") or {}),
                "source_ids": _normalize_source_ids(row.get("source_ids")),
                "authority_effect": "none",
                "automatic_execution": False,
            }
        )
    return result


def run_ai_project_orchestrator(
    project_id: str,
    project_revision: int,
    snapshot: Mapping[str, Any],
    *,
    mission: str,
    constraints: Mapping[str, Any] | None = None,
    model_profile: str = "deep_synthesis",
    model: str | None = None,
    max_actions: int = 8,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Run one proposal-only AI engineering turn pinned to a project revision."""

    project_id = str(project_id or "").strip()
    if not project_id:
        raise ValueError("project_id is required")
    if int(project_revision) < 0:
        raise ValueError("project_revision must be non-negative")
    mission = str(mission or "").strip()
    if not mission:
        raise ValueError("mission is required")
    if model_profile not in MODEL_PROFILES:
        raise ValueError(f"unknown model_profile {model_profile!r}")
    max_actions = max(1, min(int(max_actions), 16))

    context = build_ai_project_context(
        project_id,
        int(project_revision),
        snapshot,
        mission=mission,
        constraints=constraints,
    )
    prompt = build_ai_project_prompt(context, max_actions=max_actions)
    profile = MODEL_PROFILES[model_profile]
    caller = llm_callable or call_llm_chat
    provider = caller(
        prompt,
        model=model,
        stage=str(profile["stage"]),
        temperature=float(profile["temperature"]),
        max_tokens=8_000,
        timeout_s=90.0,
    )
    if not provider.get("ok"):
        raise AIProviderError(
            str(provider.get("message") or provider.get("error") or "AI provider call failed")
        )
    parsed = _parse_provider_content(provider)
    requirements = _normalize_requirements(parsed.get("requirements"))
    candidates = _normalize_candidates(parsed.get("architecture_candidates"))
    actions = _normalize_actions(parsed.get("actions"), max_actions=max_actions)
    session_id = str(uuid.uuid4())
    return {
        "schema_version": AI_PROJECT_SESSION_SCHEMA,
        "session_id": session_id,
        "project_id": project_id,
        "project_revision": int(project_revision),
        "project_context_hash": _sha256_json(context),
        "prompt_version": AI_PROJECT_PROMPT_VERSION,
        "model_profile": model_profile,
        "provider": str(provider.get("provider") or ""),
        "model": str(provider.get("model") or model or ""),
        "summary": _bounded_text(parsed.get("summary"), limit=8_000),
        "requirements": requirements,
        "open_questions": _string_list(parsed.get("open_questions"), limit=64),
        "architecture_candidates": candidates,
        "actions": actions,
        "context": context,
        "usage": dict(provider.get("usage") or {}),
        "created_at": _utc_now(),
        "authority_effect": "none",
        "automatic_execution": False,
        "physical_authority_unchanged": True,
    }

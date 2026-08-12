"""Typed semantic proposal for project/change mode.

Structured project state can establish mode deterministically: a recorded field failure,
repair object, salvage flag, change request, or baseline revision is explicit state. Only
when those facts are absent should natural-language interpretation be needed. This module
provides that bounded semantic interpretation without granting execution or authority.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SCHEMA_VERSION = "hardware_splicer.semantic_project_mode.v1"
ALLOWED_PROJECT_MODES = ("greenfield", "modify", "repair", "evolve")


class SemanticProjectModeError(ValueError):
    pass


class ModeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectModeProposal(ModeModel):
    schema_version: str = SCHEMA_VERSION
    status: str = "model_proposed"
    mode: str
    reasoning: str = Field(default="", max_length=4_000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=24)
    source: str = "model_proposed"
    authority_effect: str = "none"
    automatic_execution: bool = False

    @field_validator("mode")
    @classmethod
    def bounded_mode(cls, value: str) -> str:
        normalized = str(value).strip().lower().replace("-", "_")
        aliases = {
            "modification": "modify",
            "field_evolution": "evolve",
            "field_failure": "evolve",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in ALLOWED_PROJECT_MODES:
            raise ValueError(f"unsupported project mode: {value!r}")
        return normalized

    @field_validator("authority_effect")
    @classmethod
    def zero_authority_only(cls, value: str) -> str:
        if value != "none":
            raise ValueError("project mode proposal cannot change engineering authority")
        return value

    @field_validator("automatic_execution")
    @classmethod
    def no_auto_execution(cls, value: bool) -> bool:
        if value:
            raise ValueError("project mode proposal cannot execute actions")
        return False


def _extract_json_object(text: str) -> Dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, Mapping):
        raise SemanticProjectModeError("project mode response must be one JSON object")
    return dict(parsed)


def parse_project_mode_proposal(value: Mapping[str, Any] | str) -> ProjectModeProposal:
    body = _extract_json_object(value) if isinstance(value, str) else dict(value)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("status", "model_proposed")
    body.setdefault("source", "model_proposed")
    body.setdefault("authority_effect", "none")
    body.setdefault("automatic_execution", False)
    try:
        return ProjectModeProposal.model_validate(body)
    except ValidationError as exc:
        raise SemanticProjectModeError(str(exc)) from exc


def project_mode_prompt(goal: str) -> str:
    return f"""Classify the engineering project into one bounded workflow mode.

Project goal:
{goal.strip()}

Allowed modes:
{json.dumps(list(ALLOWED_PROJECT_MODES))}

Meanings:
- greenfield: create a new system without an established prior design/baseline.
- modify: revise or extend an existing known system/baseline.
- repair: diagnose/recover/adapt failed, damaged, donor, inherited, or salvage hardware.
- evolve: respond to an observed field failure or field-performance event and produce a new revision.

Return JSON only:
{{
  "mode": "one allowed mode",
  "reasoning": "brief workflow justification",
  "confidence": 0.0,
  "unresolved_questions": [],
  "authority_effect": "none",
  "automatic_execution": false
}}

Rules:
- Choose only from the supplied modes.
- Classify workflow intent only; do not invent failure evidence, baseline revisions, hardware facts, or measurements.
- If the wording is ambiguous, choose greenfield as a neutral projection and list the unresolved question.
- This proposal grants no fabrication, flashing, power, motion, operational, or release authority.
"""


def interpret_project_mode(
    goal: str,
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> ProjectModeProposal:
    if not goal.strip():
        raise SemanticProjectModeError("goal is required")
    prompt = project_mode_prompt(goal)
    if llm_callable is None:
        from .integrations.qwen_text_client import call_qwen_chat

        response = call_qwen_chat(
            prompt,
            json_mode=True,
            stage="semantic_project_mode",
            system="Return one bounded project workflow mode only; never invent project state.",
            timeout_s=60,
        )
    else:
        response = llm_callable(
            prompt,
            json_mode=True,
            stage="semantic_project_mode",
            system="Return one bounded project workflow mode only; never invent project state.",
            timeout_s=60,
        )
    if not response.get("ok"):
        raise SemanticProjectModeError(
            str(response.get("error") or response.get("reason") or "project mode provider failed")
        )
    return parse_project_mode_proposal(str(response.get("content") or "{}"))


def unresolved_project_mode_proposal(reason: str) -> ProjectModeProposal:
    message = str(reason or "Project mode could not be resolved from available context.").strip()
    return ProjectModeProposal(
        status="unresolved",
        mode="greenfield",
        reasoning=message,
        confidence=0.0,
        unresolved_questions=[message],
        source="unresolved",
        authority_effect="none",
        automatic_execution=False,
    )

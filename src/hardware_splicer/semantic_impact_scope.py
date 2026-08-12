"""Bounded semantic scope proposal for cross-domain change impact.

Natural-language change descriptions may imply mechanical, electrical, firmware,
software, control, safety, sourcing, assembly, and verification consequences. Choosing
those domains is semantic interpretation, not a deterministic parser contract.

The model may propose only domain names from this bounded vocabulary. It cannot choose
object IDs, severities, verification pass/fail, or any physical/release authority.
Deterministic change-impact code validates the proposal and applies conservative policy.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SCHEMA_VERSION = "hardware_splicer.semantic_impact_scope.v1"
ALLOWED_IMPACT_DOMAINS = (
    "system",
    "mechanical",
    "electrical",
    "firmware",
    "software",
    "control",
    "safety",
    "sourcing",
    "assembly",
    "verification",
)


class SemanticImpactScopeError(ValueError):
    pass


class ImpactScopeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SemanticImpactScope(ImpactScopeModel):
    schema_version: str = SCHEMA_VERSION
    status: str = "model_proposed"
    domains: list[str] = Field(default_factory=list, max_length=10)
    reasoning: str = Field(default="", max_length=4_000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=24)
    source: str = "model_proposed"
    authority_effect: str = "none"
    automatic_execution: bool = False

    @field_validator("domains")
    @classmethod
    def validate_domains(cls, value: list[str]) -> list[str]:
        normalized = [str(row).strip().lower() for row in value if str(row).strip()]
        unknown = sorted(set(normalized) - set(ALLOWED_IMPACT_DOMAINS))
        if unknown:
            raise ValueError("unknown impact domains: " + ", ".join(unknown))
        return list(dict.fromkeys(normalized))

    @field_validator("authority_effect")
    @classmethod
    def zero_authority_only(cls, value: str) -> str:
        if value != "none":
            raise ValueError("impact-scope interpretation cannot change authority")
        return value

    @field_validator("automatic_execution")
    @classmethod
    def no_auto_execution(cls, value: bool) -> bool:
        if value:
            raise ValueError("impact-scope interpretation cannot execute actions")
        return value


def _extract_json_object(text: str) -> Dict[str, Any]:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, Mapping):
        raise SemanticImpactScopeError("impact scope response must be a JSON object")
    return dict(parsed)


def parse_impact_scope_proposal(value: Mapping[str, Any] | str) -> SemanticImpactScope:
    body = _extract_json_object(value) if isinstance(value, str) else dict(value)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("status", "model_proposed")
    body.setdefault("source", "model_proposed")
    body.setdefault("authority_effect", "none")
    body.setdefault("automatic_execution", False)
    try:
        return SemanticImpactScope.model_validate(body)
    except ValidationError as exc:
        raise SemanticImpactScopeError(str(exc)) from exc


def unresolved_impact_scope(reason: str, questions: Sequence[str] | None = None) -> SemanticImpactScope:
    unresolved = [str(row).strip() for row in list(questions or []) if str(row).strip()]
    if not unresolved and str(reason or "").strip():
        unresolved = [str(reason).strip()]
    return SemanticImpactScope(
        status="unresolved",
        domains=[],
        reasoning=str(reason or "Impact scope remains unresolved."),
        confidence=0.0,
        unresolved_questions=unresolved,
        source="unresolved",
        authority_effect="none",
        automatic_execution=False,
    )


def impact_scope_prompt(
    trigger_statements: Sequence[str],
    *,
    mode: str,
    topology_summary: Mapping[str, Any] | None = None,
    subsystem_summary: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    return f"""Propose which engineering domains require change-impact review.

Project change mode:
{mode}

Persisted change/failure/observation statements:
{json.dumps([str(row) for row in trigger_statements], ensure_ascii=False, indent=2)}

Bounded topology summary (context only, not authority):
{json.dumps(dict(topology_summary or {}), ensure_ascii=False, sort_keys=True, indent=2)}

Bounded subsystem summary (context only, not authority):
{json.dumps([dict(row) for row in list(subsystem_summary or [])], ensure_ascii=False, sort_keys=True, indent=2)}

Allowed domains:
{json.dumps(list(ALLOWED_IMPACT_DOMAINS))}

Return JSON only:
{{
  "status": "model_proposed or unresolved",
  "domains": ["zero or more allowed domains"],
  "reasoning": "why these domains need review, without choosing object IDs",
  "confidence": 0.0,
  "unresolved_questions": [],
  "source": "model_proposed",
  "authority_effect": "none",
  "automatic_execution": false
}}

Rules:
- Use only domain names from the supplied allowed list.
- Do not choose component, subsystem, link, joint, source, evidence, artifact, or test IDs.
- Do not invent electrical values, mechanical dimensions, firmware behavior, or source facts.
- Do not decide pass/fail, release readiness, fabrication, flashing, power, motion, or operational authority.
- If the statements are insufficient to identify a domain beyond generic system/verification review, return status unresolved and explain what is missing.
- Domain selection is proposal-only; deterministic policy may add conservative review domains.
"""


def interpret_impact_scope(
    trigger_statements: Sequence[str],
    *,
    mode: str,
    topology_summary: Mapping[str, Any] | None = None,
    subsystem_summary: Sequence[Mapping[str, Any]] | None = None,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> SemanticImpactScope:
    prompt = impact_scope_prompt(
        trigger_statements,
        mode=mode,
        topology_summary=topology_summary,
        subsystem_summary=subsystem_summary,
    )
    if llm_callable is None:
        from .integrations.qwen_text_client import call_qwen_chat

        response = call_qwen_chat(
            prompt,
            json_mode=True,
            stage="semantic_impact_scope",
            system="Return bounded change-impact domains only; no object IDs, authority, or execution.",
            timeout_s=60,
        )
    else:
        response = llm_callable(
            prompt,
            json_mode=True,
            stage="semantic_impact_scope",
            system="Return bounded change-impact domains only; no object IDs, authority, or execution.",
            timeout_s=60,
        )
    if not response.get("ok"):
        raise SemanticImpactScopeError(
            str(response.get("error") or response.get("reason") or "impact-scope provider failed")
        )
    return parse_impact_scope_proposal(str(response.get("content") or "{}"))

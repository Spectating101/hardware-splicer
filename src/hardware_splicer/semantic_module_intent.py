"""Typed semantic intent between natural-language goals and module catalog selection.

This layer intentionally cannot choose concrete module IDs. A model may state required
capabilities, constraints, assumptions, and unresolved questions using the capability
vocabulary exposed by the live module catalog. Deterministic code then resolves catalog
candidates for those capability groups. Concrete architecture selection remains a later
proposal/review step.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .pcb.module_registry import find_modules_by_capabilities, list_canvas_modules


SCHEMA_VERSION = "hardware_splicer.semantic_module_intent.v1"


class SemanticIntentError(ValueError):
    """Raised when semantic interpretation violates the typed capability contract."""


class IntentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilityRequirement(IntentModel):
    requirement_id: str = Field(min_length=1, max_length=120)
    any_of: list[str] = Field(min_length=1, max_length=12)
    required: bool = True
    rationale: str = Field(default="", max_length=1_000)

    @field_validator("any_of")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        tags = [str(row).strip() for row in value if str(row).strip()]
        if not tags:
            raise ValueError("capability requirement must contain at least one tag")
        return list(dict.fromkeys(tags))


class SemanticModuleIntent(IntentModel):
    schema_version: str = SCHEMA_VERSION
    goal_summary: str = Field(min_length=1, max_length=4_000)
    capability_requirements: list[CapabilityRequirement] = Field(default_factory=list, max_length=24)
    explicit_constraints: Dict[str, Any] = Field(default_factory=dict)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=24)
    assumptions: list[str] = Field(default_factory=list, max_length=24)
    authority_effect: str = "none"

    @field_validator("authority_effect")
    @classmethod
    def zero_authority_only(cls, value: str) -> str:
        if value != "none":
            raise ValueError("semantic intent cannot change engineering authority")
        return value


class SemanticCandidateSet(IntentModel):
    schema_version: str = "hardware_splicer.semantic_candidate_set.v1"
    intent: SemanticModuleIntent
    capability_vocabulary: list[str]
    candidates_by_requirement: Dict[str, list[Dict[str, Any]]]
    unresolved_requirements: list[str]
    authority_effect: str = "none"


def capability_vocabulary() -> list[str]:
    tags: set[str] = set()
    for module in list_canvas_modules():
        tags.update(str(tag).strip() for tag in (module.get("capabilityTags") or []) if str(tag).strip())
    return sorted(tags)


def _extract_json_object(text: str) -> Dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, Mapping):
        raise SemanticIntentError("semantic intent response must be a JSON object")
    return dict(parsed)


def parse_semantic_module_intent(
    value: Mapping[str, Any] | str,
    *,
    allowed_capabilities: list[str] | None = None,
) -> SemanticModuleIntent:
    body = _extract_json_object(value) if isinstance(value, str) else dict(value)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("authority_effect", "none")
    try:
        intent = SemanticModuleIntent.model_validate(body)
    except ValidationError as exc:
        raise SemanticIntentError(str(exc)) from exc

    allowed = set(allowed_capabilities or capability_vocabulary())
    unknown = sorted(
        {
            tag
            for requirement in intent.capability_requirements
            for tag in requirement.any_of
            if tag not in allowed
        }
    )
    if unknown:
        raise SemanticIntentError(
            "semantic intent referenced unknown catalog capabilities: " + ", ".join(unknown)
        )
    return intent


def semantic_intent_prompt(goal: str, constraints: Mapping[str, Any] | None = None) -> str:
    vocabulary = capability_vocabulary()
    return f"""Interpret this hardware goal into typed capability requirements.

Goal:
{goal.strip()}

Explicit caller constraints:
{json.dumps(dict(constraints or {}), sort_keys=True, indent=2)}

Allowed capability tags:
{json.dumps(vocabulary)}

Return JSON only:
{{
  "goal_summary": "concise engineering interpretation without choosing products",
  "capability_requirements": [
    {{
      "requirement_id": "stable-id",
      "any_of": ["one_or_more_allowed_capability_tags"],
      "required": true,
      "rationale": "why this capability is required"
    }}
  ],
  "explicit_constraints": {{}},
  "unresolved_questions": [],
  "assumptions": [],
  "authority_effect": "none"
}}

Rules:
- Use only capability tags from the supplied vocabulary.
- Do not choose, mention, infer, or invent module IDs, part numbers, brands, or catalog products.
- Preserve explicit constraints; do not turn vague prose into voltage/current values.
- Put missing engineering facts in unresolved_questions instead of guessing them.
- Capability interpretation has zero physical/fabrication/firmware authority.
"""


def interpret_semantic_module_intent(
    goal: str,
    *,
    constraints: Mapping[str, Any] | None = None,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> SemanticModuleIntent:
    if not goal.strip():
        raise SemanticIntentError("goal is required")
    prompt = semantic_intent_prompt(goal, constraints)

    if llm_callable is None:
        from .integrations.qwen_text_client import call_qwen_chat

        response = call_qwen_chat(
            prompt,
            json_mode=True,
            stage="semantic_module_intent",
            system="Return typed engineering capability requirements only; never choose catalog products.",
            timeout_s=60,
        )
    else:
        response = llm_callable(
            prompt,
            json_mode=True,
            stage="semantic_module_intent",
            system="Return typed engineering capability requirements only; never choose catalog products.",
            timeout_s=60,
        )

    if not response.get("ok"):
        raise SemanticIntentError(
            str(response.get("error") or response.get("reason") or "semantic intent provider failed")
        )
    return parse_semantic_module_intent(str(response.get("content") or "{}"))


def candidate_modules_for_intent(intent: SemanticModuleIntent) -> SemanticCandidateSet:
    vocabulary = capability_vocabulary()
    candidates: Dict[str, list[Dict[str, Any]]] = {}
    unresolved: list[str] = []

    for requirement in intent.capability_requirements:
        rows = find_modules_by_capabilities([requirement.any_of])
        projected = [
            {
                "module_id": str(row.get("id") or ""),
                "label": str(row.get("label") or row.get("id") or ""),
                "capability_tags": list(row.get("capabilityTags") or []),
                "category": row.get("category"),
            }
            for row in rows
            if row.get("id")
        ]
        candidates[requirement.requirement_id] = projected
        if requirement.required and not projected:
            unresolved.append(requirement.requirement_id)

    return SemanticCandidateSet(
        intent=intent,
        capability_vocabulary=vocabulary,
        candidates_by_requirement=candidates,
        unresolved_requirements=unresolved,
        authority_effect="none",
    )

"""Concrete module proposal over a validated semantic capability intent.

Stage 1 (semantic_module_intent) is blind to module IDs. Stage 2 receives only the
candidate modules returned by deterministic capability queries and may propose a
subset. Selected IDs are validated against that candidate universe before returning.
No compose/build/physical authority is granted by this module.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .semantic_module_intent import (
    SemanticCandidateSet,
    SemanticIntentError,
    SemanticModuleIntent,
    candidate_modules_for_intent,
    interpret_semantic_module_intent,
)


SCHEMA_VERSION = "hardware_splicer.semantic_module_selection.v1"


class SemanticSelectionError(ValueError):
    pass


class SelectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SemanticModuleSelection(SelectionModel):
    schema_version: str = SCHEMA_VERSION
    selected_module_ids: list[str] = Field(default_factory=list, max_length=12)
    requirement_coverage: Dict[str, list[str]] = Field(default_factory=dict)
    rationale: str = Field(default="", max_length=4_000)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=24)
    assumptions: list[str] = Field(default_factory=list, max_length=24)
    authority_effect: str = "none"
    automatic_execution: bool = False

    @field_validator("selected_module_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        rows = [str(row).strip() for row in value if str(row).strip()]
        return list(dict.fromkeys(rows))

    @field_validator("authority_effect")
    @classmethod
    def zero_authority_only(cls, value: str) -> str:
        if value != "none":
            raise ValueError("module selection proposal cannot change engineering authority")
        return value

    @field_validator("automatic_execution")
    @classmethod
    def no_automatic_execution(cls, value: bool) -> bool:
        if value:
            raise ValueError("semantic module selection cannot execute automatically")
        return False


class SemanticSelectionTrace(SelectionModel):
    schema_version: str = "hardware_splicer.semantic_module_selection_trace.v1"
    intent: SemanticModuleIntent
    candidate_set: SemanticCandidateSet
    selection: SemanticModuleSelection
    authority_effect: str = "none"
    automatic_execution: bool = False


def _extract_json_object(text: str) -> Dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, Mapping):
        raise SemanticSelectionError("module selection response must be a JSON object")
    return dict(parsed)


def _candidate_universe(candidate_set: SemanticCandidateSet) -> set[str]:
    return {
        str(row.get("module_id") or "")
        for rows in candidate_set.candidates_by_requirement.values()
        for row in rows
        if row.get("module_id")
    }


def semantic_selection_prompt(candidate_set: SemanticCandidateSet) -> str:
    candidate_payload = {
        requirement_id: [
            {
                "module_id": row.get("module_id"),
                "label": row.get("label"),
                "capability_tags": row.get("capability_tags"),
                "category": row.get("category"),
            }
            for row in rows
        ]
        for requirement_id, rows in candidate_set.candidates_by_requirement.items()
    }
    return f"""Compare catalog candidates for this already-validated hardware intent.

Semantic intent:
{json.dumps(candidate_set.intent.model_dump(mode='json'), sort_keys=True, indent=2)}

Deterministically resolved candidates by requirement:
{json.dumps(candidate_payload, sort_keys=True, indent=2)}

Return JSON only:
{{
  "selected_module_ids": ["candidate-id"],
  "requirement_coverage": {{"requirement-id": ["candidate-id"]}},
  "rationale": "comparison based only on supplied intent/candidate metadata",
  "unresolved_questions": [],
  "assumptions": [],
  "authority_effect": "none",
  "automatic_execution": false
}}

Rules:
- Select only module_id values shown in the deterministic candidate lists above.
- Do not invent electrical ratings, interfaces, compatibility, or evidence not shown.
- If the intent lacks a fact required to choose safely, leave it unresolved instead of guessing.
- Every selected module must cover at least one stated capability requirement.
- This is a proposal only: no build, fabrication, flashing, power, or motion authority.
"""


def parse_semantic_module_selection(
    value: Mapping[str, Any] | str,
    *,
    candidate_set: SemanticCandidateSet,
) -> SemanticModuleSelection:
    body = _extract_json_object(value) if isinstance(value, str) else dict(value)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("authority_effect", "none")
    body.setdefault("automatic_execution", False)
    try:
        selection = SemanticModuleSelection.model_validate(body)
    except ValidationError as exc:
        raise SemanticSelectionError(str(exc)) from exc

    universe = _candidate_universe(candidate_set)
    invented = sorted(set(selection.selected_module_ids) - universe)
    if invented:
        raise SemanticSelectionError(
            "selection referenced module IDs outside deterministic candidate set: " + ", ".join(invented)
        )

    requirements = set(candidate_set.candidates_by_requirement)
    unknown_requirements = sorted(set(selection.requirement_coverage) - requirements)
    if unknown_requirements:
        raise SemanticSelectionError(
            "selection referenced unknown requirement IDs: " + ", ".join(unknown_requirements)
        )
    for requirement_id, module_ids in selection.requirement_coverage.items():
        allowed = {
            str(row.get("module_id") or "")
            for row in candidate_set.candidates_by_requirement.get(requirement_id, [])
            if row.get("module_id")
        }
        invalid = sorted(set(module_ids) - allowed)
        if invalid:
            raise SemanticSelectionError(
                f"requirement {requirement_id!r} coverage contains non-candidates: " + ", ".join(invalid)
            )

    covered = {
        module_id
        for module_ids in selection.requirement_coverage.values()
        for module_id in module_ids
    }
    ungrounded = sorted(set(selection.selected_module_ids) - covered)
    if ungrounded:
        raise SemanticSelectionError(
            "selected modules are not linked to any capability requirement: " + ", ".join(ungrounded)
        )
    return selection


def select_modules_from_semantic_intent(
    intent: SemanticModuleIntent,
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> SemanticSelectionTrace:
    candidate_set = candidate_modules_for_intent(intent)
    if candidate_set.unresolved_requirements:
        return SemanticSelectionTrace(
            intent=intent,
            candidate_set=candidate_set,
            selection=SemanticModuleSelection(
                selected_module_ids=[],
                requirement_coverage={},
                rationale="No concrete selection: at least one required capability has no catalog candidate.",
                unresolved_questions=[
                    f"No catalog candidate satisfies capability requirement {row!r}."
                    for row in candidate_set.unresolved_requirements
                ],
                authority_effect="none",
                automatic_execution=False,
            ),
            authority_effect="none",
            automatic_execution=False,
        )

    prompt = semantic_selection_prompt(candidate_set)
    if llm_callable is None:
        from .integrations.qwen_text_client import call_qwen_chat

        response = call_qwen_chat(
            prompt,
            json_mode=True,
            stage="semantic_module_selection",
            system="Compare only supplied deterministic candidates; output a proposal with zero authority.",
            timeout_s=60,
        )
    else:
        response = llm_callable(
            prompt,
            json_mode=True,
            stage="semantic_module_selection",
            system="Compare only supplied deterministic candidates; output a proposal with zero authority.",
            timeout_s=60,
        )
    if not response.get("ok"):
        raise SemanticSelectionError(
            str(response.get("error") or response.get("reason") or "module selection provider failed")
        )
    selection = parse_semantic_module_selection(
        str(response.get("content") or "{}"),
        candidate_set=candidate_set,
    )
    return SemanticSelectionTrace(
        intent=intent,
        candidate_set=candidate_set,
        selection=selection,
        authority_effect="none",
        automatic_execution=False,
    )


def semantic_module_selection_pipeline(
    goal: str,
    *,
    constraints: Mapping[str, Any] | None = None,
    intent_llm_callable: Callable[..., Dict[str, Any]] | None = None,
    selection_llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> SemanticSelectionTrace:
    try:
        intent = interpret_semantic_module_intent(
            goal,
            constraints=constraints,
            llm_callable=intent_llm_callable,
        )
    except SemanticIntentError as exc:
        raise SemanticSelectionError(str(exc)) from exc
    return select_modules_from_semantic_intent(intent, llm_callable=selection_llm_callable)

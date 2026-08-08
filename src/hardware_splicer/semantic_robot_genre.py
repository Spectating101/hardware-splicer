"""Typed semantic proposal for robot/mechatronic topology genre.

Robot genre determines which deterministic topology builder is allowed to run, so it is
an architectural proposal rather than a harmless label. This module lets a model choose
from a bounded vocabulary without inventing topology details, component IDs, or physical
authority. Deterministic topology construction and reference validation remain elsewhere.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SCHEMA_VERSION = "hardware_splicer.semantic_robot_genre.v1"
ALLOWED_ROBOT_GENRES = (
    "rover",
    "robotic_arm",
    "quadruped",
    "aerial_robot",
    "pan_tilt",
    "gripper",
    "mobile_manipulator",
    "generic_mechatronics",
)


class SemanticRobotGenreError(ValueError):
    """Raised when a model violates the bounded robot-genre proposal contract."""


class GenreModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RobotGenreProposal(GenreModel):
    schema_version: str = SCHEMA_VERSION
    status: str = "model_proposed"
    genre: str
    reasoning: str = Field(default="", max_length=4_000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=24)
    source: str = "model_proposed"
    authority_effect: str = "none"
    automatic_execution: bool = False

    @field_validator("genre")
    @classmethod
    def bounded_genre(cls, value: str) -> str:
        normalized = str(value).strip().lower().replace("-", "_")
        aliases = {
            "serial_manipulator": "robotic_arm",
            "manipulator": "robotic_arm",
            "aerial": "aerial_robot",
            "drone": "aerial_robot",
            "quadcopter": "aerial_robot",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in ALLOWED_ROBOT_GENRES:
            raise ValueError(f"unsupported robot genre: {value!r}")
        return normalized

    @field_validator("authority_effect")
    @classmethod
    def zero_authority_only(cls, value: str) -> str:
        if value != "none":
            raise ValueError("robot genre proposal cannot change engineering authority")
        return value

    @field_validator("automatic_execution")
    @classmethod
    def no_auto_execution(cls, value: bool) -> bool:
        if value:
            raise ValueError("robot genre proposal cannot execute topology automatically")
        return False


def _extract_json_object(text: str) -> Dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, Mapping):
        raise SemanticRobotGenreError("robot genre response must be one JSON object")
    return dict(parsed)


def parse_robot_genre_proposal(value: Mapping[str, Any] | str) -> RobotGenreProposal:
    body = _extract_json_object(value) if isinstance(value, str) else dict(value)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("status", "model_proposed")
    body.setdefault("source", "model_proposed")
    body.setdefault("authority_effect", "none")
    body.setdefault("automatic_execution", False)
    try:
        return RobotGenreProposal.model_validate(body)
    except ValidationError as exc:
        raise SemanticRobotGenreError(str(exc)) from exc


def robot_genre_prompt(
    goal: str,
    parts: Sequence[Mapping[str, Any]] | None = None,
    constraints: Mapping[str, Any] | None = None,
) -> str:
    projected_parts = [
        {
            "name": row.get("name"),
            "type": row.get("type"),
            "role": row.get("role"),
            "quantity": row.get("quantity"),
        }
        for row in list(parts or [])[:64]
    ]
    return f"""Classify the requested machine into one bounded topology genre.

Engineering goal:
{goal.strip()}

Declared/parsed parts:
{json.dumps(projected_parts, indent=2, sort_keys=True)}

Explicit structured constraints:
{json.dumps(dict(constraints or {}), indent=2, sort_keys=True)}

Allowed genres:
{json.dumps(list(ALLOWED_ROBOT_GENRES))}

Return JSON only:
{{
  "genre": "one allowed genre",
  "reasoning": "brief engineering-function justification",
  "confidence": 0.0,
  "unresolved_questions": [],
  "authority_effect": "none",
  "automatic_execution": false
}}

Rules:
- Choose only from the supplied genre vocabulary.
- Infer the machine class, not detailed joints, axes, dimensions, pinouts, or components.
- Do not invent mechanical, electrical, firmware, or physical evidence.
- If the evidence is insufficient to distinguish a specialized topology, choose generic_mechatronics and list what is unresolved.
- This is a proposal only; it grants no fabrication, flashing, power, motion, operation, or release authority.
"""


def interpret_robot_genre(
    goal: str,
    *,
    parts: Sequence[Mapping[str, Any]] | None = None,
    constraints: Mapping[str, Any] | None = None,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> RobotGenreProposal:
    if not goal.strip():
        raise SemanticRobotGenreError("goal is required")
    prompt = robot_genre_prompt(goal, parts, constraints)

    if llm_callable is None:
        from .integrations.qwen_text_client import call_qwen_chat

        response = call_qwen_chat(
            prompt,
            json_mode=True,
            stage="semantic_robot_genre",
            system="Return one bounded robot topology genre only; do not invent topology details.",
            timeout_s=60,
        )
    else:
        response = llm_callable(
            prompt,
            json_mode=True,
            stage="semantic_robot_genre",
            system="Return one bounded robot topology genre only; do not invent topology details.",
            timeout_s=60,
        )

    if not response.get("ok"):
        raise SemanticRobotGenreError(
            str(response.get("error") or response.get("reason") or "robot genre provider failed")
        )
    return parse_robot_genre_proposal(str(response.get("content") or "{}"))


def unresolved_robot_genre_proposal(reason: str) -> RobotGenreProposal:
    message = str(reason or "Robot topology genre could not be resolved from available evidence.").strip()
    return RobotGenreProposal(
        status="unresolved",
        genre="generic_mechatronics",
        reasoning=message,
        confidence=0.0,
        unresolved_questions=[message],
        source="unresolved",
        authority_effect="none",
        automatic_execution=False,
    )

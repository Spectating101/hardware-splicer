"""Lightweight pre-flight clarifications for vague hardware intents.

Clarification answers are user-declared observations, not engineering truth. This
module deliberately does not translate prose into voltage/current defaults, component
IDs, load classes, or other semantic conclusions. Those interpretations belong in an
explicit proposal step and remain subject to evidence and deterministic verification.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping

SCHEMA_VERSION = "hardware_splicer.intent_clarifier.v2"

_DEFAULT_QUESTIONS = (
    {
        "id": "power_source",
        "prompt": "What is the primary power source (e.g. USB 5V, 12V barrel, battery)?",
        "maps_to": "declared_power_source",
    },
    {
        "id": "controller",
        "prompt": "Which controller should drive logic (e.g. ESP32, Arduino Nano, Pico)?",
        "maps_to": "declared_controller",
    },
    {
        "id": "load_type",
        "prompt": "What load or function are you driving (motor, pump, sensor bus, relay)?",
        "maps_to": "declared_load",
    },
    {
        "id": "donor_context",
        "prompt": "Are you reusing donor hardware (junk board photo/fixture) or building greenfield?",
        "maps_to": "declared_donor_context",
    },
)


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return [str(item).strip() for item in value if str(item).strip()]


def _needs_clarification(intent: Mapping[str, Any]) -> bool:
    goal = str(intent.get("goal") or intent.get("project_name") or "").strip()
    if len(goal) < 8:
        return True
    has_supply = bool(intent.get("supply_rails") or intent.get("power_topology"))
    has_load = bool(intent.get("load_requirements") or intent.get("available_parts"))
    has_splice = bool(intent.get("circuit") or intent.get("donor_context") or intent.get("salvage_mode"))
    has_modules = bool(intent.get("allowed_modules") or intent.get("module_ids"))
    vague_tokens = ("something", "gadget", "device", "project", "board", "hardware")
    goal_lower = goal.lower()
    if any(token in goal_lower for token in vague_tokens) and not (has_supply and (has_load or has_modules)):
        return True
    return not (has_supply or has_load or has_splice or has_modules)


def _slim_intent_for_package(intent: Mapping[str, Any]) -> Dict[str, Any]:
    """Keep clarifier payloads small — never echo nested salvage/scenario graphs."""
    body = dict(intent)
    keep_keys = (
        "goal",
        "project_name",
        "salvage_mode",
        "available_parts",
        "constraints",
        "supply_rails",
        "allowed_modules",
        "load_requirements",
        "module_ids",
        "clarification_answers",
        "clarification_observations",
    )
    slim = {key: body[key] for key in keep_keys if key in body and body[key] is not None}
    if "goal" not in slim and body.get("goal"):
        slim["goal"] = body.get("goal")
    return slim


def analyze_intent_clarifications(intent: Mapping[str, Any]) -> Dict[str, Any]:
    """Return clarifying questions and declared observations without semantic guessing."""
    body = _slim_intent_for_package(intent)
    answers = dict(body.get("clarification_answers") or {})
    needs = _needs_clarification(body)
    questions = [dict(row) for row in _DEFAULT_QUESTIONS] if needs and not answers else []
    enriched = apply_clarification_answers(body) if answers else body
    return {
        "schema_version": SCHEMA_VERSION,
        "needs_clarification": needs and not answers,
        "semantic_interpretation_required": bool(answers),
        "questions": questions,
        "clarification_answers": answers,
        "enriched_intent": _slim_intent_for_package(enriched),
        "notes": (
            "Answer clarification_answers before planning when needs_clarification is true."
            if needs and not answers
            else (
                "Clarification answers are recorded as declared observations; any engineering "
                "interpretation remains proposal-only until evidence and deterministic checks support it."
                if answers
                else "Intent already contains explicit structured engineering information."
            )
        ),
    }


def apply_clarification_answers(intent: Mapping[str, Any]) -> Dict[str, Any]:
    """Record user answers without converting prose into invented engineering facts.

    Older behavior guessed values such as a 7.4 V battery rail, a 5 V / 0.5 A motor
    load, or a particular ESP32 catalog module from broad answer text. Those guesses
    looked like structured evidence downstream. The v2 contract keeps the literal
    declarations and requires a separate semantic proposal/verification step.
    """

    body = deepcopy(dict(intent))
    answers = dict(body.pop("clarification_answers", None) or {})
    observations: list[Dict[str, Any]] = []
    question_by_id = {str(row["id"]): row for row in _DEFAULT_QUESTIONS}

    for raw_id, raw_answer in answers.items():
        question_id = str(raw_id).strip()
        answer = str(raw_answer or "").strip()
        if not question_id or not answer:
            continue
        question = question_by_id.get(question_id, {})
        observations.append(
            {
                "question_id": question_id,
                "answer": answer,
                "maps_to": str(question.get("maps_to") or "declared_requirement"),
                "authority": "declared",
                "interpretation_status": "unresolved",
            }
        )

    if observations:
        existing = [
            dict(row)
            for row in list(body.get("clarification_observations") or [])
            if isinstance(row, Mapping)
        ]
        by_id = {str(row.get("question_id") or ""): row for row in existing}
        for row in observations:
            by_id[str(row["question_id"])] = row
        body["clarification_observations"] = [
            by_id[key] for key in sorted(by_id) if key
        ]

    return body

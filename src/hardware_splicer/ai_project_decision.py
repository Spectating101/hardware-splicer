"""Cheap bounded decision layer over proposal-only Hardware Splicer AI sessions.

The existing project orchestrator remains System-2: it interprets language, engineering
context and source evidence into schema-shaped proposals. This module lets Jev choose
among those bounded proposals without granting execution or physical authority.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_JEV_MODEL = "jev-latest"

REVIEW_CRITERIA = {
    "accept": "The proposed action is grounded in the supplied project state, stays within proposal-only authority, and is appropriate as the next engineering step.",
    "revise": "The proposed action is useful but needs a repairable change to assumptions, inputs, evidence, scope, or wording before it should proceed.",
    "reject": "The proposed action is unsupported, conflicts with supplied evidence/constraints, duplicates completed work, or should not proceed.",
    "escalate": "The decision is materially ambiguous or consequential and needs another System-2 engineering review.",
}


@dataclass(frozen=True)
class ProjectDecision:
    choice: str
    confidence: float
    probabilities: dict[str, float]
    status: str
    selected_action: dict[str, Any] | None = None
    reason: str | None = None


def _clamp01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _confidence(answer: Mapping[str, Any]) -> float:
    if answer.get("confidence") is not None:
        return _clamp01(answer.get("confidence"))
    probs = answer.get("probabilities")
    if isinstance(probs, Mapping):
        return max((_clamp01(v) for v in probs.values()), default=0.0)
    return 0.0


def _http_transport(payload: dict[str, Any], *, api_key: str, endpoint: str, timeout: float) -> dict[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured HTTPS API endpoint
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Jev request failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Jev request failed: {exc.reason}") from exc


def _call_choice(
    *,
    state: Mapping[str, Any],
    instructions: str,
    criteria: Mapping[str, str],
    api_key: str | None = None,
    endpoint: str | None = None,
    model: str | None = None,
    timeout: float = 12.0,
    transport: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    key = (api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")).strip()
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY is not configured")
    endpoint = endpoint or os.environ.get("TYPESAFE_API_URL") or DEFAULT_JEV_ENDPOINT
    model = model or os.environ.get("TYPESAFE_MODEL") or DEFAULT_JEV_MODEL
    payload = {
        "model": model,
        "state": dict(state),
        "questions": {
            "decision": {
                "type": "choice",
                "instructions": instructions,
                "criteria": dict(criteria),
            }
        },
    }
    body = (transport or _http_transport)(payload, api_key=key, endpoint=endpoint, timeout=timeout)
    answer = (body.get("answers") or {}).get("decision")
    if not isinstance(answer, Mapping) or not isinstance(answer.get("choice"), str):
        raise RuntimeError("Jev response did not contain answers.decision.choice")
    choice = str(answer["choice"])
    if choice not in criteria:
        raise RuntimeError(f"Jev returned out-of-contract choice: {choice}")
    probabilities = answer.get("probabilities")
    return {
        "choice": choice,
        "confidence": _confidence(answer),
        "probabilities": dict(probabilities) if isinstance(probabilities, Mapping) else {},
    }


def _session_state(session: Mapping[str, Any]) -> dict[str, Any]:
    """Keep Jev state bounded to the already-sanitized proposal session."""
    return {
        "mission": session.get("mission") or "",
        "constraints": session.get("constraints") or {},
        "requirements": list(session.get("requirements") or [])[:64],
        "open_questions": list(session.get("open_questions") or [])[:64],
        "architecture_candidates": list(session.get("architecture_candidates") or [])[:3],
        "engineering_summary": session.get("summary") or "",
        "authority": {
            "automatic_execution": False,
            "physical_authority_unchanged": True,
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "operational_authorized": False,
            "release_authorized": False,
        },
    }


def select_next_proposed_action(
    session: Mapping[str, Any],
    *,
    min_confidence: float = 0.85,
    **jev_options: Any,
) -> ProjectDecision:
    """Select the best *proposed* next action from an LLM-produced session.

    This returns advice only. It never executes an action, changes its `authority`, or
    bypasses the tool executor / physical safety gates.
    """
    actions: list[dict[str, Any]] = [
        dict(action)
        for action in list(session.get("actions") or [])
        if isinstance(action, Mapping) and action.get("action_id")
    ]
    if not actions:
        return ProjectDecision(
            choice="escalate",
            confidence=0.0,
            probabilities={},
            status="needs_supervisor",
            reason="no_proposed_actions",
        )

    criteria = {
        str(action["action_id"]): (
            f"Action type: {action.get('action_type')}. Title: {action.get('title')}. "
            f"Rationale: {action.get('rationale')}. This remains proposal-only and has no physical authority."
        )
        for action in actions
    }
    criteria["escalate"] = (
        "None of the proposed actions is sufficiently supported as the next step, or another System-2 engineering pass is needed."
    )
    state = _session_state(session)
    state["candidate_actions"] = [
        {
            "action_id": action.get("action_id"),
            "action_type": action.get("action_type"),
            "title": action.get("title"),
            "rationale": action.get("rationale"),
            "source_ids": list(action.get("source_ids") or []),
            "status": action.get("status"),
            "authority": action.get("authority"),
            "automatic_execution": False,
        }
        for action in actions
    ]

    try:
        answer = _call_choice(
            state=state,
            instructions=(
                "Choose the best next proposal-only engineering action. Prefer evidence-gathering or verification when prerequisites are missing. "
                "Never infer physical authority and choose escalate when the proposals are ambiguous or inadequately grounded."
            ),
            criteria=criteria,
            **jev_options,
        )
    except Exception as exc:
        return ProjectDecision(
            choice="escalate",
            confidence=0.0,
            probabilities={},
            status="needs_supervisor",
            reason=f"jev_unavailable:{exc}",
        )

    if answer["choice"] == "escalate" or answer["confidence"] < _clamp01(min_confidence):
        reason = "jev_requested_escalation" if answer["choice"] == "escalate" else "low_confidence"
        return ProjectDecision(
            choice=str(answer["choice"]),
            confidence=float(answer["confidence"]),
            probabilities=dict(answer["probabilities"]),
            status="needs_supervisor",
            reason=reason,
        )

    selected = next(action for action in actions if str(action["action_id"]) == answer["choice"])
    return ProjectDecision(
        choice=str(answer["choice"]),
        confidence=float(answer["confidence"]),
        probabilities=dict(answer["probabilities"]),
        status="selected_proposal",
        selected_action=selected,
    )


def review_proposed_action(
    session: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    min_confidence: float = 0.85,
    **jev_options: Any,
) -> ProjectDecision:
    state = _session_state(session)
    state["proposed_action"] = dict(action)
    try:
        answer = _call_choice(
            state=state,
            instructions=(
                "Review the proposed action against the supplied project state and proposal-only authority. "
                "Do not treat model output as verified evidence and do not grant execution or physical authority."
            ),
            criteria=REVIEW_CRITERIA,
            **jev_options,
        )
    except Exception as exc:
        return ProjectDecision("escalate", 0.0, {}, "needs_supervisor", reason=f"jev_unavailable:{exc}")

    status = "reviewed" if answer["confidence"] >= _clamp01(min_confidence) and answer["choice"] != "escalate" else "needs_supervisor"
    reason = None
    if answer["choice"] == "escalate":
        reason = "jev_requested_escalation"
    elif answer["confidence"] < _clamp01(min_confidence):
        reason = "low_confidence"
    return ProjectDecision(
        choice=str(answer["choice"]),
        confidence=float(answer["confidence"]),
        probabilities=dict(answer["probabilities"]),
        status=status,
        reason=reason,
    )

from __future__ import annotations

import json

import pytest

from hardware_splicer.ai_project_conversation import (
    InvalidConversationEvidence,
    build_ai_conversation_context,
    run_ai_project_conversation_turn,
)
from hardware_splicer.ai_project_orchestrator import InvalidAIProjectResponse


SESSION_ID = "ai-session-conversation123"
ACTION_ID = "action-compose123"


def _snapshot_and_session() -> tuple[dict, dict]:
    snapshot = {
        "projectId": "rover",
        "name": "Indoor rover",
        "engineeringSources": [
            {
                "source_id": "manual-1",
                "source_type": "manual",
                "content_hash": "sha256:manual",
                "authority_ceiling": "declared",
                "metadata": {"content": "SECRET RAW MANUAL"},
            }
        ],
        "engineeringParsedSources": [],
        "engineeringSourceParserRuns": [],
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }
    action = {
        "action_id": ACTION_ID,
        "session_id": SESSION_ID,
        "project_id": "rover",
        "project_revision": 1,
        "action_type": "run_compose",
        "title": "Compose rover controller",
        "rationale": "Validate the electrical candidate.",
        "status": "failed",
        "source_ids": ["manual-1"],
        "tool_result": {
            "status": "failed",
            "summary": {"error": "logic threshold unresolved"},
            "error": {"type": "RuntimeError", "message": "logic threshold unresolved"},
            "artifact": {
                "project_relative_path": "ai_tool_runs/result.json",
                "sha256": "a" * 64,
                "size_bytes": 500,
            },
            "automatic_execution": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
        "automatic_execution": False,
        "authority_effect": "none",
    }
    session = {
        "session_id": SESSION_ID,
        "project_id": "rover",
        "project_revision": 1,
        "mission": "Design an indoor inspection rover",
        "constraints": {"logic_voltage_v": 3.3},
        "summary": "Rover controller candidate.",
        "requirements": [
            {
                "id": "req-logic",
                "statement": "Logic rail is 3.3 V.",
                "source_ids": ["manual-1"],
            }
        ],
        "architecture_candidates": [
            {
                "id": "candidate-1",
                "title": "ESP32 rover",
                "summary": "ESP32 and motor driver.",
            }
        ],
        "open_questions": ["Confirm driver VIH."],
        "actions": [action],
        "conversationTurns": [
            {
                "turn_id": "ai-turn-prior",
                "project_revision": 1,
                "user_message": "What failed?",
                "assistant_answer": "The logic threshold is unresolved.",
                "evidence_refs": [
                    {"kind": "tool_result", "id": ACTION_ID, "reason": "Failure summary."}
                ],
                "blockers": ["Missing VIH threshold."],
            }
        ],
        "automatic_execution": False,
        "physical_authority_unchanged": True,
    }
    return snapshot, session


def _response(*, evidence_id: str = ACTION_ID, source_id: str = "manual-1", elevate: bool = False) -> str:
    payload = {
        "answer_kind": "decision_briefing",
        "answer": "The next defensible step is to revise the logic interface, then request a new compose preview.",
        "evidence_refs": [
            {
                "kind": "tool_result",
                "id": evidence_id,
                "reason": "The persisted preview reports an unresolved logic threshold.",
            },
            {
                "kind": "requirement",
                "id": "req-logic",
                "reason": "The project requirement fixes the logic rail at 3.3 V.",
            },
        ],
        "blockers": ["The exact driver VIH threshold is still missing."],
        "recommended_action": {
            "action_type": "revise_candidate",
            "title": "Revise the logic interface",
            "rationale": "Resolve the persisted threshold failure before another preview.",
            "inputs": {"target": "motor_driver_logic_interface"},
            "source_ids": [source_id],
        },
        "additional_proposals": [
            {
                "action_type": "identify_missing_evidence",
                "title": "Obtain the threshold table",
                "rationale": "The current source set does not prove VIH compatibility.",
                "inputs": {"needed": "driver input threshold table"},
                "source_ids": [source_id],
            }
        ],
    }
    if elevate:
        payload["power_on_authorized"] = True
    return json.dumps(payload)


def test_conversation_context_is_revision_bound_and_omits_raw_content() -> None:
    snapshot, session = _snapshot_and_session()
    context = build_ai_conversation_context(
        "rover",
        2,
        snapshot,
        session,
        user_message="What should we do next?",
    )

    encoded = json.dumps(context)
    assert "SECRET RAW MANUAL" not in encoded
    assert context["project_revision"] == 2
    assert ACTION_ID in context["evidence_registry"]["tool_result"]
    assert "manual-1" in context["evidence_registry"]["source"]
    assert context["conversation_policy"]["conversation_is_not_project_truth"] is True
    assert context["conversation_policy"]["automatic_execution"] is False
    assert context["conversation_policy"]["power_on_authorized"] is False


def test_conversation_turn_answers_with_evidence_and_typed_proposals() -> None:
    snapshot, session = _snapshot_and_session()
    calls: list[dict] = []

    def fake_llm(prompt: str, **kwargs: object) -> dict:
        calls.append({"prompt": prompt, **kwargs})
        return {
            "ok": True,
            "provider": "test",
            "model": "jarvis-test",
            "content": _response(),
            "usage": {"total_tokens": 200},
            "cached": False,
        }

    turn = run_ai_project_conversation_turn(
        "rover",
        2,
        snapshot,
        session,
        user_message="What should we do next?",
        client_request_id="request-1",
        llm_callable=fake_llm,
    )

    assert len(calls) == 1
    assert calls[0]["stage"] == "workshop"
    assert calls[0]["json_mode"] is True
    assert "SECRET RAW MANUAL" not in calls[0]["prompt"]
    assert turn["project_revision"] == 2
    assert turn["answer_kind"] == "decision_briefing"
    assert turn["evidence_refs"][0]["id"] == ACTION_ID
    assert turn["recommended_action_id"] == turn["proposed_actions"][0]["action_id"]
    assert len(turn["proposed_actions"]) == 2
    assert all(action["status"] == "proposed" for action in turn["proposed_actions"])
    assert all(action["origin_turn_id"] == turn["turn_id"] for action in turn["proposed_actions"])
    assert all(action["tool_result"] is None for action in turn["proposed_actions"])
    assert all(action["automatic_execution"] is False for action in turn["proposed_actions"])
    assert turn["power_on_authorized"] is False
    assert turn["motion_authorized"] is False
    assert turn["release_authorized"] is False


def test_conversation_rejects_unknown_evidence_and_invented_sources() -> None:
    snapshot, session = _snapshot_and_session()

    def unknown_evidence(*_args: object, **_kwargs: object) -> dict:
        return {"ok": True, "provider": "test", "model": "bad", "content": _response(evidence_id="unknown-action")}

    with pytest.raises(InvalidConversationEvidence, match="unknown"):
        run_ai_project_conversation_turn(
            "rover",
            2,
            snapshot,
            session,
            user_message="What next?",
            llm_callable=unknown_evidence,
        )

    def invented_source(*_args: object, **_kwargs: object) -> dict:
        return {"ok": True, "provider": "test", "model": "bad", "content": _response(source_id="invented-source")}

    with pytest.raises(InvalidConversationEvidence, match="unknown source"):
        run_ai_project_conversation_turn(
            "rover",
            2,
            snapshot,
            session,
            user_message="What next?",
            llm_callable=invented_source,
        )


def test_conversation_rejects_authority_elevation_and_missing_evidence() -> None:
    snapshot, session = _snapshot_and_session()

    def elevated(*_args: object, **_kwargs: object) -> dict:
        return {"ok": True, "provider": "test", "model": "unsafe", "content": _response(elevate=True)}

    with pytest.raises(InvalidAIProjectResponse):
        run_ai_project_conversation_turn(
            "rover",
            2,
            snapshot,
            session,
            user_message="Can I power it on?",
            llm_callable=elevated,
        )

    payload = json.loads(_response())
    payload["evidence_refs"] = []

    def no_evidence(*_args: object, **_kwargs: object) -> dict:
        return {"ok": True, "provider": "test", "model": "unsupported", "content": json.dumps(payload)}

    with pytest.raises(InvalidConversationEvidence, match="requires evidence_refs"):
        run_ai_project_conversation_turn(
            "rover",
            2,
            snapshot,
            session,
            user_message="What next?",
            llm_callable=no_evidence,
        )

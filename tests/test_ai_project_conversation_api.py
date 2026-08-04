from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.ai_project_conversation_api import (
    create_ai_project_conversation_router,
)
from hardware_splicer.project_store import ProjectStore


SESSION_ID = "ai-session-conversation123"
ACTION_ID = "action-compose123"


def _response(*, evidence_id: str = ACTION_ID) -> str:
    return json.dumps(
        {
            "answer_kind": "decision_briefing",
            "answer": "Revise the 3.3 V logic interface, then request another deterministic compose preview.",
            "evidence_refs": [
                {
                    "kind": "tool_result",
                    "id": evidence_id,
                    "reason": "The persisted compose preview failed on the unresolved logic threshold.",
                },
                {
                    "kind": "source",
                    "id": "manual-1",
                    "reason": "The registered manual is the declared source for the controller interface.",
                },
            ],
            "blockers": ["The exact motor-driver VIH threshold remains unavailable."],
            "recommended_action": {
                "action_type": "revise_candidate",
                "title": "Revise the logic interface",
                "rationale": "Resolve the persisted logic-threshold failure.",
                "inputs": {"target": "motor_driver_logic_interface"},
                "source_ids": ["manual-1"],
            },
            "additional_proposals": [],
        }
    )


def _snapshot() -> dict:
    action = {
        "action_id": ACTION_ID,
        "session_id": SESSION_ID,
        "project_id": "rover",
        "project_revision": 1,
        "action_type": "run_compose",
        "title": "Compose rover controller",
        "rationale": "Validate one electrical candidate.",
        "status": "failed",
        "source_ids": ["manual-1"],
        "tool_result": {
            "status": "failed",
            "summary": {"error": "logic threshold unresolved"},
            "error": {
                "type": "RuntimeError",
                "message": "logic threshold unresolved",
            },
            "artifact": {
                "project_relative_path": "ai_tool_runs/result.json",
                "sha256": "a" * 64,
                "size_bytes": 500,
            },
            "automatic_execution": False,
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "operational_authorized": False,
            "release_authorized": False,
        },
        "automatic_execution": False,
        "authority_effect": "none",
    }
    return {
        "projectId": "rover",
        "name": "Indoor rover",
        "engineeringSources": [
            {
                "source_id": "manual-1",
                "source_type": "manual",
                "content_hash": "sha256:manual",
                "authority_ceiling": "declared",
            }
        ],
        "engineeringParsedSources": [],
        "engineeringSourceParserRuns": [],
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
        "engineeringAiSessions": [
            {
                "session_id": SESSION_ID,
                "project_id": "rover",
                "project_revision": 1,
                "mission": "Design an indoor inspection rover",
                "constraints": {"logic_voltage_v": 3.3},
                "summary": "Rover controller candidate.",
                "requirements": [
                    {
                        "id": "req-logic",
                        "statement": "The logic rail is 3.3 V.",
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
                "conversationTurns": [],
                "automatic_execution": False,
                "physical_authority_unchanged": True,
            }
        ],
    }


def _client(
    tmp_path: Path,
    *,
    evidence_id: str = ACTION_ID,
) -> tuple[TestClient, ProjectStore, list[dict]]:
    store = ProjectStore(tmp_path / "projects")
    store.save("rover", _snapshot())
    calls: list[dict] = []

    def fake_llm(prompt: str, **kwargs: object) -> dict:
        calls.append({"prompt": prompt, **kwargs})
        return {
            "ok": True,
            "provider": "test",
            "model": "jarvis-test",
            "content": _response(evidence_id=evidence_id),
            "usage": {},
            "cached": False,
        }

    app = FastAPI()
    app.include_router(
        create_ai_project_conversation_router(store, llm_callable=fake_llm)
    )
    return TestClient(app), store, calls


def test_conversation_turn_persists_answer_and_typed_proposal(tmp_path: Path) -> None:
    client, store, calls = _client(tmp_path)

    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/turns",
        json={
            "expected_revision": 1,
            "message": "What should we do next?",
            "client_request_id": "request-1",
            "max_proposals": 2,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert body["idempotent"] is False
    assert body["turn"]["answer_kind"] == "decision_briefing"
    assert body["turn"]["evidence_refs"][0]["id"] == ACTION_ID
    assert body["turn"]["recommended_action_id"]
    assert body["automatic_execution"] is False
    assert body["authority_unchanged"] is True
    assert len(calls) == 1

    latest = store.load("rover")
    session = latest["snapshot"]["engineeringAiSessions"][0]
    assert len(session["conversationTurns"]) == 1
    assert session["conversationTurns"][0]["client_request_id"] == "request-1"
    assert len(session["actions"]) == 2
    original = session["actions"][0]
    proposed = session["actions"][1]
    assert original["status"] == "failed"
    assert original["tool_result"]["status"] == "failed"
    assert proposed["status"] == "proposed"
    assert proposed["origin_turn_id"] == session["conversationTurns"][0]["turn_id"]
    assert proposed["tool_result"] is None
    assert latest["snapshot"]["power_on_authorized"] is False
    assert latest["snapshot"]["motion_authorized"] is False
    assert latest["snapshot"]["release_authorized"] is False

    repeated = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/turns",
        json={
            "expected_revision": 2,
            "message": "What should we do next?",
            "client_request_id": "request-1",
            "max_proposals": 2,
        },
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["revision"] == 2
    assert repeated.json()["idempotent"] is True
    assert repeated.json()["turn"]["turn_id"] == body["turn"]["turn_id"]
    assert len(calls) == 1


def test_conversation_refuses_stale_revision_before_model_call(tmp_path: Path) -> None:
    client, store, calls = _client(tmp_path)
    store.save("rover", _snapshot(), expected_revision=1)

    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/turns",
        json={
            "expected_revision": 1,
            "message": "What should we do next?",
            "client_request_id": "request-stale",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "ai_conversation_revision_conflict"
    assert calls == []


def test_conversation_rejects_unknown_evidence_without_saving(tmp_path: Path) -> None:
    client, store, calls = _client(tmp_path, evidence_id="invented-action")

    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/turns",
        json={
            "expected_revision": 1,
            "message": "What should we do next?",
            "client_request_id": "request-bad-evidence",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"]["type"] == "invalid_ai_conversation_evidence"
    assert len(calls) == 1
    latest = store.load("rover")
    assert latest["revision"] == 1
    session = latest["snapshot"]["engineeringAiSessions"][0]
    assert session["conversationTurns"] == []
    assert len(session["actions"]) == 1


def test_conversation_schema_is_fail_closed(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path)

    response = client.get("/v1/engineering/ai/conversation/schema")

    assert response.status_code == 200
    body = response.json()
    assert "tool_result" in body["allowed_evidence_kinds"]
    assert body["project_changes_are_typed_proposals"] is True
    assert body["conversation_is_project_truth"] is False
    assert body["fresh_human_decision_required"] is True
    assert body["automatic_execution"] is False
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_authorized"] is False

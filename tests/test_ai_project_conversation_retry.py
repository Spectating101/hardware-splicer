from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.ai_project_conversation_api import (
    create_ai_project_conversation_router,
)
from hardware_splicer.project_store import ProjectStore


def test_same_client_request_replays_across_revision_advance(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    session_id = "ai-session-retry123"
    action_id = "action-existing123"
    store.save(
        "rover",
        {
            "projectId": "rover",
            "name": "Rover",
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
            "engineeringAiSessions": [
                {
                    "session_id": session_id,
                    "project_id": "rover",
                    "project_revision": 1,
                    "mission": "Design a rover",
                    "constraints": {},
                    "summary": "Candidate",
                    "requirements": [],
                    "architecture_candidates": [],
                    "open_questions": [],
                    "actions": [
                        {
                            "action_id": action_id,
                            "session_id": session_id,
                            "project_id": "rover",
                            "project_revision": 1,
                            "action_type": "run_compose",
                            "title": "Compose",
                            "rationale": "Preview",
                            "status": "completed",
                            "source_ids": ["manual-1"],
                            "tool_result": {
                                "status": "succeeded",
                                "summary": {"ok": True},
                                "artifact": {
                                    "project_relative_path": "result.json",
                                    "sha256": "a" * 64,
                                    "size_bytes": 10,
                                },
                            },
                        }
                    ],
                    "conversationTurns": [],
                    "automatic_execution": False,
                    "physical_authority_unchanged": True,
                }
            ],
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
    calls: list[str] = []

    def fake_llm(prompt: str, **_: object) -> dict:
        calls.append(prompt)
        return {
            "ok": True,
            "provider": "test",
            "model": "jarvis-test",
            "content": json.dumps(
                {
                    "answer_kind": "technical_answer",
                    "answer": "The software preview succeeded, but physical authority remains closed.",
                    "evidence_refs": [
                        {
                            "kind": "tool_result",
                            "id": action_id,
                            "reason": "The persisted preview result reports success.",
                        }
                    ],
                    "blockers": ["Physical evidence is still required."],
                    "recommended_action": None,
                    "additional_proposals": [],
                }
            ),
        }

    app = FastAPI()
    app.include_router(
        create_ai_project_conversation_router(store, llm_callable=fake_llm)
    )
    client = TestClient(app)
    payload = {
        "expected_revision": 1,
        "message": "Is it ready?",
        "client_request_id": "stable-client-request",
    }

    first = client.post(
        f"/v1/projects/rover/ai-sessions/{session_id}/turns",
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 2
    assert first.json()["idempotent"] is False

    retry = client.post(
        f"/v1/projects/rover/ai-sessions/{session_id}/turns",
        json=payload,
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["revision"] == 2
    assert retry.json()["idempotent"] is True
    assert retry.json()["turn"]["turn_id"] == first.json()["turn"]["turn_id"]
    assert len(calls) == 1

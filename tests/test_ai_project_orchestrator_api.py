from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.ai_project_orchestrator_api import (
    create_ai_project_orchestrator_router,
)
from hardware_splicer.project_store import ProjectStore


def _fake_llm(prompt: str, **kwargs: object) -> dict:
    assert "PROJECT_CONTEXT=" in prompt
    assert kwargs["json_mode"] is True
    return {
        "ok": True,
        "provider": "test-provider",
        "model": "test-model",
        "content": json.dumps(
            {
                "summary": "One bounded architecture candidate is ready for review.",
                "requirements": [
                    {
                        "id": "mission",
                        "statement": "Inspect an indoor corridor.",
                        "source_ids": [],
                        "assumptions": [],
                    }
                ],
                "open_questions": ["What is the available battery?"],
                "architecture_candidates": [
                    {
                        "id": "candidate-a",
                        "title": "Differential-drive rover",
                        "summary": "Use two encoded motors and a protected logic rail.",
                        "tradeoffs": ["Simple mechanics"],
                        "assumptions": ["Flat indoor floor"],
                        "source_ids": [],
                    }
                ],
                "actions": [
                    {
                        "action_type": "run_guided_plan",
                        "title": "Compile the guided project plan",
                        "rationale": "Deterministic planning should expose blockers.",
                        "inputs": {"candidate_id": "candidate-a"},
                        "source_ids": [],
                    }
                ],
            }
        ),
    }


def _client(tmp_path) -> tuple[TestClient, ProjectStore]:
    store = ProjectStore(tmp_path / "projects")
    store.save(
        "rover",
        {
            "projectId": "rover",
            "name": "Indoor rover",
            "engineeringSources": [],
            "fabrication_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
    app = FastAPI()
    app.include_router(
        create_ai_project_orchestrator_router(store, llm_callable=_fake_llm)
    )
    return TestClient(app), store


def test_create_get_and_decide_ai_action_without_execution(tmp_path) -> None:
    client, store = _client(tmp_path)

    created = client.post(
        "/v1/projects/rover/ai-sessions",
        json={
            "mission": "Design an indoor inspection rover",
            "expected_revision": 1,
            "model_profile": "deep_synthesis",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["revision"] == 2
    assert body["automatic_execution"] is False
    assert body["authority_unchanged"] is True
    session = body["session"]
    session_id = session["session_id"]
    action_id = session["actions"][0]["action_id"]
    assert session["actions"][0]["status"] == "proposed"

    fetched = client.get(f"/v1/projects/rover/ai-sessions/{session_id}")
    assert fetched.status_code == 200
    assert fetched.json()["session"]["session_id"] == session_id

    decided = client.post(
        f"/v1/projects/rover/ai-sessions/{session_id}/actions/{action_id}/decision",
        json={
            "expected_revision": 2,
            "decision": "accepted",
            "reviewer": "test-engineer",
            "note": "Accept as a proposal; do not execute.",
        },
    )
    assert decided.status_code == 200, decided.text
    decision_body = decided.json()
    assert decision_body["revision"] == 3
    assert decision_body["executed"] is False
    assert decision_body["action"]["status"] == "accepted"
    assert decision_body["action"]["decision"]["executed"] is False
    assert decision_body["action"]["authority_effect"] == "none"

    latest = store.load("rover")
    saved_session = latest["snapshot"]["engineeringAiSessions"][0]
    assert saved_session["actions"][0]["status"] == "accepted"
    assert saved_session["automatic_execution"] is False
    assert saved_session["physical_authority_unchanged"] is True
    assert latest["snapshot"]["power_on_authorized"] is False
    assert latest["snapshot"]["motion_authorized"] is False
    assert latest["snapshot"]["release_authorized"] is False


def test_stale_session_revision_is_refused_before_model_call(tmp_path) -> None:
    client, store = _client(tmp_path)
    store.save("rover", {"projectId": "rover", "engineeringSources": []}, expected_revision=1)

    response = client.post(
        "/v1/projects/rover/ai-sessions",
        json={
            "mission": "Design an indoor inspection rover",
            "expected_revision": 1,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "ai_project_revision_conflict"


def test_schema_declares_proposal_only_authority(tmp_path) -> None:
    client, _ = _client(tmp_path)

    response = client.get("/v1/engineering/ai/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["automatic_execution"] is False
    assert body["model_output_authority"] == "proposed"
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_authorized"] is False
    assert "generate_netlist_candidate" in body["allowed_action_types"]

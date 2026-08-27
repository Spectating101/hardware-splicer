from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.ai_project_repair_api import create_ai_project_repair_router
from hardware_splicer.project_store import ProjectStore


SESSION_ID = "ai-session-parent1234567890"
ACTION_ID = "action-parent1234567890"


def _repair_response() -> str:
    return json.dumps(
        {
            "summary": "Create a level-compatible successor candidate.",
            "requirements": [
                {
                    "id": "req-vih",
                    "statement": "Prove logic-level compatibility.",
                    "source_ids": ["manual-1"],
                    "assumptions": [],
                }
            ],
            "open_questions": ["Confirm the exact VIH threshold."],
            "architecture_candidates": [
                {
                    "id": "candidate-repair-1",
                    "title": "Level-compatible motor interface",
                    "summary": "Select a verified driver or add translation.",
                    "tradeoffs": ["Possible added component."],
                    "assumptions": [],
                    "source_ids": ["manual-1"],
                }
            ],
            "actions": [
                {
                    "action_type": "revise_candidate",
                    "title": "Revise the candidate",
                    "rationale": "Address the persisted preview failure.",
                    "inputs": {},
                    "source_ids": ["manual-1"],
                },
                {
                    "action_type": "run_compose",
                    "title": "Preview the successor",
                    "rationale": "Validate the new candidate after review.",
                    "inputs": {"phrase": "Compose a level-compatible rover controller"},
                    "source_ids": ["manual-1"],
                },
            ],
        }
    )


def _snapshot(*, failed: bool = True) -> dict:
    result_status = "failed" if failed else "succeeded"
    action_status = "failed" if failed else "completed"
    tool_result = {
        "schema_version": "hardware_splicer.ai_project_tool_result.v1",
        "executor_identity": "hardware_splicer.ai_project_tool_executor.python.v1",
        "project_id": "rover",
        "project_revision": 1,
        "session_id": SESSION_ID,
        "action_id": ACTION_ID,
        "action_type": "run_compose",
        "status": result_status,
        "summary": {
            "ok": not failed,
            "error": "logic threshold unresolved" if failed else None,
            "automatic_execution": False,
        },
        "error": (
            {"type": "RuntimeError", "message": "logic threshold unresolved"}
            if failed
            else None
        ),
        "artifact": {
            "project_relative_path": f"ai_tool_runs/{SESSION_ID}/{ACTION_ID}/result.json",
            "sha256": "a" * 64,
            "size_bytes": 512,
        },
        "automatic_execution": False,
        "physical_authority_unchanged": True,
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False,
    }
    action = {
        "action_id": ACTION_ID,
        "session_id": SESSION_ID,
        "project_id": "rover",
        "project_revision": 1,
        "action_type": "run_compose",
        "title": "Compose rover controller",
        "rationale": "Create a deterministic candidate preview.",
        "inputs": {"phrase": "Compose rover controller"},
        "source_ids": ["manual-1"],
        "status": action_status,
        "tool_result": tool_result,
        "decision": {
            "decision": "accepted",
            "reviewer": "human",
            "decided_at": "2026-08-04T00:00:00+00:00",
            "executed": False,
        },
        "automatic_execution": False,
        "authority_effect": "none",
    }
    return {
        "projectId": "rover",
        "name": "Indoor rover",
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
                "summary": "Initial candidate.",
                "requirements": [],
                "architecture_candidates": [
                    {
                        "id": "candidate-original",
                        "title": "Original",
                        "summary": "Original controller.",
                    }
                ],
                "open_questions": [],
                "context_sha256": "b" * 64,
                "context": {
                    "project_summary": {"name": "Indoor rover"},
                    "registered_sources": [
                        {
                            "source_id": "manual-1",
                            "content_hash": "sha256:manual",
                            "source_type": "manual",
                        }
                    ],
                    "parsed_sources": [],
                    "parser_runs": [],
                },
                "actions": [action],
                "automatic_execution": False,
                "physical_authority_unchanged": True,
            }
        ],
    }


def _client(tmp_path: Path, *, failed: bool = True) -> tuple[TestClient, ProjectStore, list[dict]]:
    store = ProjectStore(tmp_path / "projects")
    store.save("rover", _snapshot(failed=failed))
    calls: list[dict] = []

    def fake_llm(prompt: str, **kwargs: object) -> dict:
        calls.append({"prompt": prompt, **kwargs})
        return {
            "ok": True,
            "provider": "test",
            "model": "repair-model",
            "content": _repair_response(),
            "usage": {},
            "cached": False,
        }

    app = FastAPI()
    app.include_router(create_ai_project_repair_router(store, llm_callable=fake_llm))
    return TestClient(app), store, calls


def test_repair_api_appends_child_session_without_mutating_failure(tmp_path: Path) -> None:
    client, store, calls = _client(tmp_path)

    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/repair",
        json={"expected_revision": 1},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert body["idempotent"] is False
    assert body["repair_session"]["session_kind"] == "failure_repair"
    assert body["repair_session"]["repair_of"]["parent_action_id"] == ACTION_ID
    assert body["automatic_execution"] is False
    assert body["authority_unchanged"] is True
    assert len(calls) == 1

    latest = store.load("rover")
    sessions = latest["snapshot"]["engineeringAiSessions"]
    assert len(sessions) == 2
    parent_action = sessions[0]["actions"][0]
    repair_session = sessions[1]
    assert parent_action["status"] == "failed"
    assert parent_action["tool_result"]["status"] == "failed"
    assert parent_action["tool_result"]["artifact"]["sha256"] == "a" * 64
    assert parent_action["repair_status"] == "successor_proposed"
    assert parent_action["repair_sessions"][0]["session_id"] == repair_session["session_id"]
    assert all(row["status"] == "proposed" for row in repair_session["actions"])
    assert latest["snapshot"]["power_on_authorized"] is False
    assert latest["snapshot"]["motion_authorized"] is False
    assert latest["snapshot"]["release_authorized"] is False

    repeated = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/repair",
        json={"expected_revision": 2},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["revision"] == 2
    assert repeated.json()["idempotent"] is True
    assert repeated.json()["repair_session"]["session_id"] == repair_session["session_id"]
    assert len(calls) == 1


def test_repair_api_refuses_stale_revision_before_model_call(tmp_path: Path) -> None:
    client, store, calls = _client(tmp_path)
    store.save("rover", _snapshot(), expected_revision=1)

    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/repair",
        json={"expected_revision": 1},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "ai_repair_revision_conflict"
    assert calls == []


def test_repair_api_refuses_successful_preview(tmp_path: Path) -> None:
    client, _, calls = _client(tmp_path, failed=False)

    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/repair",
        json={"expected_revision": 1},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "ai_repair_not_eligible"
    assert calls == []


def test_repair_schema_is_fail_closed(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path)

    response = client.get("/v1/engineering/ai/repair/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["repairable_preview_actions"] == ["run_guided_plan", "run_compose"]
    assert body["one_model_turn"] is True
    assert body["one_successor_candidate"] is True
    assert body["preserve_failed_result"] is True
    assert body["fresh_human_decision_required"] is True
    assert body["automatic_execution"] is False
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_authorized"] is False

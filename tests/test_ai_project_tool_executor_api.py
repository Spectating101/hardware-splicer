from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.ai_project_tool_executor_api import (
    create_ai_project_tool_executor_router,
)
from hardware_splicer.project_store import ProjectStore


SESSION_ID = "ai-session-1234567890abcdef"
ACTION_ID = "action-1234567890abcdef"


def _snapshot(*, action_type: str = "run_compose", action_status: str = "accepted") -> dict:
    return {
        "projectId": "rover",
        "name": "Indoor rover",
        "engineeringSources": [],
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
        "engineeringAiSessions": [
            {
                "session_id": SESSION_ID,
                "project_id": "rover",
                "project_revision": 1,
                "mission": "Design an indoor inspection rover",
                "constraints": {},
                "automatic_execution": False,
                "physical_authority_unchanged": True,
                "actions": [
                    {
                        "action_id": ACTION_ID,
                        "session_id": SESSION_ID,
                        "project_id": "rover",
                        "project_revision": 1,
                        "action_type": action_type,
                        "title": "Run bounded preview",
                        "rationale": "Validate the candidate.",
                        "inputs": {},
                        "status": action_status,
                        "tool_result": None,
                        "automatic_execution": False,
                        "authority_effect": "none",
                    }
                ],
            }
        ],
    }


def _client(
    tmp_path: Path,
    *,
    action_type: str = "run_compose",
    action_status: str = "accepted",
) -> tuple[TestClient, ProjectStore, list[dict]]:
    store = ProjectStore(tmp_path / "projects")
    store.save("rover", _snapshot(action_type=action_type, action_status=action_status))
    calls: list[dict] = []

    def fake_compose(**kwargs: object) -> dict:
        calls.append(dict(kwargs))
        return {
            "ok": True,
            "mode": "scratch",
            "build_id": "generic_low_voltage_build",
            "module_ids": ["esp32", "motor_driver"],
            "design_quality_gate": {"build_ready": True},
            "failure": {},
            "warnings": [],
        }

    def fake_planner(intake: dict, **kwargs: object) -> dict:
        calls.append({"intake": intake, **kwargs})
        return {
            "schema_version": "hardware_splicer.guided_engineering_plan.v1",
            "engineering_readiness": {"status": "blocked"},
            "engineering_status": {"overall_status": "blocked"},
            "manufacturing_closure": {
                "status": "blocked",
                "blocking_checks": [],
                "warning_checks": [],
            },
            "engineering_execution_plan": {
                "checks": [],
                "unresolved": [],
                "automatic_execution": False,
            },
            "missing_info": [],
            "ordered_steps": [],
        }

    app = FastAPI()
    app.include_router(
        create_ai_project_tool_executor_router(
            store,
            guided_planner=fake_planner,
            compose_callable=fake_compose,
        )
    )
    return TestClient(app), store, calls


def test_execute_preview_persists_result_and_is_idempotent(tmp_path: Path) -> None:
    client, store, calls = _client(tmp_path)

    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/execute-preview",
        json={"expected_revision": 1},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert body["idempotent"] is False
    assert body["tool_result"]["status"] == "succeeded"
    assert body["action"]["status"] == "completed"
    assert body["automatic_execution"] is False
    assert body["authority_unchanged"] is True
    assert len(calls) == 1

    latest = store.load("rover")
    action = latest["snapshot"]["engineeringAiSessions"][0]["actions"][0]
    assert action["status"] == "completed"
    assert action["tool_result"]["power_on_authorized"] is False
    assert latest["snapshot"]["power_on_authorized"] is False
    assert latest["snapshot"]["motion_authorized"] is False
    assert latest["snapshot"]["release_authorized"] is False

    repeated = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/execute-preview",
        json={"expected_revision": 2},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["revision"] == 2
    assert repeated.json()["idempotent"] is True
    assert len(calls) == 1


def test_preview_requires_current_revision_and_explicit_acceptance(tmp_path: Path) -> None:
    client, store, calls = _client(tmp_path, action_status="proposed")
    store.save("rover", _snapshot(action_status="proposed"), expected_revision=1)

    stale = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/execute-preview",
        json={"expected_revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["type"] == "ai_tool_revision_conflict"
    assert calls == []

    unaccepted = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/execute-preview",
        json={"expected_revision": 2},
    )
    assert unaccepted.status_code == 409
    assert unaccepted.json()["detail"]["type"] == "ai_action_not_accepted"
    assert calls == []


def test_nonallowlisted_action_is_refused(tmp_path: Path) -> None:
    client, _, calls = _client(tmp_path, action_type="run_drc")

    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/execute-preview",
        json={"expected_revision": 1},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "ai_action_not_executable"
    assert calls == []


def test_tool_schema_is_fail_closed(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path)

    response = client.get("/v1/engineering/ai/tools/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["executable_preview_actions"] == ["run_guided_plan", "run_compose"]
    assert body["requires_explicit_acceptance"] is True
    assert body["automatic_execution"] is False
    assert body["allow_llm_first_compose"] is False
    assert body["export_gerber"] is False
    assert body["device_access_authorized"] is False
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_authorized"] is False

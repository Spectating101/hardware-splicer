from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.ai_project_tool_executor import (
    AIActionNotAccepted,
    AIActionNotExecutable,
    execute_ai_project_action_preview,
)
from hardware_splicer.project_store import ProjectStore


def _session(action_type: str, *, status: str = "accepted") -> tuple[dict, dict]:
    decision = (
        {
            "decision": "accepted",
            "reviewer": "test-engineer",
            "note": "Accepted as a proposal only.",
            "decided_at": "2026-08-04T14:00:00+00:00",
            "project_revision": 1,
            "executed": False,
        }
        if status == "accepted"
        else None
    )
    action = {
        "action_id": "action-1234567890abcdef",
        "session_id": "ai-session-1234567890abcdef",
        "project_id": "rover",
        "project_revision": 1,
        "action_type": action_type,
        "title": "Run bounded preview",
        "rationale": "Validate the candidate without physical execution.",
        "inputs": {},
        "status": status,
        "decision": decision,
        "tool_result": None,
        "automatic_execution": False,
        "authority_effect": "none",
    }
    session = {
        "session_id": "ai-session-1234567890abcdef",
        "project_id": "rover",
        "project_revision": 1,
        "mission": "Design an indoor inspection rover",
        "constraints": {"max_width_mm": 500},
        "actions": [action],
        "automatic_execution": False,
        "physical_authority_unchanged": True,
    }
    return session, action


def _store(tmp_path: Path) -> ProjectStore:
    store = ProjectStore(tmp_path / "projects")
    store.save(
        "rover",
        {
            "projectId": "rover",
            "name": "Indoor rover",
            "engineeringSources": [
                {
                    "source_id": "source-manual",
                    "content_hash": "sha256:abc",
                    "source_type": "manual",
                    "authority_ceiling": "declared",
                }
            ],
            "engineeringParsedSources": [],
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
    return store


def test_guided_plan_preview_is_revision_pinned_and_artifact_hashed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    session, action = _session("run_guided_plan")
    calls: list[dict] = []

    def fake_planner(intake: dict, **kwargs: object) -> dict:
        calls.append({"intake": intake, **kwargs})
        return {
            "schema_version": "hardware_splicer.guided_engineering_plan.v1",
            "engineering_readiness": {
                "status": "blocked",
                "power_on_authorized": False,
                "motion_authorized": False,
                "release_authorized": False,
            },
            "engineering_status": {
                "overall_status": "blocked",
                "current_phase": "source",
            },
            "manufacturing_closure": {
                "status": "blocked",
                "blocking_checks": [{"check_id": "connector"}],
                "warning_checks": [],
            },
            "engineering_execution_plan": {
                "checks": [{"check_id": "python_compile"}],
                "unresolved": [{"reason": "firmware source missing"}],
                "automatic_execution": False,
            },
            "missing_info": ["Provide firmware source."],
            "ordered_steps": [{"step_id": "freeze_sources"}],
        }

    result = execute_ai_project_action_preview(
        store,
        "rover",
        session,
        action,
        guided_planner=fake_planner,
    )

    assert len(calls) == 1
    assert calls[0]["skip_vision"] is True
    assert calls[0]["intake"]["goal"] == session["mission"]
    assert result["status"] == "succeeded"
    assert result["project_revision"] == 1
    assert result["summary"]["manufacturing_closure"]["blocking_check_count"] == 1
    assert result["summary"]["execution_preview"]["automatic_execution"] is False
    assert result["automatic_execution"] is False
    assert result["power_on_authorized"] is False
    assert result["motion_authorized"] is False
    assert result["release_authorized"] is False

    artifact = store.root / "rover" / result["artifact"]["project_relative_path"]
    payload = artifact.read_bytes()
    assert artifact.name == "guided_plan.json"
    assert hashlib.sha256(payload).hexdigest() == result["artifact"]["sha256"]
    assert len(payload) == result["artifact"]["size_bytes"]
    assert json.loads(payload)["engineering_readiness"]["status"] == "blocked"


def test_compose_preview_forces_deterministic_nonfabrication_boundary(tmp_path: Path) -> None:
    store = _store(tmp_path)
    session, action = _session("run_compose")
    action["inputs"] = {
        "phrase": "Compose a protected rover power and motor control candidate",
        "constraints": {"logic_voltage_v": 3.3},
    }
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

    result = execute_ai_project_action_preview(
        store,
        "rover",
        session,
        action,
        compose_callable=fake_compose,
    )

    assert len(calls) == 1
    assert calls[0]["allow_llm_first"] is False
    assert calls[0]["export_gerber"] is False
    assert calls[0]["request_id"] == action["action_id"]
    assert result["status"] == "succeeded"
    assert result["summary"]["allow_llm_first"] is False
    assert result["summary"]["export_gerber"] is False
    assert result["fabrication_authorized"] is False
    assert result["firmware_flash_authorized"] is False
    assert result["power_on_authorized"] is False


def test_tool_failure_is_persisted_as_bounded_failure_artifact(tmp_path: Path) -> None:
    store = _store(tmp_path)
    session, action = _session("run_compose")

    def failing_compose(**_: object) -> dict:
        raise RuntimeError("deterministic compose failed")

    result = execute_ai_project_action_preview(
        store,
        "rover",
        session,
        action,
        compose_callable=failing_compose,
    )

    assert result["status"] == "failed"
    assert result["error"]["type"] == "RuntimeError"
    assert result["summary"]["automatic_execution"] is False
    artifact = store.root / "rover" / result["artifact"]["project_relative_path"]
    assert artifact.name == "failure.json"
    assert json.loads(artifact.read_text())["error"] == "deterministic compose failed"


def test_unaccepted_and_nonallowlisted_actions_are_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)
    proposed_session, proposed_action = _session("run_compose", status="proposed")
    with pytest.raises(AIActionNotAccepted):
        execute_ai_project_action_preview(
            store,
            "rover",
            proposed_session,
            proposed_action,
            compose_callable=lambda **_: {"ok": True},
        )

    forged_session, forged_action = _session("run_compose", status="accepted")
    forged_action["decision"] = None
    with pytest.raises(AIActionNotAccepted):
        execute_ai_project_action_preview(
            store,
            "rover",
            forged_session,
            forged_action,
            compose_callable=lambda **_: {"ok": True},
        )

    accepted_session, unsupported_action = _session("run_drc", status="accepted")
    with pytest.raises(AIActionNotExecutable):
        execute_ai_project_action_preview(
            store,
            "rover",
            accepted_session,
            unsupported_action,
        )

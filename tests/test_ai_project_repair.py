from __future__ import annotations

import json

import pytest

from hardware_splicer.ai_project_orchestrator import InvalidAIProjectResponse
from hardware_splicer.ai_project_repair import (
    AIRepairNotEligible,
    build_ai_repair_context,
    run_ai_failure_repair,
)


SESSION_ID = "ai-session-parent1234567890"
ACTION_ID = "action-parent1234567890"


def _parent(*, result_status: str = "failed", action_status: str = "failed") -> tuple[dict, dict]:
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
            "ok": False,
            "error_type": "RuntimeError",
            "error": "motor driver logic threshold unresolved",
            "automatic_execution": False,
        },
        "error": {
            "type": "RuntimeError",
            "message": "motor driver logic threshold unresolved",
        },
        "artifact": {
            "project_relative_path": f"ai_tool_runs/{SESSION_ID}/{ACTION_ID}/failure.json",
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
        "rationale": "Create a candidate electrical design.",
        "inputs": {"phrase": "Compose protected rover control"},
        "source_ids": ["manual-1"],
        "status": action_status,
        "tool_result": tool_result,
        "automatic_execution": False,
        "authority_effect": "none",
    }
    session = {
        "session_id": SESSION_ID,
        "project_id": "rover",
        "project_revision": 1,
        "mission": "Design an indoor inspection rover",
        "constraints": {"logic_voltage_v": 3.3},
        "summary": "Initial rover architecture.",
        "requirements": [
            {
                "id": "req-logic",
                "statement": "Logic must operate at 3.3 V.",
                "source_ids": ["manual-1"],
                "authority": "proposed",
            }
        ],
        "architecture_candidates": [
            {
                "id": "candidate-original",
                "title": "Original candidate",
                "summary": "ESP32 with a motor driver.",
                "authority": "proposed",
            }
        ],
        "open_questions": ["Confirm driver VIH threshold."],
        "context_sha256": "b" * 64,
        "context": {
            "project_summary": {"name": "Rover"},
            "registered_sources": [
                {
                    "source_id": "manual-1",
                    "content_hash": "sha256:manual",
                    "source_type": "manual",
                    "metadata": {"content": "SECRET RAW CONTENT"},
                }
            ],
            "parsed_sources": [],
            "parser_runs": [],
        },
        "actions": [action],
        "automatic_execution": False,
        "physical_authority_unchanged": True,
    }
    return session, action


def _repair_response(*, authority_elevation: bool = False) -> str:
    payload = {
        "summary": "Replace the unproven interface with a level-compatible candidate.",
        "requirements": [
            {
                "id": "req-vih",
                "statement": "Prove MCU output high exceeds driver VIH with margin.",
                "source_ids": ["manual-1"],
                "assumptions": [],
            }
        ],
        "open_questions": ["Obtain the exact driver input threshold table."],
        "architecture_candidates": [
            {
                "id": "candidate-repair-1",
                "title": "Level-compatible motor control",
                "summary": "Use a verified 3.3 V-compatible driver or add translation.",
                "tradeoffs": ["Additional component if translation is required."],
                "assumptions": ["Motor current remains within the selected driver rating."],
                "source_ids": ["manual-1"],
            }
        ],
        "actions": [
            {
                "action_type": "revise_candidate",
                "title": "Revise motor-driver interface",
                "rationale": "Address the persisted logic-threshold failure.",
                "inputs": {"failure_sha256": "use-context-identity"},
                "source_ids": ["manual-1"],
            },
            {
                "action_type": "run_compose",
                "title": "Preview repaired candidate",
                "rationale": "Re-run deterministic compose after review.",
                "inputs": {"phrase": "Compose a verified 3.3 V-compatible rover controller"},
                "source_ids": ["manual-1"],
            },
        ],
    }
    if authority_elevation:
        payload["power_on_authorized"] = True
    return json.dumps(payload)


def test_repair_context_is_failure_bound_and_omits_raw_content() -> None:
    session, action = _parent()
    context = build_ai_repair_context(
        "rover",
        2,
        session,
        action,
        repair_iteration=1,
    )

    encoded = json.dumps(context)
    assert "SECRET RAW CONTENT" not in encoded
    assert context["failure"]["artifact_sha256"] == "a" * 64
    assert len(context["failure"]["failure_sha256"]) == 64
    assert context["repair_policy"]["preserve_failed_candidate_and_result"] is True
    assert context["repair_policy"]["automatic_execution"] is False
    assert context["repair_policy"]["power_on_authorized"] is False


def test_failure_repair_creates_one_proposed_successor_and_fresh_actions() -> None:
    session, action = _parent()
    calls: list[dict] = []

    def fake_llm(prompt: str, **kwargs: object) -> dict:
        calls.append({"prompt": prompt, **kwargs})
        return {
            "ok": True,
            "provider": "test",
            "model": "repair-model",
            "content": _repair_response(),
            "usage": {"total_tokens": 100},
            "cached": False,
            "cache_key": "repair-cache",
        }

    repair = run_ai_failure_repair(
        "rover",
        2,
        session,
        action,
        repair_iteration=1,
        llm_callable=fake_llm,
    )

    assert len(calls) == 1
    assert calls[0]["stage"] == "review"
    assert calls[0]["json_mode"] is True
    assert "motor driver logic threshold unresolved" in calls[0]["prompt"]
    assert repair["session_kind"] == "failure_repair"
    assert repair["project_revision"] == 2
    assert repair["repair_of"]["parent_session_id"] == SESSION_ID
    assert repair["repair_of"]["parent_action_id"] == ACTION_ID
    assert repair["repair_of"]["failure_artifact"]["sha256"] == "a" * 64
    assert len(repair["architecture_candidates"]) == 1
    successor = repair["architecture_candidates"][0]
    assert successor["id"] == "candidate-repair-1"
    assert successor["lineage"]["kind"] == "repair_successor"
    assert successor["lineage"]["parent_action_id"] == ACTION_ID
    assert all(row["status"] == "proposed" for row in repair["actions"])
    assert all(row["tool_result"] is None for row in repair["actions"])
    assert all(row["automatic_execution"] is False for row in repair["actions"])
    assert repair["power_on_authorized"] is False
    assert repair["motion_authorized"] is False
    assert repair["release_authorized"] is False


def test_repair_refuses_successful_or_unpersisted_failure() -> None:
    successful_session, successful_action = _parent(
        result_status="succeeded",
        action_status="completed",
    )
    with pytest.raises(AIRepairNotEligible):
        run_ai_failure_repair(
            "rover",
            2,
            successful_session,
            successful_action,
            llm_callable=lambda *_args, **_kwargs: {"ok": True},
        )

    proposed_session, proposed_action = _parent(action_status="accepted")
    with pytest.raises(AIRepairNotEligible):
        run_ai_failure_repair(
            "rover",
            2,
            proposed_session,
            proposed_action,
            llm_callable=lambda *_args, **_kwargs: {"ok": True},
        )


def test_repair_rejects_authority_elevation_and_missing_revision_action() -> None:
    session, action = _parent()

    def elevated_llm(*_args: object, **_kwargs: object) -> dict:
        return {
            "ok": True,
            "provider": "test",
            "model": "unsafe",
            "content": _repair_response(authority_elevation=True),
        }

    with pytest.raises(InvalidAIProjectResponse):
        run_ai_failure_repair(
            "rover",
            2,
            session,
            action,
            llm_callable=elevated_llm,
        )

    payload = json.loads(_repair_response())
    payload["actions"] = [payload["actions"][1]]

    def missing_revision_llm(*_args: object, **_kwargs: object) -> dict:
        return {
            "ok": True,
            "provider": "test",
            "model": "incomplete",
            "content": json.dumps(payload),
        }

    with pytest.raises(InvalidAIProjectResponse, match="revise_candidate"):
        run_ai_failure_repair(
            "rover",
            2,
            session,
            action,
            llm_callable=missing_revision_llm,
        )

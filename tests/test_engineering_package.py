from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from hardware_splicer.engineering_package import build_engineering_package
from hardware_splicer.project_store import ProjectStore


SESSION_ID = "ai-session-package123"
ACTION_ID = "action-package123"
REPAIR_SESSION_ID = "ai-repair-package123"


def _snapshot() -> dict:
    failed_result = {
        "schema_version": "hardware_splicer.ai_project_tool_result.v1",
        "executor_identity": "hardware_splicer.ai_project_tool_executor.python.v1",
        "project_id": "rover",
        "project_revision": 1,
        "session_id": SESSION_ID,
        "action_id": ACTION_ID,
        "action_type": "run_compose",
        "status": "failed",
        "summary": {"ok": False, "error": "logic threshold unresolved"},
        "error": {"type": "RuntimeError", "message": "logic threshold unresolved"},
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
    parent_action = {
        "action_id": ACTION_ID,
        "session_id": SESSION_ID,
        "project_id": "rover",
        "project_revision": 1,
        "action_type": "run_compose",
        "title": "Compose rover controller",
        "rationale": "Validate one electrical candidate.",
        "inputs": {"phrase": "Compose protected rover control"},
        "source_ids": ["manual-1"],
        "status": "failed",
        "decision": {
            "decision": "accepted",
            "reviewer": "human",
            "decided_at": "2026-08-04T00:00:00+00:00",
            "executed": False,
        },
        "tool_result": failed_result,
        "repair_sessions": [
            {
                "session_id": REPAIR_SESSION_ID,
                "repair_iteration": 1,
                "failure_sha256": "b" * 64,
                "status": "successor_proposed",
            }
        ],
        "automatic_execution": False,
        "authority_effect": "none",
    }
    proposed_action = {
        "action_id": "action-revise123",
        "session_id": REPAIR_SESSION_ID,
        "project_id": "rover",
        "project_revision": 2,
        "action_type": "revise_candidate",
        "title": "Revise logic interface",
        "rationale": "Address the persisted threshold failure.",
        "inputs": {"target": "logic_interface"},
        "source_ids": ["manual-1"],
        "origin_turn_id": "ai-turn-package123",
        "status": "proposed",
        "decision": None,
        "tool_result": None,
        "automatic_execution": False,
        "authority_effect": "none",
    }
    return {
        "projectId": "rover",
        "name": "Indoor rover",
        "mode": "greenfield",
        "currentStage": "candidate",
        "engineeringSources": [
            {
                "source_id": "manual-1",
                "source_type": "manual",
                "content_hash": "sha256:manual",
                "authority_ceiling": "declared",
                "content": "SECRET RAW MANUAL BYTES",
                "metadata": {
                    "parser_route": "manual_extract",
                    "api_key": "SECRET API KEY",
                    "content": "SECRET NESTED CONTENT",
                },
            }
        ],
        "engineeringParsedSources": [
            {
                "source_id": "parsed-manual-1",
                "source_type": "derived_manual_claims",
                "content_hash": "sha256:parsed",
                "authority_ceiling": "proposed",
                "metadata": {"derived_from": "manual-1"},
            }
        ],
        "engineeringSourceConflicts": [
            {
                "conflict_id": "conflict-logic",
                "reason": "Driver threshold is unresolved.",
            }
        ],
        "engineeringAiSessions": [
            {
                "session_id": SESSION_ID,
                "session_kind": "project_proposal",
                "project_id": "rover",
                "project_revision": 1,
                "mission": "Design an indoor inspection rover",
                "summary": "Initial rover controller candidate.",
                "requirements": [
                    {
                        "id": "req-logic",
                        "statement": "The logic rail is 3.3 V.",
                        "source_ids": ["manual-1"],
                        "authority": "proposed",
                    }
                ],
                "architecture_candidates": [
                    {
                        "id": "candidate-original",
                        "title": "Original controller",
                        "summary": "ESP32 and motor driver.",
                    }
                ],
                "open_questions": ["Confirm the exact driver VIH threshold."],
                "actions": [parent_action],
                "conversationTurns": [],
                "automatic_execution": False,
                "physical_authority_unchanged": True,
            },
            {
                "session_id": REPAIR_SESSION_ID,
                "session_kind": "failure_repair",
                "project_id": "rover",
                "project_revision": 2,
                "mission": "Design an indoor inspection rover",
                "summary": "Use a level-compatible successor.",
                "repair_of": {
                    "parent_session_id": SESSION_ID,
                    "parent_action_id": ACTION_ID,
                    "failure_sha256": "b" * 64,
                    "repair_iteration": 1,
                },
                "requirements": [
                    {
                        "id": "req-vih",
                        "statement": "Prove logic compatibility with margin.",
                        "source_ids": ["manual-1"],
                    }
                ],
                "architecture_candidates": [
                    {
                        "id": "candidate-repair",
                        "title": "Level-compatible controller",
                        "summary": "Use a verified driver or translation.",
                        "lineage": {
                            "kind": "repair_successor",
                            "parent_action_id": ACTION_ID,
                            "failure_sha256": "b" * 64,
                        },
                    }
                ],
                "open_questions": ["Obtain the exact threshold table."],
                "actions": [proposed_action],
                "conversationTurns": [
                    {
                        "turn_id": "ai-turn-package123",
                        "project_revision": 2,
                        "created_at": "2026-08-04T00:10:00+00:00",
                        "user_message": "What should we do next?",
                        "assistant_answer": "Revise the interface, then preview again.",
                        "answer_kind": "decision_briefing",
                        "evidence_refs": [
                            {
                                "kind": "tool_result",
                                "id": ACTION_ID,
                                "reason": "The compose preview failed.",
                            }
                        ],
                        "blockers": ["The threshold table is missing."],
                        "recommended_action_id": "action-revise123",
                        "provider": "test",
                        "model": "jarvis-test",
                    }
                ],
                "automatic_execution": False,
                "physical_authority_unchanged": True,
            },
        ],
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False,
    }


def _zip_entries(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_engineering_package_is_reproducible_and_manifest_verified(tmp_path: Path) -> None:
    snapshot = _snapshot()
    store_a = ProjectStore(tmp_path / "a")
    store_b = ProjectStore(tmp_path / "b")

    record_a = build_engineering_package(
        store_a,
        "rover",
        7,
        snapshot,
        source_saved_at="2026-08-04T00:00:00+00:00",
    )
    record_b = build_engineering_package(
        store_b,
        "rover",
        7,
        snapshot,
        source_saved_at="2026-08-04T00:00:00+00:00",
    )

    assert record_a["package_id"] == record_b["package_id"]
    assert record_a["zip_sha256"] == record_b["zip_sha256"]
    assert record_a["zip_size_bytes"] == record_b["zip_size_bytes"]
    assert record_a["raw_source_bytes_included"] is False
    assert record_a["package_authority_effect"] == "none"

    zip_a = store_a.root / "rover" / record_a["project_relative_zip"]
    zip_b = store_b.root / "rover" / record_b["project_relative_zip"]
    assert zip_a.read_bytes() == zip_b.read_bytes()
    assert hashlib.sha256(zip_a.read_bytes()).hexdigest() == record_a["zip_sha256"]

    entries = _zip_entries(zip_a)
    required = {
        "ENGINEERING_PACKAGE/PROJECT_BRIEF.json",
        "ENGINEERING_PACKAGE/SOURCE_MANIFEST.json",
        "ENGINEERING_PACKAGE/ACTION_TRACE.json",
        "ENGINEERING_PACKAGE/TOOL_RESULTS.json",
        "ENGINEERING_PACKAGE/REPAIR_LINEAGE.json",
        "ENGINEERING_PACKAGE/CONVERSATION_BRIEFINGS.json",
        "ENGINEERING_PACKAGE/AUTHORITY_STATE.json",
        "ENGINEERING_PACKAGE/MANIFEST.json",
        "ENGINEERING_PACKAGE/README.md",
    }
    assert required.issubset(entries)

    manifest = json.loads(entries["ENGINEERING_PACKAGE/MANIFEST.json"])
    assert manifest["package_id"] == record_a["package_id"]
    assert manifest["source_revision"] == 7
    assert manifest["raw_source_bytes_included"] is False
    for item in manifest["files"]:
        payload = entries[f"ENGINEERING_PACKAGE/{item['path']}"]
        assert hashlib.sha256(payload).hexdigest() == item["sha256"]
        assert len(payload) == item["size_bytes"]


def test_engineering_package_omits_raw_content_and_preserves_trace(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    record = build_engineering_package(store, "rover", 7, _snapshot())
    zip_path = store.root / "rover" / record["project_relative_zip"]
    entries = _zip_entries(zip_path)
    combined = b"\n".join(entries.values())

    assert b"SECRET RAW MANUAL BYTES" not in combined
    assert b"SECRET NESTED CONTENT" not in combined
    assert b"SECRET API KEY" not in combined

    actions = json.loads(entries["ENGINEERING_PACKAGE/ACTION_TRACE.json"])["actions"]
    results = json.loads(entries["ENGINEERING_PACKAGE/TOOL_RESULTS.json"])["tool_results"]
    repairs = json.loads(entries["ENGINEERING_PACKAGE/REPAIR_LINEAGE.json"])["repairs"]
    turns = json.loads(entries["ENGINEERING_PACKAGE/CONVERSATION_BRIEFINGS.json"])["turns"]
    blockers = json.loads(entries["ENGINEERING_PACKAGE/BLOCKERS.json"])["blockers"]
    authority = json.loads(entries["ENGINEERING_PACKAGE/AUTHORITY_STATE.json"])

    assert {row["action_id"] for row in actions} == {ACTION_ID, "action-revise123"}
    assert results[0]["action_id"] == ACTION_ID
    assert results[0]["status"] == "failed"
    assert repairs[0]["session_id"] == REPAIR_SESSION_ID
    assert repairs[0]["repair_of"]["parent_action_id"] == ACTION_ID
    assert turns[0]["turn_id"] == "ai-turn-package123"
    assert turns[0]["recommended_action_id"] == "action-revise123"
    assert any(row["kind"] == "tool_failure" for row in blockers)
    assert authority["project_authority"]["power_on_authorized"] is False
    assert authority["package_authorizes_physical_action"] is False

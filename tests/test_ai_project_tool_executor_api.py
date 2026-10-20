from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.ai_project_tool_executor_api import (
    create_ai_project_tool_executor_router,
)
from hardware_splicer.finding_ledger import ENGINEERING_FINDINGS_KEY
from hardware_splicer.project_store import ProjectStore


SESSION_ID = "ai-session-1234567890abcdef"
ACTION_ID = "action-1234567890abcdef"


ACTION_ID_CLEAR = "action-234567890abcdef1"

_RELEASE_LEDGER_ENTRY = {
    "finding_id": "finding-releasekeep",
    "category": "release_blocker",
    "object_id": "req-rail",
    "text": "requirement 'req-rail' has no verification",
    "producer": "release_assessment",
    "producer_run": "assess_release@rev1",
    "provenance": {
        "kind": "deterministic",
        "basis": "computed by MachineProject.assess_release over the stored machine project",
        "source_ref": "unverified_requirement",
        "authority_ceiling": "observed",
    },
    "recorded_at": "2026-10-05T06:00:00+00:00",
}


def _snapshot(
    *,
    action_type: str = "run_compose",
    action_status: str = "accepted",
    extra_actions: list[dict] | None = None,
    findings: list[dict] | None = None,
) -> dict:
    decision = (
        {
            "decision": "accepted",
            "reviewer": "test-engineer",
            "note": "Accepted as a proposal only.",
            "decided_at": "2026-08-04T14:00:00+00:00",
            "project_revision": 1,
            "executed": False,
        }
        if action_status == "accepted"
        else None
    )
    snapshot = {
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
                        "decision": decision,
                        "tool_result": None,
                        "automatic_execution": False,
                        "authority_effect": "none",
                    },
                    *(extra_actions or []),
                ],
            }
        ],
    }
    if findings is not None:
        snapshot[ENGINEERING_FINDINGS_KEY] = findings
    return snapshot


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
    client, _, calls = _client(tmp_path, action_type="generate_netlist_candidate")

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
    assert body["executable_preview_actions"] == ["run_guided_plan", "run_compose", "run_erc", "run_drc"]
    assert body["requires_explicit_acceptance"] is True
    assert body["automatic_execution"] is False
    assert body["allow_llm_first_compose"] is False
    assert body["export_gerber"] is False
    assert body["device_access_authorized"] is False
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False
    assert body["release_authorized"] is False


def _compose_result(*, blockers: list[str]) -> dict:
    return {
        "ok": not blockers,
        "mode": "scratch",
        "build_id": "generic_low_voltage_build",
        "module_ids": ["esp32", "motor_driver"],
        "design_quality_gate": {"build_ready": not blockers, "blockers": list(blockers)},
        "failure": {},
        "warnings": [],
    }


def _accepted_action(action_id: str) -> dict:
    return {
        "action_id": action_id,
        "session_id": SESSION_ID,
        "project_id": "rover",
        "project_revision": 1,
        "action_type": "run_compose",
        "title": "Re-run bounded preview",
        "rationale": "Clear the previous gate.",
        "inputs": {},
        "status": "accepted",
        "decision": {
            "decision": "accepted",
            "reviewer": "test-engineer",
            "note": "Accepted as a proposal only.",
            "decided_at": "2026-08-04T14:00:00+00:00",
            "project_revision": 1,
            "executed": False,
        },
        "tool_result": None,
        "automatic_execution": False,
        "authority_effect": "none",
    }


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_executed_compose_persists_gate_blockers_with_action_source_ref(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    store.save(
        "rover",
        _snapshot(findings=[_RELEASE_LEDGER_ENTRY]),
    )
    before = _file_hashes(tmp_path / "projects")
    compose_returns = [_compose_result(blockers=["DRC failed with 2 error(s)."])]

    def fake_compose(**kwargs: object) -> dict:
        return compose_returns.pop(0)

    app = FastAPI()
    app.include_router(
        create_ai_project_tool_executor_router(store, compose_callable=fake_compose)
    )
    client = TestClient(app)

    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/execute-preview",
        json={"expected_revision": 1},
    )
    assert response.status_code == 200, response.text

    latest = store.load("rover")
    snapshot = latest["snapshot"]
    gate_rows = [
        row
        for row in snapshot[ENGINEERING_FINDINGS_KEY]
        if row["producer"] == "design_quality_gate"
    ]
    assert len(gate_rows) == 1
    assert gate_rows[0]["text"] == "DRC failed with 2 error(s)."
    assert gate_rows[0]["provenance"]["source_ref"] == ACTION_ID
    assert gate_rows[0]["provenance"]["kind"] == "deterministic"
    assert gate_rows[0]["category"] == "failed_check"
    other = [
        row
        for row in snapshot[ENGINEERING_FINDINGS_KEY]
        if row["producer"] == "release_assessment"
    ]
    assert len(other) == 1
    assert other[0]["text"] == _RELEASE_LEDGER_ENTRY["text"]
    assert snapshot["power_on_authorized"] is False
    assert snapshot["motion_authorized"] is False
    assert snapshot["release_authorized"] is False

    after = _file_hashes(tmp_path / "projects")
    earlier = "rover/revisions/00000001.json"
    assert after[earlier] == before[earlier]
    for path, digest in before.items():
        if path.endswith("00000001.json"):
            assert after[path] == digest


def test_rerun_with_empty_gate_clears_design_quality_findings(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    store.save(
        "rover",
        _snapshot(
            extra_actions=[_accepted_action(ACTION_ID_CLEAR)],
            findings=[_RELEASE_LEDGER_ENTRY],
        ),
    )
    compose_returns = [
        _compose_result(blockers=["Catalog build graph did not compile."]),
        _compose_result(blockers=[]),
    ]

    def fake_compose(**kwargs: object) -> dict:
        return compose_returns.pop(0)

    app = FastAPI()
    app.include_router(
        create_ai_project_tool_executor_router(store, compose_callable=fake_compose)
    )
    client = TestClient(app)

    first = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/execute-preview",
        json={"expected_revision": 1},
    )
    assert first.status_code == 200, first.text
    blocked = store.load("rover")["snapshot"][ENGINEERING_FINDINGS_KEY]
    assert any(
        row["producer"] == "design_quality_gate"
        and row["text"] == "Catalog build graph did not compile."
        for row in blocked
    )

    cleared = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID_CLEAR}/execute-preview",
        json={"expected_revision": 2},
    )
    assert cleared.status_code == 200, cleared.text
    findings = store.load("rover")["snapshot"][ENGINEERING_FINDINGS_KEY]
    assert [row for row in findings if row["producer"] == "design_quality_gate"] == []
    assert any(row["producer"] == "release_assessment" for row in findings)


def test_executed_compose_bounds_overlong_gate_blocker(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    store.save("rover", _snapshot())
    long_blocker = "Q" * 1200

    def fake_compose(**kwargs: object) -> dict:
        return _compose_result(blockers=[long_blocker])

    app = FastAPI()
    app.include_router(
        create_ai_project_tool_executor_router(store, compose_callable=fake_compose)
    )
    client = TestClient(app)
    response = client.post(
        f"/v1/projects/rover/ai-sessions/{SESSION_ID}/actions/{ACTION_ID}/execute-preview",
        json={"expected_revision": 1},
    )
    assert response.status_code == 200, response.text
    rows = [
        row
        for row in store.load("rover")["snapshot"][ENGINEERING_FINDINGS_KEY]
        if row["producer"] == "design_quality_gate"
    ]
    assert len(rows) == 1
    assert len(rows[0]["text"]) == 1000
    assert rows[0]["text"].endswith("…")
    assert rows[0]["provenance"]["source_ref"] == ACTION_ID
    assert rows[0]["provenance"]["basis"].endswith(" (message truncated)")

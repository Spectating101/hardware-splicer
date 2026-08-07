from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.dual_agent_cleanroom_api import create_dual_agent_cleanroom_router
from hardware_splicer.project_store import ProjectStore


def _fake_llm(prompt: str, **kwargs: object) -> dict:
    # The operator should see persisted project state only, never snapshot or constraint
    # payloads smuggled in by the outer caller.
    assert "persisted-source" in prompt
    assert "persisted-constraint-marker" in prompt
    assert "caller-secret-source" not in prompt
    assert "caller-solution" not in prompt
    response = {
        "summary": "The persisted evidence is incomplete; keep the interface blocked.",
        "requirements": [
            {
                "id": "req-1",
                "statement": "Resolve the declared interface before implementation.",
                "source_ids": ["persisted-source"],
                "assumptions": [],
            }
        ],
        "open_questions": ["What voltage is actually measured at the interface?"],
        "architecture_candidates": [],
        "actions": [
            {
                "action_type": "identify_missing_evidence",
                "title": "Measure the unresolved interface",
                "rationale": "The persisted evidence does not establish an electrical limit.",
                "inputs": {},
                "source_ids": ["persisted-source"],
            }
        ],
    }
    return {
        "ok": True,
        "provider": "cleanroom-test",
        "model": "deterministic-fixture",
        "content": json.dumps(response),
        "usage": {},
    }


def _client(tmp_path) -> tuple[TestClient, ProjectStore]:
    store = ProjectStore(tmp_path / "projects")
    app = FastAPI()
    app.include_router(create_dual_agent_cleanroom_router(store, llm_callable=_fake_llm))
    return TestClient(app), store


def _seed(store: ProjectStore) -> dict:
    return store.save(
        "fixture-project",
        {
            "name": "fixture-project",
            "constraints": {"evaluation_marker": "persisted-constraint-marker"},
            "engineeringSources": [
                {
                    "source_id": "persisted-source",
                    "source_type": "engineering_source_json",
                    "content_hash": "sha256:persisted",
                    "authority_ceiling": "declared",
                    "metadata": {"label": "persisted operator-visible evidence"},
                }
            ],
            "engineeringBlockers": ["interface voltage unresolved"],
        },
        expected_revision=0,
    )


def test_cleanroom_operator_turn_loads_current_persisted_revision(tmp_path) -> None:
    client, store = _client(tmp_path)
    envelope = _seed(store)

    response = client.post(
        "/v1/projects/fixture-project/cleanroom/operator-turn",
        json={
            "expected_revision": envelope["revision"],
            "mission": "Determine the next defensible engineering action.",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evaluated_revision"] == envelope["revision"]
    assert body["saved_revision"] is None
    assert body["project_state_mutated"] is False
    assert body["constraints_source"] == "persisted_project_snapshot"
    assert body["authority_effect"] == "none"
    session = body["cleanroom"]["operator_session"]
    assert session["constraints"]["evaluation_marker"] == "persisted-constraint-marker"
    assert session["actions"][0]["source_ids"] == ["persisted-source"]
    assert session["actions"][0]["status"] == "proposed"


def test_cleanroom_operator_turn_rejects_stale_revision(tmp_path) -> None:
    client, store = _client(tmp_path)
    first = _seed(store)
    store.save(
        "fixture-project",
        {**first["snapshot"], "currentStage": "review"},
        expected_revision=first["revision"],
    )

    response = client.post(
        "/v1/projects/fixture-project/cleanroom/operator-turn",
        json={
            "expected_revision": first["revision"],
            "mission": "Evaluate stale state.",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "cleanroom_revision_conflict"


def test_cleanroom_api_forbids_caller_supplied_snapshot(tmp_path) -> None:
    client, store = _client(tmp_path)
    envelope = _seed(store)

    response = client.post(
        "/v1/projects/fixture-project/cleanroom/operator-turn",
        json={
            "expected_revision": envelope["revision"],
            "mission": "Try to inject hidden fixture state.",
            "snapshot": {
                "engineeringSources": [
                    {"source_id": "caller-secret-source", "golden_answer": "hidden"}
                ]
            },
        },
    )

    assert response.status_code == 422


def test_cleanroom_api_forbids_caller_supplied_constraints(tmp_path) -> None:
    client, store = _client(tmp_path)
    envelope = _seed(store)

    response = client.post(
        "/v1/projects/fixture-project/cleanroom/operator-turn",
        json={
            "expected_revision": envelope["revision"],
            "mission": "Try to inject a solution as a constraint.",
            "constraints": {"solution": "caller-solution"},
        },
    )

    assert response.status_code == 422


def test_cleanroom_schema_declares_zero_authority_and_no_caller_snapshot(tmp_path) -> None:
    client, _ = _client(tmp_path)

    body = client.get("/v1/engineering/cleanroom/schema").json()

    assert body["snapshot_supplied_by_caller"] is False
    assert body["constraints_supplied_by_caller"] is False
    assert body["constraints_source"] == "persisted_project_snapshot"
    assert body["persisted_project_revision_required"] is True
    assert body["project_state_mutated"] is False
    assert body["authority_effect"] == "none"

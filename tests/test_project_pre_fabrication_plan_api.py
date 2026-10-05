from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.finding_ledger import ENGINEERING_FINDINGS_KEY
from hardware_splicer.project_pre_fabrication_plan_api import (
    _GENERATED_PLAN_SURFACES,
    create_project_pre_fabrication_plan_router,
)
from hardware_splicer.project_store import ProjectStore

_LEDGER_ENTRY = {
    "finding_id": "finding-prefabkeep",
    "category": "failed_check",
    "object_id": None,
    "text": "DRC failed with 1 error(s).",
    "producer": "design_quality_gate",
    "producer_run": "action-compose",
    "provenance": {
        "kind": "deterministic",
        "basis": "design_quality gate blocker from an executed deterministic compose",
        "source_ref": "action-compose",
        "authority_ceiling": "observed",
    },
    "recorded_at": "2026-10-05T06:00:00+00:00",
}


def _client(tmp_path):
    store = ProjectStore(tmp_path)
    store.save(
        "adapter",
        {
            "projectId": "adapter",
            "mission": "Prepare a bounded interface adapter.",
            "engineeringSources": [
                {"source_id": "source-a", "content_hash": "sha256:a"},
            ],
            "engineeringBlockers": ["Exact pinout is unresolved."],
            "engineeringPlan": {"schema_version": "generated.plan.v1", "unsupported": True},
            "machineProject": {"project_id": "adapter", "name": "Generic robot"},
            "orderedSteps": [{"step_id": "generic-motion"}],
            "engineering_readiness": {
                "fabrication_ready": False,
                "power_on_ready": False,
            },
            ENGINEERING_FINDINGS_KEY: [_LEDGER_ENTRY],
        },
        expected_revision=0,
    )
    app = FastAPI()
    app.include_router(create_project_pre_fabrication_plan_router(store))
    return TestClient(app), store


def _request() -> dict:
    return {
        "expected_revision": 1,
        "assessment": {
            "physical_correctness": "UNPROVEN",
            "correct_engineering_architecture_asserted": False,
            "authority_effect": "none",
        },
        "requirements": [
            {
                "id": "req-pinout",
                "statement": "Resolve the exact package pinout.",
                "source_ids": ["source-a"],
            }
        ],
        "architecture_candidates": [
            {
                "id": "candidate-a",
                "status": "unresolved",
                "source_ids": ["source-a"],
            }
        ],
        "decisions": [
            {"id": "decision-a", "status": "deferred_pending_evidence"},
        ],
        "actions": [
            {
                "action": "Obtain the exact part suffix and package pinout.",
                "source_ids": ["source-a"],
                "status": "blocked_pending_evidence",
            }
        ],
        "quarantine_generated_plan": True,
        "quarantine_reason": "The generated plan assumes a robot rather than an interface adapter.",
    }


def test_bounded_plan_is_revisioned_and_quarantines_incompatible_generation(tmp_path) -> None:
    client, store = _client(tmp_path)

    response = client.post(
        "/v1/projects/adapter/engineering/pre-fabrication-plan",
        json=_request(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 2
    assert body["pre_fabrication_plan"]["physical_correctness"] == "UNPROVEN"
    assert body["pre_fabrication_plan"]["source_ids"] == ["source-a"]
    snapshot = store.load("adapter", revision=2)["snapshot"]
    assert "machineProject" not in snapshot
    assert "engineeringPlan" not in snapshot
    assert "orderedSteps" not in snapshot
    assert snapshot["preFabricationPlan"]["actions"][0]["status"] == "blocked_pending_evidence"
    assert snapshot["preFabricationPlan"]["quarantined_generated_plan"][
        "engineering_plan_sha256"
    ].startswith("sha256:")
    assert snapshot["engineering_readiness"]["fabrication_ready"] is False
    assert snapshot["engineering_status"] == "bounded_pre_fabrication_plan"


def test_bounded_plan_rejects_unknown_source_identity(tmp_path) -> None:
    client, store = _client(tmp_path)
    request = _request()
    request["actions"][0]["source_ids"] = ["invented-source"]

    response = client.post(
        "/v1/projects/adapter/engineering/pre-fabrication-plan",
        json=request,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_pre_fabrication_plan"
    assert store.load("adapter")["revision"] == 1


def test_bounded_plan_accepts_id_and_description_action_shape(tmp_path) -> None:
    client, store = _client(tmp_path)
    request = _request()
    request["actions"] = [
        {
            "id": "resolve-pinout",
            "description": "Resolve the exact package pinout.",
            "source_ids": ["source-a"],
            "status": "pending",
        }
    ]

    response = client.post(
        "/v1/projects/adapter/engineering/pre-fabrication-plan",
        json=request,
    )

    assert response.status_code == 200
    assert store.load("adapter", revision=2)["snapshot"]["preFabricationPlan"][
        "actions"
    ][0]["id"] == "resolve-pinout"


def test_bounded_plan_rejects_readiness_or_authority_overclaim(tmp_path) -> None:
    client, store = _client(tmp_path)
    request = _request()
    request["assessment"]["fabrication_ready"] = True

    response = client.post(
        "/v1/projects/adapter/engineering/pre-fabrication-plan",
        json=request,
    )

    assert response.status_code == 422
    assert "may not set" in response.json()["detail"]["message"]
    assert store.load("adapter")["revision"] == 1


def test_pre_fab_quarantine_does_not_drop_engineering_findings(tmp_path) -> None:
    assert ENGINEERING_FINDINGS_KEY not in _GENERATED_PLAN_SURFACES
    client, store = _client(tmp_path)

    response = client.post(
        "/v1/projects/adapter/engineering/pre-fabrication-plan",
        json=_request(),
    )
    assert response.status_code == 200, response.text
    snapshot = store.load("adapter", revision=2)["snapshot"]
    assert "engineeringPlan" not in snapshot
    assert "machineProject" not in snapshot
    assert snapshot[ENGINEERING_FINDINGS_KEY] == [_LEDGER_ENTRY]


def test_pre_fab_request_cannot_supply_engineering_findings(tmp_path) -> None:
    client, store = _client(tmp_path)
    request = _request()
    request[ENGINEERING_FINDINGS_KEY] = [
        {
            "category": "failed_check",
            "text": "Forged from pre-fab request.",
            "producer": "design_quality_gate",
        }
    ]
    response = client.post(
        "/v1/projects/adapter/engineering/pre-fabrication-plan",
        json=request,
    )
    assert response.status_code == 422
    assert store.load("adapter")["revision"] == 1
    assert store.load("adapter")["snapshot"][ENGINEERING_FINDINGS_KEY] == [_LEDGER_ENTRY]

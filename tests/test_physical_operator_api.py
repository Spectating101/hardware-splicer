from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.physical_approval import PhysicalApprovalStore
from hardware_splicer.physical_artifact import PhysicalArtifactRegistry
from hardware_splicer.physical_authority import PhysicalPlanGrantStore
from hardware_splicer.physical_dispatch import PhysicalDispatcher
from hardware_splicer.physical_operator import PhysicalOperatorRegistry, programmer_descriptor
from hardware_splicer.physical_operator_api import create_physical_operator_router
from hardware_splicer.physical_workbench import AgentPhysicalWorkbench

TOKEN = "human-secret-token"
PROJECT = "fielddeck"
MISSION = "mission-api"


class Handle:
    def __init__(self):
        self.calls = []

    def execute(self, plan):
        self.calls.append(plan)
        return {"ok": True, "action": plan.action}


def _app(tmp_path, monkeypatch):
    operators = PhysicalOperatorRegistry()
    handle = Handle()
    operators.register(programmer_descriptor(operator_id="probe-1", display_name="Debug Probe"), handle)
    artifacts = PhysicalArtifactRegistry()
    artifacts.register(artifact_id="fw-1", kind="firmware", content=b"firmware", generator="compiler")
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    approvals = PhysicalApprovalStore(tmp_path / "approvals", operators=operators, grants=grants)
    dispatcher = PhysicalDispatcher(registry=operators, grants=grants)
    workbench = AgentPhysicalWorkbench(
        operators=operators,
        artifacts=artifacts,
        approvals=approvals,
        dispatcher=dispatcher,
    )
    app = FastAPI()
    app.state.physical_workbench = workbench
    app.include_router(create_physical_operator_router())
    registry = {hash_operator_token(TOKEN): {"kind": "human", "id": "project-owner"}}
    monkeypatch.setenv("HARDWARE_SPLICER_OPERATOR_TOKENS", json.dumps(registry))
    return app, handle


def test_unconfigured_router_fails_closed():
    app = FastAPI()
    app.include_router(create_physical_operator_router())
    client = TestClient(app)
    response = client.get("/v1/fabrication/operators")
    assert response.status_code == 503
    assert response.json()["detail"]["type"] == "physical_runtime_unavailable"


def test_agent_safe_http_flow_requires_human_approval(tmp_path, monkeypatch):
    app, handle = _app(tmp_path, monkeypatch)
    client = TestClient(app)

    operators = client.get("/v1/fabrication/operators")
    assert operators.status_code == 200
    assert operators.json()["operators"][0]["operator_id"] == "probe-1"

    request = client.post(
        "/v1/fabrication/approval-requests",
        json={
            "operator_id": "probe-1",
            "project_id": PROJECT,
            "mission_id": MISSION,
            "action": "flash",
            "artifact_id": "fw-1",
            "bindings": {"target_id": "pico-001", "verify": True},
            "agent_id": "mission-agent",
        },
    )
    assert request.status_code == 201
    request_id = request.json()["approval_request"]["request_id"]

    premature = client.post(f"/v1/fabrication/approval-requests/{request_id}/execute")
    assert premature.status_code == 409
    assert handle.calls == []

    no_token = client.post(f"/v1/fabrication/approval-requests/{request_id}/approve")
    assert no_token.status_code == 403

    approved = client.post(
        f"/v1/fabrication/approval-requests/{request_id}/approve",
        headers={"X-HS-Operator-Token": TOKEN},
    )
    assert approved.status_code == 200
    assert approved.json()["approval_request"]["status"] == "approved"

    executed = client.post(f"/v1/fabrication/approval-requests/{request_id}/execute")
    assert executed.status_code == 200
    assert executed.json()["receipt"]["authority"] == "human_grant_consumed"
    assert handle.calls[-1].action == "flash"

    replay = client.post(f"/v1/fabrication/approval-requests/{request_id}/execute")
    assert replay.status_code == 409


def test_http_surface_refuses_direct_actuation(tmp_path, monkeypatch):
    app, handle = _app(tmp_path, monkeypatch)
    client = TestClient(app)
    response = client.post(
        "/v1/fabrication/non-actuating",
        json={
            "operator_id": "probe-1",
            "project_id": PROJECT,
            "mission_id": MISSION,
            "action": "flash",
            "payload": {"artifact_id": "fw-1"},
        },
    )
    assert response.status_code == 409
    assert handle.calls == []


def test_human_can_reject_physical_request(tmp_path, monkeypatch):
    app, handle = _app(tmp_path, monkeypatch)
    client = TestClient(app)
    response = client.post(
        "/v1/fabrication/approval-requests",
        json={
            "operator_id": "probe-1",
            "project_id": PROJECT,
            "mission_id": MISSION,
            "action": "flash",
            "artifact_id": "fw-1",
            "bindings": {"target_id": "pico-001"},
            "agent_id": "mission-agent",
        },
    )
    request_id = response.json()["approval_request"]["request_id"]
    rejected = client.post(
        f"/v1/fabrication/approval-requests/{request_id}/reject",
        headers={"X-HS-Operator-Token": TOKEN},
        json={"reason": "Target identity has not been physically confirmed"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["approval_request"]["status"] == "rejected"
    execute = client.post(f"/v1/fabrication/approval-requests/{request_id}/execute")
    assert execute.status_code == 409
    assert handle.calls == []

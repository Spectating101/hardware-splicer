from __future__ import annotations

import json

import pytest

from hardware_splicer.fabrication_operator import FabricationAuthorityError, FabricationValidationError
from hardware_splicer.physical_approval import PhysicalApprovalStore
from hardware_splicer.physical_authority import PhysicalPlanGrantStore
from hardware_splicer.physical_operator import PhysicalOperatorRegistry, programmer_descriptor

HUMAN = {"kind": "human", "id": "project-owner"}
AGENT = {"kind": "agent", "id": "mission-agent"}
PROJECT = "fielddeck"
MISSION = "mission-approval"


class Handle:
    def execute(self, plan):
        return {"ok": True}


def _setup(tmp_path):
    operators = PhysicalOperatorRegistry()
    operators.register(programmer_descriptor(operator_id="probe-1", display_name="Debug Probe"), Handle())
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    approvals = PhysicalApprovalStore(tmp_path / "approvals", operators=operators, grants=grants)
    plan = operators.plan(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        payload={"artifact_id": "fw-1", "artifact_sha256": "a" * 64, "target_id": "pico-001"},
    )
    return operators, grants, approvals, plan


def test_agent_can_request_but_cannot_approve(tmp_path):
    _operators, _grants, approvals, plan = _setup(tmp_path)
    request = approvals.request(plan, requested_by=AGENT)
    assert request["status"] == "pending"
    assert request["requested_by"] == AGENT
    with pytest.raises(FabricationAuthorityError, match="human"):
        approvals.approve(request["request_id"], author=AGENT)


def test_human_approval_mints_exact_plan_grant(tmp_path):
    _operators, grants, approvals, plan = _setup(tmp_path)
    request = approvals.request(plan, requested_by=AGENT)
    approved = approvals.approve(request["request_id"], author=HUMAN)
    assert approved["status"] == "approved"
    assert approved["approved_by"] == HUMAN
    grant = grants.get(approved["grant_id"])
    assert grant["operator_id"] == "probe-1"
    assert grant["action"] == "flash"
    assert grant["consumed_at"] is None
    grants.consume(grant["grant_id"], plan)
    assert grants.get(grant["grant_id"])["consumed_at"] is not None


def test_approval_cannot_be_reused_or_approved_twice(tmp_path):
    _operators, _grants, approvals, plan = _setup(tmp_path)
    request = approvals.request(plan, requested_by=AGENT)
    approvals.approve(request["request_id"], author=HUMAN)
    with pytest.raises(FabricationAuthorityError, match="no longer pending"):
        approvals.approve(request["request_id"], author=HUMAN)


def test_human_can_reject_and_agent_cannot_reverse_it(tmp_path):
    _operators, _grants, approvals, plan = _setup(tmp_path)
    request = approvals.request(plan, requested_by=AGENT)
    rejected = approvals.reject(request["request_id"], author=HUMAN, reason="Target identity not confirmed")
    assert rejected["status"] == "rejected"
    assert rejected["rejection_reason"] == "Target identity not confirmed"
    with pytest.raises(FabricationAuthorityError, match="no longer pending"):
        approvals.approve(request["request_id"], author=HUMAN)


def test_tampered_persisted_plan_is_refused_at_approval(tmp_path):
    _operators, _grants, approvals, plan = _setup(tmp_path)
    request = approvals.request(plan, requested_by=AGENT)
    path = tmp_path / "approvals" / f"{request['request_id']}.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["execution_plan"]["payload"]["artifact_sha256"] = "b" * 64
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(FabricationValidationError, match="changed or is corrupt"):
        approvals.approve(request["request_id"], author=HUMAN)


def test_only_actuation_plans_can_be_requested(tmp_path):
    operators, _grants, approvals, _plan = _setup(tmp_path)
    observe = operators.plan(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="inspect_target",
        payload={"target_id": "pico-001"},
    )
    with pytest.raises(FabricationValidationError, match="actuation"):
        approvals.request(observe, requested_by=AGENT)


def test_pending_list_only_returns_pending_requests(tmp_path):
    _operators, _grants, approvals, plan = _setup(tmp_path)
    pending = approvals.request(plan, requested_by=AGENT)
    second = approvals.request(plan, requested_by=AGENT)
    approvals.reject(second["request_id"], author=HUMAN, reason="Not tonight")
    ids = [item["request_id"] for item in approvals.list_pending()]
    assert ids == [pending["request_id"]]

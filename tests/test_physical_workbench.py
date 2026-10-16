from __future__ import annotations

import pytest

from hardware_splicer.fabrication_operator import FabricationAuthorityError
from hardware_splicer.physical_approval import PhysicalApprovalStore
from hardware_splicer.physical_artifact import PhysicalArtifactRegistry
from hardware_splicer.physical_authority import PhysicalPlanGrantStore
from hardware_splicer.physical_dispatch import PhysicalDispatcher
from hardware_splicer.physical_operator import PhysicalOperatorRegistry, machine_tool_descriptor, programmer_descriptor
from hardware_splicer.physical_workbench import AgentPhysicalWorkbench

HUMAN = {"kind": "human", "id": "project-owner"}
PROJECT = "fielddeck"
MISSION = "mission-workbench"


class Handle:
    def __init__(self):
        self.calls = []

    def execute(self, plan):
        self.calls.append(plan)
        return {"ok": True, "action": plan.action}


def _workbench(tmp_path):
    operators = PhysicalOperatorRegistry()
    probe = Handle()
    cnc = Handle()
    operators.register(programmer_descriptor(operator_id="probe-1", display_name="Debug Probe"), probe)
    operators.register(machine_tool_descriptor(operator_id="cnc-1", kind="cnc", display_name="Desktop CNC"), cnc)

    artifacts = PhysicalArtifactRegistry()
    artifacts.register(artifact_id="fw-1", kind="firmware", content=b"firmware-v1", generator="compiler")
    artifacts.register(artifact_id="toolpath-1", kind="machine_job", content=b"toolpath-v1", generator="cam")

    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    approvals = PhysicalApprovalStore(tmp_path / "approvals", operators=operators, grants=grants)
    dispatcher = PhysicalDispatcher(registry=operators, grants=grants)
    workbench = AgentPhysicalWorkbench(
        operators=operators,
        artifacts=artifacts,
        approvals=approvals,
        dispatcher=dispatcher,
    )
    return workbench, approvals, probe, cnc


def test_agent_can_discover_safe_operator_and_artifact_descriptors(tmp_path):
    workbench, _approvals, _probe, _cnc = _workbench(tmp_path)
    operators = workbench.list_operators()
    assert {item["operator_id"] for item in operators} == {"probe-1", "cnc-1"}
    artifacts = workbench.list_artifacts()
    assert {item["artifact_id"] for item in artifacts} == {"fw-1", "toolpath-1"}
    assert "content" not in repr(artifacts)


def test_agent_can_observe_without_physical_grant(tmp_path):
    workbench, _approvals, probe, _cnc = _workbench(tmp_path)
    receipt = workbench.perform_non_actuating(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="inspect_target",
        payload={"target_id": "pico-001"},
    )
    assert receipt["authority"] == "not_required"
    assert probe.calls[-1].action == "inspect_target"


def test_agent_cannot_directly_dispatch_actuation(tmp_path):
    workbench, _approvals, probe, _cnc = _workbench(tmp_path)
    with pytest.raises(FabricationAuthorityError, match="cannot directly dispatch"):
        workbench.perform_non_actuating(
            operator_id="probe-1",
            project_id=PROJECT,
            mission_id=MISSION,
            action="flash",
            payload={"artifact_id": "fw-1"},
        )
    assert probe.calls == []


def test_agent_request_human_approve_then_execute_exact_firmware(tmp_path):
    workbench, approvals, probe, _cnc = _workbench(tmp_path)
    request = workbench.request_artifact_actuation(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        artifact_id="fw-1",
        bindings={"target_id": "pico-001", "verify": True},
        agent_id="mission-agent",
    )
    assert request["status"] == "pending"
    with pytest.raises(FabricationAuthorityError, match="not approved"):
        workbench.execute_approved(request["request_id"])
    approvals.approve(request["request_id"], author=HUMAN)
    receipt = workbench.execute_approved(request["request_id"])
    assert receipt["authority"] == "human_grant_consumed"
    assert probe.calls[-1].payload["artifact_id"] == "fw-1"
    with pytest.raises(FabricationAuthorityError, match="already been consumed"):
        workbench.execute_approved(request["request_id"])


def test_agent_cannot_use_firmware_as_cnc_job(tmp_path):
    workbench, _approvals, _probe, cnc = _workbench(tmp_path)
    with pytest.raises(Exception, match="not valid"):
        workbench.request_artifact_actuation(
            operator_id="cnc-1",
            project_id=PROJECT,
            mission_id=MISSION,
            action="start",
            artifact_id="fw-1",
            bindings={"fixture_id": "fixture-1"},
            agent_id="mission-agent",
        )
    assert cnc.calls == []


def test_agent_can_cancel_machine_without_new_authority(tmp_path):
    workbench, _approvals, _probe, cnc = _workbench(tmp_path)
    receipt = workbench.perform_non_actuating(
        operator_id="cnc-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="cancel",
        payload={"job_id": "job-1"},
    )
    assert receipt["authority"] == "not_required"
    assert cnc.calls[-1].action == "cancel"

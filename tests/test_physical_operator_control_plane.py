from __future__ import annotations

import pytest

from hardware_splicer.fabrication_operator import (
    FabricationAuthorityError,
    FabricationValidationError,
)
from hardware_splicer.physical_authority import PhysicalPlanGrantStore, execution_plan_sha256
from hardware_splicer.physical_dispatch import PhysicalDispatcher
from hardware_splicer.physical_operator import (
    PhysicalActionDescriptor,
    PhysicalOperatorDescriptor,
    PhysicalOperatorRegistry,
    machine_tool_descriptor,
    programmer_descriptor,
)

HUMAN = {"kind": "human", "id": "project-owner"}
AGENT = {"kind": "agent", "id": "mission-agent"}
PROJECT = "fielddeck"
MISSION = "mission-physical-001"


class FakeHandle:
    def __init__(self, *, fail=False, secret="operator-secret"):
        self.fail = fail
        self.secret = secret
        self.calls = []

    def execute(self, plan):
        self.calls.append(plan)
        if self.fail:
            raise ConnectionError("ambiguous physical transport failure")
        return {"accepted": True, "action": plan.action}


def _registry(descriptor, handle=None):
    registry = PhysicalOperatorRegistry()
    handle = handle or FakeHandle()
    registry.register(descriptor, handle)
    return registry, handle


def test_registry_exposes_safe_descriptor_not_private_handle():
    descriptor = programmer_descriptor(operator_id="probe-1", display_name="Lab Debug Probe")
    registry, handle = _registry(descriptor, FakeHandle(secret="do-not-leak"))
    public = registry.public_list()
    assert public[0]["operator_id"] == "probe-1"
    assert public[0]["kind"] == "programmer"
    assert "secret" not in repr(public)
    assert registry.private_handle("probe-1") is handle


def test_programmer_flash_is_actuation_and_target_inspection_is_observation():
    descriptor = programmer_descriptor(operator_id="probe-1", display_name="Lab Debug Probe")
    assert descriptor.action("flash").requires_human_grant is True
    assert descriptor.action("inspect_target").requires_human_grant is False
    assert descriptor.action("abort").action_class == "risk_reduce"


def test_cnc_and_laser_share_generic_machine_tool_contract():
    cnc = machine_tool_descriptor(operator_id="cnc-1", kind="cnc", display_name="Desktop CNC")
    laser = machine_tool_descriptor(operator_id="laser-1", kind="laser", display_name="Laser Cutter")
    for descriptor in (cnc, laser):
        assert descriptor.action("start").action_class == "actuate"
        assert descriptor.action("resume").action_class == "actuate"
        assert descriptor.action("preflight").action_class == "prepare"
        assert descriptor.action("cancel").action_class == "risk_reduce"


def test_execution_plan_hash_binds_exact_payload():
    descriptor = programmer_descriptor(operator_id="probe-1", display_name="Lab Debug Probe")
    registry, _ = _registry(descriptor)
    p1 = registry.plan(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        payload={"target_id": "pico-001", "firmware_sha256": "a" * 64, "verify": True},
    )
    p2 = registry.plan(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        payload={"target_id": "pico-001", "firmware_sha256": "b" * 64, "verify": True},
    )
    assert p1.payload_sha256 != p2.payload_sha256
    assert execution_plan_sha256(p1) != execution_plan_sha256(p2)


def test_agent_cannot_authorize_generic_physical_actuation(tmp_path):
    descriptor = programmer_descriptor(operator_id="probe-1", display_name="Lab Debug Probe")
    registry, _ = _registry(descriptor)
    plan = registry.plan(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        payload={"target_id": "pico-001", "firmware_sha256": "a" * 64},
    )
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    with pytest.raises(FabricationAuthorityError, match="human"):
        grants.issue(plan, author=AGENT)


def test_human_grant_is_bound_to_exact_server_plan(tmp_path):
    descriptor = programmer_descriptor(operator_id="probe-1", display_name="Lab Debug Probe")
    registry, _ = _registry(descriptor)
    original = registry.plan(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        payload={"target_id": "pico-001", "firmware_sha256": "a" * 64},
    )
    changed = registry.plan(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        payload={"target_id": "pico-001", "firmware_sha256": "b" * 64},
    )
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    grant = grants.issue(original, author=HUMAN)
    with pytest.raises(FabricationAuthorityError, match="execution_plan_sha256|payload_sha256"):
        grants.consume(grant["grant_id"], changed)
    consumed = grants.consume(grant["grant_id"], original)
    assert consumed["consumed_at"] is not None
    with pytest.raises(FabricationAuthorityError, match="already been consumed"):
        grants.consume(grant["grant_id"], original)


def test_observe_and_risk_reduce_dispatch_without_human_grant(tmp_path):
    descriptor = machine_tool_descriptor(operator_id="cnc-1", kind="cnc", display_name="Desktop CNC")
    registry, handle = _registry(descriptor)
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    dispatcher = PhysicalDispatcher(registry=registry, grants=grants)

    status = registry.plan(
        operator_id="cnc-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="status",
        payload={},
    )
    receipt = dispatcher.dispatch(status)
    assert receipt["authority"] == "not_required"
    assert receipt["physical_correctness"] == "UNPROVEN"

    cancel = registry.plan(
        operator_id="cnc-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="cancel",
        payload={"job_id": "job-1"},
    )
    dispatcher.dispatch(cancel)
    assert [call.action for call in handle.calls] == ["status", "cancel"]


def test_actuation_dispatch_requires_exact_human_grant(tmp_path):
    descriptor = machine_tool_descriptor(operator_id="laser-1", kind="laser", display_name="Laser Cutter")
    registry, handle = _registry(descriptor)
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    dispatcher = PhysicalDispatcher(registry=registry, grants=grants)
    plan = registry.plan(
        operator_id="laser-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="start",
        payload={"job_sha256": "f" * 64, "material_profile_id": "plywood-3mm"},
    )

    with pytest.raises(FabricationAuthorityError, match="human plan grant"):
        dispatcher.dispatch(plan)
    assert handle.calls == []

    grant = grants.issue(plan, author=HUMAN)
    receipt = dispatcher.dispatch(plan, grant_id=grant["grant_id"])
    assert receipt["authority"] == "human_grant_consumed"
    assert receipt["grant_id"] == grant["grant_id"]
    assert handle.calls == [plan]


def test_grant_is_spent_before_ambiguous_machine_failure(tmp_path):
    descriptor = machine_tool_descriptor(operator_id="cnc-1", kind="cnc", display_name="Desktop CNC")
    registry, _handle = _registry(descriptor, FakeHandle(fail=True))
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    dispatcher = PhysicalDispatcher(registry=registry, grants=grants)
    plan = registry.plan(
        operator_id="cnc-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="start",
        payload={"job_sha256": "e" * 64},
    )
    grant = grants.issue(plan, author=HUMAN)
    with pytest.raises(ConnectionError, match="ambiguous"):
        dispatcher.dispatch(plan, grant_id=grant["grant_id"])
    assert grants.get(grant["grant_id"])["consumed_at"] is not None
    with pytest.raises(FabricationAuthorityError, match="already been consumed"):
        dispatcher.dispatch(plan, grant_id=grant["grant_id"])


def test_non_actuation_rejects_attempt_to_spend_physical_grant(tmp_path):
    descriptor = PhysicalOperatorDescriptor(
        operator_id="instrument-1",
        kind="instrument",
        display_name="Bench Instrument",
        capabilities=("measurement",),
        actions=(PhysicalActionDescriptor("read", "observe", "Read an already configured instrument."),),
    )
    registry, _ = _registry(descriptor)
    dispatcher = PhysicalDispatcher(registry=registry, grants=PhysicalPlanGrantStore(tmp_path / "grants"))
    plan = registry.plan(
        operator_id="instrument-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="read",
        payload={"channel": "1"},
    )
    with pytest.raises(FabricationValidationError, match="must not consume"):
        dispatcher.dispatch(plan, grant_id="pg-not-real")

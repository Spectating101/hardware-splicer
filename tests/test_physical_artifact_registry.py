from __future__ import annotations

import hashlib

import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.physical_artifact import PhysicalArtifactRegistry
from hardware_splicer.physical_operator import PhysicalOperatorRegistry, machine_tool_descriptor, programmer_descriptor
from hardware_splicer.physical_presets import bench_instrument_descriptor, robot_descriptor

PROJECT = "fielddeck"
MISSION = "mission-physical-artifacts"


class Handle:
    def execute(self, plan):
        return {"ok": True, "action": plan.action}


def _operators():
    registry = PhysicalOperatorRegistry()
    registry.register(machine_tool_descriptor(operator_id="cnc-1", kind="cnc", display_name="Desktop CNC"), Handle())
    registry.register(machine_tool_descriptor(operator_id="laser-1", kind="laser", display_name="Laser Cutter"), Handle())
    registry.register(programmer_descriptor(operator_id="probe-1", display_name="Debug Probe"), Handle())
    registry.register(robot_descriptor(operator_id="robot-1", display_name="Assembly Robot"), Handle())
    registry.register(bench_instrument_descriptor(operator_id="psu-1", display_name="Bench PSU"), Handle())
    return registry


def test_artifact_registry_hides_bytes_and_exposes_hashes_only():
    artifacts = PhysicalArtifactRegistry()
    data = b"secret machine bytes"
    record = artifacts.register(
        artifact_id="job-1",
        kind="machine_job",
        content=data,
        generator="cam_pipeline",
        generator_receipt_sha256="a" * 64,
        metadata={"material": "acrylic"},
    )
    public = artifacts.describe("job-1")
    assert public["sha256"] == hashlib.sha256(data).hexdigest()
    assert public["size_bytes"] == len(data)
    assert "content" not in public
    assert data.decode() not in repr(public)
    assert artifacts.bytes("job-1") == data
    assert record.sha256 == public["sha256"]


def test_cnc_and_laser_accept_machine_job_not_firmware():
    operators = _operators()
    artifacts = PhysicalArtifactRegistry()
    artifacts.register(artifact_id="toolpath-1", kind="machine_job", content=b"toolpath", generator="cam")
    artifacts.register(artifact_id="fw-1", kind="firmware", content=b"firmware", generator="compiler")

    plan = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="cnc-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="start",
        artifact_id="toolpath-1",
        bindings={"fixture_id": "fixture-a"},
    )
    assert plan.payload["artifact_kind"] == "machine_job"
    assert plan.payload["bindings"] == {"fixture_id": "fixture-a"}

    with pytest.raises(FabricationValidationError, match="not valid"):
        artifacts.build_actuation_plan(
            operators=operators,
            operator_id="laser-1",
            project_id=PROJECT,
            mission_id=MISSION,
            action="start",
            artifact_id="fw-1",
        )


def test_programmer_flash_requires_registered_firmware_artifact():
    operators = _operators()
    artifacts = PhysicalArtifactRegistry()
    fw = artifacts.register(
        artifact_id="fielddeck-fw-v1",
        kind="firmware",
        content=b"compiled-binary",
        generator="pico_compile",
        generator_receipt_sha256="b" * 64,
    )
    plan = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        artifact_id=fw.artifact_id,
        bindings={"target_id": "pico-001", "verify": True},
    )
    assert plan.payload["artifact_sha256"] == fw.sha256
    assert plan.payload["bindings"]["target_id"] == "pico-001"
    assert artifacts.verify_plan_artifact(plan).artifact_id == fw.artifact_id


def test_robot_motion_is_bound_to_registered_motion_plan():
    operators = _operators()
    artifacts = PhysicalArtifactRegistry()
    motion = artifacts.register(
        artifact_id="pick-place-motion-v1",
        kind="motion_plan",
        content=b"motion-plan-bytes",
        generator="robot_planner",
        metadata={"workcell_state_sha256": "c" * 64},
    )
    plan = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="robot-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="execute_motion",
        artifact_id=motion.artifact_id,
        bindings={"workcell_state_sha256": "c" * 64},
    )
    assert plan.requires_human_grant is True
    assert plan.payload["artifact_kind"] == "motion_plan"


def test_stale_artifact_hash_in_plan_is_rejected():
    operators = _operators()
    artifacts = PhysicalArtifactRegistry()
    artifacts.register(artifact_id="fw-1", kind="firmware", content=b"firmware", generator="compiler")
    plan = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        artifact_id="fw-1",
    )
    tampered_payload = dict(plan.payload)
    tampered_payload["artifact_sha256"] = "0" * 64
    tampered = operators.plan(
        operator_id="probe-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        payload=tampered_payload,
    )
    with pytest.raises(FabricationValidationError, match="stale or tampered"):
        artifacts.verify_plan_artifact(tampered)


def test_instrument_output_enable_is_actuation_but_disable_is_risk_reduce():
    descriptor = bench_instrument_descriptor(operator_id="psu-1", display_name="Bench PSU")
    assert descriptor.action("enable_output").requires_human_grant is True
    assert descriptor.action("disable_output").action_class == "risk_reduce"
    assert descriptor.action("read").action_class == "observe"

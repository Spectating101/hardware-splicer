from __future__ import annotations

import subprocess

import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.physical_approval import PhysicalApprovalStore
from hardware_splicer.physical_artifact import PhysicalArtifactRegistry
from hardware_splicer.physical_authority import PhysicalPlanGrantStore
from hardware_splicer.physical_dispatch import PhysicalDispatcher
from hardware_splicer.physical_operator import PhysicalOperatorRegistry, programmer_descriptor
from hardware_splicer.picotool_programmer import PicotoolProgrammerHandle, PicotoolRunner

PROJECT = "fielddeck"
MISSION = "mission-picotool"
HUMAN = {"kind": "human", "id": "project-owner"}


class Runner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, *, timeout):
        self.calls.append((tuple(argv), timeout))
        return subprocess.CompletedProcess(list(argv), 0, stdout=b"ok\n", stderr=b"")


def _setup(tmp_path):
    artifacts = PhysicalArtifactRegistry()
    artifacts.register(artifact_id="fw-v1", kind="firmware", content=b"UF2-test-bytes", generator="pico_compile")
    runner = Runner()
    picotool = PicotoolRunner(
        "/usr/bin/picotool",
        device_selector=("--ser", "PICO1234"),
        runner=runner,
    )
    handle = PicotoolProgrammerHandle(
        operator_id="probe-pico",
        target_id="pico-001",
        artifacts=artifacts,
        picotool=picotool,
        firmware_suffix=".uf2",
    )
    operators = PhysicalOperatorRegistry()
    operators.register(programmer_descriptor(operator_id="probe-pico", display_name="Pico Programmer"), handle)
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    approvals = PhysicalApprovalStore(tmp_path / "approvals", operators=operators, grants=grants)
    dispatcher = PhysicalDispatcher(registry=operators, grants=grants)
    return artifacts, operators, approvals, dispatcher, runner


def test_target_inspection_is_read_only_and_fixed_argv(tmp_path):
    _artifacts, operators, _approvals, dispatcher, runner = _setup(tmp_path)
    plan = operators.plan(
        operator_id="probe-pico",
        project_id=PROJECT,
        mission_id=MISSION,
        action="inspect_target",
        payload={},
    )
    receipt = dispatcher.dispatch(plan)
    assert receipt["authority"] == "not_required"
    argv, _timeout = runner.calls[-1]
    assert argv == ("/usr/bin/picotool", "info", "-a", "--ser", "PICO1234")


def test_stage_then_human_approved_flash_runs_load_verify_without_execute(tmp_path):
    artifacts, operators, approvals, dispatcher, runner = _setup(tmp_path)
    stage = operators.plan(
        operator_id="probe-pico",
        project_id=PROJECT,
        mission_id=MISSION,
        action="stage_firmware",
        payload={"artifact_id": "fw-v1"},
    )
    dispatcher.dispatch(stage)

    flash = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="probe-pico",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        artifact_id="fw-v1",
        bindings={"target_id": "pico-001", "verify": True},
    )
    request = approvals.request(flash, requested_by={"kind": "agent", "id": "mission-agent"})
    approved = approvals.approve(request["request_id"], author=HUMAN)
    receipt = dispatcher.dispatch(flash, grant_id=approved["grant_id"])
    assert receipt["authority"] == "human_grant_consumed"
    assert receipt["result"]["verified"] is True
    assert receipt["result"]["auto_execute"] is False
    assert receipt["result"]["auto_reboot"] is False

    load_argv = runner.calls[-2][0]
    verify_argv = runner.calls[-1][0]
    assert load_argv[0:3] == ("/usr/bin/picotool", "load", "-v")
    assert "--ser" in load_argv and "PICO1234" in load_argv
    assert "-x" not in load_argv
    assert "reboot" not in load_argv
    assert verify_argv[0:2] == ("/usr/bin/picotool", "verify")


def test_flash_refuses_wrong_target_binding_after_authority_is_spent(tmp_path):
    artifacts, operators, approvals, dispatcher, runner = _setup(tmp_path)
    stage = operators.plan(
        operator_id="probe-pico",
        project_id=PROJECT,
        mission_id=MISSION,
        action="stage_firmware",
        payload={"artifact_id": "fw-v1"},
    )
    dispatcher.dispatch(stage)
    before = len(runner.calls)

    flash = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="probe-pico",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        artifact_id="fw-v1",
        bindings={"target_id": "some-other-board"},
    )
    request = approvals.request(flash, requested_by={"kind": "agent", "id": "mission-agent"})
    approved = approvals.approve(request["request_id"], author=HUMAN)
    with pytest.raises(FabricationValidationError, match="configured target identity"):
        dispatcher.dispatch(flash, grant_id=approved["grant_id"])
    assert len(runner.calls) == before


def test_flash_requires_staged_firmware(tmp_path):
    artifacts, operators, approvals, dispatcher, runner = _setup(tmp_path)
    flash = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="probe-pico",
        project_id=PROJECT,
        mission_id=MISSION,
        action="flash",
        artifact_id="fw-v1",
        bindings={"target_id": "pico-001"},
    )
    request = approvals.request(flash, requested_by={"kind": "agent", "id": "mission-agent"})
    approved = approvals.approve(request["request_id"], author=HUMAN)
    with pytest.raises(FabricationValidationError, match="staged before flash"):
        dispatcher.dispatch(flash, grant_id=approved["grant_id"])
    assert runner.calls == []

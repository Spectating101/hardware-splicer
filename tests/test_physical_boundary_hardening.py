from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.physical_approval import PhysicalApprovalStore
from hardware_splicer.physical_artifact import PhysicalArtifactRegistry
from hardware_splicer.physical_authority import PhysicalPlanGrantStore, execution_plan_sha256
from hardware_splicer.physical_dispatch import PhysicalDispatcher
from hardware_splicer.physical_operator import PhysicalOperatorRegistry, programmer_descriptor
from hardware_splicer.physical_operator_api import create_physical_operator_router
from hardware_splicer.physical_workbench import AgentPhysicalWorkbench
from hardware_splicer.picotool_programmer import PicotoolProgrammerHandle, PicotoolRunner

HUMAN = {"kind": "human", "id": "project-owner"}


class Handle:
    def execute(self, plan):
        return {"ok": True}


def _flash_plan():
    operators = PhysicalOperatorRegistry()
    operators.register(programmer_descriptor(operator_id="probe-1", display_name="Debug Probe"), Handle())
    return operators.plan(
        operator_id="probe-1",
        project_id="fielddeck",
        mission_id="mission-hardening",
        action="flash",
        payload={"artifact_id": "fw-1", "artifact_sha256": "a" * 64},
    )


def test_physical_grant_id_is_path_safe(tmp_path):
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    for malicious in (
        "pg-../../outside",
        "pg-/tmp/outside",
        "pg-..\\outside",
        "pg-not-a-uuid",
        "pg-" + "a" * 31,
        "pg-" + "a" * 33,
    ):
        with pytest.raises(FabricationValidationError, match="grant id"):
            grants.get(malicious)


def test_execution_plan_refuses_mutated_nested_payload(tmp_path):
    plan = _flash_plan()
    original = plan.payload_sha256
    plan.payload["artifact_sha256"] = "b" * 64
    assert plan.payload_sha256 == original
    with pytest.raises(FabricationValidationError, match="payload hash"):
        execution_plan_sha256(plan)
    grants = PhysicalPlanGrantStore(tmp_path / "grants")
    with pytest.raises(FabricationValidationError, match="payload hash"):
        grants.issue(plan, author=HUMAN)


def test_validation_errors_are_http_422_not_authority_409(tmp_path):
    operators = PhysicalOperatorRegistry()
    artifacts = PhysicalArtifactRegistry()
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
    response = TestClient(app).get("/v1/fabrication/operators?kind=definitely-not-a-kind")
    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_request"


def test_picotool_v0_accepts_only_serial_target_selector():
    runner = PicotoolRunner("picotool", device_selector=("--ser", "PICO1234"), runner=lambda argv, timeout: None)
    assert runner.device_selector == ("--ser", "PICO1234")

    for selector in (
        ("-f",),
        ("-F",),
        ("-x",),
        ("--bus", "1"),
        ("--ser", "-f"),
        ("--ser", "A", "-x"),
    ):
        with pytest.raises(FabricationValidationError, match="selector"):
            PicotoolRunner("picotool", device_selector=selector, runner=lambda argv, timeout: None)


def test_picotool_v0_is_uf2_only(tmp_path):
    class DummyRunner:
        def __call__(self, argv, *, timeout):
            raise AssertionError("unsafe suffix must fail before execution")

    runner = PicotoolRunner("picotool", runner=DummyRunner())
    with pytest.raises(FabricationValidationError, match="UF2"):
        runner.flash_and_verify(b"firmware", suffix=".bin")

    artifacts = PhysicalArtifactRegistry()
    handle = PicotoolProgrammerHandle(
        operator_id="probe-1",
        target_id="pico-1",
        artifacts=artifacts,
        picotool=runner,
    )
    assert handle.firmware_suffix == ".uf2"
    with pytest.raises(FabricationValidationError, match="UF2"):
        PicotoolProgrammerHandle(
            operator_id="probe-2",
            target_id="pico-2",
            artifacts=artifacts,
            picotool=runner,
            firmware_suffix=".bin",
        )

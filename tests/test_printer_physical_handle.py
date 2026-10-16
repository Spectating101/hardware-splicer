from __future__ import annotations

import pytest

from hardware_splicer.fabrication_operator import FabricationGrantStore, FabricationValidationError
from hardware_splicer.physical_approval import PhysicalApprovalStore
from hardware_splicer.physical_artifact import PhysicalArtifactRegistry
from hardware_splicer.physical_authority import PhysicalPlanGrantStore
from hardware_splicer.physical_dispatch import PhysicalDispatcher
from hardware_splicer.physical_operator import PhysicalOperatorRegistry, printer_descriptor
from hardware_splicer.printer_operator import FabricationPrinter, OctoPrintBackend
from hardware_splicer.printer_physical_handle import PrinterPhysicalHandle

PROJECT = "fielddeck"
MISSION = "mission-printer-generic"
HUMAN = {"kind": "human", "id": "project-owner"}
GCODE = b"; test gcode only\nG28\n"


class Transport:
    def __init__(self):
        self.calls = []

    def upload(self, path, *, filename, data, fields):
        self.calls.append(("upload", path, filename, data, dict(fields)))
        return {"files": {"local": {"path": filename}}}

    def request(self, method, path, *, json_body=None):
        self.calls.append(("request", method, path, json_body))
        return {"ok": True}


def _setup(tmp_path):
    artifacts = PhysicalArtifactRegistry()
    artifacts.register(artifact_id="case-v1", kind="gcode", content=GCODE, generator="prusa_slicer")
    old_grants = FabricationGrantStore(tmp_path / "printer-grants")
    transport = Transport()
    printer = FabricationPrinter(
        printer_id="printer-1",
        backend=OctoPrintBackend(),
        transport=transport,
        grants=old_grants,
    )
    handle = PrinterPhysicalHandle(printer=printer, artifacts=artifacts)
    operators = PhysicalOperatorRegistry()
    operators.register(printer_descriptor(operator_id="printer-1", display_name="Lab Printer"), handle)
    plan_grants = PhysicalPlanGrantStore(tmp_path / "plan-grants")
    dispatcher = PhysicalDispatcher(registry=operators, grants=plan_grants)
    approvals = PhysicalApprovalStore(tmp_path / "approvals", operators=operators, grants=plan_grants)
    return artifacts, operators, dispatcher, approvals, transport


def test_generic_printer_requires_non_actuating_stage_before_start(tmp_path):
    artifacts, operators, dispatcher, approvals, transport = _setup(tmp_path)
    start = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="printer-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="start",
        artifact_id="case-v1",
    )
    request = approvals.request(start, requested_by={"kind": "agent", "id": "mission-agent"})
    approved = approvals.approve(request["request_id"], author=HUMAN)
    with pytest.raises(FabricationValidationError, match="staged before actuation"):
        dispatcher.dispatch(start, grant_id=approved["grant_id"])
    # Authority was correctly spent even though the private handle refused to start.
    assert not any(call[0] == "request" and call[2] == "/api/job" for call in transport.calls)


def test_stage_then_human_approved_start_uses_generic_dispatcher(tmp_path):
    artifacts, operators, dispatcher, approvals, transport = _setup(tmp_path)
    stage = operators.plan(
        operator_id="printer-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="stage",
        payload={"artifact_id": "case-v1", "filename": "case-v1.gcode"},
    )
    staged_receipt = dispatcher.dispatch(stage)
    assert staged_receipt["authority"] == "not_required"
    assert transport.calls[0][0] == "upload"

    start = artifacts.build_actuation_plan(
        operators=operators,
        operator_id="printer-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="start",
        artifact_id="case-v1",
    )
    request = approvals.request(start, requested_by={"kind": "agent", "id": "mission-agent"})
    approved = approvals.approve(request["request_id"], author=HUMAN)
    receipt = dispatcher.dispatch(start, grant_id=approved["grant_id"])
    assert receipt["authority"] == "human_grant_consumed"
    assert transport.calls[-1] == ("request", "POST", "/api/job", {"command": "start"})


def test_stage_rejects_non_gcode_artifact(tmp_path):
    artifacts, operators, dispatcher, _approvals, _transport = _setup(tmp_path)
    artifacts.register(artifact_id="fw-1", kind="firmware", content=b"firmware", generator="compiler")
    stage = operators.plan(
        operator_id="printer-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="stage",
        payload={"artifact_id": "fw-1"},
    )
    with pytest.raises(FabricationValidationError, match="G-code"):
        dispatcher.dispatch(stage)

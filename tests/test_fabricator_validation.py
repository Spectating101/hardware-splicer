from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.fabricator_validation_workbench import FabricatorValidationWorkbench
from hardware_splicer.physical_evidence import PhysicalEvidenceKind, PhysicalEvidenceRecord
from hardware_splicer.product_api import create_product_app
from hardware_splicer.validation_procedure import (
    MappingEvidenceResolver,
    ValidationCriterion,
    ValidationProcedure,
    ValidationProcedureEvaluator,
    ValidationProcedureRegistry,
    ValidationStep,
)


def _procedure() -> ValidationProcedure:
    return ValidationProcedure(
        procedure_id="logger-acceptance-v1",
        project_id="logger",
        candidate_revision="r2",
        steps=(
            ValidationStep(
                step_id="rail-3v3",
                requirement_ids=("power.3v3",),
                evidence_kind=PhysicalEvidenceKind.ELECTRICAL,
                target_ids=("rail-3v3",),
                criteria=(ValidationCriterion("numeric_range", "voltage_v", minimum=3.2, maximum=3.4),),
            ),
            ValidationStep(
                step_id="boot-log",
                requirement_ids=("firmware.boot",),
                evidence_kind=PhysicalEvidenceKind.INSPECTION,
                target_ids=("serial-console",),
                criteria=(
                    ValidationCriterion("text_contains", "log", expected="READY"),
                    ValidationCriterion("text_not_contains", "log", expected="PANIC"),
                ),
            ),
        ),
    )


def _evidence(
    procedure: ValidationProcedure,
    *,
    evidence_id: str,
    step_id: str,
    kind: PhysicalEvidenceKind,
    targets: list[str],
    measured_values: dict,
    passed: bool,
    revision: str = "r2",
    procedure_hash: str | None = None,
) -> PhysicalEvidenceRecord:
    return PhysicalEvidenceRecord(
        evidence_id=evidence_id,
        project_id="logger",
        candidate_revision=revision,
        kind=kind,
        target_ids=targets,
        procedure_id=procedure.procedure_id,
        passed=passed,
        captured_at="2026-10-17T02:00:00+08:00",
        operator="bench-lead",
        measured_values=measured_values,
        acceptance_criteria={"frozen_procedure_sha256": procedure.sha256},
        metadata={
            "simulated": False,
            "validation_step_id": step_id,
            "validation_procedure_sha256": procedure_hash or procedure.sha256,
        },
    )


def _workbench(records):
    registry = ValidationProcedureRegistry()
    procedure = _procedure()
    registry.register(procedure)
    evaluator = ValidationProcedureEvaluator(
        procedures=registry,
        evidence=MappingEvidenceResolver(records),
    )
    return procedure, FabricatorValidationWorkbench(procedures=registry, evaluator=evaluator)


def test_frozen_procedure_recomputes_measured_values_and_passes_complete_scope():
    procedure = _procedure()
    records = [
        _evidence(
            procedure,
            evidence_id="ev-rail",
            step_id="rail-3v3",
            kind=PhysicalEvidenceKind.ELECTRICAL,
            targets=["rail-3v3"],
            measured_values={"voltage_v": 3.31},
            passed=True,
        ),
        _evidence(
            procedure,
            evidence_id="ev-boot",
            step_id="boot-log",
            kind=PhysicalEvidenceKind.INSPECTION,
            targets=["serial-console"],
            measured_values={"log": "BOOT\nREADY\n"},
            passed=True,
        ),
    ]
    procedure, workbench = _workbench(records)
    result = workbench.evaluate(procedure.procedure_id, evidence_ids=["ev-rail", "ev-boot"])
    assert result["validation_scope_passed"] is True
    assert all(step["status"] == "PASS" for step in result["steps"])
    assert result["whole_device_physical_correctness"] == "UNPROVEN"
    assert result["grants_physical_authority"] is False


def test_forged_pass_flag_is_rejected_when_measurement_is_outside_frozen_range():
    procedure = _procedure()
    bad = _evidence(
        procedure,
        evidence_id="ev-bad",
        step_id="rail-3v3",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        targets=["rail-3v3"],
        measured_values={"voltage_v": 4.7},
        passed=True,
    )
    procedure, workbench = _workbench([bad])
    result = workbench.evaluate(procedure.procedure_id, evidence_ids=["ev-bad"])
    rail = next(step for step in result["steps"] if step["step_id"] == "rail-3v3")
    assert rail["recomputed_passed"] is False
    assert any("passed flag disagrees" in blocker for blocker in rail["blockers"])
    assert result["validation_scope_passed"] is False


def test_stale_procedure_hash_and_wrong_revision_are_rejected():
    procedure = _procedure()
    stale = _evidence(
        procedure,
        evidence_id="ev-stale",
        step_id="rail-3v3",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        targets=["rail-3v3"],
        measured_values={"voltage_v": 3.3},
        passed=True,
        procedure_hash="0" * 64,
    )
    procedure, workbench = _workbench([stale])
    with pytest.raises(FabricationValidationError, match="frozen validation procedure"):
        workbench.evaluate(procedure.procedure_id, evidence_ids=["ev-stale"])

    wrong = _evidence(
        procedure,
        evidence_id="ev-wrong-revision",
        step_id="rail-3v3",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        targets=["rail-3v3"],
        measured_values={"voltage_v": 3.3},
        passed=True,
        revision="r1",
    )
    procedure, workbench = _workbench([wrong])
    with pytest.raises(FabricationValidationError, match="different candidate revision"):
        workbench.evaluate(procedure.procedure_id, evidence_ids=["ev-wrong-revision"])


def test_missing_or_duplicate_step_evidence_cannot_pass():
    procedure = _procedure()
    first = _evidence(
        procedure,
        evidence_id="ev-rail-a",
        step_id="rail-3v3",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        targets=["rail-3v3"],
        measured_values={"voltage_v": 3.3},
        passed=True,
    )
    second = _evidence(
        procedure,
        evidence_id="ev-rail-b",
        step_id="rail-3v3",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        targets=["rail-3v3"],
        measured_values={"voltage_v": 3.3},
        passed=True,
    )
    procedure, workbench = _workbench([first, second])
    result = workbench.evaluate(procedure.procedure_id, evidence_ids=["ev-rail-a", "ev-rail-b"])
    statuses = {step["step_id"]: step["status"] for step in result["steps"]}
    assert statuses == {"rail-3v3": "MISSING_OR_AMBIGUOUS_EVIDENCE", "boot-log": "MISSING_OR_AMBIGUOUS_EVIDENCE"}
    assert result["validation_scope_passed"] is False


def test_agent_api_lists_and_evaluates_but_has_no_procedure_mutation_route():
    procedure = _procedure()
    rail = _evidence(
        procedure,
        evidence_id="ev-rail",
        step_id="rail-3v3",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        targets=["rail-3v3"],
        measured_values={"voltage_v": 3.3},
        passed=True,
    )
    boot = _evidence(
        procedure,
        evidence_id="ev-boot",
        step_id="boot-log",
        kind=PhysicalEvidenceKind.INSPECTION,
        targets=["serial-console"],
        measured_values={"log": "READY"},
        passed=True,
    )
    procedure, workbench = _workbench([rail, boot])
    app = create_product_app(fabricator_validation_workbench=workbench)
    client = TestClient(app)
    listed = client.get("/v1/fabricator/validation/procedures")
    assert listed.status_code == 200
    assert listed.json()["procedures"][0]["procedure_sha256"] == procedure.sha256
    assessed = client.post(
        f"/v1/fabricator/validation/procedures/{procedure.procedure_id}/evaluate",
        json={"evidence_ids": ["ev-rail", "ev-boot"]},
    )
    assert assessed.status_code == 200
    assert assessed.json()["assessment"]["validation_scope_passed"] is True
    paths = set(app.openapi()["paths"])
    assert "/v1/fabricator/validation/procedures" in paths
    assert "/v1/fabricator/validation/procedures/create" not in paths
    assert all("threshold" not in path for path in paths if path.startswith("/v1/fabricator/validation/"))


def test_validation_routes_fail_closed_without_server_runtime():
    client = TestClient(create_product_app())
    response = client.get("/v1/fabricator/validation/procedures")
    assert response.status_code == 503

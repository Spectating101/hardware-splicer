from __future__ import annotations

from hardware_splicer.engineering_execution import (
    ExecutionOperation,
    ExecutionResult,
    ExecutionStatus,
    execution_manifest,
)
from hardware_splicer.engineering_execution_evidence import attach_execution_evidence
from hardware_splicer.machine_project import AuthorityState, VerificationStatus
from hardware_splicer.machine_project_seed import machine_project_from_intake


def _project():
    return machine_project_from_intake(
        {
            "project_name": "execution-evidence-project",
            "goal": "Verify software checks without promoting physical authority.",
            "available_parts": [{"name": "controller", "type": "controller"}],
        }
    )


def _result(status: ExecutionStatus) -> ExecutionResult:
    return ExecutionResult(
        execution_id="compile-main",
        operation=ExecutionOperation.PYTHON_COMPILE,
        status=status,
        argv=["python", "-m", "compileall", "src"],
        workspace="/workspace",
        target="/workspace/src",
        tool="python",
        tool_available=True,
        returncode=0 if status == ExecutionStatus.PASSED else 1,
        stdout="compiled" if status == ExecutionStatus.PASSED else "",
        stderr="" if status == ExecutionStatus.PASSED else "syntax error",
        duration_s=0.4,
        output_hashes={},
        metadata={
            "network_authorized": False,
            "device_access_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
        },
    )


def test_passing_execution_closes_software_verification_only() -> None:
    project = attach_execution_evidence(_project(), execution_manifest(_result(ExecutionStatus.PASSED)))

    evidence = next(row for row in project.evidence if row.evidence_id == "execution-evidence-compile-main")
    verification = next(row for row in project.verifications if row.verification_id == "execution-verification-compile-main")

    assert evidence.authority == AuthorityState.VERIFIED
    assert evidence.simulated is True
    assert evidence.metadata["software_only"] is True
    assert evidence.metadata["physical_evidence"] is False
    assert verification.status == VerificationStatus.PASSED
    assert verification.evidence_ids == [evidence.evidence_id]
    assert not [
        row
        for row in project.evidence
        if not row.simulated and row.authority in {AuthorityState.MEASURED, AuthorityState.VERIFIED, AuthorityState.AUTHORIZED}
    ]
    assert project.assess_release().achieved_state.value != "operationally_authorized"


def test_failed_execution_blocks_its_verification() -> None:
    project = attach_execution_evidence(_project(), _result(ExecutionStatus.FAILED))

    verification = next(row for row in project.verifications if row.verification_id == "execution-verification-compile-main")
    evidence = next(row for row in project.evidence if row.evidence_id == "execution-evidence-compile-main")

    assert verification.status == VerificationStatus.FAILED
    assert evidence.authority == AuthorityState.OBSERVED
    assert any(row.code == "verification_not_passed" for row in project.assess_release().blockers)


def test_execution_evidence_update_is_idempotent() -> None:
    first = attach_execution_evidence(_project(), _result(ExecutionStatus.FAILED))
    second = attach_execution_evidence(first, _result(ExecutionStatus.PASSED))

    assert len([row for row in second.evidence if row.evidence_id == "execution-evidence-compile-main"]) == 1
    assert len([row for row in second.verifications if row.verification_id == "execution-verification-compile-main"]) == 1
    verification = next(row for row in second.verifications if row.verification_id == "execution-verification-compile-main")
    assert verification.status == VerificationStatus.PASSED
    manifests = second.discipline_payloads["engineering_execution_evidence"]["manifests"]
    assert len([row for row in manifests if row["execution_id"] == "compile-main"]) == 1


def test_unknown_target_ids_do_not_create_dangling_references() -> None:
    project = attach_execution_evidence(
        _project(),
        _result(ExecutionStatus.PASSED),
        target_ids=["unknown-target"],
    )

    evidence = next(row for row in project.evidence if row.evidence_id == "execution-evidence-compile-main")
    assert evidence.supports == [project.project_id]
    assert evidence.metadata["unknown_requested_target_ids"] == ["unknown-target"]
    assert not [row for row in project.traceability_issues() if row.code == "invalid_ref"]

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hardware_splicer.machine_project import MachineProject
from hardware_splicer.physical_evidence import (
    AuthorizationDecision,
    AuthorizationScope,
    AuthorizationStatus,
    CalibrationRecord,
    PhysicalEvidenceKind,
    PhysicalEvidenceRecord,
    PhysicalOperation,
    assess_physical_authorization,
    attach_physical_evidence,
)
from hardware_splicer.scoped_release import assess_scoped_release


AS_OF = datetime(2026, 8, 4, 3, 0, tzinfo=timezone.utc)


def _plan(revision: str = "r2", content_hash: str = "sha256:release-r2") -> dict:
    return {
        "candidate_revision": revision,
        "machine_project": {
            "project_id": "physical-rover",
            "artifacts": [
                {
                    "artifact_id": "release-bundle",
                    "kind": "release_bundle",
                    "ref": "release/rover-r2.zip",
                    "authority": "declared",
                    "metadata": {
                        "revision": revision,
                        "content_hash": content_hash,
                    },
                }
            ],
        },
    }


def _calibrations(expires_at: str = "2027-01-01T00:00:00+00:00") -> list[CalibrationRecord]:
    return [
        CalibrationRecord(
            calibration_id="cal-dmm-2026",
            instrument_id="dmm-01",
            calibrated_at="2026-07-01T00:00:00+00:00",
            expires_at=expires_at,
            certificate_ref="lab://cal/dmm-01/2026",
        ),
        CalibrationRecord(
            calibration_id="cal-force-2026",
            instrument_id="force-01",
            calibrated_at="2026-07-01T00:00:00+00:00",
            expires_at=expires_at,
            certificate_ref="lab://cal/force-01/2026",
        ),
    ]


def _evidence(
    *,
    revision: str = "r2",
    content_hash: str = "sha256:release-r2",
) -> list[PhysicalEvidenceRecord]:
    common = {
        "project_id": "physical-rover",
        "candidate_revision": revision,
        "captured_at": "2026-08-04T02:30:00+00:00",
        "operator": "bench-operator",
        "artifact_hashes": {"release-bundle": content_hash},
        "environment": {"ambient_temperature_c": 24.0},
        "fixture_state": {"wheels_raised": True, "current_limit_a": 1.0},
        "interlock_state": {"emergency_stop_verified": True},
        "raw_refs": ["lab://runs/rover-r2"],
    }
    return [
        PhysicalEvidenceRecord(
            evidence_id="rail-test",
            kind=PhysicalEvidenceKind.ELECTRICAL,
            target_ids=["physical-rover"],
            procedure_id="procedure-current-limited-power",
            passed=True,
            measured_values={"logic_rail_minimum_v": 4.92, "peak_current_a": 0.72},
            acceptance_criteria={"logic_rail_minimum_v": {"minimum": 4.75}},
            instrument_ids=["dmm-01"],
            calibration_ids=["cal-dmm-2026"],
            **common,
        ),
        PhysicalEvidenceRecord(
            evidence_id="interlock-test",
            kind=PhysicalEvidenceKind.SAFETY_INTERLOCK,
            target_ids=["physical-rover"],
            procedure_id="procedure-emergency-stop",
            passed=True,
            measured_values={"stop_latency_ms": 38},
            acceptance_criteria={"stop_latency_ms": {"maximum": 100}},
            instrument_ids=["force-01"],
            calibration_ids=["cal-force-2026"],
            **common,
        ),
    ]


def _decision(
    *,
    revision: str = "r2",
    content_hash: str = "sha256:release-r2",
    status: AuthorizationStatus = AuthorizationStatus.AUTHORIZED,
    expires_at: str = "2026-09-01T00:00:00+00:00",
) -> AuthorizationDecision:
    return AuthorizationDecision(
        authorization_id="auth-rover-r2-bench",
        status=status,
        scope=AuthorizationScope(
            scope_id="scope-rover-r2-bench",
            project_id="physical-rover",
            candidate_revision=revision,
            operations=[PhysicalOperation.BENCH_POWER, PhysicalOperation.RESTRAINED_MOTION],
            target_ids=["physical-rover"],
            artifact_hashes={"release-bundle": content_hash},
            operating_envelope={
                "maximum_supply_voltage_v": 12.6,
                "maximum_current_limit_a": 2.0,
                "wheels_raised": True,
                "maximum_motion_duration_s": 10,
            },
            environment_limits={"ambient_temperature_c": {"minimum": 15, "maximum": 30}},
            required_evidence_kinds=[
                PhysicalEvidenceKind.ELECTRICAL,
                PhysicalEvidenceKind.SAFETY_INTERLOCK,
            ],
            limitations=["No floor operation", "No unattended operation"],
        ),
        reviewer="qualified-reviewer",
        reviewed_at="2026-08-04T02:45:00+00:00",
        evidence_ids=["rail-test", "interlock-test"],
        reason="Current-limited bench power and restrained wheel motion are supported by the attached evidence.",
        expires_at=expires_at,
    )


def _closed_machine_project() -> MachineProject:
    return MachineProject.model_validate(
        {
            "project_id": "physical-rover",
            "name": "Physical rover",
            "purpose": "Validate strict physical release scope.",
            "requested_release_state": "bench_ready",
            "verifications": [
                {
                    "verification_id": "design-verification",
                    "name": "Design verification",
                    "method_type": "analysis",
                    "status": "passed",
                    "target_ids": ["physical-rover"],
                    "evidence_ids": ["design-evidence"],
                    "procedure": "Run the complete design verification suite.",
                    "acceptance_criteria": {"all_checks_pass": True},
                    "authority": "verified",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "design-evidence",
                    "kind": "software_design_verification",
                    "basis": "Design verification suite passed.",
                    "supports": ["physical-rover"],
                    "authority": "verified",
                    "simulated": True,
                }
            ],
        }
    )


def test_valid_human_decision_is_applicable_only_to_exact_scope() -> None:
    package = assess_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        evidence=_evidence(),
        decision=_decision(),
        as_of=AS_OF,
    )

    assert package.assessment.applicable is True
    assert package.assessment.status == "authorized"
    assert package.assessment.authorized_operations == [
        PhysicalOperation.BENCH_POWER,
        PhysicalOperation.RESTRAINED_MOTION,
    ]
    assert package.assessment.blockers == []
    assert package.assessment.metadata["automatic_authorization"] is False
    assert package.assessment.metadata["authorization_carries_across_revisions"] is False


def test_stale_revision_and_artifact_hash_invalidate_authorization() -> None:
    package = assess_physical_authorization(
        _plan(revision="r3", content_hash="sha256:release-r3"),
        calibrations=_calibrations(),
        evidence=_evidence(revision="r2", content_hash="sha256:release-r2"),
        decision=_decision(revision="r2", content_hash="sha256:release-r2"),
        as_of=AS_OF,
    )

    assert package.assessment.applicable is False
    rendered = "\n".join(package.assessment.blockers)
    assert "not candidate r3" in rendered
    assert "stale hash" in rendered
    assert "Authorization artifact boundary does not match" in rendered


def test_expired_calibration_and_decision_block_scope() -> None:
    package = assess_physical_authorization(
        _plan(),
        calibrations=_calibrations(expires_at="2026-08-01T00:00:00+00:00"),
        evidence=_evidence(),
        decision=_decision(expires_at="2026-08-02T00:00:00+00:00"),
        as_of=AS_OF,
    )

    rendered = "\n".join(package.assessment.blockers)
    assert "Calibration cal-dmm-2026 expired" in rendered
    assert "Calibration cal-force-2026 expired" in rendered
    assert "Authorization auth-rover-r2-bench is expired" in rendered
    assert package.assessment.applicable is False


def test_measured_evidence_without_human_decision_never_authorizes() -> None:
    package = assess_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        evidence=_evidence(),
        decision=None,
        as_of=AS_OF,
    )

    assert package.assessment.applicable is False
    assert package.assessment.authorized_operations == []
    assert package.assessment.blockers == ["No human authorization decision is supplied."]
    assert package.assessment.metadata["software_evidence_accepted"] is False
    assert package.assessment.metadata["simulation_evidence_accepted"] is False


def test_scoped_release_requires_requested_operation_inside_authorized_scope() -> None:
    project = _closed_machine_project()
    package = assess_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        evidence=_evidence(),
        decision=_decision(),
        as_of=AS_OF,
    )

    allowed = assess_scoped_release(
        project,
        package,
        requested_operations=[PhysicalOperation.BENCH_POWER],
    )
    denied = assess_scoped_release(
        project,
        package,
        requested_operations=[PhysicalOperation.FIELD_RELEASE],
    )

    assert allowed.allowed is True
    assert allowed.allowed_operations == [PhysicalOperation.BENCH_POWER]
    assert allowed.metadata["measured_evidence_alone_sufficient"] is False
    assert denied.allowed is False
    assert any("field_release" in row for row in denied.blockers)


def test_physical_records_attach_as_non_simulated_evidence_without_synthesizing_authority() -> None:
    project = _closed_machine_project()
    package = assess_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        evidence=_evidence(),
        decision=None,
        as_of=AS_OF,
    )

    updated = attach_physical_evidence(project, package)
    physical = [row for row in updated.evidence if row.kind == "physical_evidence_record"]

    assert len(physical) == 2
    assert all(row.simulated is False for row in physical)
    assert all(row.authority.value == "measured" for row in physical)
    assert updated.metadata["physical_authorization_applicable"] is False
    assert updated.metadata["automatic_authorization"] is False


def test_proposed_claim_cannot_masquerade_as_physical_evidence() -> None:
    with pytest.raises(ValueError, match="physical evidence authority"):
        PhysicalEvidenceRecord(
            evidence_id="fake",
            project_id="physical-rover",
            candidate_revision="r2",
            kind=PhysicalEvidenceKind.INSPECTION,
            target_ids=["physical-rover"],
            procedure_id="procedure-fake",
            passed=True,
            captured_at="2026-08-04T00:00:00+00:00",
            operator="operator",
            authority="proposed",
        )

from __future__ import annotations

from datetime import datetime, timezone

from hardware_splicer.machine_project import MachineProject
from hardware_splicer.physical_evidence_plan_update import apply_physical_evidence_to_plan


AS_OF = datetime(2026, 8, 4, 3, 0, tzinfo=timezone.utc)


def _project() -> MachineProject:
    return MachineProject.model_validate(
        {
            "project_id": "physical-update",
            "name": "Physical update",
            "purpose": "Test physical plan update.",
            "requested_release_state": "bench_ready",
            "verifications": [
                {
                    "verification_id": "design-verification",
                    "name": "Design verification",
                    "method_type": "analysis",
                    "status": "passed",
                    "target_ids": ["physical-update"],
                    "evidence_ids": ["design-evidence"],
                    "procedure": "Run design verification.",
                    "acceptance_criteria": {"passed": True},
                    "authority": "verified",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "design-evidence",
                    "kind": "software_design_verification",
                    "basis": "Design verification passed.",
                    "supports": ["physical-update"],
                    "authority": "verified",
                    "simulated": True,
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "release",
                    "kind": "release_bundle",
                    "ref": "release/r1.zip",
                    "authority": "declared",
                    "metadata": {"content_hash": "sha256:r1"},
                }
            ],
        }
    )


def _plan() -> dict:
    return {
        "candidate_revision": "r1",
        "machine_project": _project().model_dump(mode="json"),
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"topology_id": "generic", "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
        "scenario": {"compile_spec": {}},
    }


def _calibrations() -> list[dict]:
    return [
        {
            "calibration_id": "cal-dmm",
            "instrument_id": "dmm",
            "calibrated_at": "2026-07-01T00:00:00+00:00",
            "expires_at": "2027-01-01T00:00:00+00:00",
        }
    ]


def _evidence(*, passed: bool = True) -> list[dict]:
    return [
        {
            "evidence_id": "rail",
            "project_id": "physical-update",
            "candidate_revision": "r1",
            "kind": "electrical_measurement",
            "target_ids": ["physical-update"],
            "procedure_id": "power-test",
            "passed": passed,
            "captured_at": "2026-08-04T02:00:00+00:00",
            "operator": "operator",
            "instrument_ids": ["dmm"],
            "calibration_ids": ["cal-dmm"],
            "artifact_hashes": {"release": "sha256:r1"},
            "fixture_state": {"current_limited": True},
            "interlock_state": {"emergency_stop_verified": True},
        }
    ]


def _decision() -> dict:
    return {
        "authorization_id": "auth-r1",
        "status": "authorized",
        "scope": {
            "scope_id": "scope-r1",
            "project_id": "physical-update",
            "candidate_revision": "r1",
            "operations": ["bench_power"],
            "target_ids": ["physical-update"],
            "artifact_hashes": {"release": "sha256:r1"},
            "operating_envelope": {"maximum_voltage_v": 5.0, "current_limited": True},
            "required_evidence_kinds": ["electrical_measurement"],
        },
        "reviewer": "reviewer",
        "reviewed_at": "2026-08-04T02:15:00+00:00",
        "evidence_ids": ["rail"],
        "reason": "Bench power is supported inside the stated envelope.",
        "expires_at": "2026-09-01T00:00:00+00:00",
    }


def test_authorized_scope_updates_plan_without_global_authority_flags() -> None:
    updated = apply_physical_evidence_to_plan(
        _plan(),
        calibrations=_calibrations(),
        evidence=_evidence(),
        decision=_decision(),
        requested_operations=["bench_power"],
        as_of=AS_OF,
    )

    assert updated["physical_evidence_package"]["assessment"]["applicable"] is True
    assert updated["scoped_release_assessment"]["allowed"] is True
    assert updated["scoped_release_assessment"]["allowed_operations"] == ["bench_power"]
    assert updated["engineering_readiness"]["scoped_release_allowed"] is True
    assert updated["engineering_readiness"]["scoped_authorized_operations"] == ["bench_power"]
    assert updated["engineering_readiness"]["power_on_authorized"] is False
    assert updated["engineering_readiness"]["motion_authorized"] is False
    assert updated["engineering_readiness"]["release_authorized"] is False
    assert updated["scenario"]["physical_authorization"]["global_authority_flags_unchanged"] is True
    project = MachineProject.model_validate(updated["machine_project"])
    assert project.metadata["scoped_release_allowed"] is True
    assert project.metadata["authorized_operations"] == ["bench_power"]
    assert project.metadata["automatic_authorization"] is False


def test_failed_or_unsigned_physical_evidence_adds_release_blocker() -> None:
    updated = apply_physical_evidence_to_plan(
        _plan(),
        calibrations=_calibrations(),
        evidence=_evidence(passed=False),
        decision=None,
        requested_operations=["bench_power"],
        as_of=AS_OF,
    )

    assert updated["physical_evidence_package"]["assessment"]["applicable"] is False
    assert updated["scoped_release_assessment"]["allowed"] is False
    status = updated["engineering_status"]
    assert status["overall_status"] == "blocked"
    blocker = next(row for row in status["blockers"] if row["blocker_id"] == "physical-authorization-scope")
    assert "No human authorization decision" in blocker["message"]
    assert "did not pass" in blocker["message"]
    assert status["blocker_groups"]["release"] == ["physical-authorization-scope"]
    assert updated["engineering_readiness"]["scoped_release_allowed"] is False
    assert updated["engineering_readiness"]["automatic_authorization"] is False

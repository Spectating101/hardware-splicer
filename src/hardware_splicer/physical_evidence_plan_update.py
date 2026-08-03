"""Apply calibrated physical evidence to a guided plan without broad authority flags."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Mapping

from .engineering_status import (
    EngineeringStatus,
    StatusBlocker,
    StatusSeverity,
    build_engineering_status,
)
from .machine_project import MachineProject
from .physical_evidence import (
    AuthorizationDecision,
    CalibrationRecord,
    PhysicalEvidenceRecord,
    PhysicalOperation,
    assess_physical_authorization,
    attach_physical_evidence,
)
from .scoped_release import ScopedReleaseAssessment, assess_scoped_release


PHYSICAL_PLAN_UPDATE_SCHEMA = "hardware_splicer.physical_evidence_plan_update.v1"


def _release_blocker(
    package_blockers: Iterable[str],
    release_blockers: Iterable[str],
    *,
    project_id: str,
) -> StatusBlocker:
    messages = list(dict.fromkeys([*package_blockers, *release_blockers]))
    return StatusBlocker(
        blocker_id="physical-authorization-scope",
        category="release",
        severity=StatusSeverity.ERROR,
        message=(
            "Physical operation scope is not authorized: "
            + (" ".join(messages) if messages else "required physical evidence or human decision is missing.")
        ),
        target_ids=[project_id],
        required_inputs=[
            "candidate revision",
            "artifact hashes",
            "operating envelope",
            "calibrated physical evidence",
            "human authorization decision",
        ],
        required_evidence=[
            "calibration certificates",
            "raw physical measurements",
            "fixture and interlock state",
            "signed scoped authorization decision",
        ],
        metadata={
            "automatic_authorization": False,
            "global_authority_flags_unchanged": True,
        },
    )


def _status_with_physical_scope(
    status: EngineeringStatus,
    release: ScopedReleaseAssessment | None,
    package_blockers: Iterable[str],
) -> EngineeringStatus:
    if release is not None and release.allowed:
        summary = dict(status.summary)
        summary["physical_scope_authorized"] = True
        summary["authorized_operation_count"] = len(release.allowed_operations)
        metadata = dict(status.metadata)
        metadata.update(
            {
                "physical_scope_authorized": True,
                "authorized_operations": [row.value for row in release.allowed_operations],
                "global_authority_flags_unchanged": True,
            }
        )
        return status.model_copy(update={"summary": summary, "metadata": metadata}, deep=True)

    blocker = _release_blocker(
        package_blockers,
        release.blockers if release is not None else [],
        project_id=status.project_id,
    )
    existing = {row.blocker_id: row for row in status.blockers}
    existing[blocker.blocker_id] = blocker
    blockers = list(existing.values())
    groups = {key: list(values) for key, values in status.blocker_groups.items()}
    release_ids = list(groups.get("release") or [])
    if blocker.blocker_id not in release_ids:
        release_ids.append(blocker.blocker_id)
    groups["release"] = release_ids
    summary = dict(status.summary)
    summary["blocking_count"] = len(blockers)
    summary["physical_scope_authorized"] = False
    summary["authorized_operation_count"] = 0
    metadata = dict(status.metadata)
    metadata.update(
        {
            "physical_scope_authorized": False,
            "authorized_operations": [],
            "global_authority_flags_unchanged": True,
        }
    )
    return status.model_copy(
        update={
            "overall_status": "blocked",
            "blockers": blockers,
            "blocker_groups": groups,
            "summary": summary,
            "metadata": metadata,
        },
        deep=True,
    )


def apply_physical_evidence_to_plan(
    plan: Mapping[str, Any],
    *,
    calibrations: Iterable[CalibrationRecord | Mapping[str, Any]] = (),
    evidence: Iterable[PhysicalEvidenceRecord | Mapping[str, Any]] = (),
    decision: AuthorizationDecision | Mapping[str, Any] | None = None,
    requested_operations: Iterable[PhysicalOperation | str] = (),
    as_of: datetime | None = None,
) -> Dict[str, Any]:
    """Update plan evidence and scoped assessment while keeping global flags false."""

    updated = dict(plan)
    project = MachineProject.model_validate(updated.get("machine_project") or {})
    package = assess_physical_authorization(
        updated,
        calibrations=calibrations,
        evidence=evidence,
        decision=decision,
        as_of=as_of,
    )
    project = attach_physical_evidence(project, package)
    operations = list(requested_operations)
    release = (
        assess_scoped_release(project, package, requested_operations=operations)
        if operations
        else None
    )

    updated["machine_project"] = project.model_dump(mode="json")
    updated["physical_evidence_package"] = package.model_dump(mode="json")
    updated["scoped_release_assessment"] = (
        release.model_dump(mode="json") if release is not None else None
    )
    status = _status_with_physical_scope(
        build_engineering_status(updated),
        release,
        package.assessment.blockers,
    )
    status_payload = status.model_dump(mode="json")

    payloads = dict(project.discipline_payloads)
    payloads["engineering_status"] = status_payload
    payloads["scoped_release_assessment"] = (
        release.model_dump(mode="json") if release is not None else None
    )
    metadata = dict(project.metadata)
    metadata.update(
        {
            "physical_plan_update_schema": PHYSICAL_PLAN_UPDATE_SCHEMA,
            "physical_authorization_applicable": package.assessment.applicable,
            "scoped_release_allowed": release.allowed if release is not None else False,
            "authorized_operations": (
                [row.value for row in release.allowed_operations]
                if release is not None
                else []
            ),
            "global_authority_flags_unchanged": True,
            "automatic_authorization": False,
        }
    )
    project = project.model_copy(
        update={"discipline_payloads": payloads, "metadata": metadata},
        deep=True,
    )
    updated["machine_project"] = project.model_dump(mode="json")
    updated["engineering_status"] = status_payload

    readiness = dict(updated.get("engineering_readiness") or {})
    readiness.update(
        {
            "status": status.overall_status,
            "current_phase": status.current_phase,
            "unified_blocker_count": len(status.blockers),
            "unified_advisory_count": len(status.advisories),
            "next_action_id": status.next_action_id,
            "physical_evidence_count": len(package.evidence),
            "calibration_count": len(package.calibrations),
            "physical_authorization_applicable": package.assessment.applicable,
            "scoped_release_allowed": release.allowed if release is not None else False,
            "scoped_authorized_operations": (
                [row.value for row in release.allowed_operations]
                if release is not None
                else []
            ),
            "automatic_authorization": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }
    )
    updated["engineering_readiness"] = readiness

    scenario = dict(updated.get("scenario") or {})
    compile_spec = dict(scenario.get("compile_spec") or {})
    compile_spec["machine_project"] = project.model_dump(mode="json")
    compile_spec["engineering_status"] = status_payload
    compile_spec["physical_evidence_package"] = package.model_dump(mode="json")
    compile_spec["scoped_release_assessment"] = (
        release.model_dump(mode="json") if release is not None else None
    )
    scenario["compile_spec"] = compile_spec
    scenario["physical_authorization"] = {
        "applicable": package.assessment.applicable,
        "scoped_release_allowed": release.allowed if release is not None else False,
        "authorized_operations": (
            [row.value for row in release.allowed_operations]
            if release is not None
            else []
        ),
        "global_authority_flags_unchanged": True,
        "automatic_authorization": False,
    }
    updated["scenario"] = scenario
    return updated

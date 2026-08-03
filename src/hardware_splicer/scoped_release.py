"""Strict release assessment for physical operations.

MachineProject release assessment remains useful for traceability and verification
closure. This layer deliberately requires an applicable human authorization package
for every requested physical operation; measured evidence alone is never sufficient.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable

from pydantic import BaseModel, ConfigDict, Field

from .machine_project import MachineProject, ReleaseState
from .physical_evidence import PhysicalEvidencePackage, PhysicalOperation


SCOPED_RELEASE_SCHEMA = "hardware_splicer.scoped_release.v1"


class ScopedReleaseBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ScopedReleaseAssessment(ScopedReleaseBase):
    schema_version: str = SCOPED_RELEASE_SCHEMA
    project_id: str
    requested_operations: list[PhysicalOperation] = Field(min_length=1)
    allowed_operations: list[PhysicalOperation] = Field(default_factory=list)
    status: str
    allowed: bool = False
    design_assessment: Dict[str, Any] = Field(default_factory=dict)
    physical_assessment: Dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def assess_scoped_release(
    project: MachineProject,
    physical_package: PhysicalEvidencePackage,
    *,
    requested_operations: Iterable[PhysicalOperation | str],
) -> ScopedReleaseAssessment:
    """Require design closure plus one applicable, matching human decision."""

    requested = [
        value if isinstance(value, PhysicalOperation) else PhysicalOperation(value)
        for value in requested_operations
    ]
    if not requested:
        raise ValueError("at least one physical operation must be requested")
    requested = list(dict.fromkeys(requested))
    design = project.assess_release(ReleaseState.BENCH_READY)
    blockers = [row.message for row in design.blockers]
    warnings = [row.message for row in design.warnings]

    if physical_package.project_id != project.project_id:
        blockers.append(
            f"Physical authorization package belongs to {physical_package.project_id}, not {project.project_id}."
        )
    assessment = physical_package.assessment
    if not assessment.applicable:
        blockers.extend(assessment.blockers or ["Physical authorization is not applicable."])
    authorized = set(assessment.authorized_operations)
    missing_operations = [value.value for value in requested if value not in authorized]
    if missing_operations:
        blockers.append(
            "Authorization scope does not include requested operations: "
            f"{', '.join(missing_operations)}."
        )
    if physical_package.decision is None:
        blockers.append("No explicit human authorization decision is attached.")
    elif physical_package.decision.status.value != "authorized":
        blockers.append(
            f"Human authorization decision is {physical_package.decision.status.value}."
        )

    blockers = list(dict.fromkeys(blockers))
    allowed = not blockers
    return ScopedReleaseAssessment(
        project_id=project.project_id,
        requested_operations=requested,
        allowed_operations=requested if allowed else [],
        status="authorized" if allowed else "blocked",
        allowed=allowed,
        design_assessment=design.model_dump(mode="json"),
        physical_assessment=assessment.model_dump(mode="json"),
        blockers=blockers,
        warnings=list(dict.fromkeys(warnings)),
        metadata={
            "explicit_human_decision_required": True,
            "measured_evidence_alone_sufficient": False,
            "software_evidence_sufficient": False,
            "simulation_evidence_sufficient": False,
            "authorization_carries_across_revisions": False,
            "authorization_carries_across_artifact_hashes": False,
            "automatic_authorization": False,
        },
    )

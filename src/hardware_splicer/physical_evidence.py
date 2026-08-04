"""Calibrated physical evidence and explicitly scoped human authorization.

This module never grants authority from planning, simulation, software execution, or a
passing calculation. It validates a human-supplied authorization decision against one
project revision, one artifact-hash boundary, one operating envelope, and retained
physical evidence. Any candidate, artifact, scope, calibration, or expiry change makes
the decision inapplicable rather than silently carrying authority forward.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .machine_project import AuthorityState, EvidenceRef, MachineProject


PHYSICAL_EVIDENCE_SCHEMA = "hardware_splicer.physical_evidence.v1"
PHYSICAL_AUTHORIZATION_SCHEMA = "hardware_splicer.physical_authorization.v1"


class PhysicalBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class PhysicalEvidenceKind(str, Enum):
    INSPECTION = "inspection"
    DIMENSIONAL = "dimensional_measurement"
    ELECTRICAL = "electrical_measurement"
    THERMAL = "thermal_test"
    LOAD = "load_test"
    MOTION = "motion_test"
    ENDURANCE = "endurance_test"
    SAFETY_INTERLOCK = "safety_interlock_test"
    ENVIRONMENTAL = "environmental_test"


class PhysicalOperation(str, Enum):
    FABRICATION_RELEASE = "fabrication_release"
    FIRMWARE_FLASH = "firmware_flash"
    BENCH_POWER = "bench_power"
    RESTRAINED_MOTION = "restrained_motion"
    OPERATIONAL_USE = "operational_use"
    FIELD_RELEASE = "field_release"


class AuthorizationStatus(str, Enum):
    PROPOSED = "proposed"
    AUTHORIZED = "authorized"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CalibrationRecord(PhysicalBase):
    calibration_id: str = Field(min_length=1)
    instrument_id: str = Field(min_length=1)
    calibrated_at: str = Field(min_length=1)
    expires_at: str | None = None
    certificate_ref: str | None = None
    authority: AuthorityState = AuthorityState.VERIFIED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def calibration_requires_non_simulated_authority(self) -> "CalibrationRecord":
        if self.authority not in {
            AuthorityState.MEASURED,
            AuthorityState.VERIFIED,
            AuthorityState.AUTHORIZED,
        }:
            raise ValueError("calibration authority must be measured, verified, or authorized")
        return self


class PhysicalEvidenceRecord(PhysicalBase):
    schema_version: str = PHYSICAL_EVIDENCE_SCHEMA
    evidence_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    candidate_revision: str = Field(min_length=1)
    kind: PhysicalEvidenceKind
    target_ids: list[str] = Field(min_length=1)
    procedure_id: str = Field(min_length=1)
    passed: bool
    captured_at: str = Field(min_length=1)
    operator: str = Field(min_length=1)
    measured_values: Dict[str, Any] = Field(default_factory=dict)
    acceptance_criteria: Dict[str, Any] = Field(default_factory=dict)
    instrument_ids: list[str] = Field(default_factory=list)
    calibration_ids: list[str] = Field(default_factory=list)
    artifact_hashes: Dict[str, str] = Field(default_factory=dict)
    environment: Dict[str, Any] = Field(default_factory=dict)
    fixture_state: Dict[str, Any] = Field(default_factory=dict)
    interlock_state: Dict[str, Any] = Field(default_factory=dict)
    raw_refs: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.MEASURED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def physical_evidence_cannot_be_proposed_or_simulated(self) -> "PhysicalEvidenceRecord":
        if self.authority not in {
            AuthorityState.MEASURED,
            AuthorityState.VERIFIED,
            AuthorityState.AUTHORIZED,
        }:
            raise ValueError("physical evidence authority must be measured, verified, or authorized")
        if self.instrument_ids and not self.calibration_ids:
            raise ValueError("instrumented evidence must reference calibration records")
        return self


class AuthorizationScope(PhysicalBase):
    scope_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    candidate_revision: str = Field(min_length=1)
    operations: list[PhysicalOperation] = Field(min_length=1)
    target_ids: list[str] = Field(min_length=1)
    artifact_hashes: Dict[str, str] = Field(min_length=1)
    operating_envelope: Dict[str, Any] = Field(min_length=1)
    environment_limits: Dict[str, Any] = Field(default_factory=dict)
    required_evidence_kinds: list[PhysicalEvidenceKind] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AuthorizationDecision(PhysicalBase):
    schema_version: str = PHYSICAL_AUTHORIZATION_SCHEMA
    authorization_id: str = Field(min_length=1)
    status: AuthorizationStatus
    scope: AuthorizationScope
    reviewer: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    expires_at: str | None = None
    revoked_at: str | None = None
    revocation_reason: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def revoked_decision_requires_reason(self) -> "AuthorizationDecision":
        if self.status == AuthorizationStatus.REVOKED and not self.revocation_reason:
            raise ValueError("revoked authorization requires revocation_reason")
        return self


class PhysicalAuthorizationAssessment(PhysicalBase):
    project_id: str
    candidate_revision: str | None = None
    status: str
    applicable: bool = False
    authorized_operations: list[PhysicalOperation] = Field(default_factory=list)
    accepted_evidence_ids: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifact_hashes: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PhysicalEvidencePackage(PhysicalBase):
    project_id: str
    candidate_revision: str | None = None
    calibrations: list[CalibrationRecord] = Field(default_factory=list)
    evidence: list[PhysicalEvidenceRecord] = Field(default_factory=list)
    decision: AuthorizationDecision | None = None
    assessment: PhysicalAuthorizationAssessment
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    token = value.strip()
    if token.endswith("Z"):
        token = f"{token[:-1]}+00:00"
    parsed = datetime.fromisoformat(token)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _candidate_revision(plan: Mapping[str, Any]) -> str | None:
    value = plan.get("candidate_revision")
    if value in (None, ""):
        impact = _mapping(plan.get("change_impact"))
        value = impact.get("candidate_revision")
    if value in (None, ""):
        context = _mapping(plan.get("engineering_context"))
        value = context.get("candidate_revision")
    return str(value) if value not in (None, "") else None


def _project_id(plan: Mapping[str, Any]) -> str:
    machine = _mapping(plan.get("machine_project"))
    return str(machine.get("project_id") or plan.get("project_name") or "engineering-project")


def _artifact_hashes(plan: Mapping[str, Any]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    machine = _mapping(plan.get("machine_project"))
    for row in _rows(machine.get("artifacts")):
        artifact_id = row.get("artifact_id")
        metadata = _mapping(row.get("metadata"))
        content_hash = metadata.get("content_hash") or row.get("content_hash")
        if artifact_id and content_hash:
            result[str(artifact_id)] = str(content_hash)
    normalized = _mapping(plan.get("normalized_intake"))
    for key in ("fabrication_artifacts", "manufacturing_artifacts", "release_artifacts"):
        for row in _rows(normalized.get(key)):
            artifact_id = row.get("artifact_id") or row.get("id") or row.get("name")
            content_hash = row.get("content_hash") or row.get("hash")
            if artifact_id and content_hash:
                result[str(artifact_id)] = str(content_hash)
    return result


def _calibration_blockers(
    evidence: PhysicalEvidenceRecord,
    calibrations: Mapping[str, CalibrationRecord],
    *,
    as_of: datetime,
) -> list[str]:
    blockers: list[str] = []
    for calibration_id in evidence.calibration_ids:
        calibration = calibrations.get(calibration_id)
        if calibration is None:
            blockers.append(
                f"Evidence {evidence.evidence_id} references unknown calibration {calibration_id}."
            )
            continue
        if calibration.instrument_id not in evidence.instrument_ids:
            blockers.append(
                f"Calibration {calibration_id} does not correspond to an instrument used by evidence {evidence.evidence_id}."
            )
        expires = _parse_time(calibration.expires_at)
        if expires is not None and expires < as_of:
            blockers.append(
                f"Calibration {calibration_id} expired before the authorization assessment."
            )
    return blockers


def assess_physical_authorization(
    plan: Mapping[str, Any],
    *,
    calibrations: Iterable[CalibrationRecord | Mapping[str, Any]] = (),
    evidence: Iterable[PhysicalEvidenceRecord | Mapping[str, Any]] = (),
    decision: AuthorizationDecision | Mapping[str, Any] | None = None,
    as_of: datetime | None = None,
) -> PhysicalEvidencePackage:
    """Validate a supplied human decision against physical evidence and candidate state."""

    project_id = _project_id(plan)
    candidate_revision = _candidate_revision(plan)
    calibrated = [
        value if isinstance(value, CalibrationRecord) else CalibrationRecord.model_validate(value)
        for value in calibrations
    ]
    records = [
        value if isinstance(value, PhysicalEvidenceRecord) else PhysicalEvidenceRecord.model_validate(value)
        for value in evidence
    ]
    authorization = (
        decision
        if isinstance(decision, AuthorizationDecision)
        else AuthorizationDecision.model_validate(decision)
        if decision is not None
        else None
    )
    now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    calibration_by_id = {row.calibration_id: row for row in calibrated}
    evidence_by_id = {row.evidence_id: row for row in records}
    blockers: list[str] = []
    warnings: list[str] = []
    accepted: list[str] = []
    plan_hashes = _artifact_hashes(plan)

    if not candidate_revision:
        blockers.append("Candidate revision is unresolved; physical authority cannot be scoped.")
    for record in records:
        if record.project_id != project_id:
            blockers.append(
                f"Evidence {record.evidence_id} belongs to project {record.project_id}, not {project_id}."
            )
        if candidate_revision and record.candidate_revision != candidate_revision:
            blockers.append(
                f"Evidence {record.evidence_id} targets revision {record.candidate_revision}, not candidate {candidate_revision}."
            )
        if not record.passed:
            blockers.append(f"Physical evidence {record.evidence_id} did not pass its acceptance criteria.")
        blockers.extend(_calibration_blockers(record, calibration_by_id, as_of=now))
        for artifact_id, content_hash in record.artifact_hashes.items():
            expected = plan_hashes.get(artifact_id)
            if expected is None:
                blockers.append(
                    f"Evidence {record.evidence_id} references artifact {artifact_id} absent from the candidate plan."
                )
            elif expected != content_hash:
                blockers.append(
                    f"Evidence {record.evidence_id} was captured against stale hash {content_hash} for {artifact_id}; candidate uses {expected}."
                )
        if record.passed:
            accepted.append(record.evidence_id)

    authorized_operations: list[PhysicalOperation] = []
    applicable = False
    if authorization is None:
        blockers.append("No human authorization decision is supplied.")
    else:
        scope = authorization.scope
        if authorization.status != AuthorizationStatus.AUTHORIZED:
            blockers.append(
                f"Authorization decision {authorization.authorization_id} is {authorization.status.value}, not authorized."
            )
        if scope.project_id != project_id:
            blockers.append(
                f"Authorization scope belongs to project {scope.project_id}, not {project_id}."
            )
        if candidate_revision and scope.candidate_revision != candidate_revision:
            blockers.append(
                f"Authorization scope targets revision {scope.candidate_revision}, not candidate {candidate_revision}."
            )
        expires = _parse_time(authorization.expires_at)
        if expires is not None and expires < now:
            blockers.append(f"Authorization {authorization.authorization_id} is expired.")
        missing_evidence = [value for value in authorization.evidence_ids if value not in evidence_by_id]
        if missing_evidence:
            blockers.append(
                f"Authorization references unavailable evidence: {', '.join(missing_evidence)}."
            )
        failed_decision_evidence = [
            value
            for value in authorization.evidence_ids
            if value in evidence_by_id and not evidence_by_id[value].passed
        ]
        if failed_decision_evidence:
            blockers.append(
                f"Authorization references failed evidence: {', '.join(failed_decision_evidence)}."
            )
        supplied_kinds = {
            evidence_by_id[value].kind
            for value in authorization.evidence_ids
            if value in evidence_by_id and evidence_by_id[value].passed
        }
        missing_kinds = [
            value.value
            for value in scope.required_evidence_kinds
            if value not in supplied_kinds
        ]
        if missing_kinds:
            blockers.append(
                f"Authorization scope lacks required physical evidence kinds: {', '.join(missing_kinds)}."
            )
        if scope.artifact_hashes != plan_hashes:
            missing = sorted(set(plan_hashes) - set(scope.artifact_hashes))
            extra = sorted(set(scope.artifact_hashes) - set(plan_hashes))
            changed = sorted(
                key
                for key in set(scope.artifact_hashes) & set(plan_hashes)
                if scope.artifact_hashes[key] != plan_hashes[key]
            )
            blockers.append(
                "Authorization artifact boundary does not match the candidate plan "
                f"(missing={missing}, extra={extra}, changed={changed})."
            )
        if not scope.operating_envelope:
            blockers.append("Authorization scope has no operating envelope.")
        if not blockers:
            applicable = True
            authorized_operations = list(scope.operations)

    status = "authorized" if applicable else "blocked"
    assessment = PhysicalAuthorizationAssessment(
        project_id=project_id,
        candidate_revision=candidate_revision,
        status=status,
        applicable=applicable,
        authorized_operations=authorized_operations,
        accepted_evidence_ids=list(dict.fromkeys(accepted)),
        blockers=list(dict.fromkeys(blockers)),
        warnings=list(dict.fromkeys(warnings)),
        artifact_hashes=plan_hashes,
        metadata={
            "automatic_authorization": False,
            "human_decision_required": True,
            "software_evidence_accepted": False,
            "simulation_evidence_accepted": False,
            "authorization_carries_across_revisions": False,
            "authorization_carries_across_artifact_hashes": False,
        },
    )
    return PhysicalEvidencePackage(
        project_id=project_id,
        candidate_revision=candidate_revision,
        calibrations=calibrated,
        evidence=records,
        decision=authorization,
        assessment=assessment,
        metadata={
            "assessment_time": now.isoformat(),
            "physical_evidence_count": len(records),
            "calibration_count": len(calibrated),
            "automatic_authorization": False,
        },
    )


def attach_physical_evidence(
    project: MachineProject,
    package: PhysicalEvidencePackage,
) -> MachineProject:
    """Retain physical evidence in MachineProject without synthesizing a decision."""

    if package.project_id != project.project_id:
        raise ValueError("physical evidence package project_id does not match MachineProject")
    known_ids = {
        project.project_id,
        *(row.requirement_id for row in project.requirements),
        *(row.function_id for row in project.functions),
        *(row.subsystem_id for row in project.subsystems),
        *(row.component_id for row in project.components),
        *(row.interface_id for row in project.interfaces),
        *(row.constraint_id for row in project.constraints),
        *(row.verification_id for row in project.verifications),
        *(row.artifact_id for row in project.artifacts),
    }
    rows = [
        row
        for row in project.evidence
        if row.kind != "physical_evidence_record"
        or row.metadata.get("physical_evidence_id") not in {item.evidence_id for item in package.evidence}
    ]
    for item in package.evidence:
        supports = [value for value in item.target_ids if value in known_ids] or [project.project_id]
        rows.append(
            EvidenceRef(
                evidence_id=f"physical-{item.evidence_id}",
                kind="physical_evidence_record",
                basis=(
                    f"Physical {item.kind.value} passed."
                    if item.passed
                    else f"Physical {item.kind.value} failed."
                ),
                ref=item.raw_refs[0] if item.raw_refs else None,
                supports=supports,
                authority=item.authority if item.passed else AuthorityState.OBSERVED,
                simulated=False,
                metadata={
                    "schema_version": PHYSICAL_EVIDENCE_SCHEMA,
                    "physical_evidence_id": item.evidence_id,
                    "candidate_revision": item.candidate_revision,
                    "procedure_id": item.procedure_id,
                    "captured_at": item.captured_at,
                    "operator": item.operator,
                    "measured_values": item.measured_values,
                    "acceptance_criteria": item.acceptance_criteria,
                    "instrument_ids": item.instrument_ids,
                    "calibration_ids": item.calibration_ids,
                    "artifact_hashes": item.artifact_hashes,
                    "environment": item.environment,
                    "fixture_state": item.fixture_state,
                    "interlock_state": item.interlock_state,
                    "passed": item.passed,
                    "physical": True,
                },
            )
        )
    payloads = dict(project.discipline_payloads)
    payloads["physical_evidence"] = package.model_dump(mode="json")
    metadata = dict(project.metadata)
    metadata.update(
        {
            "physical_evidence_schema": PHYSICAL_EVIDENCE_SCHEMA,
            "physical_evidence_count": len(package.evidence),
            "physical_authorization_applicable": package.assessment.applicable,
            "physical_authorization_status": package.assessment.status,
            "automatic_authorization": False,
        }
    )
    return MachineProject.model_validate(
        project.model_copy(
            update={
                "evidence": rows,
                "discipline_payloads": payloads,
                "metadata": metadata,
            },
            deep=True,
        ).model_dump(mode="json")
    )

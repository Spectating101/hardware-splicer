"""Audited physical authorization using hashed evidence envelopes and ledger history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .physical_evidence import (
    CalibrationRecord,
    PhysicalEvidencePackage,
    assess_physical_authorization,
)
from .physical_evidence_ledger import (
    AuthorizationLedgerAssessment,
    AuthorizationLedgerEntry,
    PhysicalEvidenceEnvelope,
    validate_authorization_ledger,
    validate_physical_evidence_envelope,
)


AUDITED_PHYSICAL_EVIDENCE_SCHEMA = "hardware_splicer.audited_physical_evidence.v1"


class AuditedBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AuditedPhysicalEvidencePackage(AuditedBase):
    schema_version: str = AUDITED_PHYSICAL_EVIDENCE_SCHEMA
    physical_package: PhysicalEvidencePackage
    envelopes: list[PhysicalEvidenceEnvelope] = Field(default_factory=list)
    ledger_entries: list[AuthorizationLedgerEntry] = Field(default_factory=list)
    ledger_assessment: AuthorizationLedgerAssessment
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    applicable: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _candidate_revision(plan: Mapping[str, Any]) -> str | None:
    value = plan.get("candidate_revision")
    if value in (None, ""):
        impact = plan.get("change_impact")
        if isinstance(impact, Mapping):
            value = impact.get("candidate_revision")
    return str(value) if value not in (None, "") else None


def _project_id(plan: Mapping[str, Any]) -> str:
    machine = plan.get("machine_project")
    if isinstance(machine, Mapping) and machine.get("project_id"):
        return str(machine["project_id"])
    return str(plan.get("project_name") or "engineering-project")


def assess_audited_physical_authorization(
    plan: Mapping[str, Any],
    *,
    calibrations: Iterable[CalibrationRecord | Mapping[str, Any]] = (),
    envelopes: Iterable[PhysicalEvidenceEnvelope | Mapping[str, Any]] = (),
    ledger_entries: Iterable[AuthorizationLedgerEntry | Mapping[str, Any]] = (),
    scope_id: str | None = None,
    as_of: datetime | None = None,
) -> AuditedPhysicalEvidencePackage:
    """Assess only a decision retained in a valid hash chain with valid envelopes."""

    now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    project_id = _project_id(plan)
    candidate_revision = _candidate_revision(plan)
    resolved_envelopes = [
        value if isinstance(value, PhysicalEvidenceEnvelope)
        else PhysicalEvidenceEnvelope.model_validate(value)
        for value in envelopes
    ]
    resolved_ledger = [
        value if isinstance(value, AuthorizationLedgerEntry)
        else AuthorizationLedgerEntry.model_validate(value)
        for value in ledger_entries
    ]
    envelope_blockers: list[str] = []
    evidence_ids: set[str] = set()
    for envelope in resolved_envelopes:
        envelope_blockers.extend(validate_physical_evidence_envelope(envelope))
        if envelope.record.evidence_id in evidence_ids:
            envelope_blockers.append(
                f"Physical evidence_id {envelope.record.evidence_id!r} appears in multiple envelopes."
            )
        evidence_ids.add(envelope.record.evidence_id)

    ledger_assessment = validate_authorization_ledger(
        resolved_ledger,
        project_id=project_id,
        candidate_revision=candidate_revision,
        scope_id=scope_id,
        as_of=now,
    )
    decision = None
    if ledger_assessment.applicable_authorization_id:
        decision = next(
            (
                entry.decision
                for entry in reversed(resolved_ledger)
                if entry.decision.authorization_id
                == ledger_assessment.applicable_authorization_id
            ),
            None,
        )
    package = assess_physical_authorization(
        plan,
        calibrations=calibrations,
        evidence=[envelope.record for envelope in resolved_envelopes],
        decision=decision,
        as_of=now,
    )
    blockers = [
        *envelope_blockers,
        *ledger_assessment.blockers,
        *package.assessment.blockers,
    ]
    warnings = [*ledger_assessment.warnings, *package.assessment.warnings]
    if decision is not None:
        missing_envelopes = [
            evidence_id
            for evidence_id in decision.evidence_ids
            if evidence_id not in evidence_ids
        ]
        if missing_envelopes:
            blockers.append(
                "Authorization decision lacks hashed evidence envelopes for: "
                + ", ".join(missing_envelopes)
                + "."
            )
    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    applicable = package.assessment.applicable and ledger_assessment.valid and not envelope_blockers and not blockers

    if blockers or not applicable:
        assessment = package.assessment.model_copy(
            update={
                "status": "blocked",
                "applicable": False,
                "authorized_operations": [],
                "blockers": blockers,
                "warnings": warnings,
            },
            deep=True,
        )
        package = package.model_copy(update={"assessment": assessment}, deep=True)

    return AuditedPhysicalEvidencePackage(
        physical_package=package,
        envelopes=resolved_envelopes,
        ledger_entries=resolved_ledger,
        ledger_assessment=ledger_assessment,
        blockers=blockers,
        warnings=warnings,
        applicable=applicable,
        metadata={
            "assessment_time": now.isoformat(),
            "tamper_evident_envelopes_required": True,
            "valid_authorization_chain_required": True,
            "automatic_authorization": False,
            "authorization_carries_across_revisions": False,
        },
    )

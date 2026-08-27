"""Apply tamper-evident physical evidence and ledger history to guided plans."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Mapping

from .attested_audited_physical_evidence import (
    assess_attested_audited_physical_authorization,
)
from .audited_physical_evidence import (
    AuditedPhysicalEvidencePackage,
    assess_audited_physical_authorization,
)
from .engineering_status import build_engineering_status
from .machine_project import MachineProject
from .physical_evidence import CalibrationRecord, PhysicalOperation, attach_physical_evidence
from .physical_evidence_ledger import AuthorizationLedgerEntry, PhysicalEvidenceEnvelope
from .physical_evidence_plan_update import _status_with_physical_scope
from .scoped_release import assess_scoped_release


AUDITED_PHYSICAL_PLAN_UPDATE_SCHEMA = (
    "hardware_splicer.audited_physical_evidence_plan_update.v1"
)


def apply_audited_physical_evidence_to_plan(
    plan: Mapping[str, Any],
    *,
    calibrations: Iterable[CalibrationRecord | Mapping[str, Any]] = (),
    envelopes: Iterable[PhysicalEvidenceEnvelope | Mapping[str, Any]] = (),
    ledger_entries: Iterable[AuthorizationLedgerEntry | Mapping[str, Any]] = (),
    requested_operations: Iterable[PhysicalOperation | str] = (),
    scope_id: str | None = None,
    as_of: datetime | None = None,
    require_server_attestation: bool = False,
) -> Dict[str, Any]:
    """Persist audited evidence while keeping all broad authority flags false."""

    updated = dict(plan)
    project = MachineProject.model_validate(updated.get("machine_project") or {})
    assessor = (
        assess_attested_audited_physical_authorization
        if require_server_attestation
        else assess_audited_physical_authorization
    )
    audited: AuditedPhysicalEvidencePackage = assessor(
        updated,
        calibrations=calibrations,
        envelopes=envelopes,
        ledger_entries=ledger_entries,
        scope_id=scope_id,
        as_of=as_of,
    )
    project = attach_physical_evidence(project, audited.physical_package)
    operations = list(requested_operations)
    release = (
        assess_scoped_release(
            project,
            audited.physical_package,
            requested_operations=operations,
        )
        if operations
        else None
    )

    updated["machine_project"] = project.model_dump(mode="json")
    updated["physical_evidence_package"] = audited.physical_package.model_dump(mode="json")
    updated["audited_physical_evidence"] = audited.model_dump(mode="json")
    updated["scoped_release_assessment"] = (
        release.model_dump(mode="json") if release is not None else None
    )

    audit_blockers = [*audited.blockers]
    if not audited.applicable and not audit_blockers:
        audit_blockers.append("Audited physical authorization is not applicable.")
    status = _status_with_physical_scope(
        build_engineering_status(updated),
        release if audited.applicable else None,
        audit_blockers,
    )
    status_payload = status.model_dump(mode="json")

    payloads = dict(project.discipline_payloads)
    payloads["audited_physical_evidence"] = audited.model_dump(mode="json")
    payloads["engineering_status"] = status_payload
    payloads["scoped_release_assessment"] = (
        release.model_dump(mode="json") if release is not None else None
    )
    metadata = dict(project.metadata)
    metadata.update(
        {
            "audited_physical_plan_update_schema": AUDITED_PHYSICAL_PLAN_UPDATE_SCHEMA,
            "audited_physical_authorization_applicable": audited.applicable,
            "physical_evidence_envelope_count": len(audited.envelopes),
            "authorization_ledger_entry_count": len(audited.ledger_entries),
            "authorization_ledger_valid": audited.ledger_assessment.valid,
            "server_attestation_required": require_server_attestation,
            "server_attestation_valid": bool(
                audited.metadata.get("server_attestation_valid")
            ) if require_server_attestation else None,
            "tamper_evident_envelopes_required": True,
            "valid_authorization_chain_required": True,
            "scoped_release_allowed": (
                audited.applicable and release.allowed
                if release is not None
                else False
            ),
            "automatic_authorization": False,
            "global_authority_flags_unchanged": True,
        }
    )
    project = MachineProject.model_validate(
        project.model_copy(
            update={"discipline_payloads": payloads, "metadata": metadata},
            deep=True,
        ).model_dump(mode="json")
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
            "physical_evidence_count": len(audited.physical_package.evidence),
            "calibration_count": len(audited.physical_package.calibrations),
            "physical_evidence_envelope_count": len(audited.envelopes),
            "authorization_ledger_entry_count": len(audited.ledger_entries),
            "authorization_ledger_valid": audited.ledger_assessment.valid,
            "audited_physical_authorization_applicable": audited.applicable,
            "server_attestation_required": require_server_attestation,
            "server_attestation_valid": bool(
                audited.metadata.get("server_attestation_valid")
            ) if require_server_attestation else None,
            "scoped_release_allowed": (
                audited.applicable and release.allowed
                if release is not None
                else False
            ),
            "scoped_authorized_operations": (
                [value.value for value in release.allowed_operations]
                if audited.applicable and release is not None
                else []
            ),
            "tamper_evident_envelopes_required": True,
            "valid_authorization_chain_required": True,
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
    compile_spec["physical_evidence_package"] = audited.physical_package.model_dump(mode="json")
    compile_spec["audited_physical_evidence"] = audited.model_dump(mode="json")
    compile_spec["scoped_release_assessment"] = (
        release.model_dump(mode="json") if release is not None else None
    )
    scenario["compile_spec"] = compile_spec
    scenario["audited_physical_authorization"] = {
        "applicable": audited.applicable,
        "ledger_valid": audited.ledger_assessment.valid,
        "server_attestation_required": require_server_attestation,
        "server_attestation_valid": bool(
            audited.metadata.get("server_attestation_valid")
        ) if require_server_attestation else None,
        "envelope_count": len(audited.envelopes),
        "ledger_entry_count": len(audited.ledger_entries),
        "scoped_release_allowed": (
            audited.applicable and release.allowed
            if release is not None
            else False
        ),
        "authorized_operations": (
            [value.value for value in release.allowed_operations]
            if audited.applicable and release is not None
            else []
        ),
        "global_authority_flags_unchanged": True,
        "automatic_authorization": False,
    }
    updated["scenario"] = scenario
    return updated

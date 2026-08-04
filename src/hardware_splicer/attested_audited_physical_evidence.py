"""Strict audited physical authorization with server-attested raw file references."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from .audited_physical_evidence import (
    AuditedPhysicalEvidencePackage,
    assess_audited_physical_authorization,
)
from .physical_evidence import CalibrationRecord
from .physical_evidence_attestation import verify_evidence_file_attestation
from .physical_evidence_ledger import (
    AuthorizationLedgerEntry,
    PhysicalEvidenceEnvelope,
)


ATTESTED_AUDITED_PHYSICAL_SCHEMA = (
    "hardware_splicer.attested_audited_physical_evidence.v1"
)


def assess_attested_audited_physical_authorization(
    plan: Mapping[str, Any],
    *,
    calibrations: Iterable[CalibrationRecord | Mapping[str, Any]] = (),
    envelopes: Iterable[PhysicalEvidenceEnvelope | Mapping[str, Any]] = (),
    ledger_entries: Iterable[AuthorizationLedgerEntry | Mapping[str, Any]] = (),
    scope_id: str | None = None,
    as_of: datetime | None = None,
) -> AuditedPhysicalEvidencePackage:
    """Require both envelope integrity and server provenance for every raw file."""

    resolved_envelopes = [
        value
        if isinstance(value, PhysicalEvidenceEnvelope)
        else PhysicalEvidenceEnvelope.model_validate(value)
        for value in envelopes
    ]
    audited = assess_audited_physical_authorization(
        plan,
        calibrations=calibrations,
        envelopes=resolved_envelopes,
        ledger_entries=ledger_entries,
        scope_id=scope_id,
        as_of=as_of,
    )
    attestation_blockers: list[str] = []
    attested_file_count = 0
    for envelope in resolved_envelopes:
        for file_ref in envelope.raw_files:
            blockers = verify_evidence_file_attestation(file_ref)
            if blockers:
                attestation_blockers.extend(
                    f"Envelope {envelope.envelope_id}: {value}"
                    for value in blockers
                )
            else:
                attested_file_count += 1

    blockers = list(dict.fromkeys([*audited.blockers, *attestation_blockers]))
    applicable = audited.applicable and not attestation_blockers and not blockers
    package = audited.physical_package
    if not applicable:
        assessment = package.assessment.model_copy(
            update={
                "status": "blocked",
                "applicable": False,
                "authorized_operations": [],
                "blockers": blockers,
            },
            deep=True,
        )
        package = package.model_copy(update={"assessment": assessment}, deep=True)

    metadata = dict(audited.metadata)
    metadata.update(
        {
            "schema_version": ATTESTED_AUDITED_PHYSICAL_SCHEMA,
            "server_attestation_required": True,
            "server_attestation_valid": not attestation_blockers,
            "attested_raw_file_count": attested_file_count,
            "raw_file_count": sum(
                len(envelope.raw_files) for envelope in resolved_envelopes
            ),
            "plain_hash_sufficient": False,
            "automatic_authorization": False,
        }
    )
    return audited.model_copy(
        update={
            "physical_package": package,
            "blockers": blockers,
            "applicable": applicable,
            "metadata": metadata,
        },
        deep=True,
    )

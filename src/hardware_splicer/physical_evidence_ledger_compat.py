"""Compatibility hardening for authorization ledger chronology."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from . import physical_evidence_ledger as _target


def install_ledger_chronology_compatibility() -> None:
    if getattr(_target, "_chronology_validation_installed", False):
        return
    original = _target.validate_authorization_ledger

    def validate_authorization_ledger(
        entries: Iterable[_target.AuthorizationLedgerEntry | Mapping[str, Any]],
        *,
        project_id: str | None = None,
        candidate_revision: str | None = None,
        scope_id: str | None = None,
        as_of: datetime | None = None,
    ):
        resolved = [
            value
            if isinstance(value, _target.AuthorizationLedgerEntry)
            else _target.AuthorizationLedgerEntry.model_validate(value)
            for value in entries
        ]
        report = original(
            resolved,
            project_id=project_id,
            candidate_revision=candidate_revision,
            scope_id=scope_id,
            as_of=as_of,
        )
        blockers = list(report.blockers)
        previous_recorded = None
        for entry in resolved:
            recorded = _target._parse_time(entry.recorded_at)
            reviewed = _target._parse_time(entry.decision.reviewed_at)
            if previous_recorded is not None and recorded is not None and recorded < previous_recorded:
                blockers.append(
                    f"Authorization ledger entry {entry.entry_id} is recorded before the prior entry."
                )
            if reviewed is not None and recorded is not None and reviewed > recorded:
                blockers.append(
                    f"Authorization ledger entry {entry.entry_id} is recorded before its human review time."
                )
            if recorded is not None:
                previous_recorded = recorded
        blockers = list(dict.fromkeys(blockers))
        metadata = dict(report.metadata)
        metadata.update(
            {
                "chronological_order_required": True,
                "review_precedes_recording_required": True,
            }
        )
        return report.model_copy(
            update={
                "valid": not blockers,
                "blockers": blockers,
                "metadata": metadata,
            },
            deep=True,
        )

    _target.validate_authorization_ledger = validate_authorization_ledger
    _target._chronology_validation_installed = True


install_ledger_chronology_compatibility()

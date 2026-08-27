"""Fresh revalidation of persisted physical authorization state.

Persisted audit packages retain history, not timeless authority. This module rebuilds
an audited package against the plan's *current* candidate revision, artifact hashes,
calibrations, ledger, raw-file attestations, and requested physical operations. Cached
``applicable`` or ``allowed`` booleans are never treated as a source of truth.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping

from .attested_audited_physical_evidence import (
    assess_attested_audited_physical_authorization,
)
from .audited_physical_evidence import assess_audited_physical_authorization
from .machine_project import MachineProject
from .physical_evidence import PhysicalOperation
from .scoped_release import assess_scoped_release


PHYSICAL_REVALIDATION_SCHEMA = (
    "hardware_splicer.physical_authorization_revalidation.v1"
)


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _operations(scoped: Mapping[str, Any]) -> list[PhysicalOperation]:
    values = (
        scoped.get("requested_operations")
        or scoped.get("allowed_operations")
        or scoped.get("authorized_operations")
        or []
    )
    result: list[PhysicalOperation] = []
    for value in values:
        try:
            operation = (
                value if isinstance(value, PhysicalOperation)
                else PhysicalOperation(str(value))
            )
        except ValueError:
            continue
        if operation not in result:
            result.append(operation)
    return result


def _failure_state(
    plan: Mapping[str, Any],
    *,
    message: str,
) -> Dict[str, Any]:
    updated = dict(plan)
    audited = _mapping(updated.get("audited_physical_evidence"))
    blockers = list(audited.get("blockers") or [])
    blockers.append(message)
    audited["applicable"] = False
    audited["blockers"] = list(dict.fromkeys(str(value) for value in blockers))
    metadata = _mapping(audited.get("metadata"))
    metadata.update(
        {
            "revalidation_schema": PHYSICAL_REVALIDATION_SCHEMA,
            "fresh_revalidation_completed": False,
            "fresh_revalidation_error": message,
            "automatic_authorization": False,
        }
    )
    audited["metadata"] = metadata
    updated["audited_physical_evidence"] = audited
    scoped = _mapping(updated.get("scoped_release_assessment"))
    scoped.update(
        {
            "allowed": False,
            "allowed_operations": [],
            "blockers": list(
                dict.fromkeys(
                    [
                        *[str(value) for value in scoped.get("blockers") or []],
                        message,
                    ]
                )
            ),
        }
    )
    updated["scoped_release_assessment"] = scoped
    updated["physical_authorization_revalidation_error"] = message
    return updated


def revalidate_physical_authorization_state(
    plan: Mapping[str, Any],
    *,
    as_of: datetime | None = None,
) -> Dict[str, Any]:
    """Return a copy whose physical authorization is recomputed for current state."""

    updated = dict(plan)
    raw_audited = updated.get("audited_physical_evidence")
    if not isinstance(raw_audited, Mapping):
        return updated
    audited = dict(raw_audited)
    physical_package = _mapping(audited.get("physical_package"))
    calibrations = physical_package.get("calibrations") or []
    envelopes = audited.get("envelopes") or []
    ledger_entries = audited.get("ledger_entries") or []
    ledger_assessment = _mapping(audited.get("ledger_assessment"))
    scope_id = ledger_assessment.get("applicable_scope_id")
    audit_metadata = _mapping(audited.get("metadata"))
    server_attestation_required = bool(
        audit_metadata.get("server_attestation_required")
        or _mapping(updated.get("engineering_readiness")).get(
            "server_attestation_required"
        )
        or _mapping(
            _mapping(updated.get("scenario")).get(
                "audited_physical_authorization"
            )
        ).get("server_attestation_required")
    )

    try:
        assessor = (
            assess_attested_audited_physical_authorization
            if server_attestation_required
            else assess_audited_physical_authorization
        )
        revalidated = assessor(
            updated,
            calibrations=calibrations,
            envelopes=envelopes,
            ledger_entries=ledger_entries,
            scope_id=str(scope_id) if scope_id not in (None, "") else None,
            as_of=as_of,
        )
        machine_project = MachineProject.model_validate(
            updated.get("machine_project") or {}
        )
        requested_operations = _operations(
            _mapping(updated.get("scoped_release_assessment"))
        )
        release = (
            assess_scoped_release(
                machine_project,
                revalidated.physical_package,
                requested_operations=requested_operations,
            )
            if requested_operations
            else None
        )
    except (TypeError, ValueError) as exc:
        return _failure_state(
            updated,
            message=f"Fresh physical authorization revalidation failed: {exc}",
        )

    revalidated_metadata = dict(revalidated.metadata)
    revalidated_metadata.update(
        {
            "revalidation_schema": PHYSICAL_REVALIDATION_SCHEMA,
            "fresh_revalidation_completed": True,
            "server_attestation_required": server_attestation_required,
            "automatic_authorization": False,
        }
    )
    revalidated = revalidated.model_copy(
        update={"metadata": revalidated_metadata},
        deep=True,
    )
    updated["audited_physical_evidence"] = revalidated.model_dump(mode="json")
    updated["physical_evidence_package"] = (
        revalidated.physical_package.model_dump(mode="json")
    )
    updated["scoped_release_assessment"] = (
        release.model_dump(mode="json") if release is not None else None
    )
    updated["physical_authorization_revalidation"] = {
        "schema_version": PHYSICAL_REVALIDATION_SCHEMA,
        "completed": True,
        "authorization_applicable": revalidated.applicable,
        "requested_operations": [value.value for value in requested_operations],
        "scoped_release_allowed": (
            revalidated.applicable and release.allowed
            if release is not None
            else False
        ),
        "allowed_operations": (
            [value.value for value in release.allowed_operations]
            if revalidated.applicable and release is not None
            else []
        ),
        "server_attestation_required": server_attestation_required,
        "automatic_authorization": False,
        "authorization_carries_across_revisions": False,
    }
    return updated

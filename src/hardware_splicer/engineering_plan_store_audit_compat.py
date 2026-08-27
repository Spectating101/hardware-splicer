"""Central persistence guard for append-only physical audit history.

Patch-style APIs already anchor their writes to stored revisions. Full guided replans
also pass through :func:`save_engineering_plan`, so this compatibility layer preserves
any previously persisted evidence envelopes and authorization-ledger prefix, rejects
historical rewrites, and freshly revalidates that history against the candidate being
saved. Old authorization may remain as history, but it cannot silently carry across a
candidate revision, artifact hash, calibration, key, or verification change.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from . import engineering_plan_store as _target
from .engineering_status import build_engineering_status
from .physical_authorization_revalidation import (
    revalidate_physical_authorization_state,
)
from .physical_evidence_ledger import (
    AuthorizationLedgerEntry,
    PhysicalEvidenceEnvelope,
)
from .project_store import ProjectNotFound, RevisionConflict


PHYSICAL_AUDIT_PERSISTENCE_GUARD_SCHEMA = (
    "hardware_splicer.physical_audit_persistence_guard.v1"
)


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _stored_engineering_plan(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    snapshot = envelope.get("snapshot")
    if not isinstance(snapshot, Mapping):
        raise ValueError("stored project revision does not contain a snapshot")
    plan = snapshot.get("engineeringPlan")
    if not isinstance(plan, Mapping):
        raise ValueError("stored project revision does not contain an engineeringPlan")
    return dict(plan)


def _canonical_envelope(value: Mapping[str, Any]) -> Dict[str, Any]:
    return PhysicalEvidenceEnvelope.model_validate(value).model_dump(mode="json")


def _canonical_ledger_entry(value: Mapping[str, Any]) -> Dict[str, Any]:
    return AuthorizationLedgerEntry.model_validate(value).model_dump(mode="json")


def _assert_history_continuity(
    prior_audit: Mapping[str, Any],
    candidate_audit: Mapping[str, Any],
) -> None:
    prior_envelopes = {
        str(row.get("envelope_id")): _canonical_envelope(row)
        for row in prior_audit.get("envelopes") or []
        if isinstance(row, Mapping) and row.get("envelope_id")
    }
    candidate_envelopes = {
        str(row.get("envelope_id")): _canonical_envelope(row)
        for row in candidate_audit.get("envelopes") or []
        if isinstance(row, Mapping) and row.get("envelope_id")
    }
    for envelope_id, prior in prior_envelopes.items():
        candidate = candidate_envelopes.get(envelope_id)
        if candidate is None:
            raise RevisionConflict(
                f"candidate plan omits persisted physical evidence envelope {envelope_id!r}"
            )
        if candidate != prior:
            raise RevisionConflict(
                f"candidate plan rewrites persisted physical evidence envelope {envelope_id!r}"
            )

    prior_entries = [
        _canonical_ledger_entry(row)
        for row in prior_audit.get("ledger_entries") or []
        if isinstance(row, Mapping)
    ]
    candidate_entries = [
        _canonical_ledger_entry(row)
        for row in candidate_audit.get("ledger_entries") or []
        if isinstance(row, Mapping)
    ]
    if len(candidate_entries) < len(prior_entries):
        raise RevisionConflict(
            "candidate authorization ledger is shorter than the persisted ledger"
        )
    for index, prior in enumerate(prior_entries):
        if candidate_entries[index] != prior:
            raise RevisionConflict(
                "candidate authorization ledger rewrites the persisted prefix "
                f"at sequence {index + 1}"
            )


def _carry_prior_physical_state(
    candidate: Mapping[str, Any],
    prior: Mapping[str, Any],
) -> Dict[str, Any]:
    updated = dict(candidate)
    prior_audit = _mapping(prior.get("audited_physical_evidence"))
    if not prior_audit:
        return updated

    candidate_audit = _mapping(updated.get("audited_physical_evidence"))
    if candidate_audit:
        _assert_history_continuity(prior_audit, candidate_audit)
    else:
        updated["audited_physical_evidence"] = prior_audit
        for key in (
            "physical_evidence_package",
            "scoped_release_assessment",
            "physical_authorization_revalidation",
        ):
            value = prior.get(key)
            if value is not None:
                updated[key] = value

    revalidated = revalidate_physical_authorization_state(updated)
    status = build_engineering_status(revalidated)
    status_payload = status.model_dump(mode="json")
    revalidated["engineering_status"] = status_payload

    readiness = dict(revalidated.get("engineering_readiness") or {})
    readiness.update(
        {
            "status": status.overall_status,
            "current_phase": status.current_phase,
            "unified_blocker_count": len(status.blockers),
            "unified_advisory_count": len(status.advisories),
            "next_action_id": status.next_action_id,
            "physical_audit_history_preserved": True,
            "physical_authorization_revalidated": True,
            "automatic_authorization": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }
    )
    revalidated["engineering_readiness"] = readiness

    scenario = dict(revalidated.get("scenario") or {})
    compile_spec = dict(scenario.get("compile_spec") or {})
    compile_spec["engineering_status"] = status_payload
    compile_spec["audited_physical_evidence"] = revalidated.get(
        "audited_physical_evidence"
    )
    compile_spec["scoped_release_assessment"] = revalidated.get(
        "scoped_release_assessment"
    )
    scenario["compile_spec"] = compile_spec
    scenario["physical_audit_persistence_guard"] = {
        "schema_version": PHYSICAL_AUDIT_PERSISTENCE_GUARD_SCHEMA,
        "history_preserved": True,
        "authorization_revalidated": True,
        "automatic_authorization": False,
        "global_authority_flags_unchanged": True,
    }
    revalidated["scenario"] = scenario
    revalidated["physical_audit_persistence_guard"] = {
        "schema_version": PHYSICAL_AUDIT_PERSISTENCE_GUARD_SCHEMA,
        "history_preserved": True,
        "authorization_revalidated": True,
        "automatic_authorization": False,
        "authorization_carries_across_revisions": False,
    }
    return revalidated


def install_engineering_plan_store_audit_guard() -> None:
    if getattr(_target, "_physical_audit_guard_installed", False):
        return
    original = _target.save_engineering_plan

    def save_engineering_plan(
        store,
        plan: Mapping[str, Any],
        *,
        project_id: str | None = None,
        expected_revision: int | None = None,
    ):
        resolved_id = _target.resolve_engineering_project_id(
            plan,
            project_id=project_id,
        )
        prepared = dict(plan)
        try:
            latest = store.load_latest_with_recovery(resolved_id)
        except ProjectNotFound:
            latest = None

        if latest is not None:
            latest_revision = int(latest["revision"])
            prior_plan = _stored_engineering_plan(latest)
            prior_audit = _mapping(prior_plan.get("audited_physical_evidence"))
            if prior_audit:
                if expected_revision is None:
                    raise RevisionConflict(
                        "expected_revision is required when saving a project with "
                        "persisted physical audit history"
                    )
                if int(expected_revision) != latest_revision:
                    raise RevisionConflict(
                        f"project {resolved_id!r} is at revision {latest_revision}, "
                        f"expected {expected_revision}"
                    )
                prepared = _carry_prior_physical_state(prepared, prior_plan)

        return original(
            store,
            prepared,
            project_id=resolved_id,
            expected_revision=expected_revision,
        )

    _target.save_engineering_plan = save_engineering_plan
    _target._physical_audit_guard_installed = True


install_engineering_plan_store_audit_guard()

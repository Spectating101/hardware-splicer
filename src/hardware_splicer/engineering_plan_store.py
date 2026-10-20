"""Persistence helpers for enriched guided engineering plans."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Sequence

from pydantic import ValidationError

from .engineering_review_identity import AUTHORITY_CEILING
from .finding_ledger import (
    ENGINEERING_FINDINGS_KEY,
    bound_finding_text,
    replace_producer_findings,
)
from .machine_project import MachineProject
from .project_store import ProjectNotFound, ProjectStore, RevisionConflict

_RELEASE_ASSESSMENT_BASIS = (
    "computed by MachineProject.assess_release over the stored machine project"
)


def resolve_engineering_project_id(
    plan: Mapping[str, Any],
    *,
    project_id: str | None = None,
) -> str:
    """Resolve the stable project identity used by engineering-plan persistence.

    An explicit route/request identity wins so callers can target a known project,
    while callers that omit it inherit the identity embedded in the plan.  The
    physical-evidence persistence layer compares both forms before writing, which
    prevents an explicit project ID from silently rebinding a plan from another
    project.
    """

    explicit = str(project_id or "").strip()
    if explicit:
        return explicit

    machine_project = (
        plan.get("machine_project")
        if isinstance(plan.get("machine_project"), Mapping)
        else {}
    )
    for candidate in (
        machine_project.get("project_id"),
        plan.get("project_id"),
        plan.get("project_name"),
    ):
        resolved = str(candidate or "").strip()
        if resolved:
            return resolved
    return "engineering-project"


def _copy_previous_engineering_findings(
    snapshot: Dict[str, Any],
    previous_snapshot: Mapping[str, Any] | None,
) -> None:
    """Carry the persisted ledger only. Plan input is never a source of rows.

    The key is copied whenever it is present on the previous snapshot, including
    ``None``, strings, and dicts. Those malformed values must remain visible so
    the read projection can surface them. Omit the key only when it is absent.
    """

    if not isinstance(previous_snapshot, Mapping):
        return
    if ENGINEERING_FINDINGS_KEY not in previous_snapshot:
        return
    snapshot[ENGINEERING_FINDINGS_KEY] = deepcopy(
        previous_snapshot[ENGINEERING_FINDINGS_KEY]
    )


def engineering_snapshot(
    plan: Mapping[str, Any],
    *,
    previous_snapshot: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    machine_project = plan.get("machine_project") if isinstance(plan.get("machine_project"), Mapping) else {}
    project_id = resolve_engineering_project_id(plan)
    # A plan is untrusted request input. Never take or echo engineeringFindings
    # from it; only the previously persisted snapshot may carry the ledger.
    plan_body = dict(plan)
    plan_body.pop(ENGINEERING_FINDINGS_KEY, None)
    snapshot = {
        "snapshot_schema_version": "hardware_splicer.engineering_project_snapshot.v1",
        "projectId": project_id,
        "projectName": str(machine_project.get("name") or plan.get("project_name") or project_id),
        "mode": str((plan.get("engineering_context") or {}).get("normalized_mode") or "greenfield"),
        "currentStage": "guided_engineering_plan",
        "engineeringPlan": plan_body,
        "machineProject": dict(machine_project),
        "engineeringSourceGraph": dict(plan.get("engineering_source_graph") or {}),
        "robotTopology": dict(plan.get("robot_topology") or {}),
        "engineeringAnalysis": dict(plan.get("engineering_analysis") or {}),
        "changeImpact": dict(plan.get("change_impact") or {}),
        "engineeringIdentityMap": dict(plan.get("engineering_identity_map") or {}),
        "verificationBridge": dict(plan.get("verification_bridge") or {}),
        "engineeringArtifactProjection": dict(plan.get("engineering_artifact_projection") or {}),
        "manufacturingProjection": dict(plan.get("manufacturing_projection") or {}),
        "manufacturingClosure": dict(plan.get("manufacturing_closure") or {}),
        "engineeringExecutionPlan": dict(plan.get("engineering_execution_plan") or {}),
        "operatorGuide": dict(plan.get("operator_guide") or {}),
        "orderedSteps": list(plan.get("ordered_steps") or []),
        "sourceAdapter": dict(plan.get("source_adapter") or {}),
        "engineeringReadiness": dict(plan.get("engineering_readiness") or {}),
        "engineeringStatus": dict(plan.get("engineering_status") or {}),
        "missingInfo": list(plan.get("missing_info") or []),
    }
    _copy_previous_engineering_findings(snapshot, previous_snapshot)
    # Chemistry remains an immutable, review-recorded project discipline,
    # not an input surface on the untrusted engineering planner. Preserve
    # it from the previous accepted snapshot across ordinary re-plans and
    # physical evidence updates; never trust new plan JSON for these rows.
    if isinstance(previous_snapshot, Mapping) and "practicalChemistryAssessments" in previous_snapshot:
        snapshot["practicalChemistryAssessments"] = deepcopy(
            previous_snapshot["practicalChemistryAssessments"]
        )
    return snapshot


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)] if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _prior_engineering_plan(
    store: ProjectStore, project_id: str
) -> tuple[int, Dict[str, Any], Dict[str, Any]] | None:
    try:
        envelope = store.load(project_id)
    except ProjectNotFound:
        return None
    snapshot = envelope.get("snapshot") if isinstance(envelope.get("snapshot"), Mapping) else {}
    plan = snapshot.get("engineeringPlan") if isinstance(snapshot.get("engineeringPlan"), Mapping) else {}
    return (
        int(envelope.get("revision") or 0),
        deepcopy(dict(plan)),
        deepcopy(dict(snapshot)),
    )


def _persisted_machine_project(snapshot: Mapping[str, Any]) -> MachineProject | None:
    raw = snapshot.get("machineProject")
    if not isinstance(raw, Mapping) or not raw:
        return None
    try:
        return MachineProject.model_validate(raw)
    except (ValidationError, TypeError, ValueError):
        return None


def _release_assessment_findings(project: MachineProject) -> list[Dict[str, Any]]:
    # Recompute from the persisted machine project. Never read a caller-supplied
    # scoped_release_assessment — that is untrusted request input.
    assessment = project.assess_release()
    entries: list[Dict[str, Any]] = []
    for blocker in assessment.blockers:
        text, truncated = bound_finding_text(str(blocker.message or "").strip())
        if not text:
            continue
        basis = _RELEASE_ASSESSMENT_BASIS
        if truncated:
            basis = f"{basis} (message truncated)"
        object_id = str(blocker.object_id or "").strip() or None
        source_ref = str(blocker.code or "").strip() or None
        entries.append(
            {
                "category": "release_blocker",
                "object_id": object_id,
                "text": text,
                "provenance": {
                    "kind": "deterministic",
                    "basis": basis,
                    "source_ref": source_ref,
                    "authority_ceiling": AUTHORITY_CEILING,
                },
            }
        )
    return entries


def _record_release_assessment_findings(
    snapshot: Mapping[str, Any],
    revision: int,
) -> Dict[str, Any]:
    project = _persisted_machine_project(snapshot)
    if project is None:
        return dict(snapshot)
    return replace_producer_findings(
        snapshot,
        "release_assessment",
        f"assess_release@rev{revision}",
        _release_assessment_findings(project),
    )


def _assert_audit_history_not_rewritten(
    prior_audit: Mapping[str, Any],
    candidate_plan: Mapping[str, Any],
) -> None:
    """Reject caller attempts to edit immutable persisted envelope/ledger history.

    A normal replan is allowed to omit audit history entirely; the store carries it forward.
    If a caller explicitly supplies audit history, its persisted prefix must be byte-for-byte
    equivalent at the canonical JSON-object level. New physical evidence belongs through the
    dedicated evidence APIs, not a generic engineering-plan overwrite.
    """

    candidate_audit = candidate_plan.get("audited_physical_evidence")
    if candidate_audit is None:
        return
    if not isinstance(candidate_audit, Mapping):
        raise RevisionConflict("candidate rewrites persisted physical evidence audit history")

    prior_envelopes = _rows(prior_audit.get("envelopes"))
    candidate_envelopes = _rows(candidate_audit.get("envelopes"))
    if len(candidate_envelopes) != len(prior_envelopes):
        raise RevisionConflict("candidate rewrites persisted physical evidence envelope history")
    by_id = {str(row.get("envelope_id") or ""): row for row in candidate_envelopes}
    for persisted in prior_envelopes:
        envelope_id = str(persisted.get("envelope_id") or "")
        submitted = by_id.get(envelope_id)
        if submitted != persisted:
            raise RevisionConflict(
                f"candidate rewrites persisted physical evidence envelope {envelope_id!r}"
            )

    prior_ledger = _rows(prior_audit.get("ledger_entries"))
    candidate_ledger = _rows(candidate_audit.get("ledger_entries"))
    if len(candidate_ledger) != len(prior_ledger):
        raise RevisionConflict("candidate rewrites the persisted prefix of authorization ledger history")
    for index, persisted in enumerate(prior_ledger):
        if candidate_ledger[index] != persisted:
            raise RevisionConflict(
                f"candidate rewrites the persisted prefix of authorization ledger history at sequence {index + 1}"
            )


def _reapply_persisted_audit_history(
    plan: Mapping[str, Any],
    prior_plan: Mapping[str, Any],
) -> Dict[str, Any]:
    prior_audit = prior_plan.get("audited_physical_evidence")
    if not isinstance(prior_audit, Mapping):
        return deepcopy(dict(plan))

    _assert_audit_history_not_rewritten(prior_audit, plan)
    physical_package = prior_audit.get("physical_package") if isinstance(prior_audit.get("physical_package"), Mapping) else {}
    calibrations = _rows(physical_package.get("calibrations"))
    envelopes = _rows(prior_audit.get("envelopes"))
    ledger_entries = _rows(prior_audit.get("ledger_entries"))

    requested_operations: list[str] = []
    scope_id: str | None = None
    if ledger_entries:
        latest = ledger_entries[-1]
        decision = latest.get("decision") if isinstance(latest.get("decision"), Mapping) else {}
        scope = decision.get("scope") if isinstance(decision.get("scope"), Mapping) else {}
        requested_operations = [str(value) for value in scope.get("operations") or [] if str(value)]
        scope_id = str(scope.get("scope_id") or "").strip() or None

    from .audited_physical_evidence_plan_update import apply_audited_physical_evidence_to_plan

    candidate = deepcopy(dict(plan))
    # Reassessment must compare the persisted audit package against the new candidate, not
    # treat a caller copy of the old audit as candidate truth.
    candidate.pop("audited_physical_evidence", None)
    candidate.pop("physical_evidence_package", None)
    candidate.pop("scoped_release_assessment", None)
    updated = apply_audited_physical_evidence_to_plan(
        candidate,
        calibrations=calibrations,
        envelopes=envelopes,
        ledger_entries=ledger_entries,
        requested_operations=requested_operations,
        scope_id=scope_id,
        require_server_attestation=bool(
            (prior_audit.get("metadata") or {}).get("server_attestation_required")
            if isinstance(prior_audit.get("metadata"), Mapping)
            else False
        ),
    )
    readiness = dict(updated.get("engineering_readiness") or {})
    readiness.update(
        {
            "physical_audit_history_preserved": True,
            "physical_authorization_revalidated": True,
            "scoped_authorized_operations": (
                list(readiness.get("scoped_authorized_operations") or [])
                if bool((updated.get("audited_physical_evidence") or {}).get("applicable"))
                else []
            ),
        }
    )
    updated["engineering_readiness"] = readiness
    updated["physical_audit_persistence_guard"] = {
        "schema_version": "hardware_splicer.physical_audit_persistence_guard.v1",
        "history_preserved": True,
        "revalidated_for_candidate_revision": True,
        "authorization_carries_across_revisions": False,
        "automatic_authorization": False,
    }
    return updated


def save_engineering_plan(
    store: ProjectStore,
    plan: Mapping[str, Any],
    *,
    project_id: str | None = None,
    expected_revision: int | None = None,
) -> Dict[str, Any]:
    resolved_project_id = resolve_engineering_project_id(plan, project_id=project_id)
    prior = _prior_engineering_plan(store, resolved_project_id)
    persisted_plan: Dict[str, Any] = deepcopy(dict(plan))
    previous_snapshot: Dict[str, Any] | None = None
    next_revision = 1
    if prior is not None:
        prior_revision, prior_plan, previous_snapshot = prior
        next_revision = prior_revision + 1
        prior_audit = prior_plan.get("audited_physical_evidence")
        if isinstance(prior_audit, Mapping):
            if expected_revision is None:
                raise RevisionConflict(
                    "expected_revision is required when persisted physical audit history exists"
                )
            if int(expected_revision) != prior_revision:
                raise RevisionConflict(
                    f"project {resolved_project_id!r} is at revision {prior_revision}, expected {expected_revision}"
                )
            persisted_plan = _reapply_persisted_audit_history(persisted_plan, prior_plan)

    # A planned engineering snapshot may retain chemical screening decisions
    # outside its plan payload. Recompute the gate from the persisted previous
    # project revision, rather than trusting a caller-supplied plan's status.
    if previous_snapshot is not None:
        from .project_chemistry_release_gate import (
            apply_chemistry_hold_to_plan, evaluate_project_chemistry_gate,
        )
        chemistry = evaluate_project_chemistry_gate(
            previous_snapshot, project_id=resolved_project_id,
        )
        persisted_plan = apply_chemistry_hold_to_plan(persisted_plan, chemistry)
    snapshot = engineering_snapshot(persisted_plan, previous_snapshot=previous_snapshot)
    snapshot["projectId"] = resolved_project_id
    machine_project = snapshot.get("machineProject")
    if isinstance(machine_project, dict):
        machine_project["project_id"] = resolved_project_id
    snapshot = _record_release_assessment_findings(snapshot, next_revision)
    readiness = persisted_plan.get("engineering_readiness") if isinstance(persisted_plan.get("engineering_readiness"), Mapping) else {}
    return store.save(
        resolved_project_id,
        snapshot,
        expected_revision=expected_revision,
        metadata={
            "source": "guided_engineering_planner",
            "engineering_plan_schema": persisted_plan.get("schema_version"),
            "native_robot_genre": persisted_plan.get("native_robot_genre"),
            "blocking_source_conflict_count": readiness.get("blocking_source_conflict_count"),
            "blocking_analysis_finding_count": readiness.get("blocking_analysis_finding_count"),
            "blocking_change_impact_count": readiness.get("blocking_change_impact_count"),
            "manufacturing_closure_status": readiness.get("manufacturing_closure_status"),
            "manufacturing_closure_blocker_count": readiness.get("manufacturing_closure_blocker_count"),
            "bounded_execution_check_count": readiness.get("bounded_execution_check_count"),
            "bounded_execution_unresolved_count": readiness.get("bounded_execution_unresolved_count"),
            "operator_guide_step_count": readiness.get("operator_guide_step_count"),
            "verification_method_count": readiness.get("verification_method_count"),
            "physical_authority_unchanged": True,
            "manufacturing_authority_unchanged": True,
            "automatic_execution": False,
            "physical_audit_history_preserved": bool(readiness.get("physical_audit_history_preserved")),
        },
    )

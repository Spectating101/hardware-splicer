"""Project-scoped chemistry gate for release, fabrication and physical operations.

The stored chemistry advisor is a screening record, not a chemistry certificate.
When assessments exist, all physical operation/release gates remain closed until
independent validation is integrated. This module does NOT invent a clearance
path based on caller flags, source URLs or an accepted project review.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .finding_ledger import validate_ledger_entry
from .machine_project import (
    MachineProject, ReleaseAssessment, ReleaseState, TraceabilityIssue,
)
from .machine_release import assessment_allows
from .project_practical_chemistry_api import (
    CHEMISTRY_FINDINGS_PRODUCER,
    PROJECT_PRACTICAL_CHEMISTRY_SCHEMA,
    SNAPSHOT_KEY,
    _validate_retained_assessment,
)

GATE_SCHEMA = "hardware_splicer.project_chemistry_release_gate.v1"
_PHYSICAL_STATES = (
    ReleaseState.BUILD_READY,
    ReleaseState.BENCH_READY,
    ReleaseState.OPERATIONALLY_AUTHORIZED,
)


def evaluate_project_chemistry_gate(
    snapshot: Mapping[str, Any], *, project_id: str,
) -> dict[str, Any]:
    """Compute policy from persisted project records; never use cached allowed flags."""
    issues: list[dict[str, Any]] = []
    rows = snapshot.get(SNAPSHOT_KEY)
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        issues.append({"code": "chemistry_assessments_malformed",
                       "component_id": None,
                       "reason": "Practical chemistry records are malformed"})
        rows = []
    if len(rows) > 256:
        issues.append({"code": "chemistry_assessment_limit_exceeded",
                       "component_id": None,
                       "reason": "Too many chemistry assessments to validate safely"})
        rows = rows[:256]

    ledger = snapshot.get("engineeringFindings", [])
    if not isinstance(ledger, list):
        issues.append({"code": "chemistry_ledger_malformed",
                       "component_id": None,
                       "reason": "Engineering findings ledger is malformed"})
        ledger = []
    stored_chemistry_rows = [
        row for row in ledger
        if isinstance(row, Mapping) and row.get("producer") == CHEMISTRY_FINDINGS_PRODUCER
    ]
    if stored_chemistry_rows and not rows:
        issues.append({"code": "chemistry_findings_orphaned",
                       "component_id": None,
                       "reason": "Chemistry findings exist without a retained assessment"})

    raw_machine = snapshot.get("machineProject") or snapshot.get("machine_project")
    try:
        current_components = {
            row.component_id for row in MachineProject.model_validate(raw_machine).components
        } if isinstance(raw_machine, Mapping) else set()
    except (ValueError, TypeError):
        current_components = set()
    observed_components: set[str] = set()
    observed_assessments: set[str] = set()
    blocked = bool(issues)
    for row in rows:
        if not isinstance(row, dict):
            issues.append({"code": "chemistry_record_invalid",
                           "component_id": None,
                           "reason": "A retained chemistry record is not an object"})
            blocked = True
            continue
        component = row.get("component_id")
        assessment_id = row.get("assessment_id")
        if not isinstance(component, str) or not component or component in observed_components:
            issues.append({"code": "chemistry_component_duplicate_or_missing",
                           "component_id": component if isinstance(component,str) else None,
                           "reason": "Duplicate/missing target component in chemistry records"})
            blocked = True
            continue
        observed_components.add(component)
        if component not in current_components:
            issues.append({
                "code": "chemistry_component_not_in_machine_project",
                "component_id": component,
                "reason": "A retained chemistry assessment targets a component absent from this revision",
            })
            blocked = True
        if not isinstance(assessment_id, str) or assessment_id in observed_assessments:
            issues.append({"code": "chemistry_assessment_id_invalid",
                           "component_id": component,
                           "reason": "Duplicate/missing chemical assessment identity"})
            blocked = True
            continue
        observed_assessments.add(assessment_id)
        try:
            _validate_retained_assessment(row, project_id)
            if not isinstance(row.get("input_request"), dict) or not isinstance(row.get("assessment"), dict):
                raise ValueError("Missing computation provenance")
            report = row["assessment"]
            if report.get("physical_action_authorized") is not False:
                raise ValueError("Chemistry advisor must not authorize physical operations")
            if report.get("release_authorized") is not False:
                raise ValueError("Chemistry advisor must not authorize release")
            if not report.get("independent_repair_validation_required"):
                raise ValueError("Missing independent validation condition")
            if row.get("manufacturer_source_revision_verified") is not False:
                raise ValueError("Source revision evidence cannot be caller-claimed verified")
        except (TypeError, ValueError, KeyError) as exc:
            issues.append({"code": "chemistry_integrity_or_authority_failure",
                           "component_id": component,
                           "reason": "Retained chemistry record fails integrity/authority: " + str(exc)[:160]})
            blocked = True
            continue
        matching_release = []
        for entry in stored_chemistry_rows:
            try:
                item = validate_ledger_entry(entry)
            except (ValueError, TypeError):
                continue
            if (item["object_id"] == component
                and item["category"] == "release_blocker"
                and item["provenance"]["source_ref"] == assessment_id):
                matching_release.append(item)
        if not matching_release:
            issues.append({"code": "chemistry_release_finding_missing",
                           "component_id": component,
                           "reason": "Retained chemistry assessment has no corresponding valid release finding"})
        # An accepted review records that the assessment exists, not that the
        # materials are compatible or safe. Independent assay clearance is NOT
        # implemented: all observed chemistry assessments keep this gate closed.
        issues.append({
            "code": "chemistry_independent_validation_required",
            "component_id": component,
            "reason": (
                "Practical chemistry assessment is not independent physical "
                "validation and cannot authorize fabrication or operation"
            ),
        })
        blocked = True
    for entry in stored_chemistry_rows:
        if not isinstance(entry, Mapping):
            blocked = True
            issues.append({"code": "chemistry_ledger_row_invalid", "component_id": None,
                           "reason": "Malformed chemistry provenance entry"})
            continue
        source = entry.get("provenance")
        aid = source.get("source_ref") if isinstance(source, Mapping) else None
        try:
            validate_ledger_entry(entry)
        except (TypeError, ValueError):
            issues.append({"code": "chemistry_ledger_row_invalid",
                           "component_id": entry.get("object_id"),
                           "reason": "Chemistry finding has invalid provenance or altered identifier"})
            blocked = True
        if aid not in observed_assessments:
            issues.append({"code": "chemistry_orphaned_release_finding",
                           "component_id": entry.get("object_id"),
                           "reason": "Chemistry finding references a removed or unrecognized assessment"})
            blocked = True

    if not blocked:
        status = "not_applicable"
    else:
        status = "blocked"
    return {
        "schema_version": GATE_SCHEMA,
        "project_id": project_id,
        "status": status,
        "blocked": blocked,
        "assessment_count": len(rows),
        "release_allowed_by_chemistry": not blocked,
        "physical_operations_allowed_by_chemistry": not blocked,
        "blockers": issues,
        "recomputed_from_stored_revision": True,
        "not_a_chemical_safety_certificate": True,
        "automatic_clearance": False,
        "manual_override_supported": False,
        "physical_authority_granted": False,
    }


def assess_project_release(
    project: MachineProject, snapshot: Mapping[str, Any],
    *, requested: ReleaseState | None = None,
) -> tuple[ReleaseAssessment, dict[str, Any]]:
    gate = evaluate_project_chemistry_gate(snapshot, project_id=project.project_id)
    assessment = project.assess_release(requested=requested)
    if not gate["blocked"]:
        return assessment, gate
    target = requested or project.requested_release_state
    blockers = list(assessment.blockers)
    blockers.extend(
        TraceabilityIssue(
            code=issue["code"],
            object_id=issue.get("component_id"),
            message=issue["reason"],
        )
        for issue in gate["blockers"]
    )
    # A chemistry screen cannot cause a transition to BUILD_READY, BENCH_READY
    # or OPERATIONALLY_AUTHORIZED, even if other disciplines have passed.
    new_achieved = assessment.achieved_state
    if new_achieved in _PHYSICAL_STATES:
        new_achieved = ReleaseState.DESIGN_READY
    if new_achieved != assessment.achieved_state:
        blockers.append(TraceabilityIssue(
            code="chemistry_release_state_downgraded",
            object_id=project.project_id,
            message=f"Chemistry gate limits supported release to {new_achieved.value}",
        ))
    return assessment.model_copy(update={
        "achieved_state": new_achieved,
        "blockers": blockers,
    }), gate


def block_audited_physical_authorization(audited: Any, gate: Mapping[str, Any]) -> Any:
    """Revoke every derived grant surface, without rewriting raw evidence/ledger.

    The original human decision and evidence remain as historical data, but
    no nested physical_package.assessment may report applicability or allowed
    physical operations while chemistry clearance is unavailable.
    """
    if not gate.get("blocked"):
        return audited
    messages = [
        "Practical chemistry gate blocks physical authorization: "
        + row["code"]
        for row in gate["blockers"]
    ]
    existing = audited.physical_package.assessment
    assessment = existing.model_copy(update={
        "applicable": False,
        "authorized_operations": [],
        "status": "blocked",
        "blockers": list(dict.fromkeys([*existing.blockers, *messages])),
    })
    physical_package = audited.physical_package.model_copy(
        update={"assessment": assessment},
    )
    return audited.model_copy(update={
        "physical_package": physical_package,
        "applicable": False,
        "blockers": list(dict.fromkeys([*audited.blockers, *messages])),
    })


def apply_chemistry_hold_to_plan(
    plan: Mapping[str, Any], gate: Mapping[str, Any],
) -> dict[str, Any]:
    """Close ALL derived physical-scoped permissions on a plan without losing evidence."""
    from copy import deepcopy

    updated = deepcopy(dict(plan))
    if not gate.get("blocked"):
        return updated
    explanations = [
        "Chemistry release gate: " + row["code"]
        for row in gate["blockers"]
    ]
    for key in ("physical_evidence_package",):
        package = updated.get(key)
        if not isinstance(package, dict):
            continue
        assessment = package.get("assessment")
        if isinstance(assessment, dict):
            assessment["applicable"] = False
            assessment["authorized_operations"] = []
            assessment["status"] = "blocked"
            assessment["blockers"] = list(dict.fromkeys(
                [*assessment.get("blockers", []), *explanations]
            ))
    audited = updated.get("audited_physical_evidence")
    if isinstance(audited, dict):
        audited["applicable"] = False
        audited["blockers"] = list(dict.fromkeys(
            [*audited.get("blockers", []), *explanations]
        ))
        pack = audited.get("physical_package")
        if isinstance(pack, dict) and isinstance(pack.get("assessment"), dict):
            assessment = pack["assessment"]
            assessment["applicable"] = False
            assessment["authorized_operations"] = []
            assessment["status"] = "blocked"
            assessment["blockers"] = list(dict.fromkeys(
                [*assessment.get("blockers", []), *explanations]
            ))
    scoped = updated.get("scoped_release_assessment")
    if isinstance(scoped, dict):
        scoped["allowed"] = False
        scoped["allowed_operations"] = []
        scoped["status"] = "blocked"
        scoped["blockers"] = list(dict.fromkeys(
            [*scoped.get("blockers", []), *explanations]
        ))
    readiness = updated.get("engineering_readiness")
    if isinstance(readiness, dict):
        readiness["scoped_authorized_operations"] = []
        readiness["physical_scope_authorized"] = False
        readiness["chemistry_release_gate_blocked"] = True
    status = updated.get("engineering_status")
    if isinstance(status, dict):
        metadata = status.get("metadata")
        if isinstance(metadata, dict):
            metadata["physical_scope_authorized"] = False
            metadata["authorized_operations"] = []
    updated["chemistry_release_gate"] = deepcopy(dict(gate))
    return updated

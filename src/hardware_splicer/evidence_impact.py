"""Selective evidence invalidation for platform-to-derivative engineering.

The impact engine answers one deliberately narrow question:

    Given an explicit dependency graph and an explicit change set, which inherited
    evidence remains usable, which evidence is invalidated, and which evidence must
    remain blocked because dependency coverage is unresolved?

It does not infer hidden dependency relationships and it does not grant physical
or release authority. A missing dependency declaration is therefore not treated as
proof that evidence survives a change.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Iterable, Mapping

EVIDENCE_IMPACT_SCHEMA = "hardware_splicer.evidence_impact.v1"
EVIDENCE_IMPACT_CASE_SCHEMA = "hardware_splicer.evidence_impact_case.v1"

RETAINED = "retained"
INVALIDATED = "invalidated"
BLOCKED = "blocked"


def _unique_strings(values: Iterable[Any]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _dependency_cycle(evidence_dependencies: Mapping[str, list[str]]) -> list[str] | None:
    """Return one evidence-to-evidence cycle, if present."""

    evidence_ids = set(evidence_dependencies)
    visiting: list[str] = []
    visiting_set: set[str] = set()
    visited: set[str] = set()

    def visit(evidence_id: str) -> list[str] | None:
        if evidence_id in visiting_set:
            start = visiting.index(evidence_id)
            return [*visiting[start:], evidence_id]
        if evidence_id in visited:
            return None
        visiting.append(evidence_id)
        visiting_set.add(evidence_id)
        for dependency_id in evidence_dependencies[evidence_id]:
            if dependency_id in evidence_ids:
                cycle = visit(dependency_id)
                if cycle:
                    return cycle
        visiting.pop()
        visiting_set.remove(evidence_id)
        visited.add(evidence_id)
        return None

    for evidence_id in evidence_dependencies:
        cycle = visit(evidence_id)
        if cycle:
            return cycle
    return None


def evaluate_evidence_impact(case: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate selective evidence reuse from an explicit dependency/change case.

    Input evidence rows use:

    - ``evidence_id``: stable evidence identity;
    - ``depends_on``: external dependency ids and/or other evidence ids;
    - ``dependencies_complete``: explicit assertion that dependency coverage for
      this reuse decision is complete.

    Changed dependencies invalidate direct dependents and propagate transitively.
    Unresolved dependencies block direct dependents and propagate transitively.
    Invalidation dominates blocking because a known stale dependency is already
    sufficient to reject reuse.
    """

    source = deepcopy(dict(case))
    errors: list[str] = []
    if source.get("schema_version") not in {None, EVIDENCE_IMPACT_CASE_SCHEMA}:
        errors.append("unsupported_schema_version")

    raw_rows = source.get("evidence_items")
    if not isinstance(raw_rows, list):
        raw_rows = []
        errors.append("evidence_items_must_be_list")

    rows: list[dict[str, Any]] = []
    ids: list[str] = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, Mapping):
            errors.append(f"evidence_item_{index}_must_be_mapping")
            continue
        row = dict(raw)
        evidence_id = str(row.get("evidence_id") or "").strip()
        if not evidence_id:
            errors.append(f"evidence_item_{index}_missing_id")
            continue
        ids.append(evidence_id)
        row["evidence_id"] = evidence_id
        row["depends_on"] = _unique_strings(row.get("depends_on") or [])
        row["dependencies_complete"] = row.get("dependencies_complete") is True
        rows.append(row)

    duplicates = sorted(value for value, count in Counter(ids).items() if count > 1)
    if duplicates:
        errors.append("duplicate_evidence_ids:" + ",".join(duplicates))

    dependencies = {row["evidence_id"]: list(row["depends_on"]) for row in rows}
    cycle = _dependency_cycle(dependencies) if not duplicates else None
    if cycle:
        errors.append("evidence_dependency_cycle:" + "->".join(cycle))

    changed = set(_unique_strings(source.get("changed_dependency_ids") or []))
    unresolved = set(_unique_strings(source.get("unresolved_dependency_ids") or []))
    overlap = sorted(changed & unresolved)
    if overlap:
        errors.append("dependency_marked_changed_and_unresolved:" + ",".join(overlap))

    if errors:
        return {
            "schema_version": EVIDENCE_IMPACT_SCHEMA,
            "status": "invalid",
            "validation_errors": errors,
            "changed_dependency_ids": sorted(changed),
            "unresolved_dependency_ids": sorted(unresolved),
            "results": [],
            "summary": {"retained": 0, "invalidated": 0, "blocked": 0},
        }

    evidence_ids = set(dependencies)
    status: dict[str, str] = {}
    reasons: dict[str, list[dict[str, Any]]] = {}

    # Resolve in fixed-point iterations so evidence-to-evidence dependencies can
    # propagate without requiring callers to topologically order the input.
    for _ in range(len(rows) + 1):
        changed_any = False
        for row in rows:
            evidence_id = row["evidence_id"]
            deps = dependencies[evidence_id]
            direct_changed = sorted(dep for dep in deps if dep in changed)
            upstream_invalidated = sorted(
                dep for dep in deps if dep in evidence_ids and status.get(dep) == INVALIDATED
            )
            direct_unresolved = sorted(dep for dep in deps if dep in unresolved)
            upstream_blocked = sorted(
                dep for dep in deps if dep in evidence_ids and status.get(dep) == BLOCKED
            )

            next_status: str | None = None
            next_reasons: list[dict[str, Any]] = []
            if direct_changed or upstream_invalidated:
                next_status = INVALIDATED
                if direct_changed:
                    next_reasons.append({"kind": "changed_dependency", "ids": direct_changed})
                if upstream_invalidated:
                    next_reasons.append({"kind": "invalidated_upstream_evidence", "ids": upstream_invalidated})
            elif direct_unresolved or upstream_blocked or not row["dependencies_complete"]:
                next_status = BLOCKED
                if direct_unresolved:
                    next_reasons.append({"kind": "unresolved_dependency", "ids": direct_unresolved})
                if upstream_blocked:
                    next_reasons.append({"kind": "blocked_upstream_evidence", "ids": upstream_blocked})
                if not row["dependencies_complete"]:
                    next_reasons.append({"kind": "dependency_coverage_incomplete", "ids": []})
            else:
                # If an evidence dependency has not resolved yet, defer this row.
                unresolved_evidence_deps = [
                    dep for dep in deps if dep in evidence_ids and dep not in status
                ]
                if unresolved_evidence_deps:
                    continue
                next_status = RETAINED
                next_reasons.append({"kind": "all_declared_dependencies_unchanged", "ids": deps})

            if status.get(evidence_id) != next_status or reasons.get(evidence_id) != next_reasons:
                status[evidence_id] = next_status
                reasons[evidence_id] = next_reasons
                changed_any = True
        if not changed_any:
            break

    # Acyclic graphs should always resolve. Keep a defensive fail-closed branch.
    unresolved_rows = sorted(evidence_ids - set(status))
    for evidence_id in unresolved_rows:
        status[evidence_id] = BLOCKED
        reasons[evidence_id] = [{"kind": "dependency_resolution_incomplete", "ids": dependencies[evidence_id]}]

    results = [
        {
            "evidence_id": row["evidence_id"],
            "status": status[row["evidence_id"]],
            "depends_on": dependencies[row["evidence_id"]],
            "dependencies_complete": row["dependencies_complete"],
            "reasons": reasons[row["evidence_id"]],
            "metadata": deepcopy(dict(row.get("metadata") or {})),
        }
        for row in rows
    ]
    summary = {
        RETAINED: sum(item["status"] == RETAINED for item in results),
        INVALIDATED: sum(item["status"] == INVALIDATED for item in results),
        BLOCKED: sum(item["status"] == BLOCKED for item in results),
    }
    return {
        "schema_version": EVIDENCE_IMPACT_SCHEMA,
        "status": "evaluated",
        "validation_errors": [],
        "changed_dependency_ids": sorted(changed),
        "unresolved_dependency_ids": sorted(unresolved),
        "results": results,
        "summary": summary,
        "metadata": {
            "automatic_authorization": False,
            "physical_authority_granted": False,
            "unknown_dependency_coverage_blocks_reuse": True,
        },
    }


def score_evidence_invalidation(
    report: Mapping[str, Any],
    *,
    expected_invalidated_evidence_ids: Iterable[str],
    adjudicated_evidence_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Score predicted invalidations against an independently adjudicated set.

    This scorer exists so the same engine that predicts impact cannot grade its
    own dependency graph as correct by definition. Real platform experiments
    should freeze the prediction first, then supply the outer-audited expected
    invalidation set.
    """

    rows = [dict(row) for row in report.get("results") or [] if isinstance(row, Mapping)]
    known_ids = {str(row.get("evidence_id")) for row in rows if row.get("evidence_id")}
    adjudicated = (
        set(_unique_strings(adjudicated_evidence_ids))
        if adjudicated_evidence_ids is not None
        else set(known_ids)
    )
    unknown_adjudicated = sorted(adjudicated - known_ids)
    expected = set(_unique_strings(expected_invalidated_evidence_ids)) & adjudicated
    predicted = {
        str(row["evidence_id"])
        for row in rows
        if row.get("evidence_id") in adjudicated and row.get("status") == INVALIDATED
    }
    blocked = {
        str(row["evidence_id"])
        for row in rows
        if row.get("evidence_id") in adjudicated and row.get("status") == BLOCKED
    }

    true_positive = predicted & expected
    false_positive = predicted - expected
    false_negative = expected - predicted
    true_negative = adjudicated - expected - predicted

    return {
        "status": "invalid" if unknown_adjudicated else "scored",
        "validation_errors": (
            ["adjudicated_unknown_evidence_ids:" + ",".join(unknown_adjudicated)]
            if unknown_adjudicated
            else []
        ),
        "adjudicated_count": len(adjudicated),
        "predicted_invalidated_count": len(predicted),
        "expected_invalidated_count": len(expected),
        "correctly_invalidated_count": len(true_positive),
        "unnecessarily_invalidated_count": len(false_positive),
        "missed_invalidation_count": len(false_negative),
        "correctly_retained_or_blocked_count": len(true_negative),
        "blocked_evidence_count": len(blocked),
        "true_positive_ids": sorted(true_positive),
        "false_positive_ids": sorted(false_positive),
        "false_negative_ids": sorted(false_negative),
        "blocked_ids": sorted(blocked),
    }

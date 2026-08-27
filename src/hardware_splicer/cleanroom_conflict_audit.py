"""Audit whether embedded-operator reasoning covers persisted conflicting evidence.

A cleanroom run can satisfy the basic evidence contract by referencing *some* valid
source while still ignoring the other side of an explicit source conflict. This audit
closes that gap without prescribing a golden engineering answer: when persisted project
state declares that source A and source B conflict, the outer evaluator asks whether the
operator's structured requirements/actions/candidates actually referenced both sources.

Missing conflict coverage is a review signal, not physical authority. An invalid conflict
declaration that names a source absent from the persisted evidence inventory is evaluator
/ state evidence and is classified separately from model behavior.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from .cleanroom_replay import ReplayCase


SCHEMA_VERSION = "hardware_splicer.cleanroom_conflict_audit.v1"

_CONFLICT_KEYS = (
    "declared_conflicts",
    "engineeringSourceConflicts",
    "engineering_source_conflicts",
    "source_conflicts",
)
_SOURCE_KEYS = (
    "engineeringSources",
    "engineeringParsedSources",
    "engineeringSourceParserRuns",
)


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _source_inventory(snapshot: Mapping[str, Any]) -> set[str]:
    source_ids: set[str] = set()
    for key in _SOURCE_KEYS:
        for row in _rows(snapshot.get(key)):
            source_id = str(row.get("source_id") or "").strip()
            if source_id:
                source_ids.add(source_id)
    return source_ids


def _source_ids_from_conflict(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key).lower()
            if key in {"source_id", "left_source_id", "right_source_id", "lhs_source_id", "rhs_source_id"}:
                token = str(child or "").strip()
                if token:
                    result.add(token)
                continue
            if key in {"source_ids", "sources", "conflicting_source_ids"} and isinstance(child, Sequence) and not isinstance(child, (str, bytes, bytearray)):
                for item in child:
                    if isinstance(item, Mapping):
                        result.update(_source_ids_from_conflict(item))
                    else:
                        token = str(item or "").strip()
                        if token:
                            result.add(token)
                continue
            if isinstance(child, (Mapping, list, tuple)):
                result.update(_source_ids_from_conflict(child))
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            result.update(_source_ids_from_conflict(child))
    return result


def conflict_source_ids(snapshot: Mapping[str, Any]) -> set[str]:
    """Return source IDs that persisted project state explicitly puts in conflict."""

    result: set[str] = set()
    for key in _CONFLICT_KEYS:
        result.update(_source_ids_from_conflict(snapshot.get(key)))
    analysis = snapshot.get("engineeringAnalysis")
    if isinstance(analysis, Mapping):
        result.update(_source_ids_from_conflict(analysis.get("source_conflicts")))
        result.update(_source_ids_from_conflict(analysis.get("conflicts")))
    return result


def audit_conflict_source_coverage(
    replay_report: Mapping[str, Any],
    *,
    cases: Sequence[ReplayCase],
) -> Dict[str, Any]:
    """Measure evidence coverage for explicit conflict cases without asserting a solution."""

    result_by_case = {
        str(row.get("case_id") or ""): row
        for row in _rows(replay_report.get("results"))
        if str(row.get("case_id") or "")
    }
    findings: list[Dict[str, Any]] = []
    assessments: list[Dict[str, Any]] = []
    comparable = 0
    fully_covered = 0

    for case in cases:
        required = conflict_source_ids(case.snapshot)
        if not required:
            continue
        inventory = _source_inventory(case.snapshot)
        invalid = sorted(required - inventory)
        row = result_by_case.get(case.case_id) or {}
        referenced = {
            str(value).strip()
            for value in list((row.get("signature") or {}).get("referenced_source_ids") or [])
            if str(value).strip()
        }
        missing = sorted((required & inventory) - referenced)

        if invalid:
            findings.append(
                {
                    "case_id": case.case_id,
                    "primary_class": "TEST_ORACLE",
                    "confidence": "high",
                    "signal": "conflict_references_absent_source",
                    "source_ids": invalid,
                    "basis": "Persisted conflict metadata names source IDs absent from the case evidence inventory.",
                }
            )
        elif row.get("ok"):
            comparable += 1
            if not missing:
                fully_covered += 1
            else:
                findings.append(
                    {
                        "case_id": case.case_id,
                        "primary_class": "EVIDENCE_MODEL",
                        "confidence": "medium",
                        "alternatives": ["CONTEXT_CONSTRUCTION", "MODEL_REASONING"],
                        "signal": "conflict_source_undercoverage",
                        "source_ids": missing,
                        "basis": "The operator produced a valid session but did not reference every persisted source participating in the explicit conflict.",
                    }
                )

        assessments.append(
            {
                "case_id": case.case_id,
                "required_conflict_source_ids": sorted(required),
                "inventory_source_ids": sorted(inventory),
                "referenced_source_ids": sorted(referenced),
                "missing_conflict_source_ids": missing,
                "invalid_conflict_source_ids": invalid,
                "operator_session_ok": bool(row.get("ok")),
            }
        )

    coverage_rate = round(fully_covered / comparable, 4) if comparable else None
    return {
        "schema_version": SCHEMA_VERSION,
        "golden_answer_used": False,
        "correct_architecture_asserted": False,
        "status": "review" if findings else "pass",
        "conflict_case_count": len(assessments),
        "comparable_conflict_case_count": comparable,
        "fully_covered_conflict_case_count": fully_covered,
        "conflict_source_coverage_rate": coverage_rate,
        "assessments": assessments,
        "findings": findings,
    }

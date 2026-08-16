"""Deterministic evaluator for platform-to-derivative evidence.

The evaluator prefers frozen inventories, explicit task-hour logs, and externally
supplied invalidation scoring over manually typed headline counts. Missing or
internally inconsistent accounting fails closed as PENDING/INVALID rather than
being converted into favorable reuse economics.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.platform_derivative_evidence.v1"


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _unique_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def apply_invalidation_score(
    record: Mapping[str, Any], score: Mapping[str, Any]
) -> dict[str, Any]:
    """Attach independently scored invalidation counts to a derivative record.

    The scorer is expected to come from ``score_evidence_invalidation`` after the
    prediction was frozen and an outer adjudication supplied. This helper does not
    invent retained/new evidence counts or economic effort.
    """

    out = deepcopy(dict(record))
    evidence = dict(out.get("evidence_accounting") or {})
    evidence["invalidation_score"] = deepcopy(dict(score))
    if score.get("status") == "scored":
        tp = int(score.get("correctly_invalidated_count") or 0)
        fp = int(score.get("unnecessarily_invalidated_count") or 0)
        fn = int(score.get("missed_invalidation_count") or 0)
        evidence["invalidated_inherited_evidence_count"] = tp
        evidence["unnecessarily_invalidated_evidence_count"] = fp
        evidence["should_invalidate_inherited_evidence_count"] = tp + fn
    out["evidence_accounting"] = evidence
    return out


def evaluate_platform_derivative_evidence(record: Mapping[str, Any]) -> dict[str, Any]:
    """Compute reuse/economics metrics and a fail-closed hypothesis gate."""

    out = deepcopy(dict(record))
    errors: list[str] = []
    warnings: list[str] = []

    if out.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported_schema_version")

    artifacts = dict(out.get("artifact_accounting") or {})
    artifact_units_raw = artifacts.get("artifact_units")
    artifact_units = artifact_units_raw if isinstance(artifact_units_raw, list) else []
    if artifact_units_raw is not None and not isinstance(artifact_units_raw, list):
        errors.append("artifact_units_must_be_list")

    if artifact_units:
        normalized_units: list[dict[str, Any]] = []
        seen_units: set[str] = set()
        allowed_status = {"inherited", "changed", "new"}
        for index, raw in enumerate(artifact_units):
            if not isinstance(raw, Mapping):
                errors.append(f"artifact_unit_{index}_must_be_mapping")
                continue
            row = dict(raw)
            unit_id = str(row.get("unit_id") or "").strip()
            unit_class = str(row.get("class") or "").strip()
            status = str(row.get("status") or "").strip()
            if not unit_id:
                errors.append(f"artifact_unit_{index}_missing_id")
                continue
            if unit_id in seen_units:
                errors.append(f"duplicate_artifact_unit:{unit_id}")
                continue
            if not unit_class:
                errors.append(f"artifact_unit_{unit_id}_missing_class")
            if status not in allowed_status:
                errors.append(f"artifact_unit_{unit_id}_invalid_status:{status}")
            seen_units.add(unit_id)
            normalized_units.append(
                {
                    "unit_id": unit_id,
                    "class": unit_class,
                    "status": status,
                    "baseline_hash": row.get("baseline_hash"),
                    "candidate_hash": row.get("candidate_hash"),
                }
            )

        computed_total = len(normalized_units)
        computed_inherited = sum(row["status"] == "inherited" for row in normalized_units)
        computed_changed = computed_total - computed_inherited
        for field, computed in (
            ("validated_artifact_count_total", computed_total),
            ("validated_artifact_count_inherited", computed_inherited),
            ("validated_artifact_count_new_or_changed", computed_changed),
        ):
            supplied = artifacts.get(field)
            if supplied not in (None, 0, computed):
                errors.append(f"{field}_disagrees_with_artifact_units")
            artifacts[field] = computed

        class_counts: dict[str, dict[str, int]] = {}
        for row in normalized_units:
            bucket = class_counts.setdefault(row["class"], {"total": 0, "inherited": 0})
            bucket["total"] += 1
            bucket["inherited"] += int(row["status"] == "inherited")
        class_ratios = {
            key: _ratio(value["inherited"], value["total"])
            for key, value in sorted(class_counts.items())
        }
        artifacts["class_reuse_ratios"] = class_ratios
        artifacts["class_balanced_reuse_ratio"] = (
            sum(value for value in class_ratios.values() if value is not None) / len(class_ratios)
            if class_ratios
            else None
        )
        artifacts["artifact_inventory_hash"] = _hash(sorted(normalized_units, key=lambda row: row["unit_id"]))
    else:
        warnings.append("artifact_reuse_uses_manual_counts")

    total_artifacts = int(artifacts.get("validated_artifact_count_total") or 0)
    inherited_artifacts = int(artifacts.get("validated_artifact_count_inherited") or 0)
    changed_artifacts = int(artifacts.get("validated_artifact_count_new_or_changed") or 0)
    if min(total_artifacts, inherited_artifacts, changed_artifacts) < 0:
        errors.append("negative_artifact_count")
    if inherited_artifacts + changed_artifacts != total_artifacts:
        errors.append("artifact_counts_do_not_balance")
    engineering_reuse_ratio = _ratio(inherited_artifacts, total_artifacts)
    artifacts["engineering_reuse_ratio"] = engineering_reuse_ratio
    out["artifact_accounting"] = artifacts

    evidence = dict(out.get("evidence_accounting") or {})
    required_ids = _unique_strings(evidence.get("required_evidence_ids"))
    valid_inherited_ids = _unique_strings(evidence.get("valid_inherited_evidence_ids"))
    if required_ids or valid_inherited_ids:
        missing_from_required = sorted(set(valid_inherited_ids) - set(required_ids))
        if missing_from_required:
            errors.append("valid_inherited_evidence_not_in_required:" + ",".join(missing_from_required))
        supplied_required = evidence.get("required_evidence_count")
        supplied_retained = evidence.get("valid_inherited_evidence_count")
        if supplied_required not in (None, 0, len(required_ids)):
            errors.append("required_evidence_count_disagrees_with_inventory")
        if supplied_retained not in (None, 0, len(valid_inherited_ids)):
            errors.append("valid_inherited_evidence_count_disagrees_with_inventory")
        evidence["required_evidence_count"] = len(required_ids)
        evidence["valid_inherited_evidence_count"] = len(valid_inherited_ids)
        evidence["required_evidence_inventory_hash"] = _hash(sorted(required_ids))
    else:
        warnings.append("evidence_reuse_uses_manual_counts")

    invalidation_score = evidence.get("invalidation_score")
    if isinstance(invalidation_score, Mapping) and invalidation_score.get("status") == "scored":
        tp = int(invalidation_score.get("correctly_invalidated_count") or 0)
        fp = int(invalidation_score.get("unnecessarily_invalidated_count") or 0)
        fn = int(invalidation_score.get("missed_invalidation_count") or 0)
        evidence["invalidated_inherited_evidence_count"] = tp
        evidence["unnecessarily_invalidated_evidence_count"] = fp
        evidence["should_invalidate_inherited_evidence_count"] = tp + fn
    elif invalidation_score is not None:
        warnings.append("invalidation_score_not_scored")
    else:
        warnings.append("invalidation_metrics_use_manual_counts")

    required_evidence = int(evidence.get("required_evidence_count") or 0)
    retained_evidence = int(evidence.get("valid_inherited_evidence_count") or 0)
    correctly_invalidated = int(evidence.get("invalidated_inherited_evidence_count") or 0)
    unnecessary_invalidations = int(evidence.get("unnecessarily_invalidated_evidence_count") or 0)
    should_invalidate = int(
        evidence.get("should_invalidate_inherited_evidence_count")
        if evidence.get("should_invalidate_inherited_evidence_count") is not None
        else correctly_invalidated
    )

    if min(
        required_evidence,
        retained_evidence,
        correctly_invalidated,
        unnecessary_invalidations,
        should_invalidate,
    ) < 0:
        errors.append("negative_evidence_count")
    if retained_evidence > required_evidence:
        errors.append("retained_evidence_exceeds_required")
    if correctly_invalidated > should_invalidate:
        errors.append("invalidated_evidence_exceeds_should_invalidate")

    evidence_reuse_ratio = _ratio(retained_evidence, required_evidence)
    invalidation_precision = _ratio(
        correctly_invalidated,
        correctly_invalidated + unnecessary_invalidations,
    )
    invalidation_recall = _ratio(correctly_invalidated, should_invalidate)
    invalidation_f1 = None
    if invalidation_precision is not None and invalidation_recall is not None:
        invalidation_f1 = _ratio(
            2 * invalidation_precision * invalidation_recall,
            invalidation_precision + invalidation_recall,
        )

    inherited_decisions = retained_evidence + correctly_invalidated + unnecessary_invalidations
    unnecessary_invalidation_rate = _ratio(unnecessary_invalidations, inherited_decisions)

    evidence["evidence_reuse_ratio"] = evidence_reuse_ratio
    evidence["invalidation_precision"] = invalidation_precision
    evidence["invalidation_recall"] = invalidation_recall
    evidence["invalidation_f1"] = invalidation_f1
    evidence["unnecessary_invalidation_rate"] = unnecessary_invalidation_rate
    out["evidence_accounting"] = evidence

    effort = dict(out.get("effort_accounting") or {})
    baseline_hours_raw = effort.get("baseline_independent_build_hours")
    baseline_hours = float(baseline_hours_raw) if baseline_hours_raw is not None else 0.0
    baseline_type = effort.get("baseline_type")
    if baseline_hours_raw is not None and baseline_type not in {"measured", "estimated"}:
        errors.append("baseline_type_must_be_measured_or_estimated")

    task_hours = effort.get("hours_by_task_class")
    task_hours_complete = effort.get("task_hours_complete") is True
    computed_derivative_hours: float | None = None
    if task_hours_complete:
        if not isinstance(task_hours, Mapping):
            errors.append("complete_task_hours_must_be_mapping")
        else:
            values: list[float] = []
            for key, raw in task_hours.items():
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    errors.append(f"invalid_task_hours:{key}")
                    continue
                if value < 0:
                    errors.append(f"negative_task_hours:{key}")
                values.append(value)
            computed_derivative_hours = sum(values)
            supplied = effort.get("derivative_engineering_hours")
            if supplied is not None and abs(float(supplied) - computed_derivative_hours) > 1e-9:
                errors.append("derivative_engineering_hours_disagrees_with_task_log")
            effort["derivative_engineering_hours"] = computed_derivative_hours
    else:
        warnings.append("derivative_hours_not_from_complete_task_log")

    derivative_hours_raw = effort.get("derivative_engineering_hours")
    derivative_hours = float(derivative_hours_raw) if derivative_hours_raw is not None else 0.0
    if baseline_hours < 0 or derivative_hours < 0:
        errors.append("negative_effort_hours")
    marginal_engineering_ratio = _ratio(derivative_hours, baseline_hours)
    effort["marginal_engineering_ratio"] = marginal_engineering_ratio
    out["effort_accounting"] = effort

    physical = dict(out.get("physical_retest") or {})
    blank_slate_tests = int(physical.get("blank_slate_test_count") or 0)
    safely_reused = int(physical.get("tests_reused_or_safely_waived") or 0)
    rerun = int(physical.get("tests_rerun") or 0)
    if min(blank_slate_tests, safely_reused, rerun) < 0:
        errors.append("negative_physical_test_count")
    if safely_reused + rerun > blank_slate_tests:
        errors.append("physical_test_counts_exceed_blank_slate")
    physical_retest_compression = _ratio(safely_reused, blank_slate_tests)
    physical["physical_retest_compression"] = physical_retest_compression
    out["physical_retest"] = physical

    authority = dict(out.get("authority") or {})
    authority_violations = int(authority.get("violations") or 0)
    if authority_violations < 0:
        errors.append("negative_authority_violation_count")

    gate = dict(out.get("hypothesis_gate") or {})
    reuse_target = float(gate.get("engineering_reuse_ratio_target", 0.70))
    evidence_target = float(gate.get("evidence_reuse_ratio_target", 0.65))
    marginal_max = float(gate.get("marginal_engineering_ratio_max", 0.40))
    invalidation_precision_target = float(gate.get("invalidation_precision_target", 0.95))
    invalidation_recall_target = float(gate.get("invalidation_recall_target", 0.95))
    authority_max = int(gate.get("authority_violations_max", 0))

    required_metrics = {
        "engineering_reuse_ratio": engineering_reuse_ratio,
        "evidence_reuse_ratio": evidence_reuse_ratio,
        "marginal_engineering_ratio": marginal_engineering_ratio,
        "invalidation_precision": invalidation_precision,
        "invalidation_recall": invalidation_recall,
    }
    missing = sorted(name for name, value in required_metrics.items() if value is None)

    checks = {
        "engineering_reuse_ratio": engineering_reuse_ratio is not None and engineering_reuse_ratio >= reuse_target,
        "evidence_reuse_ratio": evidence_reuse_ratio is not None and evidence_reuse_ratio >= evidence_target,
        "marginal_engineering_ratio": marginal_engineering_ratio is not None and marginal_engineering_ratio <= marginal_max,
        "invalidation_precision": invalidation_precision is not None and invalidation_precision >= invalidation_precision_target,
        "invalidation_recall": invalidation_recall is not None and invalidation_recall >= invalidation_recall_target,
        "authority_violations": authority_violations <= authority_max,
    }

    proof_blockers: list[str] = []
    if gate.get("require_frozen_artifact_inventory") is True:
        if not artifact_units:
            proof_blockers.append("frozen_artifact_inventory_required")
        if not artifacts.get("baseline_inventory_hash"):
            proof_blockers.append("baseline_inventory_hash_required")
        if not artifacts.get("accounting_policy_id"):
            proof_blockers.append("artifact_accounting_policy_required")
    if gate.get("require_scored_invalidation") is True:
        if not isinstance(invalidation_score, Mapping) or invalidation_score.get("status") != "scored":
            proof_blockers.append("outer_scored_invalidation_required")
    if gate.get("require_complete_task_log") is True and not task_hours_complete:
        proof_blockers.append("complete_task_hour_log_required")
    if gate.get("require_measured_baseline") is True and baseline_type != "measured":
        proof_blockers.append("measured_independent_baseline_required")

    threshold_failures = sorted(name for name, passed in checks.items() if not passed)
    if errors:
        result = "INVALID"
    elif missing or proof_blockers:
        result = "PENDING"
    elif threshold_failures:
        result = "FAIL"
    else:
        result = "PASS"

    gate["computed_checks"] = checks
    gate["missing_metrics"] = missing
    gate["proof_blockers"] = proof_blockers
    gate["threshold_failures"] = threshold_failures
    gate["validation_errors"] = errors
    gate["measurement_warnings"] = list(dict.fromkeys(warnings))
    gate["result"] = result
    out["hypothesis_gate"] = gate
    return out

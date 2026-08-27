"""Deterministic evaluator for platform-to-derivative evidence.

The evaluator prefers frozen inventories, explicit task-hour logs, and externally
supplied invalidation scoring over manually typed headline counts. Missing or
internally inconsistent accounting fails closed as PENDING/INVALID rather than
being converted into favorable reuse economics.
"""

from __future__ import annotations

import hashlib
import json
import math
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


def _number(
    value: Any,
    *,
    field: str,
    errors: list[str],
    default: float | None = 0.0,
) -> float | None:
    """Parse a finite numeric measurement without allowing conversion failures to escape."""

    if value is None:
        return default
    if isinstance(value, bool):
        errors.append(f"invalid_number:{field}")
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"invalid_number:{field}")
        return default
    if not math.isfinite(number):
        errors.append(f"invalid_number:{field}")
        return default
    return number


def _integer(
    value: Any,
    *,
    field: str,
    errors: list[str],
    default: int | None = 0,
) -> int | None:
    """Parse a finite integral count without truncating fractions or booleans."""

    if value is None:
        return default
    if isinstance(value, bool):
        errors.append(f"invalid_integer:{field}")
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"invalid_integer:{field}")
        return default
    if not math.isfinite(number) or not number.is_integer():
        errors.append(f"invalid_integer:{field}")
        return default
    return int(number)


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
        score_errors: list[str] = []
        tp = _integer(
            score.get("correctly_invalidated_count"),
            field="invalidation_score.correctly_invalidated_count",
            errors=score_errors,
            default=None,
        )
        fp = _integer(
            score.get("unnecessarily_invalidated_count"),
            field="invalidation_score.unnecessarily_invalidated_count",
            errors=score_errors,
            default=None,
        )
        fn = _integer(
            score.get("missed_invalidation_count"),
            field="invalidation_score.missed_invalidation_count",
            errors=score_errors,
            default=None,
        )
        if not score_errors and tp is not None and fp is not None and fn is not None:
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
        artifacts["artifact_inventory_hash"] = _hash(
            sorted(normalized_units, key=lambda row: row["unit_id"])
        )
    else:
        warnings.append("artifact_reuse_uses_manual_counts")

    total_artifacts = _integer(
        artifacts.get("validated_artifact_count_total"),
        field="artifact_accounting.validated_artifact_count_total",
        errors=errors,
    )
    inherited_artifacts = _integer(
        artifacts.get("validated_artifact_count_inherited"),
        field="artifact_accounting.validated_artifact_count_inherited",
        errors=errors,
    )
    changed_artifacts = _integer(
        artifacts.get("validated_artifact_count_new_or_changed"),
        field="artifact_accounting.validated_artifact_count_new_or_changed",
        errors=errors,
    )
    assert total_artifacts is not None
    assert inherited_artifacts is not None
    assert changed_artifacts is not None
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
        tp = _integer(
            invalidation_score.get("correctly_invalidated_count"),
            field="invalidation_score.correctly_invalidated_count",
            errors=errors,
        )
        fp = _integer(
            invalidation_score.get("unnecessarily_invalidated_count"),
            field="invalidation_score.unnecessarily_invalidated_count",
            errors=errors,
        )
        fn = _integer(
            invalidation_score.get("missed_invalidation_count"),
            field="invalidation_score.missed_invalidation_count",
            errors=errors,
        )
        assert tp is not None
        assert fp is not None
        assert fn is not None
        evidence["invalidated_inherited_evidence_count"] = tp
        evidence["unnecessarily_invalidated_evidence_count"] = fp
        evidence["should_invalidate_inherited_evidence_count"] = tp + fn
    elif invalidation_score is not None:
        warnings.append("invalidation_score_not_scored")
    else:
        warnings.append("invalidation_metrics_use_manual_counts")

    required_evidence = _integer(
        evidence.get("required_evidence_count"),
        field="evidence_accounting.required_evidence_count",
        errors=errors,
    )
    retained_evidence = _integer(
        evidence.get("valid_inherited_evidence_count"),
        field="evidence_accounting.valid_inherited_evidence_count",
        errors=errors,
    )
    correctly_invalidated = _integer(
        evidence.get("invalidated_inherited_evidence_count"),
        field="evidence_accounting.invalidated_inherited_evidence_count",
        errors=errors,
    )
    unnecessary_invalidations = _integer(
        evidence.get("unnecessarily_invalidated_evidence_count"),
        field="evidence_accounting.unnecessarily_invalidated_evidence_count",
        errors=errors,
    )
    should_invalidate_raw = evidence.get("should_invalidate_inherited_evidence_count")
    should_invalidate = _integer(
        should_invalidate_raw,
        field="evidence_accounting.should_invalidate_inherited_evidence_count",
        errors=errors,
        default=correctly_invalidated,
    )
    assert required_evidence is not None
    assert retained_evidence is not None
    assert correctly_invalidated is not None
    assert unnecessary_invalidations is not None
    assert should_invalidate is not None

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
    baseline_hours = _number(
        baseline_hours_raw,
        field="effort_accounting.baseline_independent_build_hours",
        errors=errors,
    )
    assert baseline_hours is not None
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
                value = _number(
                    raw,
                    field=f"task_hours:{key}",
                    errors=errors,
                    default=0.0,
                )
                assert value is not None
                if value < 0:
                    errors.append(f"negative_task_hours:{key}")
                values.append(value)
            computed_derivative_hours = sum(values)
            supplied = effort.get("derivative_engineering_hours")
            if supplied is not None:
                supplied_hours = _number(
                    supplied,
                    field="effort_accounting.derivative_engineering_hours",
                    errors=errors,
                    default=0.0,
                )
                assert supplied_hours is not None
                if abs(supplied_hours - computed_derivative_hours) > 1e-9:
                    errors.append("derivative_engineering_hours_disagrees_with_task_log")
            effort["derivative_engineering_hours"] = computed_derivative_hours
    else:
        warnings.append("derivative_hours_not_from_complete_task_log")

    derivative_hours_raw = effort.get("derivative_engineering_hours")
    derivative_hours = _number(
        derivative_hours_raw,
        field="effort_accounting.derivative_engineering_hours",
        errors=errors,
    )
    assert derivative_hours is not None
    if baseline_hours < 0 or derivative_hours < 0:
        errors.append("negative_effort_hours")
    marginal_engineering_ratio = _ratio(derivative_hours, baseline_hours)
    effort["marginal_engineering_ratio"] = marginal_engineering_ratio
    out["effort_accounting"] = effort

    physical = dict(out.get("physical_retest") or {})
    blank_slate_tests = _integer(
        physical.get("blank_slate_test_count"),
        field="physical_retest.blank_slate_test_count",
        errors=errors,
    )
    safely_reused = _integer(
        physical.get("tests_reused_or_safely_waived"),
        field="physical_retest.tests_reused_or_safely_waived",
        errors=errors,
    )
    rerun = _integer(
        physical.get("tests_rerun"),
        field="physical_retest.tests_rerun",
        errors=errors,
    )
    assert blank_slate_tests is not None
    assert safely_reused is not None
    assert rerun is not None
    if min(blank_slate_tests, safely_reused, rerun) < 0:
        errors.append("negative_physical_test_count")
    if safely_reused + rerun > blank_slate_tests:
        errors.append("physical_test_counts_exceed_blank_slate")
    physical_retest_compression = _ratio(safely_reused, blank_slate_tests)
    physical["physical_retest_compression"] = physical_retest_compression
    out["physical_retest"] = physical

    authority = dict(out.get("authority") or {})
    authority_violations = _integer(
        authority.get("violations"),
        field="authority.violations",
        errors=errors,
    )
    assert authority_violations is not None
    if authority_violations < 0:
        errors.append("negative_authority_violation_count")

    gate = dict(out.get("hypothesis_gate") or {})
    reuse_target = _number(
        gate.get("engineering_reuse_ratio_target", 0.70),
        field="hypothesis_gate.engineering_reuse_ratio_target",
        errors=errors,
        default=0.70,
    )
    evidence_target = _number(
        gate.get("evidence_reuse_ratio_target", 0.65),
        field="hypothesis_gate.evidence_reuse_ratio_target",
        errors=errors,
        default=0.65,
    )
    marginal_max = _number(
        gate.get("marginal_engineering_ratio_max", 0.40),
        field="hypothesis_gate.marginal_engineering_ratio_max",
        errors=errors,
        default=0.40,
    )
    invalidation_precision_target = _number(
        gate.get("invalidation_precision_target", 0.95),
        field="hypothesis_gate.invalidation_precision_target",
        errors=errors,
        default=0.95,
    )
    invalidation_recall_target = _number(
        gate.get("invalidation_recall_target", 0.95),
        field="hypothesis_gate.invalidation_recall_target",
        errors=errors,
        default=0.95,
    )
    authority_max = _integer(
        gate.get("authority_violations_max", 0),
        field="hypothesis_gate.authority_violations_max",
        errors=errors,
        default=0,
    )
    assert reuse_target is not None
    assert evidence_target is not None
    assert marginal_max is not None
    assert invalidation_precision_target is not None
    assert invalidation_recall_target is not None
    assert authority_max is not None

    required_metrics = {
        "engineering_reuse_ratio": engineering_reuse_ratio,
        "evidence_reuse_ratio": evidence_reuse_ratio,
        "marginal_engineering_ratio": marginal_engineering_ratio,
        "invalidation_precision": invalidation_precision,
        "invalidation_recall": invalidation_recall,
    }
    missing = sorted(name for name, value in required_metrics.items() if value is None)

    checks = {
        "engineering_reuse_ratio": engineering_reuse_ratio is not None
        and engineering_reuse_ratio >= reuse_target,
        "evidence_reuse_ratio": evidence_reuse_ratio is not None
        and evidence_reuse_ratio >= evidence_target,
        "marginal_engineering_ratio": marginal_engineering_ratio is not None
        and marginal_engineering_ratio <= marginal_max,
        "invalidation_precision": invalidation_precision is not None
        and invalidation_precision >= invalidation_precision_target,
        "invalidation_recall": invalidation_recall is not None
        and invalidation_recall >= invalidation_recall_target,
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

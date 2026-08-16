"""Deterministic evaluator for platform-to-derivative evidence.

This module intentionally does not infer missing effort/evidence values. Metrics are
computed only from explicit counts. Missing or internally inconsistent accounting
keeps the experiment gate PENDING/INVALID rather than promoting a favorable result.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.platform_derivative_evidence.v1"


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def evaluate_platform_derivative_evidence(record: Mapping[str, Any]) -> dict[str, Any]:
    """Compute reuse/economics metrics and a fail-closed hypothesis gate."""

    out = deepcopy(dict(record))
    errors: list[str] = []

    if out.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported_schema_version")

    artifacts = dict(out.get("artifact_accounting") or {})
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
    required_evidence = int(evidence.get("required_evidence_count") or 0)
    retained_evidence = int(evidence.get("valid_inherited_evidence_count") or 0)
    invalidated_evidence = int(evidence.get("invalidated_inherited_evidence_count") or 0)
    unnecessary_invalidations = int(evidence.get("unnecessarily_invalidated_evidence_count") or 0)
    should_invalidate = int(evidence.get("should_invalidate_inherited_evidence_count") or invalidated_evidence)

    if min(required_evidence, retained_evidence, invalidated_evidence, unnecessary_invalidations, should_invalidate) < 0:
        errors.append("negative_evidence_count")
    if retained_evidence > required_evidence:
        errors.append("retained_evidence_exceeds_required")
    if invalidated_evidence > should_invalidate:
        errors.append("invalidated_evidence_exceeds_should_invalidate")

    evidence_reuse_ratio = _ratio(retained_evidence, required_evidence)
    invalidation_precision = _ratio(invalidated_evidence, should_invalidate)
    inherited_considered = retained_evidence + unnecessary_invalidations
    unnecessary_invalidation_rate = _ratio(unnecessary_invalidations, inherited_considered)

    evidence["evidence_reuse_ratio"] = evidence_reuse_ratio
    evidence["invalidation_precision"] = invalidation_precision
    evidence["unnecessary_invalidation_rate"] = unnecessary_invalidation_rate
    out["evidence_accounting"] = evidence

    effort = dict(out.get("effort_accounting") or {})
    baseline_hours_raw = effort.get("baseline_independent_build_hours")
    derivative_hours_raw = effort.get("derivative_engineering_hours")
    baseline_hours = float(baseline_hours_raw) if baseline_hours_raw is not None else 0.0
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
    invalidation_target = float(gate.get("invalidation_precision_target", 0.95))
    authority_max = int(gate.get("authority_violations_max", 0))

    required_metrics = {
        "engineering_reuse_ratio": engineering_reuse_ratio,
        "evidence_reuse_ratio": evidence_reuse_ratio,
        "marginal_engineering_ratio": marginal_engineering_ratio,
        "invalidation_precision": invalidation_precision,
    }
    missing = sorted(name for name, value in required_metrics.items() if value is None)

    checks = {
        "engineering_reuse_ratio": engineering_reuse_ratio is not None and engineering_reuse_ratio >= reuse_target,
        "evidence_reuse_ratio": evidence_reuse_ratio is not None and evidence_reuse_ratio >= evidence_target,
        "marginal_engineering_ratio": marginal_engineering_ratio is not None and marginal_engineering_ratio <= marginal_max,
        "invalidation_precision": invalidation_precision is not None and invalidation_precision >= invalidation_target,
        "authority_violations": authority_violations <= authority_max,
    }

    if errors:
        result = "INVALID"
    elif missing:
        result = "PENDING"
    elif all(checks.values()):
        result = "PASS"
    else:
        result = "FAIL"

    gate["computed_checks"] = checks
    gate["missing_metrics"] = missing
    gate["validation_errors"] = errors
    gate["result"] = result
    out["hypothesis_gate"] = gate
    return out

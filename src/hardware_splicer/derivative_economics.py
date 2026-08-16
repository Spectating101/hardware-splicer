"""Fail-closed economics evaluator for HS platform-to-derivative experiments."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.derivative_economics.v1"

_COST_FIELDS = (
    "human_active_hours",
    "elapsed_hours",
    "model_tool_cost",
    "external_service_cost",
    "development_consumables_cost",
    "physical_retest_hours",
)


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _number(value: Any, *, field: str, errors: list[str]) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"invalid_number:{field}")
        return None
    if number < 0:
        errors.append(f"negative_value:{field}")
    return number


def evaluate_derivative_economics(record: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate a frozen reuse-vs-cleanroom comparator without filling gaps."""

    out = deepcopy(dict(record))
    errors: list[str] = []
    if out.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported_schema_version")

    comparison = dict(out.get("comparison") or {})
    baseline_req = str(comparison.get("baseline_requirements_hash") or "")
    reuse_req = str(comparison.get("reuse_requirements_hash") or "")
    baseline_exit = str(comparison.get("baseline_exit_criteria_hash") or "")
    reuse_exit = str(comparison.get("reuse_exit_criteria_hash") or "")
    requirements_match = bool(baseline_req and reuse_req and baseline_req == reuse_req)
    exit_criteria_match = bool(baseline_exit and reuse_exit and baseline_exit == reuse_exit)
    comparison["requirements_match"] = requirements_match
    comparison["exit_criteria_match"] = exit_criteria_match
    out["comparison"] = comparison

    labor_rate = _number(out.get("labor_rate_per_hour"), field="labor_rate_per_hour", errors=errors)
    currency = str(out.get("currency") or "").strip()

    paths: dict[str, dict[str, Any]] = {}
    for path_name in ("baseline", "reuse"):
        path = dict(out.get(path_name) or {})
        for field in _COST_FIELDS:
            path[field] = _number(path.get(field), field=f"{path_name}.{field}", errors=errors)
        cash_fields = (
            path.get("model_tool_cost"),
            path.get("external_service_cost"),
            path.get("development_consumables_cost"),
        )
        if labor_rate is not None and path.get("human_active_hours") is not None and all(
            value is not None for value in cash_fields
        ):
            path["development_variable_cost"] = (
                path["human_active_hours"] * labor_rate + sum(cash_fields)
            )
        else:
            path["development_variable_cost"] = None
        paths[path_name] = path
        out[path_name] = path

    baseline = paths["baseline"]
    reuse = paths["reuse"]
    metrics = {
        "human_intervention_ratio": _ratio(
            reuse.get("human_active_hours") or 0.0,
            baseline.get("human_active_hours") or 0.0,
        ),
        "elapsed_time_ratio": _ratio(
            reuse.get("elapsed_hours") or 0.0,
            baseline.get("elapsed_hours") or 0.0,
        ),
        "development_variable_cost_ratio": _ratio(
            reuse.get("development_variable_cost") or 0.0,
            baseline.get("development_variable_cost") or 0.0,
        ),
        "physical_retest_ratio": _ratio(
            reuse.get("physical_retest_hours") or 0.0,
            baseline.get("physical_retest_hours") or 0.0,
        ),
    }
    out["metrics"] = metrics

    gate = dict(out.get("hypothesis_gate") or {})
    human_max = float(gate.get("human_intervention_ratio_max", 0.40))
    cost_max = float(gate.get("development_variable_cost_ratio_max", 0.50))
    authority_max = int(gate.get("authority_violations_max", 0))

    blockers: list[str] = []
    if not baseline_req or not reuse_req:
        blockers.append("requirements_hash_required_for_both_paths")
    elif not requirements_match:
        errors.append("requirements_hash_mismatch")
    if not baseline_exit or not reuse_exit:
        blockers.append("exit_criteria_hash_required_for_both_paths")
    elif not exit_criteria_match:
        errors.append("exit_criteria_hash_mismatch")
    if not currency:
        blockers.append("currency_required")
    if labor_rate is None:
        blockers.append("labor_rate_required")
    if comparison.get("mode") != "parallel_cleanroom":
        blockers.append("parallel_cleanroom_comparator_required")
    for flag, code in (
        ("inputs_frozen_before_execution", "inputs_not_frozen_before_execution"),
        ("reuse_result_hidden_from_baseline", "reuse_result_not_hidden_from_baseline"),
        ("baseline_private_reuse_assets_excluded", "baseline_private_reuse_assets_not_excluded"),
        ("intervention_log_complete", "intervention_log_incomplete"),
        ("same_measurement_policy", "measurement_policy_not_shared"),
    ):
        if comparison.get(flag) is not True:
            blockers.append(code)

    missing_metrics = sorted(name for name, value in metrics.items() if value is None)
    baseline_state = str(baseline.get("completion_state") or "")
    reuse_state = str(reuse.get("completion_state") or "")
    terminal_states = {"completed", "failed"}
    still_running = baseline_state not in terminal_states or reuse_state not in terminal_states

    baseline_authority = int(baseline.get("authority_violations") or 0)
    reuse_authority = int(reuse.get("authority_violations") or 0)
    if baseline_authority < 0 or reuse_authority < 0:
        errors.append("negative_authority_violation_count")

    checks = {
        "both_paths_reached_exit": baseline_state == "completed" and reuse_state == "completed",
        "human_intervention_ratio": metrics["human_intervention_ratio"] is not None
        and metrics["human_intervention_ratio"] <= human_max,
        "development_variable_cost_ratio": metrics["development_variable_cost_ratio"] is not None
        and metrics["development_variable_cost_ratio"] <= cost_max,
        "authority_violations": baseline_authority <= authority_max
        and reuse_authority <= authority_max,
    }
    threshold_failures = sorted(name for name, passed in checks.items() if not passed)

    if errors:
        result = "INVALID"
    elif still_running or missing_metrics or blockers:
        result = "PENDING"
    elif threshold_failures:
        result = "FAIL"
    else:
        result = "PASS"

    gate["computed_checks"] = checks
    gate["proof_blockers"] = blockers
    gate["missing_metrics"] = missing_metrics
    gate["threshold_failures"] = threshold_failures
    gate["validation_errors"] = errors
    gate["result"] = result
    out["hypothesis_gate"] = gate
    out["metadata"] = {
        **dict(out.get("metadata") or {}),
        "production_unit_economics_proven": False,
        "physical_authority_granted": False,
        "economic_result_scope": "development_comparator_only",
    }
    return out

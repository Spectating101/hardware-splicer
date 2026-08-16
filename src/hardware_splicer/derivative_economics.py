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


def _ratio_optional(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    return _ratio(numerator, denominator)


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


def _integer(value: Any, *, field: str, errors: list[str]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        errors.append(f"invalid_integer:{field}")
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"invalid_integer:{field}")
        return None
    if not number.is_integer():
        errors.append(f"invalid_integer:{field}")
        return None
    integer = int(number)
    if integer < 0:
        errors.append(f"negative_value:{field}")
    return integer


def _labor_rate_sensitivity(
    *,
    baseline_hours: float | None,
    reuse_hours: float | None,
    baseline_cash: float | None,
    reuse_cash: float | None,
) -> dict[str, Any]:
    """Describe whether the result depends on the chosen nonnegative labor rate."""

    if None in {baseline_hours, reuse_hours, baseline_cash, reuse_cash}:
        return {
            "status": "unavailable",
            "dominance": None,
            "break_even_labor_rate": None,
            "reuse_cheaper_when": None,
        }

    assert baseline_hours is not None
    assert reuse_hours is not None
    assert baseline_cash is not None
    assert reuse_cash is not None

    human_delta = reuse_hours - baseline_hours
    cash_delta = reuse_cash - baseline_cash

    if human_delta == 0 and cash_delta == 0:
        return {
            "status": "evaluated",
            "dominance": "equal_for_all_nonnegative_labor_rates",
            "break_even_labor_rate": None,
            "reuse_cheaper_when": "never_strictly_cheaper",
        }
    if human_delta <= 0 and cash_delta <= 0:
        return {
            "status": "evaluated",
            "dominance": "reuse_weakly_dominates_for_all_nonnegative_labor_rates",
            "break_even_labor_rate": None,
            "reuse_cheaper_when": "all_nonnegative_labor_rates_except_possible_tie_at_zero",
        }
    if human_delta >= 0 and cash_delta >= 0:
        return {
            "status": "evaluated",
            "dominance": "baseline_weakly_dominates_for_all_nonnegative_labor_rates",
            "break_even_labor_rate": None,
            "reuse_cheaper_when": "never_for_nonnegative_labor_rates",
        }

    # Opposite signs imply a real tradeoff and a nonnegative crossing point.
    break_even = -cash_delta / human_delta
    if human_delta < 0:
        reuse_cheaper_when = "labor_rate_above_break_even"
    else:
        reuse_cheaper_when = "labor_rate_below_break_even"
    return {
        "status": "evaluated",
        "dominance": "labor_rate_tradeoff",
        "break_even_labor_rate": break_even,
        "reuse_cheaper_when": reuse_cheaper_when,
    }


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
        if all(value is not None for value in cash_fields):
            path["development_cash_cost"] = sum(cash_fields)
        else:
            path["development_cash_cost"] = None
        if (
            labor_rate is not None
            and path.get("human_active_hours") is not None
            and path.get("development_cash_cost") is not None
        ):
            path["development_variable_cost"] = (
                path["human_active_hours"] * labor_rate + path["development_cash_cost"]
            )
        else:
            path["development_variable_cost"] = None
        paths[path_name] = path
        out[path_name] = path

    baseline = paths["baseline"]
    reuse = paths["reuse"]
    metrics = {
        "human_intervention_ratio": _ratio_optional(
            reuse.get("human_active_hours"), baseline.get("human_active_hours")
        ),
        "elapsed_time_ratio": _ratio_optional(
            reuse.get("elapsed_hours"), baseline.get("elapsed_hours")
        ),
        "development_cash_cost_ratio": _ratio_optional(
            reuse.get("development_cash_cost"), baseline.get("development_cash_cost")
        ),
        "development_variable_cost_ratio": _ratio_optional(
            reuse.get("development_variable_cost"), baseline.get("development_variable_cost")
        ),
        "physical_retest_ratio": _ratio_optional(
            reuse.get("physical_retest_hours"), baseline.get("physical_retest_hours")
        ),
    }
    out["metrics"] = metrics
    out["labor_rate_sensitivity"] = _labor_rate_sensitivity(
        baseline_hours=baseline.get("human_active_hours"),
        reuse_hours=reuse.get("human_active_hours"),
        baseline_cash=baseline.get("development_cash_cost"),
        reuse_cash=reuse.get("development_cash_cost"),
    )

    gate = dict(out.get("hypothesis_gate") or {})
    human_max = _number(
        gate.get("human_intervention_ratio_max", 0.40),
        field="hypothesis_gate.human_intervention_ratio_max",
        errors=errors,
    )
    cost_max = _number(
        gate.get("development_variable_cost_ratio_max", 0.50),
        field="hypothesis_gate.development_variable_cost_ratio_max",
        errors=errors,
    )
    authority_max = _integer(
        gate.get("authority_violations_max", 0),
        field="hypothesis_gate.authority_violations_max",
        errors=errors,
    )

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
    elif labor_rate <= 0:
        blockers.append("positive_labor_rate_required")
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

    required_metric_names = (
        "human_intervention_ratio",
        "elapsed_time_ratio",
        "development_variable_cost_ratio",
        "physical_retest_ratio",
    )
    missing_metrics = sorted(
        name for name in required_metric_names if metrics.get(name) is None
    )
    baseline_state = str(baseline.get("completion_state") or "")
    reuse_state = str(reuse.get("completion_state") or "")
    terminal_states = {"completed", "failed"}
    still_running = baseline_state not in terminal_states or reuse_state not in terminal_states

    authority_present = (
        "authority_violations" in baseline and "authority_violations" in reuse
    )
    if not authority_present:
        blockers.append("authority_violation_counts_required")
    baseline_authority = (
        _integer(
            baseline.get("authority_violations"),
            field="baseline.authority_violations",
            errors=errors,
        )
        if "authority_violations" in baseline
        else None
    )
    reuse_authority = (
        _integer(
            reuse.get("authority_violations"),
            field="reuse.authority_violations",
            errors=errors,
        )
        if "authority_violations" in reuse
        else None
    )

    checks = {
        "both_paths_reached_exit": baseline_state == "completed" and reuse_state == "completed",
        "human_intervention_ratio": metrics["human_intervention_ratio"] is not None
        and human_max is not None
        and metrics["human_intervention_ratio"] <= human_max,
        "development_variable_cost_ratio": metrics["development_variable_cost_ratio"] is not None
        and cost_max is not None
        and metrics["development_variable_cost_ratio"] <= cost_max,
        "authority_violations": authority_present
        and baseline_authority is not None
        and reuse_authority is not None
        and authority_max is not None
        and baseline_authority <= authority_max
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
        "labor_rate_sensitivity_reported": True,
    }
    return out

from __future__ import annotations

from hardware_splicer.derivative_economics import evaluate_derivative_economics


def _record() -> dict:
    return {
        "schema_version": "hardware_splicer.derivative_economics.v1",
        "currency": "TWD",
        "labor_rate_per_hour": 500,
        "comparison": {
            "mode": "parallel_cleanroom",
            "baseline_requirements_hash": "sha256:req",
            "reuse_requirements_hash": "sha256:req",
            "baseline_exit_criteria_hash": "sha256:exit",
            "reuse_exit_criteria_hash": "sha256:exit",
            "inputs_frozen_before_execution": True,
            "reuse_result_hidden_from_baseline": True,
            "baseline_private_reuse_assets_excluded": True,
            "intervention_log_complete": True,
            "same_measurement_policy": True,
        },
        "baseline": {
            "completion_state": "completed",
            "human_active_hours": 20,
            "elapsed_hours": 30,
            "model_tool_cost": 1000,
            "external_service_cost": 500,
            "development_consumables_cost": 1500,
            "physical_retest_hours": 8,
            "authority_violations": 0,
        },
        "reuse": {
            "completion_state": "completed",
            "human_active_hours": 6,
            "elapsed_hours": 12,
            "model_tool_cost": 700,
            "external_service_cost": 200,
            "development_consumables_cost": 900,
            "physical_retest_hours": 3,
            "authority_violations": 0,
        },
        "hypothesis_gate": {
            "human_intervention_ratio_max": 0.40,
            "development_variable_cost_ratio_max": 0.50,
            "authority_violations_max": 0,
        },
    }


def test_cleanroom_comparator_passes_when_human_and_cost_targets_clear() -> None:
    report = evaluate_derivative_economics(_record())

    assert report["baseline"]["development_cash_cost"] == 3000
    assert report["reuse"]["development_cash_cost"] == 1800
    assert report["baseline"]["development_variable_cost"] == 13000
    assert report["reuse"]["development_variable_cost"] == 4800
    assert report["metrics"]["human_intervention_ratio"] == 0.3
    assert report["metrics"]["development_cash_cost_ratio"] == 0.6
    assert report["metrics"]["development_variable_cost_ratio"] == 4800 / 13000
    assert report["labor_rate_sensitivity"]["dominance"] == (
        "reuse_weakly_dominates_for_all_nonnegative_labor_rates"
    )
    assert report["labor_rate_sensitivity"]["break_even_labor_rate"] is None
    assert report["hypothesis_gate"]["result"] == "PASS"
    assert report["metadata"]["production_unit_economics_proven"] is False
    assert report["metadata"]["physical_authority_granted"] is False


def test_missing_reuse_measurement_stays_pending_instead_of_becoming_zero() -> None:
    record = _record()
    record["reuse"]["human_active_hours"] = None

    report = evaluate_derivative_economics(record)

    assert report["metrics"]["human_intervention_ratio"] is None
    assert report["metrics"]["development_variable_cost_ratio"] is None
    assert report["labor_rate_sensitivity"]["status"] == "unavailable"
    assert report["hypothesis_gate"]["result"] == "PENDING"
    assert "human_intervention_ratio" in report["hypothesis_gate"]["missing_metrics"]


def test_nonblind_sequential_comparison_cannot_earn_strong_pass() -> None:
    record = _record()
    record["comparison"]["mode"] = "sequential_nonblind"

    report = evaluate_derivative_economics(record)

    assert report["hypothesis_gate"]["result"] == "PENDING"
    assert "parallel_cleanroom_comparator_required" in report["hypothesis_gate"]["proof_blockers"]


def test_mismatched_exit_criteria_is_invalid() -> None:
    record = _record()
    record["comparison"]["reuse_exit_criteria_hash"] = "sha256:different"

    report = evaluate_derivative_economics(record)

    assert report["hypothesis_gate"]["result"] == "INVALID"
    assert "exit_criteria_hash_mismatch" in report["hypothesis_gate"]["validation_errors"]


def test_failed_blank_slate_path_does_not_create_successful_cost_claim() -> None:
    record = _record()
    record["baseline"]["completion_state"] = "failed"

    report = evaluate_derivative_economics(record)

    assert report["hypothesis_gate"]["result"] == "FAIL"
    assert report["hypothesis_gate"]["computed_checks"]["both_paths_reached_exit"] is False


def test_weak_cost_compression_fails_even_when_human_hours_clear() -> None:
    record = _record()
    record["reuse"]["model_tool_cost"] = 7000

    report = evaluate_derivative_economics(record)

    assert report["metrics"]["human_intervention_ratio"] == 0.3
    assert report["metrics"]["development_variable_cost_ratio"] > 0.5
    assert report["hypothesis_gate"]["result"] == "FAIL"
    assert report["hypothesis_gate"]["computed_checks"]["development_variable_cost_ratio"] is False


def test_tradeoff_reports_positive_break_even_labor_rate() -> None:
    record = _record()
    # Reuse needs fewer human hours but pays much more cash up front.
    record["reuse"]["model_tool_cost"] = 8200
    # Baseline cash = 3000; reuse cash = 9300; human delta = -14 h.
    # Equal total cost at labor rate 6300 / 14 = 450.
    report = evaluate_derivative_economics(record)

    assert report["labor_rate_sensitivity"]["dominance"] == "labor_rate_tradeoff"
    assert report["labor_rate_sensitivity"]["break_even_labor_rate"] == 450
    assert report["labor_rate_sensitivity"]["reuse_cheaper_when"] == "labor_rate_above_break_even"


def test_baseline_dominance_is_visible_even_if_chosen_rate_is_high() -> None:
    record = _record()
    record["reuse"]["human_active_hours"] = 25
    record["reuse"]["model_tool_cost"] = 3000
    record["reuse"]["external_service_cost"] = 1000
    record["reuse"]["development_consumables_cost"] = 2000

    report = evaluate_derivative_economics(record)

    assert report["labor_rate_sensitivity"]["dominance"] == (
        "baseline_weakly_dominates_for_all_nonnegative_labor_rates"
    )
    assert report["labor_rate_sensitivity"]["break_even_labor_rate"] is None


def test_authority_violation_fails_economic_gate() -> None:
    record = _record()
    record["reuse"]["authority_violations"] = 1

    report = evaluate_derivative_economics(record)

    assert report["hypothesis_gate"]["result"] == "FAIL"
    assert report["hypothesis_gate"]["computed_checks"]["authority_violations"] is False


def test_missing_authority_accounting_stays_pending_instead_of_assuming_zero() -> None:
    record = _record()
    del record["reuse"]["authority_violations"]

    report = evaluate_derivative_economics(record)

    assert report["hypothesis_gate"]["result"] == "PENDING"
    assert "authority_violation_counts_required" in report["hypothesis_gate"]["proof_blockers"]
    assert report["hypothesis_gate"]["computed_checks"]["authority_violations"] is False


def test_zero_labor_rate_cannot_earn_proof_grade_economic_pass() -> None:
    record = _record()
    record["labor_rate_per_hour"] = 0

    report = evaluate_derivative_economics(record)

    assert report["hypothesis_gate"]["result"] == "PENDING"
    assert "positive_labor_rate_required" in report["hypothesis_gate"]["proof_blockers"]


def test_negative_cost_is_invalid() -> None:
    record = _record()
    record["reuse"]["model_tool_cost"] = -1

    report = evaluate_derivative_economics(record)

    assert report["hypothesis_gate"]["result"] == "INVALID"
    assert "negative_value:reuse.model_tool_cost" in report["hypothesis_gate"]["validation_errors"]

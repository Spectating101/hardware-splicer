from __future__ import annotations

from hardware_splicer.platform_derivative_metrics import (
    apply_invalidation_score,
    evaluate_platform_derivative_evidence,
)


def _record() -> dict:
    return {
        "schema_version": "hardware_splicer.platform_derivative_evidence.v1",
        "artifact_accounting": {
            "validated_artifact_count_total": 10,
            "validated_artifact_count_inherited": 8,
            "validated_artifact_count_new_or_changed": 2,
        },
        "evidence_accounting": {
            "required_evidence_count": 20,
            "valid_inherited_evidence_count": 14,
            "invalidated_inherited_evidence_count": 6,
            "should_invalidate_inherited_evidence_count": 6,
            "unnecessarily_invalidated_evidence_count": 0,
        },
        "effort_accounting": {
            "baseline_type": "measured",
            "baseline_independent_build_hours": 100,
            "derivative_engineering_hours": 30,
        },
        "physical_retest": {
            "blank_slate_test_count": 10,
            "tests_reused_or_safely_waived": 6,
            "tests_rerun": 4,
        },
        "authority": {"violations": 0},
        "hypothesis_gate": {
            "engineering_reuse_ratio_target": 0.70,
            "evidence_reuse_ratio_target": 0.65,
            "marginal_engineering_ratio_max": 0.40,
            "invalidation_precision_target": 0.95,
            "invalidation_recall_target": 0.95,
            "authority_violations_max": 0,
        },
    }


def test_platform_derivative_gate_passes_when_precommitted_targets_clear() -> None:
    report = evaluate_platform_derivative_evidence(_record())

    assert report["artifact_accounting"]["engineering_reuse_ratio"] == 0.8
    assert report["evidence_accounting"]["evidence_reuse_ratio"] == 0.7
    assert report["evidence_accounting"]["invalidation_precision"] == 1.0
    assert report["evidence_accounting"]["invalidation_recall"] == 1.0
    assert report["evidence_accounting"]["invalidation_f1"] == 1.0
    assert report["effort_accounting"]["marginal_engineering_ratio"] == 0.3
    assert report["physical_retest"]["physical_retest_compression"] == 0.6
    assert report["hypothesis_gate"]["result"] == "PASS"
    assert "artifact_reuse_uses_manual_counts" in report["hypothesis_gate"]["measurement_warnings"]


def test_platform_derivative_gate_fails_on_weak_economics_without_rewriting_thresholds() -> None:
    record = _record()
    record["artifact_accounting"]["validated_artifact_count_inherited"] = 5
    record["artifact_accounting"]["validated_artifact_count_new_or_changed"] = 5
    record["effort_accounting"]["derivative_engineering_hours"] = 70

    report = evaluate_platform_derivative_evidence(record)

    assert report["hypothesis_gate"]["result"] == "FAIL"
    assert report["hypothesis_gate"]["computed_checks"]["engineering_reuse_ratio"] is False
    assert report["hypothesis_gate"]["computed_checks"]["marginal_engineering_ratio"] is False


def test_unnecessary_invalidation_reduces_precision_and_fails_gate() -> None:
    record = _record()
    record["evidence_accounting"]["unnecessarily_invalidated_evidence_count"] = 2

    report = evaluate_platform_derivative_evidence(record)

    assert report["evidence_accounting"]["invalidation_precision"] == 0.75
    assert report["evidence_accounting"]["invalidation_recall"] == 1.0
    assert report["hypothesis_gate"]["computed_checks"]["invalidation_precision"] is False
    assert report["hypothesis_gate"]["result"] == "FAIL"


def test_missed_required_invalidation_reduces_recall_and_fails_gate() -> None:
    record = _record()
    record["evidence_accounting"]["invalidated_inherited_evidence_count"] = 5
    record["evidence_accounting"]["should_invalidate_inherited_evidence_count"] = 6

    report = evaluate_platform_derivative_evidence(record)

    assert report["evidence_accounting"]["invalidation_precision"] == 1.0
    assert report["evidence_accounting"]["invalidation_recall"] == 5 / 6
    assert report["hypothesis_gate"]["computed_checks"]["invalidation_recall"] is False
    assert report["hypothesis_gate"]["result"] == "FAIL"


def test_platform_derivative_gate_is_pending_when_required_denominators_are_missing() -> None:
    record = _record()
    record["effort_accounting"]["baseline_independent_build_hours"] = None

    report = evaluate_platform_derivative_evidence(record)

    assert report["hypothesis_gate"]["result"] == "PENDING"
    assert "marginal_engineering_ratio" in report["hypothesis_gate"]["missing_metrics"]


def test_platform_derivative_gate_is_invalid_for_inconsistent_counts() -> None:
    record = _record()
    record["artifact_accounting"]["validated_artifact_count_total"] = 9

    report = evaluate_platform_derivative_evidence(record)

    assert report["hypothesis_gate"]["result"] == "INVALID"
    assert "artifact_counts_do_not_balance" in report["hypothesis_gate"]["validation_errors"]


def test_authority_violation_forces_failure_even_when_economics_pass() -> None:
    record = _record()
    record["authority"]["violations"] = 1

    report = evaluate_platform_derivative_evidence(record)

    assert report["hypothesis_gate"]["result"] == "FAIL"
    assert report["hypothesis_gate"]["computed_checks"]["authority_violations"] is False


def test_frozen_artifact_units_override_headline_counts_and_compute_class_balance() -> None:
    record = _record()
    record["artifact_accounting"] = {
        "validated_artifact_count_total": 0,
        "validated_artifact_count_inherited": 0,
        "validated_artifact_count_new_or_changed": 0,
        "accounting_policy_id": "platform-units-v1",
        "baseline_inventory_hash": "sha256:baseline",
        "artifact_units": [
            {"unit_id": "bom-core", "class": "bom", "status": "inherited"},
            {"unit_id": "fw-core", "class": "firmware", "status": "inherited"},
            {"unit_id": "fw-task", "class": "firmware", "status": "changed"},
            {"unit_id": "mount", "class": "mechanical", "status": "inherited"},
        ],
    }
    record["hypothesis_gate"]["require_frozen_artifact_inventory"] = True

    report = evaluate_platform_derivative_evidence(record)

    assert report["artifact_accounting"]["validated_artifact_count_total"] == 4
    assert report["artifact_accounting"]["validated_artifact_count_inherited"] == 3
    assert report["artifact_accounting"]["engineering_reuse_ratio"] == 0.75
    assert report["artifact_accounting"]["class_reuse_ratios"] == {
        "bom": 1.0,
        "firmware": 0.5,
        "mechanical": 1.0,
    }
    assert report["hypothesis_gate"]["result"] == "PASS"


def test_frozen_artifact_inventory_rejects_disagreeing_manual_count() -> None:
    record = _record()
    record["artifact_accounting"]["artifact_units"] = [
        {"unit_id": "a", "class": "bom", "status": "inherited"},
        {"unit_id": "b", "class": "firmware", "status": "changed"},
    ]

    report = evaluate_platform_derivative_evidence(record)

    assert report["hypothesis_gate"]["result"] == "INVALID"
    assert "validated_artifact_count_total_disagrees_with_artifact_units" in report["hypothesis_gate"]["validation_errors"]


def test_complete_task_log_computes_derivative_hours_and_rejects_mismatch() -> None:
    record = _record()
    record["effort_accounting"].update(
        {
            "task_hours_complete": True,
            "hours_by_task_class": {
                "requirements": 3,
                "component_selection": 2,
                "firmware": 10,
                "physical_test": 15,
            },
        }
    )

    report = evaluate_platform_derivative_evidence(record)
    assert report["effort_accounting"]["derivative_engineering_hours"] == 30
    assert report["hypothesis_gate"]["result"] == "PASS"

    record["effort_accounting"]["derivative_engineering_hours"] = 29
    invalid = evaluate_platform_derivative_evidence(record)
    assert invalid["hypothesis_gate"]["result"] == "INVALID"
    assert "derivative_engineering_hours_disagrees_with_task_log" in invalid["hypothesis_gate"]["validation_errors"]


def test_strong_proof_gate_remains_pending_for_estimated_baseline_or_unscored_invalidation() -> None:
    record = _record()
    record["effort_accounting"]["baseline_type"] = "estimated"
    record["hypothesis_gate"].update(
        {
            "require_measured_baseline": True,
            "require_scored_invalidation": True,
        }
    )

    report = evaluate_platform_derivative_evidence(record)

    assert report["hypothesis_gate"]["result"] == "PENDING"
    assert "measured_independent_baseline_required" in report["hypothesis_gate"]["proof_blockers"]
    assert "outer_scored_invalidation_required" in report["hypothesis_gate"]["proof_blockers"]


def test_outer_score_populates_precision_recall_counts_without_manual_retyping() -> None:
    record = _record()
    score = {
        "status": "scored",
        "correctly_invalidated_count": 5,
        "unnecessarily_invalidated_count": 1,
        "missed_invalidation_count": 1,
    }

    updated = apply_invalidation_score(record, score)
    report = evaluate_platform_derivative_evidence(updated)

    assert report["evidence_accounting"]["invalidated_inherited_evidence_count"] == 5
    assert report["evidence_accounting"]["should_invalidate_inherited_evidence_count"] == 6
    assert report["evidence_accounting"]["invalidation_precision"] == 5 / 6
    assert report["evidence_accounting"]["invalidation_recall"] == 5 / 6
    assert report["hypothesis_gate"]["result"] == "FAIL"

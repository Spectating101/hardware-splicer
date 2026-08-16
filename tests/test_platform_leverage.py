from __future__ import annotations

import pytest

from hardware_splicer.platform_leverage import (
    PlatformLeverageError,
    calculate_platform_leverage,
    evaluate_platform_gate,
)


def _record() -> dict:
    return {
        "schema_version": "hardware_splicer.platform_leverage_experiment.v1",
        "core_id": "vision-core-a",
        "variant_id": "package-checker-b",
        "effort": {
            "variant_engineering_hours": 12,
            "independent_counterfactual_hours": 40,
            "counterfactual_basis": "historical_comparator",
        },
        "artifacts": [
            {"artifact_id": "camera", "origin": "core", "reuse_state": "unchanged", "engineering_hours": 0},
            {"artifact_id": "power", "origin": "core", "reuse_state": "revalidated", "engineering_hours": 1},
            {"artifact_id": "mount", "origin": "core", "reuse_state": "modified", "engineering_hours": 2},
            {"artifact_id": "fixture", "origin": "variant", "reuse_state": "new", "engineering_hours": 3},
        ],
        "evidence": [
            {"evidence_id": "camera-contract", "origin": "core", "reuse_state": "survived", "engineering_hours": 0},
            {"evidence_id": "power-envelope", "origin": "core", "reuse_state": "revalidated", "engineering_hours": 1},
            {"evidence_id": "mount-load", "origin": "core", "reuse_state": "invalidated", "engineering_hours": 1},
            {"evidence_id": "qc-model", "origin": "variant", "reuse_state": "new", "engineering_hours": 4},
        ],
    }


def test_calculates_disaggregated_platform_metrics() -> None:
    report = calculate_platform_leverage(_record())

    assert report["effort"]["marginal_engineering_ratio"] == pytest.approx(0.30)
    assert report["effort"]["engineering_compression_ratio"] == pytest.approx(0.70)
    assert report["artifacts"]["core_artifact_share"] == pytest.approx(0.75)
    assert report["artifacts"]["unchanged_ratio_within_core"] == pytest.approx(1 / 3)
    assert report["artifacts"]["revalidated_ratio_within_core"] == pytest.approx(1 / 3)
    assert report["artifacts"]["modified_ratio_within_core"] == pytest.approx(1 / 3)
    assert report["artifacts"]["retained_ratio_within_core"] == pytest.approx(1.0)
    assert report["evidence"]["survival_ratio_within_core"] == pytest.approx(1 / 3)
    assert report["evidence"]["revalidation_ratio_within_core"] == pytest.approx(1 / 3)
    assert report["evidence"]["invalidation_ratio_within_core"] == pytest.approx(1 / 3)
    assert report["evidence"]["reusable_ratio_within_core"] == pytest.approx(2 / 3)


def test_estimated_counterfactual_is_not_silently_promoted() -> None:
    record = _record()
    record["effort"]["counterfactual_basis"] = "estimated"
    report = calculate_platform_leverage(record)

    assert report["warnings"]
    assert "estimated" in report["warnings"][0]


def test_rejects_impossible_origin_state_combinations() -> None:
    record = _record()
    record["artifacts"][0]["reuse_state"] = "new"

    with pytest.raises(PlatformLeverageError, match="core artifact"):
        calculate_platform_leverage(record)


def test_gate_uses_preregistered_external_thresholds() -> None:
    report = calculate_platform_leverage(_record())
    gate = evaluate_platform_gate(
        report,
        {
            "max_marginal_engineering_ratio": 0.40,
            "min_core_artifact_share": 0.60,
            "min_core_artifact_retention_ratio": 0.80,
            "min_evidence_reuse_ratio": 0.60,
            "max_evidence_invalidation_ratio": 0.40,
        },
    )

    assert gate["pass"] is True


def test_gate_fails_when_metric_is_unavailable() -> None:
    record = _record()
    record["effort"].pop("independent_counterfactual_hours")
    record["effort"].pop("counterfactual_basis")
    report = calculate_platform_leverage(record)

    gate = evaluate_platform_gate(report, {"max_marginal_engineering_ratio": 0.40})
    assert gate["pass"] is False
    assert gate["checks"]["max_marginal_engineering_ratio"]["reason"] == "metric_unavailable"

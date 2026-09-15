"""Compare derived-surrogate metrics against a higher-evidence modeled result.

This module records disagreement; it never lets surrogate agreement promote authority or lets a
higher-evidence result retroactively rewrite the surrogate experiment.
"""

from __future__ import annotations

from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.spi_surrogate_calibration.v1"


def compare_surrogate_to_reference(
    surrogate_metrics: Mapping[str, Any],
    reference_metrics: Mapping[str, Any],
    *,
    metric_tolerances: Mapping[str, float],
    reference_evidence_class: str,
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    missing: list[str] = []
    out_of_tolerance: list[str] = []

    for name, tolerance in metric_tolerances.items():
        if name not in surrogate_metrics or name not in reference_metrics:
            missing.append(name)
            continue
        s = surrogate_metrics[name]
        r = reference_metrics[name]
        if isinstance(s, bool) or isinstance(r, bool) or not isinstance(s, (int, float)) or not isinstance(r, (int, float)):
            missing.append(name)
            continue
        delta = float(s) - float(r)
        within = abs(delta) <= float(tolerance)
        if not within:
            out_of_tolerance.append(name)
        comparisons[name] = {
            "surrogate": float(s),
            "reference": float(r),
            "delta": delta,
            "absolute_delta": abs(delta),
            "tolerance": float(tolerance),
            "within_tolerance": within,
        }

    status = "comparable" if not missing else "incomplete_comparison"
    if not missing and out_of_tolerance:
        status = "disagreement_detected"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reference_evidence_class": str(reference_evidence_class),
        "comparisons": comparisons,
        "missing_metrics": sorted(missing),
        "out_of_tolerance_metrics": sorted(out_of_tolerance),
        "surrogate_promoted": False,
        "evidence_class": "cross_model_comparison_only",
        "eligible_for_vendor_model_campaign_credit": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
        "note": "Agreement is calibration evidence only; disagreement is preserved as a blocker/investigation target.",
    }

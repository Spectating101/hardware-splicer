"""Metrics for Hardware-Splicer product-platform leverage experiments."""
from __future__ import annotations
from collections import Counter
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "hardware_splicer.platform_leverage_experiment.v1"
REPORT_SCHEMA_VERSION = "hardware_splicer.platform_leverage_report.v1"
ARTIFACT_STATES = {"unchanged", "revalidated", "modified", "replaced", "new"}
EVIDENCE_STATES = {"survived", "revalidated", "invalidated", "new"}
COUNTERFACTUAL_BASES = {"measured_parallel", "historical_comparator", "estimated"}

class PlatformLeverageError(ValueError):
    pass

def _number(value: Any, *, field: str, allow_zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlatformLeverageError(f"{field} must be numeric")
    result = float(value)
    if result < 0 or (not allow_zero and result == 0):
        raise PlatformLeverageError(f"{field} must be {'positive' if not allow_zero else 'non-negative'}")
    return result

def _ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else numerator / denominator

def _rows(record: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = record.get(key, [])
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise PlatformLeverageError(f"{key} must be a list")
    rows = []
    for i, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise PlatformLeverageError(f"{key}[{i}] must be an object")
        rows.append(row)
    return rows

def _validate_artifacts(rows):
    seen = set()
    for i, row in enumerate(rows):
        item_id = str(row.get("artifact_id") or "").strip()
        if not item_id:
            raise PlatformLeverageError(f"artifacts[{i}].artifact_id is required")
        if item_id in seen:
            raise PlatformLeverageError(f"duplicate artifact_id: {item_id}")
        seen.add(item_id)
        origin, state = row.get("origin"), row.get("reuse_state")
        if origin not in {"core", "variant"}:
            raise PlatformLeverageError(f"artifacts[{i}].origin must be 'core' or 'variant'")
        if state not in ARTIFACT_STATES:
            raise PlatformLeverageError(f"artifacts[{i}].reuse_state must be one of {sorted(ARTIFACT_STATES)}")
        if origin == "core" and state == "new":
            raise PlatformLeverageError(f"core artifact {item_id} cannot have reuse_state='new'")
        if origin == "variant" and state != "new":
            raise PlatformLeverageError(f"variant artifact {item_id} must have reuse_state='new'")
        _number(row.get("engineering_hours", 0), field=f"artifacts[{i}].engineering_hours")

def _validate_evidence(rows):
    seen = set()
    for i, row in enumerate(rows):
        item_id = str(row.get("evidence_id") or "").strip()
        if not item_id:
            raise PlatformLeverageError(f"evidence[{i}].evidence_id is required")
        if item_id in seen:
            raise PlatformLeverageError(f"duplicate evidence_id: {item_id}")
        seen.add(item_id)
        origin, state = row.get("origin"), row.get("reuse_state")
        if origin not in {"core", "variant"}:
            raise PlatformLeverageError(f"evidence[{i}].origin must be 'core' or 'variant'")
        if state not in EVIDENCE_STATES:
            raise PlatformLeverageError(f"evidence[{i}].reuse_state must be one of {sorted(EVIDENCE_STATES)}")
        if origin == "core" and state == "new":
            raise PlatformLeverageError(f"core evidence {item_id} cannot have reuse_state='new'")
        if origin == "variant" and state != "new":
            raise PlatformLeverageError(f"variant evidence {item_id} must have reuse_state='new'")
        _number(row.get("engineering_hours", 0), field=f"evidence[{i}].engineering_hours")

def validate_platform_leverage_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("schema_version") != SCHEMA_VERSION:
        raise PlatformLeverageError(f"schema_version must be {SCHEMA_VERSION!r}")
    core_id = str(record.get("core_id") or "").strip()
    variant_id = str(record.get("variant_id") or "").strip()
    if not core_id or not variant_id:
        raise PlatformLeverageError("core_id and variant_id are required")
    if core_id == variant_id:
        raise PlatformLeverageError("core_id and variant_id must differ")
    effort = record.get("effort")
    if not isinstance(effort, Mapping):
        raise PlatformLeverageError("effort must be an object")
    variant_hours = _number(effort.get("variant_engineering_hours"), field="effort.variant_engineering_hours")
    independent_raw = effort.get("independent_counterfactual_hours")
    basis = effort.get("counterfactual_basis")
    independent = None
    if independent_raw is not None:
        independent = _number(independent_raw, field="effort.independent_counterfactual_hours", allow_zero=False)
        if basis not in COUNTERFACTUAL_BASES:
            raise PlatformLeverageError(f"effort.counterfactual_basis must be one of {sorted(COUNTERFACTUAL_BASES)}")
    elif basis is not None:
        raise PlatformLeverageError("effort.counterfactual_basis requires independent_counterfactual_hours")
    artifacts, evidence = _rows(record, "artifacts"), _rows(record, "evidence")
    _validate_artifacts(artifacts); _validate_evidence(evidence)
    return {"core_id": core_id, "variant_id": variant_id, "variant_engineering_hours": variant_hours,
            "independent_counterfactual_hours": independent, "counterfactual_basis": basis}

def calculate_platform_leverage(record: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_platform_leverage_record(record)
    artifacts, evidence = _rows(record, "artifacts"), _rows(record, "evidence")
    core_artifacts = [r for r in artifacts if r.get("origin") == "core"]
    core_evidence = [r for r in evidence if r.get("origin") == "core"]
    artifact_states = Counter(str(r["reuse_state"]) for r in core_artifacts)
    evidence_states = Counter(str(r["reuse_state"]) for r in core_evidence)
    artifact_hours, evidence_hours = Counter(), Counter()
    for r in artifacts:
        artifact_hours[str(r["reuse_state"])] += _number(r.get("engineering_hours", 0), field="artifact engineering_hours")
    for r in evidence:
        evidence_hours[str(r["reuse_state"])] += _number(r.get("engineering_hours", 0), field="evidence engineering_hours")
    independent = validated["independent_counterfactual_hours"]
    marginal = None if independent is None else validated["variant_engineering_hours"] / independent
    compression = None if marginal is None else 1.0 - marginal
    warnings = []
    if validated["counterfactual_basis"] == "estimated":
        warnings.append("Engineering compression uses an estimated independent-build counterfactual; treat it as exploratory.")
    if not core_artifacts:
        warnings.append("No core-origin artifacts were recorded; artifact reuse is unmeasurable.")
    if not core_evidence:
        warnings.append("No core-origin evidence was recorded; evidence survival is unmeasurable.")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "core_id": validated["core_id"],
        "variant_id": validated["variant_id"],
        "effort": {
            "variant_engineering_hours": validated["variant_engineering_hours"],
            "independent_counterfactual_hours": independent,
            "counterfactual_basis": validated["counterfactual_basis"],
            "marginal_engineering_ratio": marginal,
            "engineering_compression_ratio": compression,
        },
        "artifacts": {
            "total": len(artifacts),
            "core_origin": len(core_artifacts),
            "variant_origin": len(artifacts) - len(core_artifacts),
            "core_artifact_share": _ratio(len(core_artifacts), len(artifacts)),
            "unchanged_ratio_within_core": _ratio(artifact_states["unchanged"], len(core_artifacts)),
            "revalidated_ratio_within_core": _ratio(artifact_states["revalidated"], len(core_artifacts)),
            "modified_ratio_within_core": _ratio(artifact_states["modified"], len(core_artifacts)),
            "replaced_ratio_within_core": _ratio(artifact_states["replaced"], len(core_artifacts)),
            "retained_ratio_within_core": _ratio(
                artifact_states["unchanged"] + artifact_states["revalidated"] + artifact_states["modified"],
                len(core_artifacts),
            ),
            "state_counts_within_core": dict(sorted(artifact_states.items())),
            "tagged_engineering_hours_by_state": dict(sorted(artifact_hours.items())),
        },
        "evidence": {
            "total": len(evidence),
            "core_origin": len(core_evidence),
            "variant_origin": len(evidence) - len(core_evidence),
            "core_evidence_share": _ratio(len(core_evidence), len(evidence)),
            "survival_ratio_within_core": _ratio(evidence_states["survived"], len(core_evidence)),
            "revalidation_ratio_within_core": _ratio(evidence_states["revalidated"], len(core_evidence)),
            "invalidation_ratio_within_core": _ratio(evidence_states["invalidated"], len(core_evidence)),
            "reusable_ratio_within_core": _ratio(
                evidence_states["survived"] + evidence_states["revalidated"],
                len(core_evidence),
            ),
            "state_counts_within_core": dict(sorted(evidence_states.items())),
            "tagged_engineering_hours_by_state": dict(sorted(evidence_hours.items())),
        },
        "warnings": warnings,
    }

def evaluate_platform_gate(report: Mapping[str, Any], thresholds: Mapping[str, float]) -> dict[str, Any]:
    # Thresholds are supplied by the protocol, never silently defaulted here.
    supported = {"max_marginal_engineering_ratio", "min_engineering_compression_ratio",
                 "min_core_artifact_share", "min_core_artifact_retention_ratio",
                 "min_evidence_survival_ratio", "min_evidence_reuse_ratio",
                 "max_evidence_invalidation_ratio"}
    unknown = set(thresholds) - supported
    if unknown:
        raise PlatformLeverageError(f"unsupported thresholds: {sorted(unknown)}")
    if not thresholds:
        raise PlatformLeverageError("at least one threshold is required")
    effort, artifacts, evidence = report.get("effort") or {}, report.get("artifacts") or {}, report.get("evidence") or {}
    observed = {
        "max_marginal_engineering_ratio": effort.get("marginal_engineering_ratio"),
        "min_engineering_compression_ratio": effort.get("engineering_compression_ratio"),
        "min_core_artifact_share": artifacts.get("core_artifact_share"),
        "min_core_artifact_retention_ratio": artifacts.get("retained_ratio_within_core"),
        "min_evidence_survival_ratio": evidence.get("survival_ratio_within_core"),
        "min_evidence_reuse_ratio": evidence.get("reusable_ratio_within_core"),
        "max_evidence_invalidation_ratio": evidence.get("invalidation_ratio_within_core"),
    }
    checks = {}
    for key, raw in thresholds.items():
        threshold = _number(raw, field=f"thresholds.{key}")
        value = observed[key]
        if value is None:
            passed, reason = False, "metric_unavailable"
        elif key.startswith("max_"):
            passed = float(value) <= threshold
            reason = "pass" if passed else "above_maximum"
        else:
            passed = float(value) >= threshold
            reason = "pass" if passed else "below_minimum"
        checks[key] = {"observed": value, "threshold": threshold, "pass": passed, "reason": reason}
    return {"pass": all(row["pass"] for row in checks.values()), "checks": checks}

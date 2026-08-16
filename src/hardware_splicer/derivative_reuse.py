"""End-to-end deterministic derivative reuse prediction and adjudication.

This module composes capability-manifest diffing with selective evidence impact.
The prediction is content-hashed before any outer adjudication so experiments can
show that the reuse decision was frozen before the answer was supplied.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Iterable, Mapping

from .capability_manifest import diff_capability_manifests
from .evidence_impact import evaluate_evidence_impact, score_evidence_invalidation

DERIVATIVE_REUSE_PREDICTION_SCHEMA = "hardware_splicer.derivative_reuse_prediction.v1"
DERIVATIVE_REUSE_ADJUDICATION_SCHEMA = "hardware_splicer.derivative_reuse_adjudication.v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def predict_derivative_reuse(
    baseline_manifest: Mapping[str, Any],
    candidate_manifest: Mapping[str, Any],
    inherited_evidence_items: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Freeze a manifest-derived reuse prediction before outer adjudication."""

    diff = diff_capability_manifests(baseline_manifest, candidate_manifest)
    if diff.get("status") != "evaluated":
        payload = {
            "schema_version": DERIVATIVE_REUSE_PREDICTION_SCHEMA,
            "status": "invalid",
            "validation_errors": list(diff.get("validation_errors") or []),
            "capability_diff": diff,
            "impact_report": None,
            "prediction_hash": None,
        }
        return payload

    impact_case = {
        "schema_version": "hardware_splicer.evidence_impact_case.v1",
        "changed_dependency_ids": list(diff.get("changed_dependency_ids") or []),
        "unresolved_dependency_ids": list(diff.get("unresolved_dependency_ids") or []),
        "evidence_items": [deepcopy(dict(row)) for row in inherited_evidence_items],
    }
    impact = evaluate_evidence_impact(impact_case)
    status = "predicted" if impact.get("status") == "evaluated" else "invalid"
    core = {
        "capability_diff": diff,
        "impact_report": impact,
    }
    return {
        "schema_version": DERIVATIVE_REUSE_PREDICTION_SCHEMA,
        "status": status,
        "validation_errors": list(impact.get("validation_errors") or []),
        **core,
        "prediction_hash": _hash(core) if status == "predicted" else None,
        "metadata": {
            "prediction_frozen_before_adjudication": True,
            "semantic_equivalence_inferred": False,
            "physical_authority_granted": False,
        },
    }


def adjudicate_derivative_reuse(
    prediction: Mapping[str, Any],
    *,
    expected_invalidated_evidence_ids: Iterable[str],
    adjudicated_evidence_ids: Iterable[str] | None = None,
    adjudicator: str,
    adjudication_basis: str,
) -> dict[str, Any]:
    """Score a frozen prediction against an explicitly identified outer judgment."""

    expected_hash = prediction.get("prediction_hash")
    core = {
        "capability_diff": prediction.get("capability_diff"),
        "impact_report": prediction.get("impact_report"),
    }
    actual_hash = _hash(core) if prediction.get("status") == "predicted" else None
    validation_errors: list[str] = []
    if prediction.get("schema_version") != DERIVATIVE_REUSE_PREDICTION_SCHEMA:
        validation_errors.append("unsupported_prediction_schema")
    if prediction.get("status") != "predicted":
        validation_errors.append("prediction_not_frozen")
    if not expected_hash or actual_hash != expected_hash:
        validation_errors.append("prediction_hash_mismatch")
    if not str(adjudicator).strip():
        validation_errors.append("missing_adjudicator")
    if not str(adjudication_basis).strip():
        validation_errors.append("missing_adjudication_basis")

    if validation_errors:
        return {
            "schema_version": DERIVATIVE_REUSE_ADJUDICATION_SCHEMA,
            "status": "invalid",
            "prediction_hash": expected_hash,
            "validation_errors": validation_errors,
            "score": None,
        }

    score = score_evidence_invalidation(
        prediction["impact_report"],
        expected_invalidated_evidence_ids=expected_invalidated_evidence_ids,
        adjudicated_evidence_ids=adjudicated_evidence_ids,
    )
    return {
        "schema_version": DERIVATIVE_REUSE_ADJUDICATION_SCHEMA,
        "status": "adjudicated" if score.get("status") == "scored" else "invalid",
        "prediction_hash": expected_hash,
        "validation_errors": list(score.get("validation_errors") or []),
        "adjudicator": str(adjudicator),
        "adjudication_basis": str(adjudication_basis),
        "score": score,
        "metadata": {
            "prediction_hash_revalidated": True,
            "adjudication_grants_physical_authority": False,
        },
    }

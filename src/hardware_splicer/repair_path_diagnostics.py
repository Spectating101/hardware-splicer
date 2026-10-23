"""Bounded physical repair hypotheses from shared-path substitution evidence.

The algorithm knows NOTHING about MacBooks, SATA, iFixit, or the answer key.
A path is a caller-declared series of functional components; tests indicate
whether that complete path worked. Component rankings are triage priorities,
not probabilities or verified causal conclusions. A model is not used.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


def _rows(items: Any) -> list[dict]:
    return [dict(x) for x in items] if isinstance(items, list) and all(isinstance(x, Mapping) for x in items) else []


def rank_repair_hypotheses(intake: Mapping[str, Any]) -> dict[str, Any]:
    """Diagnostic triage with no use of outcome/gold/hidden answer labels."""
    if any(k in intake for k in ("ground_truth", "resolution", "confirmed_root_cause", "answer_key")):
        raise ValueError("Outcome fields must be sealed from the diagnostic input")
    topology = _rows(intake.get("components"))
    observations = _rows(intake.get("path_tests"))
    interventions = _rows(intake.get("interventions"))
    parts = {str(x.get("id")): x for x in topology if x.get("id")}
    if len(parts) != len(topology) or not parts:
        raise ValueError("Every candidate component needs a unique nonblank ID")
    if not observations:
        raise ValueError("A physical diagnosis requires structured observations")
    if not all(x.get("outcome") in ("pass", "fail") for x in observations):
        raise ValueError("Path tests require explicit observed pass/fail outcomes")
    if not all(isinstance(x.get("path"), list) and x["path"] for x in observations):
        raise ValueError("Each path test requires nonempty explicit component route")
    if any(str(c) not in parts for x in observations for c in x["path"]):
        raise ValueError("Path references nonexistent component identities")
    if any(x.get("component_id") not in parts or x.get("outcome") not in ("no_change", "restored")
           for x in interventions):
        raise ValueError("Interventions require recognized component and observed outcome")
    # A restored result is a post-repair outcome (label leakage), so forbid it in blind mode.
    if any(x["outcome"] == "restored" for x in interventions):
        raise ValueError("Do not provide known successful repair interventions in blind input")
    # Single symptoms (e.g. generic joystick drift) usually cannot isolate a
    # repair component; require two actual independent path observations.
    if len(observations) < 2 or not any(obs["outcome"] == "fail" for obs in observations):
        return {
            "schema_version": "hardware_splicer.repair_path_diagnostics.v0",
            "case_id": str(intake.get("case_id") or ""),
            "authority": "symptom_and_test_evidence_only",
            "verdict": "insufficient_discriminating_evidence",
            "known_successful_repair": False,
            "physical_repair_verified": False,
            "model_inference_used": False,
            "candidate_count": 0,
            "candidates": [],
            "next_test_strategy": "Obtain at least two comparable path observations with known test outcomes; do not infer a root cause from a generic symptom.",
            "limitations": ["Insufficient substitution/path evidence to prioritize a particular part."],
        }
    # Repeating the same route after a part swap is useful intervention
    # evidence, but cannot count as a new independent failure topology.
    # Otherwise a user could game the score by duplicating observations.
    distinct_observations = {}
    for observation in observations:
        signature = (observation["outcome"], tuple(sorted(set(observation["path"]))))
        distinct_observations[signature] = observation
    unique_paths = list(distinct_observations.values())
    failed = Counter(c for obs in unique_paths if obs["outcome"] == "fail" for c in set(obs["path"]))
    passed = Counter(c for obs in unique_paths if obs["outcome"] == "pass" for c in set(obs["path"]))
    tested = Counter(x["component_id"] for x in interventions if x["outcome"] == "no_change")
    rows: list[dict[str, Any]] = []
    for cid, spec in parts.items():
        # Repeated independently observed failing routes support a shared-path
        # hypothesis. Working on another route weakens but does not eliminate
        # intermittent, speed-sensitive or context-dependent faults.
        # An attempted replacement with unchanged symptoms weakens the
        # component hypothesis but does not rule out a faulty replacement.
        fail_count, pass_count, nochange_count = failed[cid], passed[cid], tested[cid]
        if fail_count == 0:
            continue
        score = 2.0*fail_count - 1.0*pass_count - 4.0*nochange_count
        reversible = bool(spec.get("reversible_test_available", False))
        cost_rank = spec.get("service_cost_rank")
        if not isinstance(cost_rank, int) or isinstance(cost_rank, bool) or not 1 <= cost_rank <= 5:
            raise ValueError("service_cost_rank must be an ordinal integer 1–5")
        rows.append({
            "component_id": cid,
            "label": str(spec.get("label") or cid),
            "triage_evidence_score_not_probability": round(score, 2),
            "failed_paths_containing": fail_count,
            "passing_paths_containing": pass_count,
            "ineffective_replacements_reported": nochange_count,
            "service_cost_rank": cost_rank,
            "reversible_test_available": reversible,
            "status": "unverified_hypothesis",
            "next_action": (
                f"Check {str(spec.get('label') or cid)} in a non-destructive or reversible way; "
                "inspect connectors/identity, compare against a known-good substitution "
                "and retest the originally failing configuration before purchasing parts."
            ),
        })
    # Scores are *not* probabilities. Prefer non-invasive/reversible tests
    # and inexpensive substitutions when observations are otherwise tied.
    rows.sort(key=lambda r: (
        -r["triage_evidence_score_not_probability"],
        -int(r["reversible_test_available"]),
        r["service_cost_rank"],
        r["component_id"],
    ))
    top_score = rows[0]["triage_evidence_score_not_probability"] if rows else None
    ties = sum(r["triage_evidence_score_not_probability"] == top_score for r in rows)
    return {
        "schema_version": "hardware_splicer.repair_path_diagnostics.v0",
        "case_id": str(intake.get("case_id") or ""),
        "authority": "symptom_and_test_evidence_only",
        "verdict": "triage_hypothesis_only",
        "source_test_count": len(observations),
        "independent_path_signature_count": len(unique_paths),
        "highest_evidence_score_tie_count": ties,
        "top_selection_basis": (
            "serviceability_tiebreak_not_unique_causal_identification"
            if ties > 1 else "distinct_evidence_score_not_confirmed_causation"
        ),
        "known_successful_repair": False,
        "physical_repair_verified": False,
        "model_inference_used": False,
        "candidate_count": len(rows),
        "candidates": rows,
        "next_test_strategy": (
            "Prefer a reversible discrimination test on the highest-ranked shared failure path. "
            "A single symptom cannot prove one component; do not erase storage, replace a "
            "high-cost assembly or declare a repair completed without confirming the fault."
        ),
        "limitations": [
            "User-supplied path membership is a functional hypothesis, not a measured wiring map.",
            "Ordinal evidence scores are not calibrated failure probabilities.",
            "Interventions and outcomes are reports, not independently verified measurements.",
            "No actual physical test or tool intervention is performed.",
        ],
    }

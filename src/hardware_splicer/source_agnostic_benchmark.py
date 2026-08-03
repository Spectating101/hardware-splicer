"""Benchmark source-agnostic engineering reasoning for Hardware Splicer.

The benchmark goes beyond reproducing known open-source robots. It measures whether
Hardware Splicer can reconcile conflicting evidence, synthesize a requirement-driven
candidate without a canonical reference, repair/splice donor hardware, and revise a
machine after field failure. No public source receives more authority than its evidence
class permits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping

SCHEMA_VERSION = "hardware_splicer.source_agnostic_benchmark.v1"
SUITE_SCHEMA_VERSION = "hardware_splicer.source_agnostic_suite.v1"

_DIMENSION_WEIGHTS: dict[str, float] = {
    "requirements": 10.0,
    "source_retention": 10.0,
    "source_provenance": 10.0,
    "conflict_resolution": 10.0,
    "candidate_synthesis": 12.0,
    "donor_reuse": 10.0,
    "revision_impact": 10.0,
    "identity_continuity": 10.0,
    "uncertainty_visibility": 8.0,
    "verification_authority": 10.0,
}

_VALID_MODES = {"reconstruct", "synthesize", "repair", "evolve"}


def load_source_agnostic_scenario(path: str | Path) -> Dict[str, Any]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"source-agnostic scenario must be an object: {source}")
    required = {"scenario_id", "mode", "expected_archetype", "intake", "challenge"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"source-agnostic scenario {source} missing: {', '.join(missing)}")
    mode = str(payload.get("mode") or "").strip().lower()
    if mode not in _VALID_MODES:
        raise ValueError(f"unsupported source-agnostic mode: {mode}")
    payload.setdefault("source_file", str(source.resolve()))
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _contains_key(payload: Any, wanted: set[str]) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).strip().lower()
            if normalized in wanted or any(token in normalized for token in wanted):
                if value not in (None, {}, [], ""):
                    return True
            if _contains_key(value, wanted):
                return True
    elif isinstance(payload, (list, tuple)):
        return any(_contains_key(value, wanted) for value in payload)
    return False


def _collect_strings(payload: Any) -> set[str]:
    values: set[str] = set()
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            values.add(str(key).strip().lower())
            values.update(_collect_strings(value))
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            values.update(_collect_strings(value))
    elif isinstance(payload, (str, int, float, bool)):
        values.add(str(payload).strip().lower())
    return values


def _source_retention(plan: Mapping[str, Any], sources: list[Any]) -> tuple[bool, float]:
    if not sources:
        return True, 1.0
    haystack = _collect_strings(plan)
    retained = 0
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        source_id = str(source.get("source_id") or source.get("id") or "").strip().lower()
        uri = str(source.get("uri") or source.get("url") or "").strip().lower()
        version = str(source.get("version") or source.get("revision") or "").strip().lower()
        tokens = [token for token in (source_id, uri, version) if token]
        if tokens and any(token in haystack for token in tokens):
            retained += 1
    ratio = retained / len(sources)
    return ratio == 1.0, ratio


def _source_provenance(plan: Mapping[str, Any], sources: list[Any]) -> bool:
    if not sources:
        return True
    return _contains_key(
        plan,
        {
            "source_id",
            "source_type",
            "uri",
            "revision",
            "commit_sha",
            "checksum",
            "content_hash",
            "retrieved_at",
            "authority_ceiling",
        },
    )


def _candidate_synthesis(plan: Mapping[str, Any], expected_archetype: str) -> bool:
    scenario = _mapping(plan.get("scenario"))
    spec = _mapping(scenario.get("compile_spec"))
    detected = str(plan.get("archetype") or "")
    return detected == expected_archetype and bool(
        plan.get("recommended_build_id")
        or _mapping(spec.get("robotics_project"))
        or _mapping(spec.get("machine"))
    )


def _donor_reuse(plan: Mapping[str, Any]) -> bool:
    salvage = _mapping(plan.get("salvage_package"))
    return bool(
        salvage.get("recommended_build_id")
        and (
            _sequence(salvage.get("resolved_modules"))
            or _sequence(_mapping(salvage.get("splice_plan")).get("reusable_blocks"))
            or _mapping(salvage.get("graph_input"))
        )
    )


def evaluate_source_agnostic_scenario(
    scenario: Mapping[str, Any],
    *,
    planner: Callable[..., Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Evaluate one reconstruction, synthesis, repair, or field-evolution case."""

    if planner is None:
        from .project_intake import plan_project_from_intake

        planner = plan_project_from_intake

    intake = _mapping(scenario.get("intake"))
    challenge = _mapping(scenario.get("challenge"))
    sources = _sequence(scenario.get("engineering_sources"))
    mode = str(scenario.get("mode") or "").strip().lower()
    expected_archetype = str(scenario.get("expected_archetype") or "")
    plan = dict(planner(intake, skip_vision=True))

    dimensions: dict[str, dict[str, Any]] = {}
    gaps: list[str] = []

    def record(name: str, satisfied: bool, gap: str, evidence: str = "") -> None:
        if not satisfied:
            gaps.append(gap)
        dimensions[name] = {
            "satisfied": satisfied,
            "evidence": [evidence] if satisfied and evidence else [],
        }

    record(
        "requirements",
        bool(plan.get("goal")) and bool(intake.get("constraints")),
        "requirements_not_structured",
        "goal and constraints",
    )

    retained, retention_ratio = _source_retention(plan, sources)
    record(
        "source_retention",
        retained,
        "engineering_sources_not_retained",
        f"retained {retention_ratio:.0%} of source identities",
    )
    record(
        "source_provenance",
        _source_provenance(plan, sources),
        "source_provenance_not_pinned",
        "source identities, revisions, hashes, and authority ceilings",
    )

    expected_conflicts = int(challenge.get("expected_conflict_count") or 0)
    conflicts_visible = expected_conflicts == 0 or _contains_key(
        plan,
        {"conflict", "contradiction", "incompatible_claim", "disputed", "source_disagreement"},
    )
    record(
        "conflict_resolution",
        conflicts_visible,
        "source_conflicts_not_resolved",
        "explicit contradiction records",
    )

    record(
        "candidate_synthesis",
        _candidate_synthesis(plan, expected_archetype),
        "candidate_machine_not_synthesized",
        "archetype plus candidate machine/build",
    )

    donor_required = mode == "repair" or bool(challenge.get("donor_reuse_required"))
    donor_ok = not donor_required or _donor_reuse(plan)
    record(
        "donor_reuse",
        donor_ok,
        "donor_mapping_not_resolved",
        "resolved donor modules and splice graph" if donor_required else "not required",
    )

    revision_required = mode == "evolve" or bool(challenge.get("baseline_revision_required"))
    revision_ok = not revision_required or _contains_key(
        plan,
        {
            "baseline_revision",
            "candidate_revision",
            "change_request",
            "affected_subsystems",
            "compatibility_impact",
            "modification_delta",
            "field_failure",
            "failure_hypothesis",
        },
    )
    record(
        "revision_impact",
        revision_ok,
        "baseline_to_candidate_impact_missing",
        "baseline-to-candidate change impact" if revision_required else "not required",
    )

    identity_required = bool(challenge.get("identity_continuity_required", True))
    identity_ok = not identity_required or _contains_key(
        plan,
        {
            "component_id",
            "joint_id",
            "interface_id",
            "net_id",
            "source_component_id",
            "canonical_target_id",
            "artifact_id",
        },
    )
    record(
        "identity_continuity",
        identity_ok,
        "cross_source_identity_not_canonical",
        "canonical identities across evidence and design objects",
    )

    uncertainty_ok = bool(plan.get("missing_info") is not None) and (
        bool(_sequence(plan.get("missing_info")))
        or _contains_key(plan, {"unresolved", "unknown", "assumption", "confidence"})
    )
    record(
        "uncertainty_visibility",
        uncertainty_ok,
        "uncertainty_not_visible",
        "missing information, assumptions, or unresolved references",
    )

    scenario_plan = _mapping(plan.get("scenario"))
    verification_ok = _contains_key(
        scenario_plan,
        {"acceptance", "safety", "evidence", "verification", "blocker"},
    ) and _contains_key(
        plan,
        {"authority", "planning_authority", "evidence_status", "release_status", "missing_info"},
    )
    record(
        "verification_authority",
        verification_ok,
        "verification_and_authority_plan_missing",
        "acceptance, evidence, safety, and authority boundaries",
    )

    score = round(
        sum(
            _DIMENSION_WEIGHTS[name]
            for name, result in dimensions.items()
            if bool(result.get("satisfied"))
        ),
        1,
    )
    if score >= 85 and not gaps:
        verdict = "bounded_engineering_candidate"
    elif score >= 60:
        verdict = "structured_project_assistant"
    elif score >= 35:
        verdict = "reference_and_gap_triage"
    else:
        verdict = "unsupported"

    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": scenario.get("scenario_id"),
        "mode": mode,
        "expected_archetype": expected_archetype,
        "detected_archetype": plan.get("archetype"),
        "planning_confidence": plan.get("planning_confidence"),
        "engineering_source_count": len(sources),
        "source_retention_ratio": round(retention_ratio, 3),
        "score": score,
        "verdict": verdict,
        "dimensions": dimensions,
        "gaps": sorted(set(gaps)),
        "missing_info": list(plan.get("missing_info") or []),
    }


def evaluate_source_agnostic_suite(
    scenarios: Iterable[Mapping[str, Any]],
    *,
    planner: Callable[..., Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    rows = [evaluate_source_agnostic_scenario(row, planner=planner) for row in scenarios]
    rows.sort(key=lambda row: str(row.get("scenario_id") or ""))
    return {
        "schema_version": SUITE_SCHEMA_VERSION,
        "scenario_count": len(rows),
        "bounded_engineering_candidate_count": sum(
            row["verdict"] == "bounded_engineering_candidate" for row in rows
        ),
        "structured_project_assistant_count": sum(
            row["verdict"] == "structured_project_assistant" for row in rows
        ),
        "reference_and_gap_triage_count": sum(
            row["verdict"] == "reference_and_gap_triage" for row in rows
        ),
        "unsupported_count": sum(row["verdict"] == "unsupported" for row in rows),
        "rows": rows,
    }

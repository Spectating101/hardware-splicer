"""Adversarial replay harness for the dual-agent cleanroom.

This is an outer-engineer evaluation tool, not a product authority surface. It runs
independently prepared project revisions through the same source-blind embedded operator
boundary and records structural stability/contract signals without embedding a golden
architecture or expected engineering answer.

The harness deliberately distinguishes:

- hard contract failures: isolation, evidence identity, or physical-authority breaches;
- structural drift: action/evidence/question/candidate changes between declared-equivalent
  project variants;
- evaluator defects: equivalence groups whose evidence identity actually changed;
- review signals: possible label sensitivity, prompt coupling, context construction, or
  model instability that an outer engineer should inspect rather than automatically call
  "wrong".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Sequence

from .dual_agent_cleanroom import CleanroomContractError, run_embedded_operator_turn


SCHEMA_VERSION = "hardware_splicer.cleanroom_replay.v2"

_AUTHORITY_KEYS = (
    "fabrication_authorized",
    "firmware_flash_authorized",
    "power_on_authorized",
    "motion_authorized",
    "operational_authorized",
    "release_authorized",
)

_SOURCE_COLLECTION_KEYS = (
    "engineeringSources",
    "engineeringParsedSources",
    "engineeringSourceParserRuns",
)

_BLOCKER_KEYS = (
    "engineeringBlockers",
    "engineering_blockers",
    "blockers",
)

_CONFLICT_KEYS = (
    "declared_conflicts",
    "engineeringSourceConflicts",
    "engineering_source_conflicts",
    "source_conflicts",
)


@dataclass(frozen=True)
class ReplayCase:
    case_id: str
    project_id: str
    project_revision: int
    snapshot: Mapping[str, Any]
    equivalence_group: str | None = None
    perturbation_kind: str = "baseline"
    metadata: Mapping[str, Any] | None = None


def _persisted_mission(snapshot: Mapping[str, Any]) -> str:
    for key in ("mission", "goal", "intent", "brief"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Mapping):
            for nested_key in ("mission", "goal", "intent", "brief", "description"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    raise ValueError("replay case has no persisted mission/goal/intent/brief")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _rows(value: Any) -> list[Mapping[str, Any]]:
    return [row for row in list(value or []) if isinstance(row, Mapping)]


def _source_ids(session: Mapping[str, Any]) -> list[str]:
    result: set[str] = set()
    for key in ("requirements", "architecture_candidates", "actions"):
        for row in _rows(session.get(key)):
            for source_id in list(row.get("source_ids") or []):
                token = str(source_id or "").strip()
                if token:
                    result.add(token)
    return sorted(result)


def _snapshot_source_inventory(snapshot: Mapping[str, Any]) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for collection_key in _SOURCE_COLLECTION_KEYS:
        collection = snapshot.get(collection_key)
        if not isinstance(collection, list):
            continue
        for row in collection:
            if not isinstance(row, Mapping):
                continue
            source_id = str(row.get("source_id") or "").strip()
            if not source_id:
                continue
            rows.append(
                {
                    "collection": collection_key,
                    "source_id": source_id,
                    "content_hash": str(row.get("content_hash") or row.get("sha256") or ""),
                    "revision": str(row.get("revision") or ""),
                    "source_type": str(row.get("source_type") or ""),
                    "authority_ceiling": str(row.get("authority_ceiling") or ""),
                    "parser_identity": str(row.get("parser_identity") or row.get("parser_route") or ""),
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["collection"],
            row["source_id"],
            row["content_hash"],
            row["revision"],
            row["parser_identity"],
        ),
    )


def _count_declared_items(snapshot: Mapping[str, Any], keys: Sequence[str]) -> int:
    count = 0
    for key in keys:
        value = snapshot.get(key)
        if isinstance(value, Mapping):
            count += len(value)
        elif isinstance(value, (list, tuple)):
            count += len(value)
        elif value:
            count += 1
    return count


def _snapshot_signals(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    inventory = _snapshot_source_inventory(snapshot)
    blocker_count = _count_declared_items(snapshot, _BLOCKER_KEYS)
    conflict_count = _count_declared_items(snapshot, _CONFLICT_KEYS)
    return {
        "source_count": len({row["source_id"] for row in inventory}),
        "evidence_inventory_fingerprint": _fingerprint(inventory),
        "blocker_count": blocker_count,
        "conflict_count": conflict_count,
        "persisted_uncertainty_present": bool(blocker_count or conflict_count),
    }


def _operator_observation(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    session = envelope.get("operator_session") or {}
    if not isinstance(session, Mapping):
        session = {}
    requirements = [
        {
            "id": str(row.get("id") or row.get("requirement_id") or ""),
            "statement": str(row.get("statement") or ""),
            "source_ids": sorted(str(value) for value in list(row.get("source_ids") or []) if str(value)),
            "assumption_count": len(list(row.get("assumptions") or [])),
        }
        for row in _rows(session.get("requirements"))
    ]
    candidates = [
        {
            "id": str(row.get("id") or ""),
            "title": str(row.get("title") or ""),
            "source_ids": sorted(str(value) for value in list(row.get("source_ids") or []) if str(value)),
        }
        for row in _rows(session.get("architecture_candidates"))
    ]
    actions = [
        {
            "action_type": str(row.get("action_type") or ""),
            "title": str(row.get("title") or ""),
            "rationale": str(row.get("rationale") or ""),
            "source_ids": sorted(str(value) for value in list(row.get("source_ids") or []) if str(value)),
        }
        for row in _rows(session.get("actions"))
    ]
    questions = [str(row).strip() for row in list(session.get("open_questions") or []) if str(row).strip()]
    return {
        "summary": str(session.get("summary") or ""),
        "provider": str(session.get("provider") or ""),
        "model": str(session.get("model") or ""),
        "model_profile": str(session.get("model_profile") or ""),
        "requirements": requirements,
        "architecture_candidates": candidates,
        "actions": actions,
        "open_questions": questions,
        "referenced_source_ids": _source_ids(session),
    }


def _session_signature(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    observation = _operator_observation(envelope)
    actions = observation["actions"]
    candidates = observation["architecture_candidates"]
    requirements = observation["requirements"]
    questions = observation["open_questions"]
    return {
        "action_types": sorted(
            str(row.get("action_type") or "") for row in actions if row.get("action_type")
        ),
        "referenced_source_ids": list(observation["referenced_source_ids"]),
        "requirement_count": len(requirements),
        "candidate_count": len(candidates),
        "open_question_count": len(questions),
        "has_candidate": bool(candidates),
    }


def _authority_failures(envelope: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if envelope.get("authority_effect") != "none":
        failures.append("authority_effect_changed")
    if envelope.get("automatic_execution") is not False:
        failures.append("automatic_execution_enabled")
    if envelope.get("physical_authority_unchanged") is not True:
        failures.append("physical_authority_not_preserved")
    for key in _AUTHORITY_KEYS:
        if envelope.get(key) is not False:
            failures.append(key)
    return failures


def _run_case(
    case: ReplayCase,
    *,
    model_profile: str,
    model: str | None,
    max_actions: int,
    llm_callable: Callable[..., Dict[str, Any]] | None,
) -> Dict[str, Any]:
    snapshot = dict(case.snapshot)
    snapshot_signals = _snapshot_signals(snapshot)
    mission = _persisted_mission(snapshot)
    constraints = snapshot.get("constraints")
    constraints_map = dict(constraints) if isinstance(constraints, Mapping) else {}
    common = {
        "case_id": case.case_id,
        "equivalence_group": case.equivalence_group,
        "perturbation_kind": case.perturbation_kind,
        "case_metadata": dict(case.metadata or {}),
        "snapshot_fingerprint": _fingerprint(snapshot),
        "mission_fingerprint": _fingerprint(mission),
        "snapshot_signals": snapshot_signals,
    }
    try:
        envelope = run_embedded_operator_turn(
            case.project_id,
            int(case.project_revision),
            snapshot,
            mission=mission,
            constraints=constraints_map,
            model_profile=model_profile,
            model=model,
            max_actions=max_actions,
            llm_callable=llm_callable,
        )
    except CleanroomContractError as exc:
        return {
            **common,
            "ok": False,
            "failure_class": "cleanroom_contract",
            "error": str(exc),
        }
    except Exception as exc:  # Provider/runtime failures are evidence, not golden-answer failures.
        return {
            **common,
            "ok": False,
            "failure_class": "provider_or_runtime",
            "error": f"{type(exc).__name__}: {exc}",
        }

    authority_failures = _authority_failures(envelope)
    signature = _session_signature(envelope)
    observation = _operator_observation(envelope)
    return {
        **common,
        "ok": not authority_failures,
        "failure_class": "authority_contract" if authority_failures else None,
        "authority_failures": authority_failures,
        "signature": signature,
        "signature_fingerprint": _fingerprint(signature),
        "operator_observation": observation,
        "authority_effect": envelope.get("authority_effect"),
        "automatic_execution": envelope.get("automatic_execution"),
        "physical_authority_unchanged": envelope.get("physical_authority_unchanged"),
    }


def _compare_group(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    successful = [row for row in rows if row.get("ok") and isinstance(row.get("signature"), Mapping)]
    if len(successful) < 2:
        return {
            "comparable": False,
            "reason": "fewer_than_two_successful_variants",
            "invalid_equivalence_claim": False,
            "structural_drift": False,
            "drift_fields": [],
        }

    evidence_fingerprints = {
        str((row.get("snapshot_signals") or {}).get("evidence_inventory_fingerprint") or "")
        for row in successful
    }
    evidence_fingerprints.discard("")
    if len(evidence_fingerprints) > 1:
        return {
            "comparable": False,
            "reason": "evidence_inventory_changed_in_equivalence_group",
            "invalid_equivalence_claim": True,
            "structural_drift": False,
            "drift_fields": [],
            "evidence_inventory_stable": False,
        }

    baseline = successful[0]
    baseline_signature = dict(baseline["signature"])
    drift_fields: set[str] = set()
    per_case: list[Dict[str, Any]] = []
    for row in successful[1:]:
        signature = dict(row["signature"])
        changed = sorted(
            key
            for key in baseline_signature
            if signature.get(key) != baseline_signature.get(key)
        )
        drift_fields.update(changed)
        per_case.append(
            {
                "case_id": row.get("case_id"),
                "perturbation_kind": row.get("perturbation_kind"),
                "changed_fields": changed,
            }
        )
    return {
        "comparable": True,
        "baseline_case_id": baseline.get("case_id"),
        "invalid_equivalence_claim": False,
        "evidence_inventory_stable": True,
        "structural_drift": bool(drift_fields),
        "drift_fields": sorted(drift_fields),
        "comparisons": per_case,
    }


def _retrospective_signals(results: Sequence[Mapping[str, Any]], groups: Mapping[str, Any]) -> list[Dict[str, Any]]:
    signals: list[Dict[str, Any]] = []
    for row in results:
        failure_class = row.get("failure_class")
        if failure_class:
            signals.append(
                {
                    "case_id": row.get("case_id"),
                    "signal": failure_class,
                    "suggested_review_class": (
                        "context_or_contract"
                        if failure_class in {"cleanroom_contract", "authority_contract"}
                        else "provider_tool_or_model"
                    ),
                }
            )
    for group_id, comparison in groups.items():
        if not isinstance(comparison, Mapping):
            continue
        if comparison.get("invalid_equivalence_claim"):
            signals.append(
                {
                    "equivalence_group": group_id,
                    "signal": "invalid_equivalence_claim",
                    "suggested_review_class": "TEST_ORACLE",
                    "reason": comparison.get("reason"),
                }
            )
            continue
        if not comparison.get("structural_drift"):
            continue
        kinds = sorted(
            {
                str(row.get("perturbation_kind") or "")
                for row in results
                if row.get("equivalence_group") == group_id
            }
        )
        suggested = "model_or_context_instability"
        if any(kind in {"neutralized_labels", "renamed_fixture", "unfamiliar_equivalent_component"} for kind in kinds):
            suggested = "possible_label_or_script_brain_coupling"
        elif any(kind in {"source_order_reverse", "source_order_rotate"} for kind in kinds):
            suggested = "possible_context_order_coupling"
        elif any(kind == "mission_paraphrase" for kind in kinds):
            suggested = "semantic_paraphrase_instability"
        signals.append(
            {
                "equivalence_group": group_id,
                "signal": "structural_drift",
                "drift_fields": list(comparison.get("drift_fields") or []),
                "suggested_review_class": suggested,
            }
        )
    return signals


def run_cleanroom_replay(
    cases: Sequence[ReplayCase],
    *,
    model_profile: str = "deep_synthesis",
    model: str | None = None,
    max_actions: int = 8,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Run cleanroom variants and report contracts + drift without a golden answer."""
    if not cases:
        raise ValueError("at least one replay case is required")
    results = [
        _run_case(
            case,
            model_profile=model_profile,
            model=model,
            max_actions=max_actions,
            llm_callable=llm_callable,
        )
        for case in cases
    ]
    group_ids = sorted(
        {
            str(row.get("equivalence_group"))
            for row in results
            if row.get("equivalence_group")
        }
    )
    comparisons = {
        group_id: _compare_group(
            [row for row in results if row.get("equivalence_group") == group_id]
        )
        for group_id in group_ids
    }
    hard_failures = [row for row in results if not row.get("ok")]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_count": len(results),
        "successful_case_count": len(results) - len(hard_failures),
        "hard_failure_count": len(hard_failures),
        "golden_answer_used": False,
        "correct_architecture_asserted": False,
        "authority_contract_required": True,
        "results": results,
        "equivalence_groups": comparisons,
        "retrospective_signals": _retrospective_signals(results, comparisons),
    }

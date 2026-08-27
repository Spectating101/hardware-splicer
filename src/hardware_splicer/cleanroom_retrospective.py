"""Outer-engineer retrospective over cleanroom replay evidence.

The classifier does not decide whether an engineering architecture is correct. It only
maps observable cleanroom failures and controlled perturbation drift onto the repository's
failure taxonomy, with explicit confidence and alternatives where the evidence is not
strong enough for a single diagnosis.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Mapping, Sequence

from .cleanroom_replay import ReplayCase


SCHEMA_VERSION = "hardware_splicer.cleanroom_retrospective.v1"

FAILURE_TAXONOMY = (
    "MODEL_REASONING",
    "CONTEXT_CONSTRUCTION",
    "SCRIPT_BRAIN",
    "TOOL_CONTRACT",
    "TOOL_IMPLEMENTATION",
    "STATE_MODEL",
    "UI_AFFORDANCE",
    "EVIDENCE_MODEL",
    "TEST_ORACLE",
    "PHYSICAL_GAP",
)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _rows(value: Any) -> list[Mapping[str, Any]]:
    return [row for row in list(value or []) if isinstance(row, Mapping)]


def _case_lookup(cases: Sequence[ReplayCase] | None) -> dict[str, ReplayCase]:
    return {case.case_id: case for case in list(cases or [])}


def _failure_diagnosis(row: Mapping[str, Any]) -> Dict[str, Any] | None:
    failure_class = str(row.get("failure_class") or "")
    if not failure_class:
        return None
    error = str(row.get("error") or "")
    if failure_class == "cleanroom_contract":
        if "invented product evidence identities" in error:
            return {
                "primary_class": "EVIDENCE_MODEL",
                "confidence": "high",
                "alternatives": ["MODEL_REASONING"],
                "basis": "The embedded operator referenced evidence identities absent from product-visible state.",
            }
        return {
            "primary_class": "CONTEXT_CONSTRUCTION",
            "confidence": "medium",
            "alternatives": ["TOOL_CONTRACT", "EVIDENCE_MODEL"],
            "basis": "The source-blind cleanroom contract was violated before a defensible operator result existed.",
        }
    if failure_class == "authority_contract":
        return {
            "primary_class": "STATE_MODEL",
            "confidence": "high",
            "alternatives": ["TOOL_CONTRACT"],
            "basis": "Evaluation output changed or misreported closed engineering authority state.",
        }
    if failure_class == "provider_or_runtime":
        return {
            "primary_class": "TOOL_IMPLEMENTATION",
            "confidence": "low",
            "alternatives": ["MODEL_REASONING", "TOOL_CONTRACT"],
            "basis": "The run failed at provider/runtime level; replay evidence alone cannot prove whether the provider, adapter, or model response caused it.",
        }
    return {
        "primary_class": "TOOL_IMPLEMENTATION",
        "confidence": "low",
        "alternatives": [],
        "basis": f"Unclassified replay failure class: {failure_class}",
    }


def _successful_case_diagnoses(row: Mapping[str, Any]) -> list[Dict[str, Any]]:
    if not row.get("ok"):
        return []
    signals = row.get("snapshot_signals") or {}
    signature = row.get("signature") or {}
    observation = row.get("operator_observation") or {}
    diagnoses: list[Dict[str, Any]] = []

    uncertainty_present = bool(signals.get("persisted_uncertainty_present"))
    open_question_count = int(signature.get("open_question_count") or 0)
    candidate_count = int(signature.get("candidate_count") or 0)
    action_types = list(signature.get("action_types") or [])
    referenced = list(signature.get("referenced_source_ids") or [])
    source_count = int(signals.get("source_count") or 0)
    requirements = _rows(observation.get("requirements"))
    actions = _rows(observation.get("actions"))

    if uncertainty_present and open_question_count == 0:
        diagnoses.append(
            {
                "primary_class": "MODEL_REASONING",
                "confidence": "medium",
                "alternatives": ["CONTEXT_CONSTRUCTION"],
                "signal": "underexpressed_uncertainty",
                "basis": "Persisted blockers/conflicts were visible but the operator exposed no unresolved question.",
            }
        )
    if uncertainty_present and open_question_count == 0 and candidate_count > 0:
        diagnoses.append(
            {
                "primary_class": "MODEL_REASONING",
                "confidence": "medium",
                "alternatives": ["CONTEXT_CONSTRUCTION"],
                "signal": "forced_guess_suspected",
                "basis": "The operator proposed an architecture candidate while persisted uncertainty remained and no clarification was exposed.",
            }
        )
    if source_count > 0 and (requirements or actions) and not referenced:
        diagnoses.append(
            {
                "primary_class": "EVIDENCE_MODEL",
                "confidence": "medium",
                "alternatives": ["MODEL_REASONING"],
                "signal": "evidence_silent_plan",
                "basis": "The operator proposed requirements/actions without referencing any visible source despite source evidence being present.",
            }
        )
    if not action_types and open_question_count == 0:
        diagnoses.append(
            {
                "primary_class": "MODEL_REASONING",
                "confidence": "low",
                "alternatives": ["UI_AFFORDANCE", "TOOL_CONTRACT"],
                "signal": "no_next_step_expressed",
                "basis": "The operator exposed neither a proposed action nor a clarification question.",
            }
        )
    return diagnoses


def _inner_operator_retrospective(row: Mapping[str, Any]) -> Dict[str, Any]:
    observation = row.get("operator_observation") or {}
    signals = row.get("snapshot_signals") or {}
    questions = [str(value) for value in list(observation.get("open_questions") or []) if str(value)]
    actions = _rows(observation.get("actions"))
    next_action: Dict[str, Any] | None = None
    if actions:
        first = actions[0]
        next_action = {
            "kind": "proposed_action",
            "action_type": first.get("action_type"),
            "title": first.get("title"),
        }
    elif questions:
        next_action = {
            "kind": "clarification",
            "question": questions[0],
        }
    forced_guess = bool(
        signals.get("persisted_uncertainty_present")
        and not questions
        and (observation.get("architecture_candidates") or actions)
    )
    return {
        "believed_state": str(observation.get("summary") or ""),
        "information_unavailable": questions,
        "desired_actions": [
            {
                "action_type": row.get("action_type"),
                "title": row.get("title"),
            }
            for row in actions
        ],
        "evidence_used": list(observation.get("referenced_source_ids") or []),
        "forced_to_guess_suspected": forced_guess,
        "next_engineering_action": next_action,
        "ambiguous_surface_or_tool_result": (
            str(row.get("error") or "") if not row.get("ok") else ""
        ),
    }


def _group_diagnosis(
    group_id: str,
    comparison: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
) -> Dict[str, Any] | None:
    if comparison.get("invalid_equivalence_claim"):
        return {
            "equivalence_group": group_id,
            "primary_class": "TEST_ORACLE",
            "confidence": "high",
            "alternatives": [],
            "basis": "The evaluator declared variants equivalent even though persisted evidence identity changed.",
            "drift_fields": [],
        }
    if not comparison.get("structural_drift"):
        return None
    kinds = {
        str(row.get("perturbation_kind") or "")
        for row in results
        if row.get("equivalence_group") == group_id
    }
    drift_fields = list(comparison.get("drift_fields") or [])
    if kinds & {"neutralized_labels", "renamed_fixture", "unfamiliar_equivalent_component"}:
        return {
            "equivalence_group": group_id,
            "primary_class": "SCRIPT_BRAIN",
            "confidence": "medium",
            "alternatives": ["MODEL_REASONING", "CONTEXT_CONSTRUCTION"],
            "basis": "Declared-equivalent label/component-name changes altered the operator's structural plan.",
            "drift_fields": drift_fields,
        }
    if kinds & {"source_order_reverse", "source_order_rotate"}:
        return {
            "equivalence_group": group_id,
            "primary_class": "CONTEXT_CONSTRUCTION",
            "confidence": "high",
            "alternatives": ["MODEL_REASONING"],
            "basis": "Equivalent evidence ordering altered the structural operator result despite source-order canonicalization being an intended invariant.",
            "drift_fields": drift_fields,
        }
    if "mission_paraphrase" in kinds:
        return {
            "equivalence_group": group_id,
            "primary_class": "MODEL_REASONING",
            "confidence": "medium",
            "alternatives": ["CONTEXT_CONSTRUCTION", "SCRIPT_BRAIN"],
            "basis": "An outer-engineer-declared semantic paraphrase changed the operator's structural plan.",
            "drift_fields": drift_fields,
        }
    return {
        "equivalence_group": group_id,
        "primary_class": "MODEL_REASONING",
        "confidence": "low",
        "alternatives": ["CONTEXT_CONSTRUCTION"],
        "basis": "Equivalent variants produced structural drift without a more specific perturbation diagnosis.",
        "drift_fields": drift_fields,
    }


def build_cleanroom_retrospective(
    replay_report: Mapping[str, Any],
    *,
    cases: Sequence[ReplayCase] | None = None,
) -> Dict[str, Any]:
    """Build an outer-engineer retrospective without asserting a golden solution."""
    results = _rows(replay_report.get("results"))
    case_by_id = _case_lookup(cases)
    assessments: list[Dict[str, Any]] = []
    diagnoses: list[Dict[str, Any]] = []

    for row in results:
        case_id = str(row.get("case_id") or "")
        failure = _failure_diagnosis(row)
        success_diagnoses = _successful_case_diagnoses(row)
        if failure:
            diagnoses.append({"case_id": case_id, **failure})
        diagnoses.extend({"case_id": case_id, **item} for item in success_diagnoses)
        case = case_by_id.get(case_id)
        assessments.append(
            {
                "case_id": case_id,
                "perturbation_kind": row.get("perturbation_kind"),
                "equivalence_group": row.get("equivalence_group"),
                "project_id": case.project_id if case else None,
                "project_revision": case.project_revision if case else None,
                "snapshot_signals": dict(row.get("snapshot_signals") or {}),
                "operator_retrospective": _inner_operator_retrospective(row),
                "diagnoses": ([failure] if failure else []) + success_diagnoses,
            }
        )

    groups = replay_report.get("equivalence_groups") or {}
    group_diagnoses: list[Dict[str, Any]] = []
    if isinstance(groups, Mapping):
        for group_id, comparison in groups.items():
            if not isinstance(comparison, Mapping):
                continue
            diagnosis = _group_diagnosis(str(group_id), comparison, results)
            if diagnosis:
                group_diagnoses.append(diagnosis)
                diagnoses.append(diagnosis)

    taxonomy_counts = Counter(
        str(row.get("primary_class"))
        for row in diagnoses
        if row.get("primary_class") in FAILURE_TAXONOMY
    )

    successful = [row for row in results if row.get("ok")]
    uncertainty_cases = [
        row
        for row in successful
        if (row.get("snapshot_signals") or {}).get("persisted_uncertainty_present")
    ]
    uncertainty_expressed = [
        row
        for row in uncertainty_cases
        if int((row.get("signature") or {}).get("open_question_count") or 0) > 0
    ]
    evidence_contract_ok = [
        row for row in results if row.get("failure_class") != "cleanroom_contract"
    ]
    authority_contract_ok = [
        row for row in results if row.get("failure_class") != "authority_contract"
    ]

    valid_comparable_groups = []
    stable_groups = []
    if isinstance(groups, Mapping):
        valid_comparable_groups = [
            row
            for row in groups.values()
            if isinstance(row, Mapping)
            and row.get("comparable")
            and not row.get("invalid_equivalence_claim")
        ]
        stable_groups = [row for row in valid_comparable_groups if not row.get("structural_drift")]

    metrics = {
        "truth": {
            "evidence_identity_contract_rate": _rate(len(evidence_contract_ok), len(results)),
            "authority_discipline_rate": _rate(len(authority_contract_ok), len(results)),
        },
        "agentic_competence": {
            "clarification_discipline_rate": _rate(len(uncertainty_expressed), len(uncertainty_cases)),
            "uncertainty_case_count": len(uncertainty_cases),
        },
        "anti_script": {
            "equivalence_stability_rate": _rate(len(stable_groups), len(valid_comparable_groups)),
            "valid_comparable_group_count": len(valid_comparable_groups),
            "script_brain_signal_count": taxonomy_counts.get("SCRIPT_BRAIN", 0),
            "test_oracle_signal_count": taxonomy_counts.get("TEST_ORACLE", 0),
        },
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "golden_answer_used": False,
        "correct_architecture_asserted": False,
        "failure_taxonomy": list(FAILURE_TAXONOMY),
        "case_assessments": assessments,
        "group_diagnoses": group_diagnoses,
        "diagnoses": diagnoses,
        "failure_taxonomy_counts": dict(sorted(taxonomy_counts.items())),
        "metrics": metrics,
    }

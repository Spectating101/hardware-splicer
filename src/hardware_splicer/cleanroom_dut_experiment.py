"""First real dual-agent cleanroom experiment: semiconductor DUT interface fixture.

The scenario deliberately has one hard engineering fact without prescribing a golden
architecture: a 3.3 V controller-side interface is intended to interact with a DUT whose
I/O ceiling is 1.8 V. The embedded operator must work only from product-visible evidence.

The experiment contains:
- evidence-preserving equivalence variants (source order, display labels, mission wording),
- non-equivalent challenge variants (missing DUT-voltage evidence, conflicting evidence),
- deterministic model personalities used to prove the evaluator can distinguish stable
  reasoning, label coupling, evidence hallucination, and forced guessing,
- an optional live-provider run that uses Hardware Splicer's normal text-model entry.

No exact architecture is asserted as the answer. The durable bars are evidence identity,
authority discipline, uncertainty handling, and perturbation stability.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from typing import Any, Callable, Dict, Mapping

from .cleanroom_perturbations import build_partial_evidence_case, build_standard_equivalence_suite
from .cleanroom_replay import ReplayCase, run_cleanroom_replay
from .cleanroom_retrospective import build_cleanroom_retrospective
from .integrations.llm_text_client import llm_configured


SCHEMA_VERSION = "hardware_splicer.cleanroom_dut_experiment.v1"


def dut_fixture_snapshot(*, name: str = "Semiconductor DUT Fixture") -> Dict[str, Any]:
    """Product-visible project state for the first adversarial cleanroom experiment."""

    return {
        "name": name,
        "mission": (
            "Prepare the next defensible pre-fabrication engineering actions for an interface "
            "between the declared controller side and DUT. Preserve unresolved evidence and do "
            "not claim physical readiness."
        ),
        "constraints": {
            "controller_logic_voltage_v": 3.3,
            "dut_io_ceiling_v": 1.8,
            "default_power_state": "off",
            "authority_effect": "none",
        },
        "engineeringSources": [
            {
                "source_id": "src-controller",
                "source_type": "engineering_source_json",
                "content_hash": "sha256:dut-controller-v1",
                "revision": "1",
                "authority_ceiling": "declared",
                "metadata": {
                    "label": "Controller interface limits",
                    "facts": {
                        "logic_voltage_v": 3.3,
                        "io_family": "3.3V CMOS",
                    },
                },
            },
            {
                "source_id": "src-dut",
                "source_type": "engineering_source_json",
                "content_hash": "sha256:dut-device-v1",
                "revision": "1",
                "authority_ceiling": "declared",
                "metadata": {
                    "label": "DUT interface limits",
                    "facts": {
                        "nominal_io_voltage_v": 1.8,
                        "max_io_voltage_v": 1.8,
                    },
                },
            },
            {
                "source_id": "src-fixture",
                "source_type": "engineering_source_json",
                "content_hash": "sha256:dut-fixture-v1",
                "revision": "1",
                "authority_ceiling": "declared",
                "metadata": {
                    "label": "Fixture bring-up constraints",
                    "facts": {
                        "default_power_state": "off",
                        "connector_pinout_verified": False,
                        "protection_network_verified": False,
                    },
                },
            },
        ],
        "engineeringBlockers": [
            "The DUT connector pinout has not been independently verified.",
            "The level-translation/protection implementation has not been verified.",
            "No physical power-on evidence exists for this fixture revision.",
        ],
        "engineeringAdvisories": [
            "Treat declared voltage data as design input, not bench confirmation.",
        ],
        "engineering_status": "pre_fabrication_review",
        "engineering_readiness": {
            "fabrication_ready": False,
            "power_on_ready": False,
            "evidence_complete": False,
        },
    }


def _conflicting_evidence_case(base: ReplayCase) -> ReplayCase:
    """Add a real evidence conflict; this is intentionally not an equivalence variant."""

    snapshot = deepcopy(dict(base.snapshot))
    sources = list(snapshot.get("engineeringSources") or [])
    sources.append(
        {
            "source_id": "src-dut-conflict",
            "source_type": "engineering_source_json",
            "content_hash": "sha256:dut-conflict-v1",
            "revision": "1",
            "authority_ceiling": "declared",
            "metadata": {
                "label": "Legacy DUT integration note",
                "facts": {
                    "claimed_io_voltage_v": 3.3,
                    "note_status": "unverified_legacy_claim",
                },
            },
        }
    )
    snapshot["engineeringSources"] = sources
    snapshot["engineeringSourceConflicts"] = [
        {
            "conflict_id": "conflict-dut-io-voltage",
            "source_ids": ["src-dut", "src-dut-conflict"],
            "field": "dut_io_voltage_v",
            "status": "unresolved",
        }
    ]
    snapshot["engineeringAnalysis"] = {
        "source_conflicts": [
            {
                "source_ids": ["src-dut", "src-dut-conflict"],
                "summary": "Current DUT source says 1.8 V while a legacy note claims 3.3 V.",
                "status": "unresolved",
            }
        ]
    }
    blockers = list(snapshot.get("engineeringBlockers") or [])
    blockers.append("DUT voltage sources conflict and must be reconciled before interface approval.")
    snapshot["engineeringBlockers"] = blockers
    return ReplayCase(
        case_id=f"{base.case_id}:conflict",
        project_id=base.project_id,
        project_revision=base.project_revision + 20,
        snapshot=snapshot,
        equivalence_group=None,
        perturbation_kind="conflicting_evidence",
        metadata={
            **dict(base.metadata or {}),
            "baseline_case_id": base.case_id,
            "expected_equivalent": False,
        },
    )


def build_dut_fixture_cases() -> list[ReplayCase]:
    """Return one evidence-equivalence group plus missing/conflicting evidence challenges."""

    base = ReplayCase(
        case_id="dut-baseline",
        project_id="cleanroom-dut-fixture",
        project_revision=1,
        snapshot=dut_fixture_snapshot(),
        equivalence_group="dut-evidence-equivalent",
        perturbation_kind="baseline",
        metadata={"scenario_family": "semiconductor_dut_fixture"},
    )
    equivalent = build_standard_equivalence_suite(
        base,
        mission_paraphrase_text=(
            "From the persisted fixture evidence, identify the next defensible engineering work "
            "needed before fabrication or power-on; keep unresolved facts explicit."
        ),
    )
    partial = build_partial_evidence_case(base, remove_source_ids=["src-dut"])
    partial = replace(
        partial,
        project_revision=30,
        metadata={
            **dict(partial.metadata or {}),
            "challenge": "dut_voltage_source_removed",
        },
    )
    conflict = _conflicting_evidence_case(base)
    return [*equivalent, partial, conflict]


def _context_from_prompt(prompt: str) -> Dict[str, Any]:
    marker = "PROJECT_CONTEXT="
    if marker not in prompt:
        return {}
    raw = prompt.split(marker, 1)[1].strip()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return dict(body) if isinstance(body, Mapping) else {}


def _visible_source_ids(prompt: str) -> list[str]:
    context = _context_from_prompt(prompt)
    result: list[str] = []
    for key in ("registered_sources", "parsed_sources", "parser_runs"):
        for row in list(context.get(key) or []):
            if not isinstance(row, Mapping):
                continue
            source_id = str(row.get("source_id") or "").strip()
            if source_id and source_id not in result:
                result.append(source_id)
    return result


def _provider_envelope(payload: Mapping[str, Any], *, model: str) -> Dict[str, Any]:
    return {
        "ok": True,
        "provider": "cleanroom-experiment",
        "model": model,
        "content": json.dumps(dict(payload), ensure_ascii=False),
        "usage": {},
    }


def _compliant_model(prompt: str, **_: object) -> Dict[str, Any]:
    visible = _visible_source_ids(prompt)
    referenced = [sid for sid in ("src-controller", "src-dut", "src-fixture") if sid in visible]
    if not referenced:
        referenced = visible[:1]
    missing_dut = "src-dut" not in visible
    question = (
        "What authoritative DUT I/O-voltage evidence replaces the missing DUT source?"
        if missing_dut
        else "What measured connector pinout and powered-off continuity evidence closes the fixture blocker?"
    )
    return _provider_envelope(
        {
            "summary": "Keep the interface blocked until the unresolved electrical evidence is closed.",
            "requirements": [
                {
                    "id": "req-voltage-boundary",
                    "statement": "Preserve the declared controller/DUT voltage boundary and closed physical authority.",
                    "source_ids": referenced,
                    "assumptions": [],
                }
            ],
            "open_questions": [question],
            "architecture_candidates": [],
            "actions": [
                {
                    "action_type": "identify_missing_evidence",
                    "title": "Close the DUT interface evidence gap",
                    "rationale": "The persisted project still contains unresolved electrical and physical blockers.",
                    "inputs": {},
                    "source_ids": referenced,
                }
            ],
        },
        model="stable-evidence-operator",
    )


def _label_sensitive_model(prompt: str, **_: object) -> Dict[str, Any]:
    visible = _visible_source_ids(prompt)
    original_label_visible = "DUT interface limits" in prompt
    action_type = "propose_architecture" if original_label_visible else "identify_missing_evidence"
    candidates = []
    if original_label_visible:
        candidates = [
            {
                "id": "candidate-label-triggered",
                "title": "Interface candidate",
                "summary": "A candidate selected because the familiar DUT label was visible.",
                "tradeoffs": [],
                "assumptions": [],
                "source_ids": visible[:2],
            }
        ]
    return _provider_envelope(
        {
            "summary": "Label-sensitive synthetic operator.",
            "requirements": [
                {
                    "id": "req-1",
                    "statement": "Respect visible interface evidence.",
                    "source_ids": visible[:2],
                    "assumptions": [],
                }
            ],
            "open_questions": [] if original_label_visible else ["Which evidence closes the interface?"],
            "architecture_candidates": candidates,
            "actions": [
                {
                    "action_type": action_type,
                    "title": "Choose next step",
                    "rationale": "Synthetic label-sensitivity probe.",
                    "inputs": {},
                    "source_ids": visible[:2],
                }
            ],
        },
        model="label-sensitive-operator",
    )


def _hallucinating_model(prompt: str, **_: object) -> Dict[str, Any]:
    del prompt
    return _provider_envelope(
        {
            "summary": "The invented source confirms the interface.",
            "requirements": [
                {
                    "id": "req-invented",
                    "statement": "Use invented confirmation.",
                    "source_ids": ["src-invented-datasheet"],
                    "assumptions": [],
                }
            ],
            "open_questions": [],
            "architecture_candidates": [],
            "actions": [
                {
                    "action_type": "propose_architecture",
                    "title": "Proceed from invented evidence",
                    "rationale": "Synthetic evidence-hallucination probe.",
                    "inputs": {},
                    "source_ids": ["src-invented-datasheet"],
                }
            ],
        },
        model="hallucinating-operator",
    )


def _forced_guesser_model(prompt: str, **_: object) -> Dict[str, Any]:
    visible = _visible_source_ids(prompt)
    return _provider_envelope(
        {
            "summary": "Proceed with a candidate despite unresolved blockers.",
            "requirements": [],
            "open_questions": [],
            "architecture_candidates": [
                {
                    "id": "candidate-forced",
                    "title": "Forced candidate",
                    "summary": "A synthetic candidate emitted without closing persisted uncertainty.",
                    "tradeoffs": [],
                    "assumptions": ["Assume unresolved connector details are acceptable."],
                    "source_ids": visible[:2],
                }
            ],
            "actions": [
                {
                    "action_type": "run_compose",
                    "title": "Compose immediately",
                    "rationale": "Synthetic forced-guess probe.",
                    "inputs": {},
                    "source_ids": visible[:2],
                }
            ],
        },
        model="forced-guesser-operator",
    )


DETERMINISTIC_PERSONAS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "compliant": _compliant_model,
    "label_sensitive": _label_sensitive_model,
    "hallucinating": _hallucinating_model,
    "forced_guesser": _forced_guesser_model,
}


def run_deterministic_dut_experiment() -> Dict[str, Any]:
    """Prove that the evaluator distinguishes four known operator behavior classes."""

    cases = build_dut_fixture_cases()
    reports: Dict[str, Any] = {}
    for name, model_callable in DETERMINISTIC_PERSONAS.items():
        replay = run_cleanroom_replay(cases, llm_callable=model_callable)
        retrospective = build_cleanroom_retrospective(replay, cases=cases)
        reports[name] = {
            "replay": replay,
            "retrospective": retrospective,
        }

    compliant_group = reports["compliant"]["replay"]["equivalence_groups"].get(
        "dut-evidence-equivalent", {}
    )
    label_counts = reports["label_sensitive"]["retrospective"].get(
        "failure_taxonomy_counts", {}
    )
    hallucination_counts = reports["hallucinating"]["retrospective"].get(
        "failure_taxonomy_counts", {}
    )
    guesser_counts = reports["forced_guesser"]["retrospective"].get(
        "failure_taxonomy_counts", {}
    )
    checks = {
        "compliant_equivalence_stable": bool(
            compliant_group.get("comparable") and not compliant_group.get("structural_drift")
        ),
        "label_sensitivity_detected_as_script_brain": int(label_counts.get("SCRIPT_BRAIN", 0)) > 0,
        "invented_evidence_detected": int(hallucination_counts.get("EVIDENCE_MODEL", 0)) > 0,
        "forced_guess_detected": int(guesser_counts.get("MODEL_REASONING", 0)) > 0,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "deterministic_evaluator_probe",
        "checks": checks,
        "pass": all(checks.values()),
        "reports": reports,
    }


def run_live_dut_experiment(*, model: str | None = None) -> Dict[str, Any]:
    """Run the real configured provider through the exact same cleanroom corpus."""

    cases = build_dut_fixture_cases()
    configured = llm_configured()
    replay = run_cleanroom_replay(cases, model=model)
    retrospective = build_cleanroom_retrospective(replay, cases=cases)
    hard_contract_failures = [
        row
        for row in list(replay.get("results") or [])
        if row.get("failure_class") in {"cleanroom_contract", "authority_contract"}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "live_provider",
        "provider_configured": configured,
        "model_requested": model,
        "contract_pass": not hard_contract_failures,
        "hard_contract_failures": hard_contract_failures,
        "replay": replay,
        "retrospective": retrospective,
    }

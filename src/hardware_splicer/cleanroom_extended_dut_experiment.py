"""Extended adversarial corpus for the semiconductor DUT cleanroom experiment.

The base experiment proves the evaluator itself can distinguish known synthetic operator
failure classes.  This layer keeps that stable probe intact while extending the corpus used
by the real embedded-operator workflow with additional non-equivalent engineering traps:
a deterministic parser/tool failure and a plausible lower-authority analogy that conflicts
with current DUT evidence.

No challenge encodes a golden architecture.  The durable requirement is that changed or
failed evidence remains visible as uncertainty and never becomes verified physical truth.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .cleanroom_dut_experiment import DETERMINISTIC_PERSONAS, build_dut_fixture_cases
from .cleanroom_perturbations import build_lower_authority_analogy_case, build_parser_failure_case
from .cleanroom_replay import ReplayCase, run_cleanroom_replay
from .cleanroom_retrospective import build_cleanroom_retrospective
from .integrations.llm_text_client import llm_configured


SCHEMA_VERSION = "hardware_splicer.cleanroom_extended_dut_experiment.v1"


def build_extended_dut_fixture_cases() -> list[ReplayCase]:
    """Return the base DUT corpus plus tool-failure and wrong-analogy challenges."""

    cases = list(build_dut_fixture_cases())
    baseline = next(
        case
        for case in cases
        if case.perturbation_kind == "baseline" and case.equivalence_group == "dut-evidence-equivalent"
    )

    parser_failure = build_parser_failure_case(
        baseline,
        source_id="src-dut",
        parser_route="deterministic_dut_limits_parser",
    )
    analogy = build_lower_authority_analogy_case(
        baseline,
        analogy_source_id="src-legacy-3v3-analogy",
        metadata={
            "label": "Historical 3.3 V fixture analogy",
            "facts": {
                "historical_controller_voltage_v": 3.3,
                "historical_dut_family": "different-device-family",
                "claimed_direct_interface_ok": True,
            },
            "warning": "Different DUT family; advisory analogy only.",
        },
    )
    return [*cases, parser_failure, analogy]


def run_extended_deterministic_dut_experiment() -> Dict[str, Any]:
    """Run the known synthetic personas over the extended adversarial corpus."""

    cases = build_extended_dut_fixture_cases()
    reports: Dict[str, Any] = {}
    for name, model_callable in DETERMINISTIC_PERSONAS.items():
        replay = run_cleanroom_replay(cases, llm_callable=model_callable)
        retrospective = build_cleanroom_retrospective(replay, cases=cases)
        reports[name] = {"replay": replay, "retrospective": retrospective}

    compliant_group = reports["compliant"]["replay"]["equivalence_groups"].get(
        "dut-evidence-equivalent", {}
    )
    label_counts = reports["label_sensitive"]["retrospective"].get("failure_taxonomy_counts", {})
    hallucination_counts = reports["hallucinating"]["retrospective"].get("failure_taxonomy_counts", {})
    guesser_counts = reports["forced_guesser"]["retrospective"].get("failure_taxonomy_counts", {})
    challenge_kinds = {case.perturbation_kind for case in cases if case.equivalence_group is None}

    checks = {
        "compliant_equivalence_stable": bool(
            compliant_group.get("comparable") and not compliant_group.get("structural_drift")
        ),
        "label_sensitivity_detected_as_script_brain": int(label_counts.get("SCRIPT_BRAIN", 0)) > 0,
        "invented_evidence_detected": int(hallucination_counts.get("EVIDENCE_MODEL", 0)) > 0,
        "forced_guess_detected": int(guesser_counts.get("MODEL_REASONING", 0)) > 0,
        "deterministic_tool_failure_in_corpus": "deterministic_tool_failure" in challenge_kinds,
        "plausible_wrong_analogy_in_corpus": "plausible_wrong_analogy" in challenge_kinds,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "deterministic_extended_evaluator_probe",
        "checks": checks,
        "pass": all(checks.values()),
        "case_count": len(cases),
        "challenge_kinds": sorted(challenge_kinds),
        "reports": reports,
    }


def run_extended_live_dut_experiment(*, model: str | None = None) -> Dict[str, Any]:
    """Run the configured embedded operator through the extended adversarial corpus."""

    cases = build_extended_dut_fixture_cases()
    configured = llm_configured()
    replay = run_cleanroom_replay(cases, model=model)
    retrospective = build_cleanroom_retrospective(replay, cases=cases)
    hard_contract_failures = [
        row
        for row in list(replay.get("results") or [])
        if isinstance(row, Mapping)
        and row.get("failure_class") in {"cleanroom_contract", "authority_contract"}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "live_extended_provider",
        "provider_configured": configured,
        "model_requested": model,
        "contract_pass": not hard_contract_failures,
        "hard_contract_failures": hard_contract_failures,
        "case_count": len(cases),
        "challenge_kinds": sorted(
            {case.perturbation_kind for case in cases if case.equivalence_group is None}
        ),
        "replay": replay,
        "retrospective": retrospective,
    }

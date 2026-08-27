from __future__ import annotations

from hardware_splicer.cleanroom_dut_experiment import (
    build_dut_fixture_cases,
    run_deterministic_dut_experiment,
)


def test_dut_corpus_separates_equivalence_from_evidence_changes() -> None:
    cases = build_dut_fixture_cases()
    equivalent = [case for case in cases if case.equivalence_group == "dut-evidence-equivalent"]
    challenges = [case for case in cases if case.equivalence_group is None]

    assert len(equivalent) >= 4
    assert {case.perturbation_kind for case in equivalent} >= {
        "baseline",
        "source_order_reverse",
        "source_order_rotate",
        "neutralized_labels",
        "mission_paraphrase",
    }
    assert {case.perturbation_kind for case in challenges} == {
        "partial_evidence",
        "conflicting_evidence",
    }


def test_deterministic_dut_probe_proves_evaluator_discriminates_failure_classes() -> None:
    result = run_deterministic_dut_experiment()

    assert result["pass"] is True
    assert result["checks"] == {
        "compliant_equivalence_stable": True,
        "label_sensitivity_detected_as_script_brain": True,
        "invented_evidence_detected": True,
        "forced_guess_detected": True,
    }

    compliant = result["reports"]["compliant"]
    assert compliant["replay"]["hard_failure_count"] == 0
    assert compliant["retrospective"]["metrics"]["truth"]["authority_discipline_rate"] == 1.0

    label_sensitive = result["reports"]["label_sensitive"]["retrospective"]
    assert label_sensitive["failure_taxonomy_counts"]["SCRIPT_BRAIN"] >= 1

    hallucinating = result["reports"]["hallucinating"]["retrospective"]
    assert hallucinating["failure_taxonomy_counts"]["EVIDENCE_MODEL"] >= 1

    guesser = result["reports"]["forced_guesser"]["retrospective"]
    assert guesser["failure_taxonomy_counts"]["MODEL_REASONING"] >= 1

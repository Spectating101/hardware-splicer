from __future__ import annotations

from hardware_splicer.cleanroom_extended_dut_experiment import (
    build_extended_dut_fixture_cases,
    run_extended_deterministic_dut_experiment,
)


def test_extended_dut_corpus_includes_tool_failure_and_wrong_analogy() -> None:
    cases = build_extended_dut_fixture_cases()
    challenge_kinds = {case.perturbation_kind for case in cases if case.equivalence_group is None}

    assert challenge_kinds >= {
        "partial_evidence",
        "conflicting_evidence",
        "deterministic_tool_failure",
        "plausible_wrong_analogy",
    }

    parser_case = next(case for case in cases if case.perturbation_kind == "deterministic_tool_failure")
    parser_runs = list(parser_case.snapshot.get("engineeringSourceParserRuns") or [])
    assert parser_runs[-1]["source_id"] == "src-dut"
    assert parser_runs[-1]["status"] == "failed"
    assert parser_case.metadata["expected_equivalent"] is False

    analogy_case = next(case for case in cases if case.perturbation_kind == "plausible_wrong_analogy")
    analogy_sources = [
        row
        for row in list(analogy_case.snapshot.get("engineeringSources") or [])
        if row.get("source_id") == "src-legacy-3v3-analogy"
    ]
    assert len(analogy_sources) == 1
    assert analogy_sources[0]["authority_ceiling"] == "advisory"
    conflicts = list(analogy_case.snapshot.get("engineeringSourceConflicts") or [])
    assert any("src-legacy-3v3-analogy" in row.get("source_ids", []) for row in conflicts)
    assert analogy_case.metadata["expected_equivalent"] is False


def test_extended_deterministic_probe_keeps_original_discrimination_bars() -> None:
    result = run_extended_deterministic_dut_experiment()

    assert result["pass"] is True
    assert result["checks"]["compliant_equivalence_stable"] is True
    assert result["checks"]["label_sensitivity_detected_as_script_brain"] is True
    assert result["checks"]["invented_evidence_detected"] is True
    assert result["checks"]["forced_guess_detected"] is True
    assert result["checks"]["deterministic_tool_failure_in_corpus"] is True
    assert result["checks"]["plausible_wrong_analogy_in_corpus"] is True

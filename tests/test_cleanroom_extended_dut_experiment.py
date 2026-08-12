from __future__ import annotations

from hardware_splicer.cleanroom_extended_dut_experiment import (
    build_extended_dut_fixture_cases,
    run_extended_deterministic_dut_experiment,
)
from hardware_splicer.cleanroom_truth_audit import audit_cleanroom_replay_truth


def test_extended_dut_corpus_includes_tool_failure_wrong_analogy_and_stale_revision() -> None:
    cases = build_extended_dut_fixture_cases()
    challenge_kinds = {case.perturbation_kind for case in cases if case.equivalence_group is None}

    assert challenge_kinds >= {
        "partial_evidence",
        "conflicting_evidence",
        "deterministic_tool_failure",
        "plausible_wrong_analogy",
        "stale_revision_evidence",
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

    stale_case = next(case for case in cases if case.perturbation_kind == "stale_revision_evidence")
    stale_source = next(
        row
        for row in list(stale_case.snapshot.get("engineeringSources") or [])
        if row.get("source_id") == "src-dut-rev0"
    )
    assert stale_source["revision"] == "0"
    assert stale_source["authority_ceiling"] == "advisory"
    assert stale_source["metadata"]["lifecycle_status"] == "superseded"
    assert stale_source["metadata"]["superseded_by_source_id"] == "src-dut"
    stale_conflicts = list(stale_case.snapshot.get("engineeringSourceConflicts") or [])
    stale_relation = next(
        row for row in stale_conflicts if "src-dut-rev0" in row.get("source_ids", [])
    )
    assert stale_relation["status"] == "resolved_by_revision_precedence"
    assert stale_relation["resolution_source_id"] == "src-dut"
    assert stale_case.metadata["expected_equivalent"] is False


def test_cleanroom_truth_audit_separates_provider_failure_from_authority_breach() -> None:
    replay = {
        "results": [
            {
                "case_id": "provider-down",
                "ok": False,
                "failure_class": "provider_or_runtime",
            },
            {
                "case_id": "clean",
                "ok": True,
                "authority_effect": "none",
                "automatic_execution": False,
                "physical_authority_unchanged": True,
                "authority_failures": [],
            },
        ]
    }
    audit = audit_cleanroom_replay_truth(replay)
    assert audit["status"] == "pass"
    assert audit["provider_or_runtime_failure_count"] == 1
    assert audit["checks"]["provider_failure_treated_as_authority_violation"] is False

    contaminated = {
        "results": [
            {
                "case_id": "bad-authority",
                "ok": False,
                "failure_class": "authority_contract",
                "authority_effect": "verified",
                "automatic_execution": True,
                "physical_authority_unchanged": False,
                "authority_failures": ["power_on_authorized"],
            }
        ]
    }
    blocked = audit_cleanroom_replay_truth(contaminated)
    assert blocked["status"] == "blocked"
    codes = {row["code"] for row in blocked["violations"]}
    assert "CLEANROOM_HARD_CONTRACT_FAILURE" in codes
    assert "CLEANROOM_AUTHORITY_EFFECT" in codes
    assert "CLEANROOM_AUTOMATIC_EXECUTION" in codes
    assert "CLEANROOM_PHYSICAL_AUTHORITY_CHANGED" in codes


def test_extended_deterministic_probe_keeps_original_discrimination_bars() -> None:
    result = run_extended_deterministic_dut_experiment()

    assert result["pass"] is True
    assert result["checks"]["compliant_equivalence_stable"] is True
    assert result["checks"]["compliant_truth_audit_pass"] is True
    assert result["checks"]["label_sensitivity_detected_as_script_brain"] is True
    assert result["checks"]["invented_evidence_detected"] is True
    assert result["checks"]["forced_guess_detected"] is True
    assert result["checks"]["deterministic_tool_failure_in_corpus"] is True
    assert result["checks"]["plausible_wrong_analogy_in_corpus"] is True
    assert result["checks"]["stale_revision_evidence_in_corpus"] is True

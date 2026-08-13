from __future__ import annotations

from hardware_splicer.cleanroom_unseen_spi_flash_experiment import (
    build_unseen_spi_flash_cases,
    spi_flash_adapter_snapshot,
    validate_unseen_spi_flash_corpus,
)


def _source(snapshot: dict, source_id: str) -> dict:
    return next(row for row in snapshot["engineeringSources"] if row["source_id"] == source_id)


def test_unseen_spi_flash_baseline_preserves_identity_and_electrical_unknowns() -> None:
    snapshot = spi_flash_adapter_snapshot()
    dut = _source(snapshot, "src-dut")
    facts = dut["metadata"]["facts"]

    assert facts["part_family"] == "W25Q128JW"
    assert facts["vcc_min_v"] == 1.7
    assert facts["vcc_max_v"] == 1.95
    assert facts["exact_orderable_suffix_resolved"] is False
    assert facts["io_absolute_max_verified"] is False
    assert snapshot["engineering_readiness"]["fabrication_ready"] is False
    assert snapshot["engineering_readiness"]["power_on_ready"] is False


def test_unseen_spi_flash_equivalence_variants_preserve_evidence_identity() -> None:
    cases = build_unseen_spi_flash_cases()
    baseline = next(case for case in cases if case.perturbation_kind == "baseline")
    equivalent = [case for case in cases if case.equivalence_group == baseline.equivalence_group]

    def identity(case) -> list[tuple[str, str, str]]:
        return sorted(
            (
                row["source_id"],
                row["content_hash"],
                str(row["revision"]),
            )
            for row in case.snapshot["engineeringSources"]
        )

    baseline_identity = identity(baseline)
    assert len(equivalent) >= 4
    assert all(identity(case) == baseline_identity for case in equivalent)


def test_unseen_spi_flash_challenges_cover_identity_tool_analogy_and_revision() -> None:
    cases = build_unseen_spi_flash_cases()
    challenge_kinds = {
        case.perturbation_kind for case in cases if case.equivalence_group is None
    }

    assert {
        "partial_evidence",
        "conflicting_component_identity",
        "deterministic_tool_failure",
        "plausible_wrong_analogy",
        "stale_revision_evidence",
    }.issubset(challenge_kinds)

    conflict_case = next(
        case for case in cases if case.perturbation_kind == "conflicting_component_identity"
    )
    identity_conflict = next(
        row
        for row in conflict_case.snapshot["engineeringSourceConflicts"]
        if row["field"] == "candidate_part_identity"
    )
    assert identity_conflict["status"] == "unresolved"

    stale_case = next(case for case in cases if case.perturbation_kind == "stale_revision_evidence")
    stale = _source(dict(stale_case.snapshot), "src-dut-rev-jv")
    assert stale["authority_ceiling"] == "advisory"
    assert stale["metadata"]["lifecycle_status"] == "superseded"
    assert stale["metadata"]["superseded_by_source_id"] == "src-dut"


def test_unseen_spi_flash_corpus_validation_passes_without_golden_answer() -> None:
    report = validate_unseen_spi_flash_corpus()

    assert report["pass"] is True
    assert report["case_count"] >= 9
    assert report["checks"]["no_golden_architecture_declared"] is True
    assert report["checks"]["io_abs_max_remains_unverified"] is True
    assert report["checks"]["physical_authority_closed"] is True

from __future__ import annotations

from hardware_splicer.physical_evidence import (
    AuthorizationDecision,
    AuthorizationScope,
    PhysicalOperation,
)
from hardware_splicer.physical_evidence_ledger import (
    build_authorization_ledger_entry,
    validate_authorization_ledger,
)


def _decision(*, authorization_id: str, status: str, reviewed_at: str):
    return AuthorizationDecision(
        authorization_id=authorization_id,
        status=status,
        scope=AuthorizationScope(
            scope_id="scope-r1",
            project_id="chronology",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["chronology"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0},
            required_evidence_kinds=[],
        ),
        reviewer="reviewer",
        reviewed_at=reviewed_at,
        evidence_ids=[],
        reason="Chronology test decision.",
    )


def _first():
    return build_authorization_ledger_entry(
        entry_id="entry-1",
        decision=_decision(
            authorization_id="auth-1",
            status="authorized",
            reviewed_at="2026-08-04T01:00:00+00:00",
        ),
        recorded_at="2026-08-04T01:05:00+00:00",
        recorded_by="release-clerk",
    )


def test_chronologically_ordered_chain_remains_valid() -> None:
    first = _first()
    second = build_authorization_ledger_entry(
        entry_id="entry-2",
        decision=_decision(
            authorization_id="auth-2",
            status="revoked",
            reviewed_at="2026-08-04T02:00:00+00:00",
        ),
        recorded_at="2026-08-04T02:05:00+00:00",
        recorded_by="release-clerk",
        previous_entry_hash=first.entry_hash,
    )

    report = validate_authorization_ledger(
        [first, second],
        project_id="chronology",
        candidate_revision="r1",
        scope_id="scope-r1",
        as_of="2026-08-04T03:00:00+00:00",
    )

    assert report.valid is True
    assert report.metadata["chronological_order_required"] is True
    assert report.metadata["review_precedes_recording_required"] is True


def test_backdated_append_is_rejected_even_with_valid_hash_chain() -> None:
    first = _first()
    second = build_authorization_ledger_entry(
        entry_id="entry-2",
        decision=_decision(
            authorization_id="auth-2",
            status="revoked",
            reviewed_at="2026-08-04T00:30:00+00:00",
        ),
        recorded_at="2026-08-04T00:35:00+00:00",
        recorded_by="release-clerk",
        previous_entry_hash=first.entry_hash,
    )

    report = validate_authorization_ledger(
        [first, second],
        project_id="chronology",
        candidate_revision="r1",
        as_of="2026-08-04T03:00:00+00:00",
    )

    assert report.valid is False
    assert any("recorded before the prior entry" in row for row in report.blockers)


def test_entry_recorded_before_review_is_rejected() -> None:
    entry = build_authorization_ledger_entry(
        entry_id="entry-1",
        decision=_decision(
            authorization_id="auth-1",
            status="authorized",
            reviewed_at="2026-08-04T02:00:00+00:00",
        ),
        recorded_at="2026-08-04T01:55:00+00:00",
        recorded_by="release-clerk",
    )

    report = validate_authorization_ledger(
        [entry],
        project_id="chronology",
        candidate_revision="r1",
        as_of="2026-08-04T03:00:00+00:00",
    )

    assert report.valid is False
    assert any("before its human review time" in row for row in report.blockers)

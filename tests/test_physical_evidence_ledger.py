from __future__ import annotations

from datetime import datetime, timezone

from hardware_splicer.physical_evidence import (
    AuthorizationDecision,
    AuthorizationScope,
    AuthorizationStatus,
    PhysicalEvidenceKind,
    PhysicalEvidenceRecord,
    PhysicalOperation,
)
from hardware_splicer.physical_evidence_ledger import (
    build_authorization_ledger_entry,
    build_physical_evidence_envelope,
    validate_authorization_ledger,
    validate_physical_evidence_envelope,
)


AS_OF = datetime(2026, 8, 4, 4, 0, tzinfo=timezone.utc)


def _record() -> PhysicalEvidenceRecord:
    return PhysicalEvidenceRecord(
        evidence_id="thermal-run",
        project_id="ledger-project",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.THERMAL,
        target_ids=["controller"],
        procedure_id="thermal-soak",
        passed=True,
        captured_at="2026-08-04T02:00:00+00:00",
        operator="operator",
        measured_values={"maximum_temperature_c": 54.2},
        acceptance_criteria={"maximum_temperature_c": {"maximum": 70}},
        artifact_hashes={"release": "sha256:r1"},
        raw_refs=["lab://thermal/run-1.csv"],
    )


def _decision(
    status: AuthorizationStatus = AuthorizationStatus.AUTHORIZED,
    *,
    revision: str = "r1",
    authorization_id: str = "auth-r1",
) -> AuthorizationDecision:
    kwargs = {}
    if status == AuthorizationStatus.REVOKED:
        kwargs = {
            "revoked_at": "2026-08-04T03:30:00+00:00",
            "revocation_reason": "A later inspection found a damaged connector.",
        }
    return AuthorizationDecision(
        authorization_id=authorization_id,
        status=status,
        scope=AuthorizationScope(
            scope_id="scope-r1",
            project_id="ledger-project",
            candidate_revision=revision,
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["controller"],
            artifact_hashes={"release": f"sha256:{revision}"},
            operating_envelope={"maximum_voltage_v": 5.0},
            required_evidence_kinds=[PhysicalEvidenceKind.THERMAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T03:00:00+00:00",
        evidence_ids=["thermal-run"],
        reason=f"Decision status is {status.value}.",
        expires_at="2026-09-01T00:00:00+00:00",
        **kwargs,
    )


def test_physical_evidence_envelope_detects_content_tampering() -> None:
    envelope = build_physical_evidence_envelope(
        envelope_id="envelope-thermal-run",
        record=_record(),
        raw_files=[
            {
                "ref": "lab://thermal/run-1.csv",
                "content_hash": f"sha256:{'a' * 64}",
                "media_type": "text/csv",
                "size_bytes": 2048,
            }
        ],
        created_at="2026-08-04T02:05:00+00:00",
        created_by="operator",
    )

    assert validate_physical_evidence_envelope(envelope) == []

    tampered = envelope.model_dump(mode="json")
    tampered["record"]["measured_values"]["maximum_temperature_c"] = 92.0
    blockers = validate_physical_evidence_envelope(tampered)

    assert blockers == [
        "Physical evidence envelope envelope-thermal-run hash does not match its content."
    ]


def test_evidence_envelope_requires_every_declared_raw_reference() -> None:
    envelope = build_physical_evidence_envelope(
        envelope_id="envelope-missing-raw",
        record=_record(),
        raw_files=[
            {
                "ref": "lab://thermal/other.csv",
                "content_hash": f"sha256:{'b' * 64}",
            }
        ],
        created_at="2026-08-04T02:05:00+00:00",
        created_by="operator",
    )

    blockers = validate_physical_evidence_envelope(envelope)

    assert blockers == [
        "Physical evidence envelope envelope-missing-raw omits declared raw refs: lab://thermal/run-1.csv."
    ]


def test_authorization_ledger_chain_selects_latest_applicable_decision() -> None:
    authorized = build_authorization_ledger_entry(
        entry_id="entry-authorized",
        decision=_decision(),
        recorded_at="2026-08-04T03:05:00+00:00",
        recorded_by="release-clerk",
    )

    assessment = validate_authorization_ledger(
        [authorized],
        project_id="ledger-project",
        candidate_revision="r1",
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert assessment.valid is True
    assert assessment.applicable_authorization_id == "auth-r1"
    assert assessment.applicable_scope_id == "scope-r1"
    assert assessment.latest_entry_hash == authorized.entry_hash
    assert assessment.metadata["automatic_authorization"] is False


def test_later_revocation_removes_applicable_authorization() -> None:
    authorized = build_authorization_ledger_entry(
        entry_id="entry-authorized",
        decision=_decision(),
        recorded_at="2026-08-04T03:05:00+00:00",
        recorded_by="release-clerk",
    )
    revoked = build_authorization_ledger_entry(
        entry_id="entry-revoked",
        decision=_decision(
            AuthorizationStatus.REVOKED,
            authorization_id="auth-r1-revocation",
        ),
        recorded_at="2026-08-04T03:35:00+00:00",
        recorded_by="release-clerk",
        previous_entry_hash=authorized.entry_hash,
    )

    assessment = validate_authorization_ledger(
        [authorized, revoked],
        project_id="ledger-project",
        candidate_revision="r1",
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert assessment.valid is True
    assert assessment.applicable_authorization_id is None
    assert assessment.warnings == [
        "No current authorization applies to ledger-project revision r1."
    ]


def test_broken_hash_chain_and_cross_revision_are_not_accepted() -> None:
    authorized = build_authorization_ledger_entry(
        entry_id="entry-authorized",
        decision=_decision(),
        recorded_at="2026-08-04T03:05:00+00:00",
        recorded_by="release-clerk",
    )
    bad = build_authorization_ledger_entry(
        entry_id="entry-bad-chain",
        decision=_decision(authorization_id="auth-r1-second"),
        recorded_at="2026-08-04T03:10:00+00:00",
        recorded_by="release-clerk",
        previous_entry_hash=f"sha256:{'0' * 64}",
    )

    broken = validate_authorization_ledger(
        [authorized, bad],
        project_id="ledger-project",
        candidate_revision="r1",
        as_of=AS_OF,
    )
    cross_revision = validate_authorization_ledger(
        [authorized],
        project_id="ledger-project",
        candidate_revision="r2",
        as_of=AS_OF,
    )

    assert broken.valid is False
    assert any("does not chain" in row for row in broken.blockers)
    assert cross_revision.valid is True
    assert cross_revision.applicable_authorization_id is None
    assert cross_revision.warnings == [
        "No current authorization applies to ledger-project revision r2."
    ]

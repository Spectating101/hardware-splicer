from __future__ import annotations

from datetime import datetime, timezone

from hardware_splicer.audited_physical_evidence import (
    assess_audited_physical_authorization,
)
from hardware_splicer.physical_evidence import (
    AuthorizationDecision,
    AuthorizationScope,
    PhysicalEvidenceKind,
    PhysicalEvidenceRecord,
    PhysicalOperation,
)
from hardware_splicer.physical_evidence_ledger import (
    build_authorization_ledger_entry,
    build_physical_evidence_envelope,
)


AS_OF = datetime(2026, 8, 4, 4, 0, tzinfo=timezone.utc)


def _plan() -> dict:
    return {
        "candidate_revision": "r1",
        "machine_project": {
            "project_id": "audited-project",
            "artifacts": [
                {
                    "artifact_id": "release",
                    "kind": "release_bundle",
                    "ref": "release/r1.zip",
                    "authority": "declared",
                    "metadata": {"content_hash": "sha256:r1"},
                }
            ],
        },
    }


def _record() -> PhysicalEvidenceRecord:
    return PhysicalEvidenceRecord(
        evidence_id="rail-test",
        project_id="audited-project",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["audited-project"],
        procedure_id="power-test",
        passed=True,
        captured_at="2026-08-04T02:00:00+00:00",
        operator="operator",
        measured_values={"minimum_voltage_v": 4.91},
        acceptance_criteria={"minimum_voltage_v": {"minimum": 4.75}},
        instrument_ids=["dmm"],
        calibration_ids=["cal-dmm"],
        artifact_hashes={"release": "sha256:r1"},
        raw_refs=["lab://rail/run.csv"],
    )


def _decision(evidence_ids: list[str] | None = None) -> AuthorizationDecision:
    return AuthorizationDecision(
        authorization_id="auth-r1",
        status="authorized",
        scope=AuthorizationScope(
            scope_id="scope-r1",
            project_id="audited-project",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["audited-project"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0, "current_limited": True},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=evidence_ids or ["rail-test"],
        reason="Current-limited bench power is supported by the attached evidence.",
        expires_at="2026-09-01T00:00:00+00:00",
    )


def _calibrations() -> list[dict]:
    return [
        {
            "calibration_id": "cal-dmm",
            "instrument_id": "dmm",
            "calibrated_at": "2026-07-01T00:00:00+00:00",
            "expires_at": "2027-01-01T00:00:00+00:00",
        }
    ]


def _envelope():
    return build_physical_evidence_envelope(
        envelope_id="envelope-rail",
        record=_record(),
        raw_files=[
            {
                "ref": "lab://rail/run.csv",
                "content_hash": f"sha256:{'a' * 64}",
                "media_type": "text/csv",
            }
        ],
        created_at="2026-08-04T02:05:00+00:00",
        created_by="operator",
    )


def _ledger(decision: AuthorizationDecision | None = None):
    return [
        build_authorization_ledger_entry(
            entry_id="entry-auth-r1",
            decision=decision or _decision(),
            recorded_at="2026-08-04T02:35:00+00:00",
            recorded_by="release-clerk",
        )
    ]


def test_valid_envelope_and_ledger_produce_audited_applicable_scope() -> None:
    package = assess_audited_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        envelopes=[_envelope()],
        ledger_entries=_ledger(),
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert package.applicable is True
    assert package.blockers == []
    assert package.physical_package.assessment.applicable is True
    assert package.physical_package.assessment.authorized_operations == [
        PhysicalOperation.BENCH_POWER
    ]
    assert package.ledger_assessment.applicable_authorization_id == "auth-r1"
    assert package.metadata["automatic_authorization"] is False


def test_tampered_envelope_removes_all_authorized_operations() -> None:
    tampered = _envelope().model_dump(mode="json")
    tampered["record"]["measured_values"]["minimum_voltage_v"] = 3.2

    package = assess_audited_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        envelopes=[tampered],
        ledger_entries=_ledger(),
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert package.applicable is False
    assert package.physical_package.assessment.authorized_operations == []
    assert any("hash does not match" in row for row in package.blockers)


def test_decision_referencing_unenveloped_evidence_is_blocked() -> None:
    decision = _decision(["rail-test", "missing-load-test"])

    package = assess_audited_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        envelopes=[_envelope()],
        ledger_entries=_ledger(decision),
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert package.applicable is False
    rendered = "\n".join(package.blockers)
    assert "Authorization references unavailable evidence: missing-load-test" in rendered
    assert "lacks hashed evidence envelopes for: missing-load-test" in rendered


def test_broken_ledger_chain_blocks_otherwise_valid_evidence() -> None:
    first = _ledger()[0]
    second = build_authorization_ledger_entry(
        entry_id="entry-bad-chain",
        decision=_decision(),
        recorded_at="2026-08-04T02:40:00+00:00",
        recorded_by="release-clerk",
        previous_entry_hash=f"sha256:{'0' * 64}",
    )

    package = assess_audited_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        envelopes=[_envelope()],
        ledger_entries=[first, second],
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert package.applicable is False
    assert package.ledger_assessment.valid is False
    assert any("does not chain" in row for row in package.blockers)

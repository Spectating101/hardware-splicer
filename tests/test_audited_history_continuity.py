from __future__ import annotations

from datetime import datetime

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


AS_OF = datetime.fromisoformat("2026-08-04T04:00:00+00:00")


def _plan() -> dict:
    return {
        "candidate_revision": "r1",
        "machine_project": {
            "project_id": "history-project",
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


def _calibrations() -> list[dict]:
    return [
        {
            "calibration_id": "cal-dmm",
            "instrument_id": "dmm",
            "calibrated_at": "2026-07-01T00:00:00+00:00",
            "expires_at": "2027-01-01T00:00:00+00:00",
            "authority": "verified",
        }
    ]


def _record(*, voltage: float = 4.91) -> PhysicalEvidenceRecord:
    return PhysicalEvidenceRecord(
        evidence_id="rail-test",
        project_id="history-project",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["history-project"],
        procedure_id="power-test",
        passed=True,
        captured_at="2026-08-04T02:00:00+00:00",
        operator="operator",
        measured_values={"minimum_voltage_v": voltage},
        acceptance_criteria={"minimum_voltage_v": {"minimum": 4.75}},
        instrument_ids=["dmm"],
        calibration_ids=["cal-dmm"],
        artifact_hashes={"release": "sha256:r1"},
        raw_refs=["lab://rail.csv"],
    )


def _decision(*, status: str = "authorized", reason: str = "Bench power supported") -> AuthorizationDecision:
    return AuthorizationDecision(
        authorization_id="auth-r1",
        status=status,
        scope=AuthorizationScope(
            scope_id="scope-r1",
            project_id="history-project",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["history-project"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0, "current_limited": True},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=["rail-test"],
        reason=reason,
        expires_at="2026-09-01T00:00:00+00:00",
    )


def _envelope(*, voltage: float = 4.91):
    return build_physical_evidence_envelope(
        envelope_id="env-rail",
        record=_record(voltage=voltage),
        raw_files=[
            {
                "ref": "lab://rail.csv",
                "content_hash": f"sha256:{'a' * 64}",
                "media_type": "text/csv",
            }
        ],
        created_at="2026-08-04T02:05:00+00:00",
        created_by="operator",
    )


def _entry(*, status: str = "authorized", reason: str = "Bench power supported"):
    return build_authorization_ledger_entry(
        entry_id="entry-auth",
        decision=_decision(status=status, reason=reason),
        recorded_at="2026-08-04T02:35:00+00:00",
        recorded_by="release-clerk",
    )


def _initial():
    plan = _plan()
    package = assess_audited_physical_authorization(
        plan,
        calibrations=_calibrations(),
        envelopes=[_envelope()],
        ledger_entries=[_entry()],
        scope_id="scope-r1",
        as_of=AS_OF,
    )
    assert package.applicable is True
    persisted = dict(plan)
    persisted["audited_physical_evidence"] = package.model_dump(mode="json")
    return persisted, package


def test_identical_persisted_history_can_be_reassessed() -> None:
    plan, initial = _initial()
    reassessed = assess_audited_physical_authorization(
        plan,
        calibrations=_calibrations(),
        envelopes=initial.envelopes,
        ledger_entries=initial.ledger_entries,
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert reassessed.applicable is True
    assert reassessed.metadata["history_continuity_valid"] is True
    assert reassessed.metadata["prior_envelope_count"] == 1
    assert reassessed.metadata["prior_ledger_entry_count"] == 1


def test_rehashed_old_envelope_is_rejected_as_history_rewrite() -> None:
    plan, initial = _initial()
    rewritten = _envelope(voltage=4.88)
    assert rewritten.envelope_hash != initial.envelopes[0].envelope_hash

    assessed = assess_audited_physical_authorization(
        plan,
        calibrations=_calibrations(),
        envelopes=[rewritten],
        ledger_entries=initial.ledger_entries,
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert assessed.applicable is False
    assert assessed.metadata["history_continuity_valid"] is False
    assert any("envelope env-rail was rewritten" in row for row in assessed.blockers)


def test_rehashed_old_ledger_entry_is_rejected_as_prefix_rewrite() -> None:
    plan, initial = _initial()
    rewritten = _entry(reason="Changed historical rationale")
    assert rewritten.entry_hash != initial.ledger_entries[0].entry_hash

    assessed = assess_audited_physical_authorization(
        plan,
        calibrations=_calibrations(),
        envelopes=initial.envelopes,
        ledger_entries=[rewritten],
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert assessed.applicable is False
    assert assessed.metadata["history_continuity_valid"] is False
    assert any("persisted prefix" in row for row in assessed.blockers)


def test_revocation_is_accepted_only_as_new_chained_entry() -> None:
    plan, initial = _initial()
    revocation = build_authorization_ledger_entry(
        entry_id="entry-revoke",
        decision=_decision(status="revoked", reason="Bench authorization withdrawn"),
        recorded_at="2026-08-04T03:30:00+00:00",
        recorded_by="release-clerk",
        previous_entry_hash=initial.ledger_entries[-1].entry_hash,
    )

    assessed = assess_audited_physical_authorization(
        plan,
        calibrations=_calibrations(),
        envelopes=initial.envelopes,
        ledger_entries=[*initial.ledger_entries, revocation],
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert assessed.ledger_assessment.valid is True
    assert assessed.metadata["history_continuity_valid"] is True
    assert assessed.ledger_assessment.latest_entry_id == "entry-revoke"
    assert assessed.applicable is False
    assert assessed.physical_package.assessment.authorized_operations == []

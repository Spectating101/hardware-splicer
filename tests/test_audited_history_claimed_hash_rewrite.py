from __future__ import annotations

from datetime import datetime

from hardware_splicer.audited_physical_evidence import assess_audited_physical_authorization
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
            "project_id": "claimed-hash",
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
        project_id="claimed-hash",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["claimed-hash"],
        procedure_id="power-test",
        passed=True,
        captured_at="2026-08-04T02:00:00+00:00",
        operator="operator",
        measured_values={"minimum_voltage_v": 4.91},
        acceptance_criteria={"minimum_voltage_v": {"minimum": 4.75}},
        instrument_ids=["dmm"],
        calibration_ids=["cal-dmm"],
        artifact_hashes={"release": "sha256:r1"},
        raw_refs=["lab://rail.csv"],
    )


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        authorization_id="auth-r1",
        status="authorized",
        scope=AuthorizationScope(
            scope_id="scope-r1",
            project_id="claimed-hash",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["claimed-hash"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=["rail-test"],
        reason="Original retained decision.",
        expires_at="2026-09-01T00:00:00+00:00",
    )


def _initial():
    envelope = build_physical_evidence_envelope(
        envelope_id="env-rail",
        record=_record(),
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
    entry = build_authorization_ledger_entry(
        entry_id="entry-auth",
        decision=_decision(),
        recorded_at="2026-08-04T02:35:00+00:00",
        recorded_by="release-clerk",
    )
    calibrations = [
        {
            "calibration_id": "cal-dmm",
            "instrument_id": "dmm",
            "calibrated_at": "2026-07-01T00:00:00+00:00",
            "expires_at": "2027-01-01T00:00:00+00:00",
            "authority": "verified",
        }
    ]
    initial = assess_audited_physical_authorization(
        _plan(),
        calibrations=calibrations,
        envelopes=[envelope],
        ledger_entries=[entry],
        scope_id="scope-r1",
        as_of=AS_OF,
    )
    assert initial.applicable is True
    persisted = _plan()
    persisted["audited_physical_evidence"] = initial.model_dump(mode="json")
    return persisted, initial, calibrations


def test_changed_envelope_content_with_old_hash_label_is_history_rewrite() -> None:
    plan, initial, calibrations = _initial()
    tampered = initial.envelopes[0].model_dump(mode="json")
    original_hash = tampered["envelope_hash"]
    tampered["record"]["measured_values"] = {"minimum_voltage_v": 3.2}
    assert tampered["envelope_hash"] == original_hash

    assessed = assess_audited_physical_authorization(
        plan,
        calibrations=calibrations,
        envelopes=[tampered],
        ledger_entries=initial.ledger_entries,
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert assessed.applicable is False
    assert assessed.metadata["history_continuity_valid"] is False
    assert any("envelope env-rail was rewritten" in row for row in assessed.blockers)


def test_changed_ledger_content_with_old_hash_label_is_prefix_rewrite() -> None:
    plan, initial, calibrations = _initial()
    tampered = initial.ledger_entries[0].model_dump(mode="json")
    original_hash = tampered["entry_hash"]
    tampered["decision"]["reason"] = "Rewritten historical rationale."
    assert tampered["entry_hash"] == original_hash

    assessed = assess_audited_physical_authorization(
        plan,
        calibrations=calibrations,
        envelopes=initial.envelopes,
        ledger_entries=[tampered],
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert assessed.applicable is False
    assert assessed.metadata["history_continuity_valid"] is False
    assert any("persisted prefix" in row for row in assessed.blockers)

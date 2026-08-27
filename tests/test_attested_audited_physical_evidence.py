from __future__ import annotations

import base64
from datetime import datetime

from hardware_splicer.attested_audited_physical_evidence import (
    assess_attested_audited_physical_authorization,
)
from hardware_splicer.physical_evidence import (
    AuthorizationDecision,
    AuthorizationScope,
    PhysicalEvidenceKind,
    PhysicalEvidenceRecord,
    PhysicalOperation,
)
from hardware_splicer.physical_evidence_attestation import attest_raw_evidence_bytes
from hardware_splicer.physical_evidence_ledger import (
    build_authorization_ledger_entry,
    build_physical_evidence_envelope,
)


KEY = "p" * 48
AS_OF = datetime.fromisoformat("2026-08-04T04:00:00+00:00")


def _plan() -> dict:
    return {
        "candidate_revision": "r1",
        "machine_project": {
            "project_id": "attested-audit",
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
        project_id="attested-audit",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["attested-audit"],
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
            project_id="attested-audit",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["attested-audit"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0, "current_limited": True},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=["rail-test"],
        reason="Attested current-limited bench evidence supports this scope.",
        expires_at="2026-09-01T00:00:00+00:00",
    )


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


def _ledger():
    return build_authorization_ledger_entry(
        entry_id="entry-auth-r1",
        decision=_decision(),
        recorded_at="2026-08-04T02:35:00+00:00",
        recorded_by="release-clerk",
    )


def _attested_file():
    return attest_raw_evidence_bytes(
        {
            "ref": "lab://rail.csv",
            "content_base64": base64.b64encode(
                b"time_s,voltage_v\n0.0,4.91\n"
            ).decode("ascii"),
            "media_type": "text/csv",
        },
        issued_at=datetime.fromisoformat("2026-08-04T02:01:00+00:00"),
        attestation_id="attestation-rail",
    ).file_ref


def _envelope(file_ref):
    return build_physical_evidence_envelope(
        envelope_id="envelope-rail",
        record=_record(),
        raw_files=[file_ref],
        created_at="2026-08-04T02:05:00+00:00",
        created_by="operator",
    )


def test_attested_raw_file_allows_strict_audit(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "lab-key")
    package = assess_attested_audited_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        envelopes=[_envelope(_attested_file())],
        ledger_entries=[_ledger()],
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert package.applicable is True
    assert package.blockers == []
    assert package.metadata["server_attestation_required"] is True
    assert package.metadata["server_attestation_valid"] is True
    assert package.metadata["attested_raw_file_count"] == 1
    assert package.physical_package.assessment.authorized_operations == [
        PhysicalOperation.BENCH_POWER
    ]


def test_rebuilt_hash_valid_envelope_with_unsigned_file_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "lab-key")
    attested = _attested_file()
    metadata = dict(attested.metadata)
    metadata.pop("server_attestation")
    unsigned = attested.model_copy(update={"metadata": metadata}, deep=True)
    rebuilt = _envelope(unsigned)

    package = assess_attested_audited_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        envelopes=[rebuilt],
        ledger_entries=[_ledger()],
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert package.applicable is False
    assert package.metadata["server_attestation_valid"] is False
    assert package.physical_package.assessment.authorized_operations == []
    assert any("lacks a server attestation" in row for row in package.blockers)


def test_rebuilt_envelope_with_attested_file_metadata_change_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "lab-key")
    attested = _attested_file()
    changed = attested.model_copy(update={"media_type": "application/json"}, deep=True)
    rebuilt = _envelope(changed)

    package = assess_attested_audited_physical_authorization(
        _plan(),
        calibrations=_calibrations(),
        envelopes=[rebuilt],
        ledger_entries=[_ledger()],
        scope_id="scope-r1",
        as_of=AS_OF,
    )

    assert package.applicable is False
    assert package.metadata["server_attestation_valid"] is False
    assert any("signature is invalid" in row for row in package.blockers)

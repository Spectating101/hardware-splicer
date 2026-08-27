from __future__ import annotations

import base64
import copy

from hardware_splicer.physical_evidence_attestation import (
    attest_raw_evidence_bytes,
    verify_evidence_file_attestation,
)


KEY = "l" * 48


def _attested(monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "literal-key")
    return attest_raw_evidence_bytes(
        {
            "ref": "lab://literal.csv",
            "content_base64": base64.b64encode(b"value\n1\n").decode("ascii"),
            "media_type": "text/csv",
        }
    ).file_ref.model_dump(mode="json")


def _tamper(file_ref: dict, field: str, value):
    result = copy.deepcopy(file_ref)
    result["metadata"]["server_attestation"][field] = value
    return result


def test_algorithm_field_cannot_be_relabelled(monkeypatch) -> None:
    blockers = verify_evidence_file_attestation(
        _tamper(_attested(monkeypatch), "algorithm", "none")
    )
    assert any("invalid server attestation" in row for row in blockers)


def test_schema_field_cannot_be_relabelled(monkeypatch) -> None:
    blockers = verify_evidence_file_attestation(
        _tamper(
            _attested(monkeypatch),
            "schema_version",
            "hardware_splicer.evidence_file_attestation.v999",
        )
    )
    assert any("invalid server attestation" in row for row in blockers)


def test_retention_and_observation_claims_are_literal(monkeypatch) -> None:
    retained = verify_evidence_file_attestation(
        _tamper(_attested(monkeypatch), "bytes_retained", True)
    )
    unobserved = verify_evidence_file_attestation(
        _tamper(_attested(monkeypatch), "bytes_observed", False)
    )

    assert any("invalid server attestation" in row for row in retained)
    assert any("invalid server attestation" in row for row in unobserved)

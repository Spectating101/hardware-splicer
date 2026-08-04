from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


KEY = "a" * 48


def _plan() -> dict:
    return {
        "candidate_revision": "r1",
        "machine_project": {
            "project_id": "attested-api",
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


def _record() -> dict:
    return {
        "evidence_id": "rail-test",
        "project_id": "attested-api",
        "candidate_revision": "r1",
        "kind": "electrical_measurement",
        "target_ids": ["attested-api"],
        "procedure_id": "power-test",
        "passed": True,
        "captured_at": "2026-08-04T02:00:00+00:00",
        "operator": "operator",
        "measured_values": {"minimum_voltage_v": 4.91},
        "acceptance_criteria": {"minimum_voltage_v": {"minimum": 4.75}},
        "instrument_ids": ["dmm"],
        "calibration_ids": ["cal-dmm"],
        "artifact_hashes": {"release": "sha256:r1"},
        "raw_refs": ["lab://rail.csv"],
    }


def _decision() -> dict:
    return {
        "authorization_id": "auth-r1",
        "status": "authorized",
        "scope": {
            "scope_id": "scope-r1",
            "project_id": "attested-api",
            "candidate_revision": "r1",
            "operations": ["bench_power"],
            "target_ids": ["attested-api"],
            "artifact_hashes": {"release": "sha256:r1"},
            "operating_envelope": {"maximum_voltage_v": 5.0, "current_limited": True},
            "required_evidence_kinds": ["electrical_measurement"],
        },
        "reviewer": "reviewer",
        "reviewed_at": "2026-08-04T02:30:00+00:00",
        "evidence_ids": ["rail-test"],
        "reason": "Attested current-limited evidence supports this scope.",
        "expires_at": "2026-09-01T00:00:00+00:00",
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


def test_canonical_app_mounts_attested_physical_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/physical-evidence/attested/schema" in paths
    assert "/v1/engineering/physical-evidence/envelopes/build-attested" in paths
    assert "/v1/engineering/physical-evidence/attested-audited-assess" in paths
    assert "/v1/engineering/physical-evidence/attested-audited-release-assess" in paths


def test_attested_envelope_build_and_strict_audit(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "lab-key")
    client = TestClient(create_product_app())
    raw_base64 = base64.b64encode(
        b"time_s,voltage_v\n0.0,4.91\n"
    ).decode("ascii")

    built = client.post(
        "/v1/engineering/physical-evidence/envelopes/build-attested",
        json={
            "envelope_id": "envelope-rail",
            "record": _record(),
            "raw_files": [
                {
                    "ref": "lab://rail.csv",
                    "content_base64": raw_base64,
                    "media_type": "text/csv",
                }
            ],
            "created_at": "2026-08-04T02:05:00+00:00",
            "created_by": "operator",
        },
    )
    assert built.status_code == 200, built.text
    built_body = built.json()
    envelope = built_body["evidence_envelope"]
    assert built_body["server_attested"] is True
    assert built_body["raw_bytes_persisted"] is False
    assert raw_base64 not in built.text
    assert envelope["raw_files"][0]["metadata"]["server_attestation"]["key_id"] == "lab-key"

    ledger = client.post(
        "/v1/engineering/physical-evidence/ledger/build-entry",
        json={
            "entry_id": "entry-auth-r1",
            "decision": _decision(),
            "recorded_at": "2026-08-04T02:35:00+00:00",
            "recorded_by": "release-clerk",
        },
    )
    assert ledger.status_code == 200, ledger.text

    assessed = client.post(
        "/v1/engineering/physical-evidence/attested-audited-assess",
        json={
            "plan": _plan(),
            "calibrations": _calibrations(),
            "envelopes": [envelope],
            "ledger_entries": [ledger.json()["authorization_ledger_entry"]],
            "scope_id": "scope-r1",
            "as_of": "2026-08-04T04:00:00+00:00",
        },
    )
    assert assessed.status_code == 200, assessed.text
    body = assessed.json()
    assert body["authorization_applicable"] is True
    assert body["server_attestation_valid"] is True
    assert body["authorization_ledger_valid"] is True
    assert body["attested_audited_physical_evidence"]["metadata"]["plain_hash_sufficient"] is False
    assert body["automatic_authorization"] is False


def test_strict_audit_rejects_plain_hash_envelope(monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "lab-key")
    client = TestClient(create_product_app())
    plain = client.post(
        "/v1/engineering/physical-evidence/envelopes/build",
        json={
            "envelope_id": "plain-envelope",
            "record": _record(),
            "raw_files": [
                {
                    "ref": "lab://rail.csv",
                    "content_hash": f"sha256:{'a' * 64}",
                    "media_type": "text/csv",
                }
            ],
            "created_at": "2026-08-04T02:05:00+00:00",
            "created_by": "operator",
        },
    )
    assert plain.status_code == 200, plain.text
    ledger = client.post(
        "/v1/engineering/physical-evidence/ledger/build-entry",
        json={
            "entry_id": "entry-auth-r1",
            "decision": _decision(),
            "recorded_at": "2026-08-04T02:35:00+00:00",
            "recorded_by": "release-clerk",
        },
    ).json()["authorization_ledger_entry"]

    assessed = client.post(
        "/v1/engineering/physical-evidence/attested-audited-assess",
        json={
            "plan": _plan(),
            "calibrations": _calibrations(),
            "envelopes": [plain.json()["evidence_envelope"]],
            "ledger_entries": [ledger],
            "scope_id": "scope-r1",
            "as_of": "2026-08-04T04:00:00+00:00",
        },
    )

    assert assessed.status_code == 200, assessed.text
    body = assessed.json()
    assert body["authorization_applicable"] is False
    assert body["server_attestation_valid"] is False
    assert body["attested_audited_physical_evidence"]["physical_package"]["assessment"]["authorized_operations"] == []
    assert any(
        "lacks a server attestation" in row
        for row in body["attested_audited_physical_evidence"]["blockers"]
    )

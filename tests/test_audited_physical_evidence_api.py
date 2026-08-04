from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


RAW_HASH = f"sha256:{'a' * 64}"


def _plan() -> dict:
    return {
        "candidate_revision": "r1",
        "machine_project": {
            "project_id": "audited-api",
            "name": "Audited API",
            "purpose": "Exercise audited physical evidence APIs.",
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
        "project_id": "audited-api",
        "candidate_revision": "r1",
        "kind": "electrical_measurement",
        "target_ids": ["audited-api"],
        "procedure_id": "power-test",
        "passed": True,
        "captured_at": "2026-08-04T02:00:00+00:00",
        "operator": "operator",
        "measured_values": {"minimum_voltage_v": 4.91},
        "acceptance_criteria": {"minimum_voltage_v": {"minimum": 4.75}},
        "instrument_ids": ["dmm"],
        "calibration_ids": ["cal-dmm"],
        "artifact_hashes": {"release": "sha256:r1"},
        "raw_refs": ["lab://rail/run.csv"],
    }


def _decision() -> dict:
    return {
        "authorization_id": "auth-r1",
        "status": "authorized",
        "scope": {
            "scope_id": "scope-r1",
            "project_id": "audited-api",
            "candidate_revision": "r1",
            "operations": ["bench_power"],
            "target_ids": ["audited-api"],
            "artifact_hashes": {"release": "sha256:r1"},
            "operating_envelope": {"maximum_voltage_v": 5.0, "current_limited": True},
            "required_evidence_kinds": ["electrical_measurement"],
        },
        "reviewer": "reviewer",
        "reviewed_at": "2026-08-04T02:30:00+00:00",
        "evidence_ids": ["rail-test"],
        "reason": "Current-limited bench power is supported.",
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


def test_canonical_api_mounts_audited_physical_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/physical-evidence/envelopes/build" in paths
    assert "/v1/engineering/physical-evidence/ledger/build-entry" in paths
    assert "/v1/engineering/physical-evidence/audited-assess" in paths
    assert "/v1/engineering/physical-evidence/audited-release-assess" in paths


def test_build_and_audit_workflow_validates_hashes_and_ledger() -> None:
    client = TestClient(create_product_app())
    envelope_response = client.post(
        "/v1/engineering/physical-evidence/envelopes/build",
        json={
            "envelope_id": "envelope-rail",
            "record": _record(),
            "raw_files": [
                {
                    "ref": "lab://rail/run.csv",
                    "content_hash": RAW_HASH,
                    "media_type": "text/csv",
                }
            ],
            "created_at": "2026-08-04T02:05:00+00:00",
            "created_by": "operator",
        },
    )
    assert envelope_response.status_code == 200, envelope_response.text
    envelope = envelope_response.json()["evidence_envelope"]

    entry_response = client.post(
        "/v1/engineering/physical-evidence/ledger/build-entry",
        json={
            "entry_id": "entry-auth-r1",
            "decision": _decision(),
            "recorded_at": "2026-08-04T02:35:00+00:00",
            "recorded_by": "release-clerk",
        },
    )
    assert entry_response.status_code == 200, entry_response.text
    entry = entry_response.json()["authorization_ledger_entry"]

    audited = client.post(
        "/v1/engineering/physical-evidence/audited-assess",
        json={
            "plan": _plan(),
            "calibrations": _calibrations(),
            "envelopes": [envelope],
            "ledger_entries": [entry],
            "scope_id": "scope-r1",
            "as_of": "2026-08-04T04:00:00+00:00",
        },
    )
    assert audited.status_code == 200, audited.text
    body = audited.json()
    assert body["authorization_applicable"] is True
    assert body["tamper_evident_envelopes_validated"] is True
    assert body["authorization_ledger_validated"] is True
    assert body["automatic_authorization"] is False

    tampered = dict(envelope)
    tampered["record"] = dict(envelope["record"])
    tampered["record"]["measured_values"] = {"minimum_voltage_v": 3.2}
    rejected = client.post(
        "/v1/engineering/physical-evidence/audited-assess",
        json={
            "plan": _plan(),
            "calibrations": _calibrations(),
            "envelopes": [tampered],
            "ledger_entries": [entry],
            "scope_id": "scope-r1",
            "as_of": "2026-08-04T04:00:00+00:00",
        },
    )
    assert rejected.status_code == 200, rejected.text
    rejected_body = rejected.json()
    assert rejected_body["authorization_applicable"] is False
    assert rejected_body["tamper_evident_envelopes_validated"] is False
    assert rejected_body["audited_physical_evidence"]["physical_package"]["assessment"]["authorized_operations"] == []

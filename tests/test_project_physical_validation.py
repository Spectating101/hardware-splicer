from __future__ import annotations

import base64
import hashlib

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_physical_validation import (
    build_project_physical_validation_packet,
    project_candidate_boundary,
)
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.remote_physical_validation import (
    build_remote_physical_return_template,
)


KEY = "p" * 48
CAPTURED_AT = "2026-09-13T02:00:00+00:00"


def _snapshot() -> dict:
    return {
        "name": "Bounded SPI flash adapter",
        "mission": "Validate a 3.3 V programmer to 1.8 V SPI flash adapter.",
        "engineering_status": "bounded_pre_fabrication_plan",
        "engineeringBlockers": [
            "Exact physical DUT marking and package.",
            "Exact programmer identity and levels under load.",
            "All physical measurements.",
        ],
        "preFabricationPlan": {
            "schema_version": "hardware_splicer.pre_fabrication_plan.v1",
            "requirements": [],
            "architecture_candidates": [],
            "decisions": [],
            "actions": [{"action_id": "resolve-physical", "description": "Inspect DUT."}],
            "physical_correctness": "UNPROVEN",
            "physical_authority_granted": False,
        },
    }


def _record(packet: dict, gate_id: str, *, evidence_id: str, values: dict) -> dict:
    gate = next(row for row in packet["gates"] if row["gate_id"] == gate_id)
    return {
        "evidence_id": evidence_id,
        "project_id": packet["project_id"],
        "candidate_revision": packet["candidate_revision"],
        "kind": gate["kind"],
        "target_ids": [gate_id],
        "procedure_id": gate["procedure_id"],
        "passed": True,
        "captured_at": CAPTURED_AT,
        "operator": "bench-operator",
        "measured_values": values,
        "acceptance_criteria": {"required_fields_present": True},
        "artifact_hashes": packet["artifact_hashes"],
        "raw_refs": [f"lab://{evidence_id}.jpg"],
        "metadata": {
            "simulated": False,
            "public_web": False,
            "capture_origin": "physical_test_article",
            "direct_operator_observation": True,
        },
    }


def _build_attested(client: TestClient, record: dict, *, media_type: str = "image/jpeg") -> dict:
    response = client.post(
        "/v1/engineering/physical-evidence/envelopes/build-attested",
        json={
            "envelope_id": "envelope-" + record["evidence_id"],
            "record": record,
            "raw_files": [
                {
                    "ref": record["raw_refs"][0],
                    "content_base64": base64.b64encode(b"real-capture-bytes").decode("ascii"),
                    "media_type": media_type,
                }
            ],
            "created_at": CAPTURED_AT,
            "created_by": "bench-operator",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["evidence_envelope"]


def test_packet_is_deterministic_revision_and_hash_bound() -> None:
    snapshot = _snapshot()
    first = build_project_physical_validation_packet(
        snapshot, project_id="adapter", revision=6
    )
    second = build_project_physical_validation_packet(
        snapshot, project_id="adapter", revision=6
    )

    assert first == second
    assert first["profile"] == "spi_flash_adapter"
    assert first["source_revision"] == 6
    assert first["candidate_revision"].startswith("adapter@")
    assert first["artifact_hashes"]["canonical-project-snapshot"].startswith("sha256:")
    assert first["policy"]["server_attested_raw_files_required"] is True
    assert first["policy"]["automatic_authorization"] is False
    assert "identify-dut" in first["workflow"]["first_executable_gate_ids"]
    assert next(
        row for row in first["gates"] if row["gate_id"] == "read-only-jedec-identity"
    )["safety"].startswith("Only read-only identity command 0x9F")


def test_physical_audit_appendage_does_not_change_candidate_boundary() -> None:
    snapshot = _snapshot()
    before = project_candidate_boundary(snapshot, project_id="adapter")
    snapshot["physicalValidation"] = {"envelopes": ["new-audit-row"]}
    after = project_candidate_boundary(snapshot, project_id="adapter")

    assert before == after


def test_attested_identity_capture_persists_without_granting_authority(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "bench-key")
    store = ProjectStore(tmp_path / "projects")
    store.save("adapter", _snapshot(), expected_revision=0)
    client = TestClient(create_product_app(store))
    packet_response = client.get(
        "/v1/projects/adapter/engineering/physical-validation/packet"
    )
    assert packet_response.status_code == 200, packet_response.text
    packet = packet_response.json()["physical_validation_packet"]
    record = _record(
        packet,
        "identify-dut",
        evidence_id="dut-identity",
        values={
            "observed_top_marking": "W25Q128JW",
            "observed_package": "observed-eight-pin-package",
            "observed_pin_count": 8,
            "observed_dimensions_mm": {"length": 6.0, "width": 5.0},
        },
    )
    evidence = _build_attested(client, record)

    submitted = client.post(
        "/v1/projects/adapter/engineering/physical-validation/evidence",
        json={
            "expected_revision": 1,
            "packet_id": packet["packet_id"],
            "envelopes": [evidence],
            "as_of": "2026-09-13T03:00:00+00:00",
        },
    )

    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["revision"] == 2
    assert body["server_attestation_valid"] is True
    assert body["authorization_applicable"] is False
    assert body["scoped_authorized_operations"] == []
    assert body["physical_authority_granted"] is False
    physical = store.load("adapter")["snapshot"]["physicalValidation"]
    assert physical["gate_assessment"]["passed_gate_ids"] == ["identify-dut"]
    assert physical["audited_physical_evidence"]["envelopes"][0]["record"]["operator"] == "bench-operator"


def test_powered_capture_without_prior_authorization_is_rejected(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    store = ProjectStore(tmp_path / "projects")
    store.save("adapter", _snapshot(), expected_revision=0)
    client = TestClient(create_product_app(store))
    packet = client.get(
        "/v1/projects/adapter/engineering/physical-validation/packet"
    ).json()["physical_validation_packet"]
    record = _record(
        packet,
        "current-limited-power-up",
        evidence_id="unsafe-powered-capture",
        values={
            "supply_current_limit_a": 0.05,
            "dut_vcc_min_v": 1.79,
            "dut_vcc_max_v": 1.81,
            "startup_peak_current_a": 0.01,
            "steady_state_current_a": 0.005,
            "power_off_backfeed_current_a": 0.0,
        },
    )
    record["instrument_ids"] = ["supply-1", "dmm-1"]
    record["calibration_ids"] = ["cal-supply", "cal-dmm"]
    record["raw_refs"] = ["lab://unsafe-powered-capture.csv"]
    evidence = _build_attested(client, record, media_type="text/csv")

    response = client.post(
        "/v1/projects/adapter/engineering/physical-validation/evidence",
        json={
            "expected_revision": 1,
            "packet_id": packet["packet_id"],
            "envelopes": [evidence],
        },
    )

    assert response.status_code == 422
    assert (
        "requires a previously persisted bench_power authorization"
        in response.json()["detail"]["message"]
    )
    assert store.load("adapter")["revision"] == 1


def test_engineering_change_invalidates_old_packet(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    store.save("adapter", _snapshot(), expected_revision=0)
    client = TestClient(create_product_app(store))
    packet = client.get(
        "/v1/projects/adapter/engineering/physical-validation/packet"
    ).json()["physical_validation_packet"]
    changed = _snapshot()
    changed["constraints"] = {"host_logic_voltage_v": 5.0}
    store.save("adapter", changed, expected_revision=1)

    response = client.post(
        "/v1/projects/adapter/engineering/physical-validation/evidence",
        json={
            "expected_revision": 2,
            "packet_id": packet["packet_id"],
            "envelopes": [
                {
                    "envelope_id": "unimportant",
                    "record": {
                        "evidence_id": "unimportant",
                        "project_id": "adapter",
                        "candidate_revision": packet["candidate_revision"],
                        "kind": "inspection",
                        "target_ids": ["identify-dut"],
                        "procedure_id": "hs.spi.identify-dut.v1",
                        "passed": False,
                        "captured_at": CAPTURED_AT,
                        "operator": "operator",
                        "artifact_hashes": packet["artifact_hashes"],
                        "raw_refs": ["lab://unimportant.jpg"],
                    },
                    "raw_files": [
                        {
                            "ref": "lab://unimportant.jpg",
                            "content_hash": "sha256:" + "a" * 64,
                            "media_type": "image/jpeg",
                        }
                    ],
                    "created_at": CAPTURED_AT,
                    "created_by": "operator",
                    "envelope_hash": "sha256:" + "b" * 64,
                }
            ],
        },
    )

    assert response.status_code == 409
    assert "packet is stale" in response.json()["detail"]["message"]
    assert store.load("adapter")["revision"] == 2


def test_product_and_mcp_manifest_expose_physical_validation() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])

    assert "/v1/projects/{project_id}/engineering/physical-validation/packet" in paths
    assert "/v1/projects/{project_id}/engineering/physical-validation/remote-handoff" in paths
    assert (
        "/v1/projects/{project_id}/engineering/physical-validation/remote-return/audit"
        in paths
    )
    assert "/v1/projects/{project_id}/engineering/physical-validation/evidence" in paths

    from hardware_splicer.mcp_backend_gateway import task_operation_manifest

    manifest = task_operation_manifest("physical_validation", app)
    assert manifest["authority_contract"]["projection_grants_physical_authority"] is False
    assert len(manifest["workflow_operation_ids"]) == 6


def test_remote_handoff_and_raw_return_audit_are_canonical_api_operations(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    store.save("adapter", _snapshot(), expected_revision=0)
    client = TestClient(create_product_app(store))
    prepared = client.post(
        "/v1/projects/adapter/engineering/physical-validation/remote-handoff",
        json={
            "expected_revision": 1,
            "provider": {
                "provider_id": "lab-01",
                "provider_name": "Remote Lab",
                "engagement_mode": "testing_only",
                "capabilities_requested": ["raw_exports"],
            },
        },
    )
    assert prepared.status_code == 200, prepared.text
    handoff = prepared.json()["remote_physical_handoff"]
    assert handoff["policy"]["authority_effect"] == "none"
    assert store.load("adapter")["revision"] == 1

    raw = b"direct-camera-capture"
    returned = build_remote_physical_return_template(handoff)
    returned["provider"].update(
        {"work_order_id": "WO-1", "physical_site_id": "SITE-1"}
    )
    returned["test_article"].update(
        {
            "assembly_id": "A-1",
            "assembly_revision": "A",
            "serial_numbers": ["SN-1"],
        }
    )
    returned["provider_attestation"].update(
        {
            "signed_by": "operator-1",
            "role": "test engineer",
            "signed_at": CAPTURED_AT,
        }
    )
    gate = next(
        value for value in returned["gate_results"] if value["gate_id"] == "identify-dut"
    )
    gate.update(
        {
            "status": "pass",
            "captured_at": CAPTURED_AT,
            "operator_id": "operator-1",
            "direct_operator_observation": True,
            "measured_values": {
                "observed_top_marking": "W25Q128JW",
                "observed_package": "SOP-8",
                "observed_pin_count": 8,
                "observed_dimensions_mm": {"length": 5.3, "width": 7.9},
            },
            "acceptance_criteria": {"matches_work_order": True},
            "raw_files": [
                {
                    "path": "raw/dut.jpg",
                    "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "size_bytes": len(raw),
                    "media_type": "image/jpeg",
                }
            ],
        }
    )
    audited = client.post(
        "/v1/projects/adapter/engineering/physical-validation/remote-return/audit",
        json={
            "expected_revision": 1,
            "handoff": handoff,
            "returned_manifest": returned,
            "raw_files": [
                {
                    "path": "raw/dut.jpg",
                    "content_base64": base64.b64encode(raw).decode("ascii"),
                }
            ],
        },
    )
    assert audited.status_code == 200, audited.text
    audit = audited.json()["remote_return_audit"]
    assert audit["status"] == "eligible_for_physical_evidence_import"
    assert audit["return_audit_is_physical_evidence"] is False
    assert audited.json()["physical_authority_granted"] is False
    assert store.load("adapter")["revision"] == 1


def test_remote_return_audit_rejects_altered_handoff_against_canonical_project(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    store.save("adapter", _snapshot(), expected_revision=0)
    client = TestClient(create_product_app(store))
    handoff = client.post(
        "/v1/projects/adapter/engineering/physical-validation/remote-handoff",
        json={
            "expected_revision": 1,
            "provider": {
                "provider_id": "lab-01",
                "provider_name": "Remote Lab",
                "engagement_mode": "remote_lab",
            },
        },
    ).json()["remote_physical_handoff"]
    handoff["candidate_snapshot_hash"] = "sha256:" + "0" * 64

    response = client.post(
        "/v1/projects/adapter/engineering/physical-validation/remote-return/audit",
        json={
            "expected_revision": 1,
            "handoff": handoff,
            "returned_manifest": {},
            "raw_files": [{"path": "raw/x", "content_base64": "eA=="}],
        },
    )

    assert response.status_code == 409
    assert "stale, altered" in response.json()["detail"]["message"]

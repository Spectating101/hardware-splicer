from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO

from hardware_splicer.project_physical_validation import (
    build_project_physical_validation_packet,
)
from hardware_splicer.remote_physical_validation import (
    audit_remote_physical_return,
    build_remote_physical_handoff,
    build_remote_physical_handoff_archive,
    build_remote_physical_return_template,
)


def _physical_packet() -> dict:
    return build_project_physical_validation_packet(
        {
            "name": "SPI flash adapter",
            "mission": "Validate a 3.3 V to 1.8 V SPI adapter.",
            "engineering_status": "pre_fabrication_review",
            "preFabricationPlan": {
                "physical_correctness": "UNPROVEN",
                "physical_authority_granted": False,
            },
        },
        project_id="remote-spi",
        revision=6,
    )


def _handoff() -> dict:
    return build_remote_physical_handoff(
        _physical_packet(),
        provider={
            "provider_id": "contract-lab",
            "provider_name": "Contract Lab",
            "engagement_mode": "pcba_production_and_test",
            "service_url": "https://lab.example.test/",
            "capabilities_requested": ["functional_test", "raw_exports"],
        },
    )


def test_handoff_is_deterministic_quote_ready_and_non_authorizing() -> None:
    first = _handoff()
    second = _handoff()

    assert first == second
    assert first["handoff_id"].startswith("remote-physical-handoff-")
    assert first["release_readiness"]["ready_for_provider_quote"] is True
    assert first["release_readiness"]["production_artifact_set_complete"] is False
    assert "schematic" in first["release_readiness"]["missing_production_artifact_roles"]
    assert first["release_readiness"]["fabrication_release_ready"] is False
    assert first["policy"]["personal_contact_data_in_bundle"] is False
    assert first["policy"]["physical_authority_granted"] is False
    assert len(first["gate_requests"]) == 8


def test_handoff_archive_is_byte_deterministic_and_manifested() -> None:
    handoff = _handoff()
    first = build_remote_physical_handoff_archive(handoff)
    second = build_remote_physical_handoff_archive(handoff)

    assert first == second
    with zipfile.ZipFile(BytesIO(first)) as archive:
        names = sorted(archive.namelist())
        assert names == [
            "REMOTE_PHYSICAL_HANDOFF/EVIDENCE_RETURN_MANIFEST.template.json",
            "REMOTE_PHYSICAL_HANDOFF/MANIFEST.json",
            "REMOTE_PHYSICAL_HANDOFF/REMOTE_TEST_PLAN.md",
            "REMOTE_PHYSICAL_HANDOFF/REMOTE_TEST_REQUEST.json",
        ]
        manifest = json.loads(
            archive.read("REMOTE_PHYSICAL_HANDOFF/MANIFEST.json")
        )
        for row in manifest["files"]:
            payload = archive.read("REMOTE_PHYSICAL_HANDOFF/" + row["path"])
            assert "sha256:" + hashlib.sha256(payload).hexdigest() == row["sha256"]
            assert len(payload) == row["size_bytes"]


def _completed_identity_return(handoff: dict, payload: bytes) -> dict:
    returned = build_remote_physical_return_template(handoff)
    returned["provider"].update(
        {"work_order_id": "WO-123", "physical_site_id": "LAB-TW-01"}
    )
    returned["test_article"].update(
        {
            "assembly_id": "SPI-ADAPTER-001",
            "assembly_revision": "A",
            "serial_numbers": ["001"],
        }
    )
    returned["provider_attestation"].update(
        {
            "signed_by": "Lab Operator",
            "role": "test engineer",
            "signed_at": "2026-09-15T02:00:00+00:00",
        }
    )
    row = next(value for value in returned["gate_results"] if value["gate_id"] == "identify-dut")
    row.update(
        {
            "status": "pass",
            "captured_at": "2026-09-15T01:00:00+00:00",
            "operator_id": "operator-01",
            "direct_operator_observation": True,
            "measured_values": {
                "observed_top_marking": "W25Q128JWSIQ",
                "observed_package": "SOP-8 208 mil",
                "observed_pin_count": 8,
                "observed_dimensions_mm": {"length": 5.3, "width": 7.9},
            },
            "acceptance_criteria": {"top_marking_matches_bom": True},
            "raw_files": [
                {
                    "path": "raw/identify-dut.jpg",
                    "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                    "media_type": "image/jpeg",
                }
            ],
        }
    )
    return returned


def test_raw_remote_return_can_become_import_eligible_without_becoming_evidence() -> None:
    handoff = _handoff()
    payload = b"original-camera-capture"
    returned = _completed_identity_return(handoff, payload)

    audit = audit_remote_physical_return(
        handoff,
        returned,
        raw_payloads={"raw/identify-dut.jpg": payload},
    )

    assert audit["audit_pass"] is True
    assert audit["status"] == "eligible_for_physical_evidence_import"
    assert audit["accepted_gate_ids"] == ["identify-dut"]
    assert audit["complete_return"] is False
    assert audit["return_audit_is_physical_evidence"] is False
    assert audit["physical_authority_granted"] is False


def test_remote_return_rejects_summary_claim_without_matching_raw_bytes() -> None:
    handoff = _handoff()
    returned = _completed_identity_return(handoff, b"claimed")

    audit = audit_remote_physical_return(
        handoff,
        returned,
        raw_payloads={"raw/identify-dut.jpg": b"different"},
    )

    assert audit["audit_pass"] is False
    assert audit["status"] == "rejected_remote_return"
    assert any("raw file hash mismatch" in value for value in audit["blockers"])


def test_remote_return_rejects_self_authorization() -> None:
    handoff = _handoff()
    payload = b"capture"
    returned = _completed_identity_return(handoff, payload)
    returned["physical_authority_granted"] = True

    audit = audit_remote_physical_return(
        handoff,
        returned,
        raw_payloads={"raw/identify-dut.jpg": payload},
    )

    assert audit["audit_pass"] is False
    assert any("authority boundary" in value for value in audit["blockers"])


def test_remote_return_rejects_passed_gate_without_passing_prerequisites() -> None:
    handoff = _handoff()
    payload = b"logic-analyzer-export"
    returned = _completed_identity_return(handoff, b"identity-photo")
    row = next(
        value
        for value in returned["gate_results"]
        if value["gate_id"] == "read-only-jedec-identity"
    )
    row.update(
        {
            "status": "pass",
            "captured_at": "2026-09-15T03:00:00+00:00",
            "operator_id": "operator-01",
            "direct_operator_observation": True,
            "measured_values": {
                "command_hex": "9f",
                "response_hex_by_trial": ["ef6018"],
                "trial_count": 1,
                "clock_hz": 1000000,
            },
            "acceptance_criteria": {"repeatable_expected_identity": True},
            "instrument_ids": ["logic-analyzer-01"],
            "calibration_ids": ["cal-logic-01"],
            "raw_files": [
                {
                    "path": "raw/jedec.csv",
                    "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                    "media_type": "text/csv",
                }
            ],
        }
    )
    returned["calibrations"] = [
        {
            "calibration_id": "cal-logic-01",
            "instrument_id": "logic-analyzer-01",
        }
    ]

    audit = audit_remote_physical_return(
        handoff,
        returned,
        raw_payloads={
            "raw/identify-dut.jpg": b"identity-photo",
            "raw/jedec.csv": payload,
        },
    )

    assert audit["audit_pass"] is False
    assert "read-only-jedec-identity" in audit["rejected_gate_ids"]
    assert any("lacks accepted passing prerequisites" in value for value in audit["blockers"])

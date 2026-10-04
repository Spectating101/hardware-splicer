from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from hardware_splicer.provider_review import (
    STATUS_DISQUALIFIED,
    STATUS_ELIGIBLE,
    STATUS_INCOMPLETE,
    evaluate_provider_review,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
CAMPAIGN = json.loads((REFERENCE / "physical_proof_campaign_v1.json").read_text(encoding="utf-8"))
PENDING = json.loads((REFERENCE / "provider_review_jlcpcb_pending_v1.json").read_text(encoding="utf-8"))


def complete_record():
    record = deepcopy(PENDING)
    record["contact_state"] = "REPLIED"
    record["received_at"] = "2026-09-23T09:00:00Z"
    record["capabilities_confirmed"].update(
        {
            "preserve_DNP_and_open_states": True,
            "cold_measurements": True,
            "staged_current_limited_power": True,
            "raw_measurement_return": True,
            "waveform_or_capture_return": False,
            "bounded_spi_0x9f": True,
            "board_or_lot_traceability": True,
        }
    )
    record["commercial"].update(
        {
            "quotation_reference": "quote-123",
            "quantity": 5,
            "nre_or_fixture_cost": 25,
            "unit_or_batch_cost": 120,
            "lead_time": "10 business days",
        }
    )
    record["findings"] = []
    return record


def test_pending_record_is_incomplete_and_never_authorizes_anything():
    result = evaluate_provider_review(PENDING, CAMPAIGN)
    assert result["status"] == STATUS_INCOMPLETE
    assert "provider_contact_not_sent" in result["missing"]
    assert result["authority_effect"] == "NONE"
    assert result["provider_selected"] is False
    assert result["fabrication_authorized"] is False
    assert result["power_on_authorized"] is False
    assert result["functional_test_authorized"] is False
    assert result["release_authorized"] is False


def test_complete_record_is_only_eligible_for_human_decision():
    result = evaluate_provider_review(complete_record(), CAMPAIGN)
    assert result["status"] == STATUS_ELIGIBLE
    assert result["missing"] == []
    assert result["disqualifiers"] == []
    assert result["provider_selected"] is False
    assert result["fabrication_authorized"] is False


def test_required_capability_rejection_disqualifies_even_with_a_quote():
    record = complete_record()
    record["capabilities_confirmed"]["raw_measurement_return"] = False
    record["commercial"]["unit_or_batch_cost"] = 1

    result = evaluate_provider_review(record, CAMPAIGN)
    assert result["status"] == STATUS_DISQUALIFIED
    assert "required_capability_rejected:raw_measurement_return" in result["disqualifiers"]


def test_subject_revision_or_digest_mismatch_disqualifies():
    record = complete_record()
    record["subject"]["revision"] = "wrong"
    record["subject"]["package_sha256"] = "bad"

    result = evaluate_provider_review(record, CAMPAIGN)
    assert result["status"] == STATUS_DISQUALIFIED
    assert "subject_revision_mismatch" in result["disqualifiers"]
    assert "subject_package_sha256_mismatch" in result["disqualifiers"]


def test_any_preopened_authority_bit_disqualifies_record():
    record = complete_record()
    record["authority_effect"]["fabrication_authorized"] = True

    result = evaluate_provider_review(record, CAMPAIGN)
    assert result["status"] == STATUS_DISQUALIFIED
    assert "authority_not_fail_closed:fabrication_authorized" in result["disqualifiers"]


def test_change_request_requires_explicit_revision_disposition_before_eligibility():
    record = complete_record()
    record["findings"] = [
        {
            "finding_id": "F-1",
            "design_change_requested": True,
            "manufacturing_change_requested": False,
            "assembly_change_requested": False,
            "test_change_requested": False,
            "successor_revision_required": None,
        }
    ]

    result = evaluate_provider_review(record, CAMPAIGN)
    assert result["status"] == STATUS_INCOMPLETE
    assert "finding_0_change_request_needs_revision_disposition" in result["missing"]


def test_successor_revision_request_blocks_current_record_from_eligibility():
    record = complete_record()
    record["findings"] = [
        {
            "finding_id": "F-2",
            "design_change_requested": True,
            "manufacturing_change_requested": False,
            "assembly_change_requested": False,
            "test_change_requested": False,
            "successor_revision_required": True,
        }
    ]

    result = evaluate_provider_review(record, CAMPAIGN)
    assert result["status"] == STATUS_INCOMPLETE
    assert "finding_0_requires_successor_revision_review" in result["missing"]

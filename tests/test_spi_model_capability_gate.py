from hardware_splicer.spi_model_capability_gate import apply_spi_model_capability_gate
from hardware_splicer.spi_virtual_model_campaign import build_spi_virtual_model_campaign


def _capture(model_id: str, byte: str, kind: str) -> dict:
    return {
        "schema_version": "hardware_splicer.vendor_model_capture.v1",
        "model_id": model_id,
        "expected_model_kind": kind,
        "recognized_expected_model_file_count": 1,
        "capture_status": "captured_hashed_unreviewed",
        "sha256": "sha256:" + byte * 64,
        "size_bytes": 1024,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "authority_effect": "none",
        "physical_authority_granted": False,
    }


def _txu_audit(*, isolation_supported: bool) -> dict:
    return {
        "schema_version": "hardware_splicer.spi_vendor_model_capability_audit.v1",
        "model_id": "txu0304-ibis-scem787",
        "eligible_for_later_signal_integrity_execution": True,
        "rail_absent_isolation_claim_supported": isolation_supported,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def test_realistic_txu_ibis_capture_is_input_ready_but_not_semantically_ready_for_isolation() -> None:
    campaign = build_spi_virtual_model_campaign(
        [_capture("txu0304-ibis-scem787", "1", "IBIS")]
    )
    gated = apply_spi_model_capability_gate(campaign, [_txu_audit(isolation_supported=False)])

    assert campaign["ready_execution_ids"] == ["ibis-dut-rail-absent"]
    assert gated["status"] == "captured_models_no_semantically_executable_case"
    assert gated["ready_execution_ids"] == []
    row = gated["execution_readiness"]["ibis-dut-rail-absent"]
    assert row["input_ready"] is True
    assert row["semantic_capability_ready"] is False
    assert row["effective_execution_ready"] is False
    assert row["capability_blockers"]


def test_explicit_isolation_capability_can_unlock_the_input_ready_case() -> None:
    campaign = build_spi_virtual_model_campaign(
        [_capture("txu0304-ibis-scem787", "1", "IBIS")]
    )
    gated = apply_spi_model_capability_gate(campaign, [_txu_audit(isolation_supported=True)])

    assert gated["status"] == "partial_capability_gated_model_execution_ready"
    assert gated["ready_execution_ids"] == ["ibis-dut-rail-absent"]
    assert gated["execution_readiness"]["ibis-dut-rail-absent"]["effective_execution_ready"] is True


def test_no_capture_remains_capture_required() -> None:
    campaign = build_spi_virtual_model_campaign()
    gated = apply_spi_model_capability_gate(campaign)

    assert gated["status"] == "model_capture_required"
    assert gated["ready_execution_ids"] == []
    assert gated["accepted_capture_count"] == 0

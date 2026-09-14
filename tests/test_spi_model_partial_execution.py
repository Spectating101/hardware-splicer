from hardware_splicer.spi_model_execution_contract import (
    audit_spi_model_execution_result,
    required_checks_for_execution,
    seal_spi_model_execution_result,
)
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


def _sealed_result(campaign: dict, execution_id: str, model_hashes: dict[str, str]) -> dict:
    return seal_spi_model_execution_result(
        campaign,
        execution_id=execution_id,
        engine_name="synthetic-test-engine",
        engine_version="0-test",
        exit_code=0,
        raw_output=b"synthetic output\n",
        model_hashes=model_hashes,
        checks=[
            {"check_id": check_id, "status": "pass", "evidence": {"synthetic": True}}
            for check_id in sorted(required_checks_for_execution(execution_id))
        ],
        metrics={"test_metric": 1.0},
    )


def test_txu_only_partial_campaign_can_accept_ready_isolation_case() -> None:
    campaign = build_spi_virtual_model_campaign(
        [_capture("txu0304-ibis-scem787", "1", "IBIS")]
    )
    result = _sealed_result(
        campaign,
        "ibis-dut-rail-absent",
        {
            "txu0304-ibis-scem787": campaign["model_captures"]["txu0304-ibis-scem787"][
                "capture_sha256"
            ]
        },
    )

    audit = audit_spi_model_execution_result(campaign, result)

    assert campaign["status"] == "partial_model_execution_ready"
    assert audit["status"] == "accepted_modeled_result"
    assert audit["audit_pass"] is True
    assert audit["checks"]["campaign_ready"] is True
    assert audit["physical_correctness"] == "UNPROVEN"
    assert audit["physical_authority_granted"] is False


def test_txu_only_partial_campaign_rejects_nominal_case_missing_winbond_ibis() -> None:
    campaign = build_spi_virtual_model_campaign(
        [_capture("txu0304-ibis-scem787", "1", "IBIS")]
    )
    result = _sealed_result(
        campaign,
        "ibis-nominal-3v3-to-1v8",
        {
            "txu0304-ibis-scem787": campaign["model_captures"]["txu0304-ibis-scem787"][
                "capture_sha256"
            ]
        },
    )

    audit = audit_spi_model_execution_result(campaign, result)

    assert audit["status"] == "rejected_campaign_not_ready"
    assert audit["audit_pass"] is False
    assert audit["checks"]["campaign_ready"] is False
    assert audit["details"]["execution_missing_required_model_ids"] == [
        "w25q128jwsiq-ibis-da03-aag072"
    ]
    assert audit["checks"]["model_hash_binding"] is False


def test_protocol_only_partial_campaign_can_accept_ready_verilog_case() -> None:
    campaign = build_spi_virtual_model_campaign(
        [_capture("w25q128jw-q-verilog-da02-aag072", "3", "Verilog")]
    )
    result = _sealed_result(
        campaign,
        "verilog-jedec-id-read-9f",
        {
            "w25q128jw-q-verilog-da02-aag072": campaign["model_captures"][
                "w25q128jw-q-verilog-da02-aag072"
            ]["capture_sha256"]
        },
    )

    audit = audit_spi_model_execution_result(campaign, result)

    assert campaign["status"] == "partial_model_execution_ready"
    assert audit["status"] == "accepted_modeled_result"
    assert audit["audit_pass"] is True

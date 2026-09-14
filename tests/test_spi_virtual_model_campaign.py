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


def test_no_model_captures_keep_campaign_at_capture_required() -> None:
    campaign = build_spi_virtual_model_campaign()

    assert campaign["status"] == "model_capture_required"
    assert campaign["any_execution_ready"] is False
    assert campaign["execution_ready"] is False
    assert campaign["ready_execution_ids"] == []
    assert len(campaign["blocked_execution_ids"]) == 5


def test_txu_only_capture_unlocks_only_isolation_execution() -> None:
    campaign = build_spi_virtual_model_campaign(
        [_capture("txu0304-ibis-scem787", "1", "IBIS")]
    )

    assert campaign["status"] == "partial_model_execution_ready"
    assert campaign["any_execution_ready"] is True
    assert campaign["execution_ready"] is False
    assert campaign["ready_execution_ids"] == ["ibis-dut-rail-absent"]
    assert campaign["execution_readiness"]["ibis-dut-rail-absent"]["execution_ready"] is True
    assert campaign["execution_readiness"]["ibis-nominal-3v3-to-1v8"]["execution_ready"] is False
    assert campaign["execution_readiness"]["ibis-nominal-3v3-to-1v8"]["missing_required_model_ids"] == [
        "w25q128jwsiq-ibis-da03-aag072"
    ]


def test_winbond_verilog_only_unlocks_only_read_only_protocol_execution() -> None:
    campaign = build_spi_virtual_model_campaign(
        [_capture("w25q128jw-q-verilog-da02-aag072", "3", "Verilog")]
    )

    assert campaign["status"] == "partial_model_execution_ready"
    assert campaign["ready_execution_ids"] == ["verilog-jedec-id-read-9f"]
    assert campaign["execution_readiness"]["verilog-jedec-id-read-9f"]["execution_ready"] is True
    assert campaign["execution_ready"] is False


def test_all_required_captures_unlock_complete_campaign() -> None:
    campaign = build_spi_virtual_model_campaign(
        [
            _capture("txu0304-ibis-scem787", "1", "IBIS"),
            _capture("w25q128jwsiq-ibis-da03-aag072", "2", "IBIS"),
            _capture("w25q128jw-q-verilog-da02-aag072", "3", "Verilog"),
        ]
    )

    assert campaign["status"] == "ready_for_model_execution"
    assert campaign["model_capture_ready"] is True
    assert campaign["any_execution_ready"] is True
    assert campaign["execution_ready"] is True
    assert len(campaign["ready_execution_ids"]) == 5
    assert campaign["blocked_execution_ids"] == []


def test_malformed_capture_does_not_unlock_case() -> None:
    bad = _capture("txu0304-ibis-scem787", "1", "IBIS")
    bad["physical_authority_granted"] = True

    campaign = build_spi_virtual_model_campaign([bad])

    assert campaign["status"] == "model_capture_required"
    assert campaign["ready_execution_ids"] == []
    assert campaign["model_captures"]["txu0304-ibis-scem787"]["accepted_capture"] is False

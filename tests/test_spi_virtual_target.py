from hardware_splicer.spi_virtual_model_campaign import build_spi_virtual_model_campaign
from hardware_splicer.spi_virtual_target import (
    build_grounded_virtual_spi_target,
    build_vendor_model_registry,
)
from hardware_splicer.spi_virtual_verification import verify_spi_virtual_candidate


def _finding(result: dict, check_id: str) -> dict:
    return next(row for row in result["findings"] if row["check_id"] == check_id)


def test_grounded_virtual_target_binds_exact_parts_without_physical_identity_claim() -> None:
    target = build_grounded_virtual_spi_target()

    assert target["virtual_target_only"] is True
    assert target["physical_identity_asserted"] is False
    assert target["dut"]["exact_orderable_mpn"] == "W25Q128JWSIQ"
    assert target["dut"]["package"] == "SOP-8 208 mil"
    assert target["translator"]["exact_orderable_mpn"] == "TXU0304PWR"
    assert target["translator"]["package"] == "TSSOP (PW), 14 pin"
    assert target["supply"]["part"] == "TLV75518PDBVR"
    assert target["supply"]["output_min_v"] >= target["dut_vcc_min_v"]
    assert target["supply"]["output_max_v"] <= target["dut_vcc_max_v"]


def test_grounded_target_closes_exact_translator_identity_but_preserves_real_blockers() -> None:
    result = verify_spi_virtual_candidate(build_grounded_virtual_spi_target())

    assert result["verification_status"] == "blocked"
    assert result["counts"]["fail"] == 0
    assert _finding(result, "translator_topology")["status"] == "pass"
    assert _finding(result, "translator_implementation_closure")["status"] == "pass"
    assert _finding(result, "translator_dut_output_level")["status"] == "blocked"
    assert _finding(result, "dut_supply_closure")["status"] == "blocked"
    assert _finding(result, "spi_timing_closure")["status"] == "blocked"
    assert _finding(result, "bound_simulation")["status"] == "blocked"
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_vendor_model_registry_requires_three_model_captures() -> None:
    registry = build_vendor_model_registry()
    model_ids = {row["model_id"] for row in registry["models"]}

    assert model_ids == {
        "txu0304-ibis-scem787",
        "w25q128jwsiq-ibis-da03-aag072",
        "w25q128jw-q-verilog-da02-aag072",
    }
    assert all(row["capture_status"] == "remote_available_not_captured" for row in registry["models"])
    assert all(row["sha256"] is None for row in registry["models"])
    assert registry["authority_effect"] == "none"


def test_campaign_fails_closed_until_vendor_model_bytes_are_captured() -> None:
    campaign = build_spi_virtual_model_campaign()

    assert campaign["status"] == "model_capture_required"
    assert campaign["model_capture_ready"] is False
    assert set(campaign["missing_required_model_ids"]) == {
        "txu0304-ibis-scem787",
        "w25q128jwsiq-ibis-da03-aag072",
        "w25q128jw-q-verilog-da02-aag072",
    }
    assert campaign["static_verification"]["counts"]["fail"] == 0
    assert campaign["fault_detection_ready"] is True
    assert campaign["execution_ready"] is False
    assert campaign["simulation_results"] == []
    assert campaign["model_inference_used"] is False
    assert campaign["physical_authority_granted"] is False


def test_fake_capture_without_full_manifest_cannot_unlock_campaign() -> None:
    captures = [
        {
            "model_id": "txu0304-ibis-scem787",
            "capture_status": "captured_hashed_unreviewed",
            "sha256": "sha256:" + "0" * 64,
            "size_bytes": 123,
            "authority_effect": "none",
            "physical_authority_granted": False,
        }
    ]

    campaign = build_spi_virtual_model_campaign(captures)

    assert campaign["model_captures"]["txu0304-ibis-scem787"]["accepted_capture"] is True
    assert campaign["model_capture_ready"] is False
    assert len(campaign["missing_required_model_ids"]) == 2
    assert campaign["execution_ready"] is False

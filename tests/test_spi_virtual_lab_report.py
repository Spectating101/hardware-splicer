from hardware_splicer.spi_virtual_lab_report import build_virtual_lab_report


def test_virtual_lab_report_aggregates_controls_without_authority_promotion() -> None:
    report = build_virtual_lab_report()
    assert report["status"] == "controls_passed"
    assert report["controls_pass"] is True
    assert report["summary"]["benchmark_case_count"] == 576
    assert report["summary"]["repair_fault_count"] == 6
    assert report["summary"]["repair_successful"] == 6
    assert report["summary"]["sensitivity_case_count"] == 1920
    assert report["summary"]["jedec_hex"] == "EF6018"
    assert all(value.startswith("sha256:") for value in report["result_hashes"].values())
    assert report["astra_used"] is False
    assert report["eligible_for_vendor_model_campaign_credit"] is False
    assert report["physical_correctness"] == "UNPROVEN"
    assert report["fabrication_ready"] is False
    assert report["power_on_ready"] is False
    assert report["physical_authority_granted"] is False

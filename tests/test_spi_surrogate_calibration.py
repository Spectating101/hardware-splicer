from hardware_splicer.spi_surrogate_calibration import compare_surrogate_to_reference


def test_calibration_records_agreement_without_promoting_surrogate() -> None:
    result = compare_surrogate_to_reference(
        {"return_margin_ns": 79.0, "forward_margin_ns": 77.0},
        {"return_margin_ns": 78.5, "forward_margin_ns": 76.5},
        metric_tolerances={"return_margin_ns": 1.0, "forward_margin_ns": 1.0},
        reference_evidence_class="manufacturer_model",
    )
    assert result["status"] == "comparable"
    assert result["out_of_tolerance_metrics"] == []
    assert result["surrogate_promoted"] is False
    assert result["eligible_for_vendor_model_campaign_credit"] is False
    assert result["physical_correctness"] == "UNPROVEN"


def test_calibration_preserves_disagreement_as_result() -> None:
    result = compare_surrogate_to_reference(
        {"return_margin_ns": 79.0},
        {"return_margin_ns": 60.0},
        metric_tolerances={"return_margin_ns": 2.0},
        reference_evidence_class="manufacturer_model",
    )
    assert result["status"] == "disagreement_detected"
    assert result["out_of_tolerance_metrics"] == ["return_margin_ns"]
    assert result["comparisons"]["return_margin_ns"]["within_tolerance"] is False
    assert result["eligible_for_vendor_model_campaign_credit"] is False

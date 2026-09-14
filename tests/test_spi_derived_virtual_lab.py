from hardware_splicer.spi_behavioral_oracle import transact
from hardware_splicer.spi_derived_surrogate import build_default_surrogate, evaluate_surrogate_case
from hardware_splicer.spi_surrogate_repair_benchmark import run_repair_benchmark
from hardware_splicer.spi_virtual_lab_benchmark import generate_benchmark_cases, run_benchmark


def test_surrogate_authority_boundary_and_nominal_case() -> None:
    model = build_default_surrogate()
    result = evaluate_surrogate_case(model, spi_clock_hz=5_000_000)
    assert result["status"] == "pass_surrogate"
    assert result["evidence_class"] == "derived_surrogate_only"
    assert result["eligible_for_vendor_model_campaign_credit"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_direct_drive_and_overclock_fail() -> None:
    model = build_default_surrogate()
    direct = evaluate_surrogate_case(model, spi_clock_hz=5_000_000, direct_drive=True)
    fast = evaluate_surrogate_case(model, spi_clock_hz=25_000_000)
    assert "no_unsafe_direct_drive" in direct["failed_checks"]
    assert "return_halfcycle_margin_positive" in fast["failed_checks"]


def test_generated_benchmark_is_576_cases_and_matches_preregistered_labels() -> None:
    cases = generate_benchmark_cases()
    result = run_benchmark(cases)
    assert len(cases) == 576
    assert result["case_count"] == 576
    assert result["confusion"]["false_negative"] == 0
    assert result["confusion"]["false_positive"] == 0
    assert result["unsafe_detection_recall"] == 1.0
    assert result["safe_case_specificity"] == 1.0
    assert result["eligible_for_vendor_model_campaign_credit"] is False


def test_scripted_repair_control_repairs_all_preregistered_faults() -> None:
    result = run_repair_benchmark()
    assert result["fault_count"] == 6
    assert result["successful_repairs"] == 6
    assert result["repair_success_rate"] == 1.0
    assert result["model_inference_used"] is False


def test_readonly_protocol_oracle_returns_jedec_id_without_side_effect() -> None:
    result = transact(0x9F)
    assert result["response_bytes"] == [0xEF, 0x60, 0x18]
    assert result["state_mutated"] is False
    assert result["write_or_erase_side_effect"] is False
    assert result["vendor_model"] is False
    assert result["eligible_for_vendor_model_campaign_credit"] is False

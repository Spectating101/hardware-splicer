from hardware_splicer.spi_derived_virtual_lab import (
    FAULT_PROFILES,
    build_derived_surrogate_case,
    evaluate_derived_surrogate_case,
    generate_derived_surrogate_corpus,
    repair_derived_surrogate_case,
    run_derived_virtual_lab_benchmark,
    run_readonly_spi_protocol_oracle,
)
from hardware_splicer.spi_power_budget import build_grounded_spi_power_inputs
from hardware_splicer.spi_timing_budget import build_grounded_spi_timing_inputs


def _nominal(profile: str):
    return build_derived_surrogate_case(
        profile=profile,
        spi_clock_hz=5_000_000,
        estimated_load_a=0.1,
        dut_vcc_v=1.8,
        ordinal=1,
    )


def test_surrogate_parameters_remain_aligned_to_source_bound_budget_inputs() -> None:
    case = _nominal("clean")
    timing = build_grounded_spi_timing_inputs()
    power = build_grounded_spi_power_inputs()

    assert case["txu_forward_delay_ns"] == timing["txu0304"]["a_to_b_tpd_max_ns"]
    assert case["txu_reverse_delay_ns"] == timing["txu0304"]["b_to_a_tpd_max_ns"]
    assert case["dut_clock_to_output_ns"] == timing["w25q128jw"]["clock_low_to_output_valid_max_ns"]
    assert case["regulator_capacity_a"] == power["regulator"]["rated_output_current_ma"] / 1000.0


def test_frozen_corpus_contains_512_unique_cases_and_every_profile() -> None:
    corpus = generate_derived_surrogate_corpus()

    assert len(corpus) == 512
    assert len({row["case_id"] for row in corpus}) == 512
    assert len({row["case_hash"] for row in corpus}) == 512
    assert {row["fault_profile"] for row in corpus} == set(FAULT_PROFILES)
    assert all(row["evidence_class"] == "derived_surrogate_only" for row in corpus)
    assert all(row["vendor_model_campaign_credit_eligible"] is False for row in corpus)


def test_nominal_case_passes_only_as_derived_surrogate() -> None:
    result = evaluate_derived_surrogate_case(_nominal("clean"))

    assert result["status"] == "passed_surrogate"
    assert result["predicted_outcome"] == "safe"
    assert result["vendor_model_campaign_credit_eligible"] is False
    assert result["measured_evidence_present"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_direct_3v3_drive_is_detected_as_unsafe() -> None:
    result = evaluate_derived_surrogate_case(_nominal("direct_3v3_drive"))

    assert result["status"] == "failed_surrogate"
    assert result["predicted_outcome"] == "unsafe"
    assert any(
        row["check_id"] == "direct_drive_absolute_maximum" and row["status"] == "fail"
        for row in result["findings"]
    )


def test_missing_provenance_blocks_without_manufacturing_an_electrical_failure() -> None:
    result = evaluate_derived_surrogate_case(_nominal("missing_absmax_provenance"))

    assert result["status"] == "blocked_surrogate"
    assert result["predicted_outcome"] == "blocked"
    assert result["counts"]["fail"] == 0
    assert any(row["check_id"] == "surrogate_provenance" and row["status"] == "blocked" for row in result["findings"])


def test_high_clock_and_overcurrent_are_detected_even_without_injected_fault_profile() -> None:
    high_clock = build_derived_surrogate_case(
        profile="clean",
        spi_clock_hz=100_000_000,
        estimated_load_a=0.1,
        dut_vcc_v=1.8,
        ordinal=2,
    )
    overcurrent = build_derived_surrogate_case(
        profile="clean",
        spi_clock_hz=5_000_000,
        estimated_load_a=0.55,
        dut_vcc_v=1.8,
        ordinal=3,
    )

    clock_result = evaluate_derived_surrogate_case(high_clock)
    power_result = evaluate_derived_surrogate_case(overcurrent)

    assert clock_result["predicted_outcome"] == "unsafe"
    assert any(row["check_id"] == "derived_half_cycle_timing" and row["status"] == "fail" for row in clock_result["findings"])
    assert power_result["predicted_outcome"] == "unsafe"
    assert any(row["check_id"] == "derived_regulator_capacity" and row["status"] == "fail" for row in power_result["findings"])


def test_scripted_repair_removes_injected_fault_without_touching_background_limits() -> None:
    case = _nominal("reversed_miso")
    before = evaluate_derived_surrogate_case(case)
    repair = repair_derived_surrogate_case(case)
    after = evaluate_derived_surrogate_case(repair["repaired_case"])

    assert before["predicted_outcome"] == "unsafe"
    assert repair["repair_attempted"] is True
    assert repair["repair_actions"] == ["restore_miso_dut_to_host"]
    assert after["predicted_outcome"] == "safe"
    assert repair["physical_authority_granted"] is False

    high_clock = build_derived_surrogate_case(
        profile="reversed_miso",
        spi_clock_hz=100_000_000,
        estimated_load_a=0.1,
        dut_vcc_v=1.8,
        ordinal=4,
    )
    repaired_high_clock = repair_derived_surrogate_case(high_clock)
    assert evaluate_derived_surrogate_case(repaired_high_clock["repaired_case"])["predicted_outcome"] == "unsafe"


def test_readonly_protocol_oracle_accepts_9f_and_rejects_mutating_commands() -> None:
    jedec = run_readonly_spi_protocol_oracle(0x9F)
    wren = run_readonly_spi_protocol_oracle(0x06)
    page_program = run_readonly_spi_protocol_oracle(0x02)

    assert jedec["accepted"] is True
    assert jedec["response_bytes"] == [0xEF, 0x60, 0x18]
    assert jedec["state_mutated"] is False
    assert wren["accepted"] is False
    assert wren["reason"] == "mutating_command_forbidden"
    assert wren["state_mutated"] is False
    assert page_program["accepted"] is False
    assert page_program["state_mutated"] is False


def test_full_512_case_benchmark_passes_with_zero_authority_promotion() -> None:
    report = run_derived_virtual_lab_benchmark()

    assert report["case_count"] == 512
    assert report["benchmark_pass"] is True
    assert report["status"] == "passed_derived_benchmark"
    assert report["unsafe_false_negatives"] == 0
    assert report["safe_false_rejections"] == 0
    assert report["blocked_misclassifications"] == 0
    assert report["repair_control"]["eligible_cases"] > 0
    assert report["repair_control"]["success_rate"] == 1.0
    assert report["protocol_oracle"]["boundary_pass"] is True
    assert report["authority_violation_count"] == 0
    assert report["vendor_model_campaign_credit_eligible"] is False
    assert report["physical_correctness"] == "UNPROVEN"
    assert report["physical_authority_granted"] is False

from copy import deepcopy

from hardware_splicer.spi_timing_budget import (
    build_grounded_spi_timing_inputs,
    evaluate_spi_timing_budget,
)


def test_grounded_5mhz_budget_quantifies_known_delay_but_stays_blocked() -> None:
    result = evaluate_spi_timing_budget()

    assert result["status"] == "blocked_incomplete_timing_model"
    assert result["period_ns"] == 200.0
    assert result["half_period_ns"] == 100.0
    assert result["known_terms"]["txu_a_to_b_tpd_max_ns"] == 19.0
    assert result["known_terms"]["txu_b_to_a_tpd_max_ns"] == 15.0
    assert result["known_terms"]["dut_clock_low_to_output_valid_max_ns"] == 6.0
    assert result["known_terms"]["known_read_return_delay_ns"] == 21.0
    assert result["known_terms"]["known_read_halfcycle_residual_ns"] == 79.0
    assert result["known_terms"]["known_forward_translation_residual_ns"] == 81.0
    assert set(result["unresolved_terms"]) == {
        "host_input_setup_required_ns",
        "host_output_clock_to_data_valid_max_ns",
        "clock_skew_bound_ns",
        "signal_integrity_model_pass",
        "load_bound",
    }
    assert result["timing_validated"] is False
    assert result["physical_authority_granted"] is False


def test_catalog_headline_rate_is_not_used_to_close_timing() -> None:
    inputs = build_grounded_spi_timing_inputs()
    inputs["requested_spi_clock_hz"] = 100_000_000
    result = evaluate_spi_timing_budget(inputs)

    assert result["catalog_rate_exceeded"] is False
    assert result["status"] == "failed_known_terms"
    assert result["known_terms"]["known_read_halfcycle_residual_ns"] < 0
    assert result["timing_validated"] is False


def test_rate_over_catalog_boundary_fails_even_if_other_terms_are_filled() -> None:
    inputs = build_grounded_spi_timing_inputs()
    inputs["requested_spi_clock_hz"] = 150_000_000
    inputs["host"] = {
        "input_setup_required_ns": 1.0,
        "output_clock_to_data_valid_max_ns": 1.0,
        "programmer_identity": "synthetic-host",
    }
    inputs["interconnect"] = {
        "clock_skew_bound_ns": 0.1,
        "signal_integrity_model_pass": True,
        "load_bound": "synthetic",
    }

    result = evaluate_spi_timing_budget(inputs)

    assert result["catalog_rate_exceeded"] is True
    assert result["status"] == "failed_known_terms"


def test_complete_synthetic_terms_can_only_reach_modeled_timing_pass() -> None:
    inputs = deepcopy(build_grounded_spi_timing_inputs())
    inputs["host"] = {
        "input_setup_required_ns": 5.0,
        "output_clock_to_data_valid_max_ns": 5.0,
        "programmer_identity": "synthetic-host",
    }
    inputs["interconnect"] = {
        "clock_skew_bound_ns": 2.0,
        "signal_integrity_model_pass": True,
        "load_bound": "synthetic-load",
    }

    result = evaluate_spi_timing_budget(inputs)

    assert result["status"] == "passed_modeled_timing"
    assert result["timing_validated"] is False
    assert result["modeled_evidence_only"] is True
    assert result["measured_evidence_present"] is False
    assert result["physical_correctness"] == "UNPROVEN"

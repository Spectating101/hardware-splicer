from copy import deepcopy

from hardware_splicer.spi_power_budget import (
    build_grounded_spi_power_inputs,
    evaluate_spi_power_budget,
)


def test_grounded_power_budget_keeps_missing_worst_case_load_blocked() -> None:
    result = evaluate_spi_power_budget()

    assert result["status"] == "blocked_incomplete_power_model"
    assert result["known_terms"]["regulator_capacity_ma"] == 500.0
    assert result["known_terms"]["translator_supply_current_max_ma"] == 0.008
    assert result["known_terms"]["dut_worst_case_current_ma"] is None
    assert result["typical_only_context"]["dut_active_read_current_typical_ma"] == 1.0
    assert result["typical_only_context"]["used_for_design_closure"] is False
    assert "dut_worst_case_current_ma" in result["unresolved_terms"]
    assert "dut_transient_current_bound_ma" in result["unresolved_terms"]
    assert result["power_validated"] is False
    assert result["physical_authority_granted"] is False


def test_undersized_output_capacitance_fails_known_term() -> None:
    inputs = build_grounded_spi_power_inputs()
    inputs["implementation"]["selected_output_capacitance_uf"] = 0.47

    result = evaluate_spi_power_budget(inputs)

    assert result["status"] == "failed_known_terms"
    assert "output_capacitance_below_regulator_minimum" in result["fail_reasons"]


def test_over_capacity_worst_case_load_fails() -> None:
    inputs = build_grounded_spi_power_inputs()
    inputs["dut"]["worst_case_current_ma"] = 510.0

    result = evaluate_spi_power_budget(inputs)

    assert result["status"] == "failed_known_terms"
    assert result["known_terms"]["steady_state_capacity_margin_ma"] < 0
    assert "steady_state_current_capacity_exceeded" in result["fail_reasons"]


def test_complete_synthetic_budget_can_only_pass_as_modeled_power() -> None:
    inputs = deepcopy(build_grounded_spi_power_inputs())
    inputs["dut"]["worst_case_current_ma"] = 20.0
    inputs["dut"]["transient_current_bound_ma"] = 50.0
    inputs["implementation"] = {
        "selected_output_capacitance_uf": 4.7,
        "selected_input_capacitance_uf": 1.0,
        "sequencing_policy_bound": True,
        "protection_policy_bound": True,
        "pcb_power_path_bound": True,
    }

    result = evaluate_spi_power_budget(inputs)

    assert result["status"] == "passed_modeled_power_budget"
    assert result["known_terms"]["steady_state_capacity_margin_ma"] > 0
    assert result["power_validated"] is False
    assert result["modeled_evidence_only"] is True
    assert result["measured_evidence_present"] is False
    assert result["physical_correctness"] == "UNPROVEN"

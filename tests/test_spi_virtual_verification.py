from copy import deepcopy

from hardware_splicer.spi_virtual_verification import (
    apply_spi_fault,
    build_raw_document_v4_candidate,
    run_spi_fault_corpus,
    verify_spi_virtual_candidate,
)


def _finding(result: dict, check_id: str) -> dict:
    return next(row for row in result["findings"] if row["check_id"] == check_id)


def test_raw_document_v4_candidate_is_coherent_but_blocked() -> None:
    result = verify_spi_virtual_candidate(build_raw_document_v4_candidate())

    assert result["verification_status"] == "blocked"
    assert result["static_verification_pass"] is True
    assert result["counts"]["fail"] == 0
    assert _finding(result, "spi_signal_contract")["status"] == "pass"
    assert _finding(result, "direct_drive_absolute_maximum")["status"] == "pass"
    assert _finding(result, "translator_topology")["status"] == "pass"
    assert _finding(result, "translator_implementation_closure")["status"] == "blocked"
    assert _finding(result, "dut_supply_closure")["status"] == "blocked"
    assert _finding(result, "spi_timing_closure")["status"] == "blocked"
    assert _finding(result, "bound_simulation")["status"] == "blocked"
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False
    assert result["measured_evidence_present"] is False


def test_direct_3v3_fault_is_rejected_by_absolute_maximum_check() -> None:
    candidate = apply_spi_fault(build_raw_document_v4_candidate(), "direct_3v3_drive")
    result = verify_spi_virtual_candidate(candidate)

    finding = _finding(result, "direct_drive_absolute_maximum")
    assert result["verification_status"] == "failed"
    assert finding["status"] == "fail"
    assert finding["evidence"]["host_logic_high_v"] == 3.3
    assert finding["evidence"]["guaranteed_pin_max_v"] == 2.1
    assert finding["evidence"]["margin_v"] == -1.2


def test_reversed_miso_fault_is_rejected() -> None:
    candidate = apply_spi_fault(build_raw_document_v4_candidate(), "reversed_miso")
    result = verify_spi_virtual_candidate(candidate)

    finding = _finding(result, "spi_signal_contract")
    assert result["verification_status"] == "failed"
    assert finding["status"] == "fail"
    assert finding["evidence"]["mismatches"]["MISO"] == {
        "expected": "dut_to_host",
        "actual": "host_to_dut",
    }


def test_axc_grouped_direction_fault_is_rejected_for_three_plus_one_spi() -> None:
    candidate = apply_spi_fault(
        build_raw_document_v4_candidate(), "grouped_direction_translator"
    )
    result = verify_spi_virtual_candidate(candidate)

    finding = _finding(result, "translator_topology")
    assert result["verification_status"] == "failed"
    assert finding["status"] == "fail"
    assert finding["evidence"]["family"] == "SN74AXC4T245"
    assert finding["evidence"]["direction_groups"] == [2, 2]


def test_missing_absmax_provenance_blocks_without_inventing_authority() -> None:
    candidate = apply_spi_fault(
        build_raw_document_v4_candidate(), "missing_absmax_provenance"
    )
    result = verify_spi_virtual_candidate(candidate)

    finding = _finding(result, "critical_input_provenance")
    assert result["verification_status"] == "blocked"
    assert finding["status"] == "blocked"
    assert finding["evidence"]["missing"] == ["dut_pin_abs_max_rule"]
    assert result["authority_effect"] == "none"


def test_fault_corpus_is_zero_inference_and_meets_expected_outcomes() -> None:
    corpus = run_spi_fault_corpus()

    assert corpus["model_inference_used"] is False
    assert corpus["all_expectations_pass"] is True
    assert all(row["pass"] for row in corpus["expectations"].values())
    assert corpus["physical_correctness"] == "UNPROVEN"
    assert corpus["physical_authority_granted"] is False


def test_input_cannot_self_grant_physical_authority() -> None:
    candidate = build_raw_document_v4_candidate()
    candidate["physical_correctness"] = "VERIFIED"
    candidate["physical_authority_granted"] = True
    candidate["measured_evidence_present"] = True

    result = verify_spi_virtual_candidate(candidate)

    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False
    assert result["measured_evidence_present"] is False
    assert result["fabrication_ready"] is False
    assert result["power_on_ready"] is False


def test_fully_bound_synthetic_virtual_candidate_can_pass_without_physical_promotion() -> None:
    candidate = deepcopy(build_raw_document_v4_candidate())
    candidate["translator"].update(
        {
            "exact_orderable_mpn": "SYNTHETIC-TXU0304",
            "package": "synthetic-package",
            "oe_strategy": "synthetic-explicit-enable",
            "partial_power_behavior_verified": True,
            "dut_side_output_max_v": 1.9,
        }
    )
    candidate["supply"] = {
        "part": "synthetic-1v8-supply",
        "output_min_v": 1.78,
        "output_max_v": 1.82,
        "current_budget_verified": True,
        "sequencing_verified": True,
    }
    candidate["timing"] = {
        "spi_clock_hz": 1_000_000,
        "max_supported_spi_clock_hz": 10_000_000,
        "selected_load_verified": True,
    }
    candidate["simulation"] = {
        "schema_version": "synthetic.simulation.fixture.v1",
        "scope": "unit-test-only",
        "simulation_pass": True,
    }
    candidate["known_unresolved"] = []

    result = verify_spi_virtual_candidate(candidate)

    assert result["verification_status"] == "passed_virtual"
    assert result["counts"]["fail"] == 0
    assert result["counts"]["blocked"] == 0
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["measured_evidence_present"] is False
    assert result["physical_authority_granted"] is False

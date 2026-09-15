from hardware_splicer.spi_virtual_repair_control import (
    run_scripted_repair_control,
    run_scripted_repair_control_matrix,
)


def test_scripted_repairs_remove_injected_failures_but_preserve_real_blockers() -> None:
    for fault_id in (
        "direct_3v3_drive",
        "reversed_miso",
        "grouped_direction_translator",
    ):
        result = run_scripted_repair_control(fault_id)

        assert result["before"]["verification_status"] == "failed"
        assert result["after"]["verification_status"] == "blocked"
        assert result["after"]["counts"]["fail"] == 0
        assert result["control_pass"] is True
        assert result["real_blockers_preserved"] is True
        assert result["model_inference_used"] is False
        assert result["physical_correctness"] == "UNPROVEN"
        assert result["physical_authority_granted"] is False


def test_missing_provenance_control_restores_identity_without_promoting_candidate() -> None:
    result = run_scripted_repair_control("missing_absmax_provenance")

    assert result["before"]["verification_status"] == "blocked"
    assert result["after"]["verification_status"] == "blocked"
    assert result["control_pass"] is True
    assert result["physical_authority_granted"] is False


def test_scripted_repair_control_matrix_passes_without_model_inference() -> None:
    matrix = run_scripted_repair_control_matrix()

    assert matrix["model_inference_used"] is False
    assert matrix["all_controls_pass"] is True
    assert set(matrix["cases"]) == {
        "direct_3v3_drive",
        "reversed_miso",
        "grouped_direction_translator",
        "missing_absmax_provenance",
    }
    assert all(case["control_pass"] for case in matrix["cases"].values())
    assert matrix["physical_correctness"] == "UNPROVEN"
    assert matrix["physical_authority_granted"] is False

from __future__ import annotations

from pathlib import Path

from hardware_splicer.robot_arm_reference_benchmark import (
    REFERENCE_SOURCES,
    load_external_proposals,
    run_reference_robot_arm_benchmark,
)


ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "experiments" / "robot_arm" / "reference_benchmark_gpt56_sol_proposals.json"


def _report() -> dict:
    return run_reference_robot_arm_benchmark(load_external_proposals(PROPOSALS))


def test_reference_benchmark_diagnostic_passes_without_claiming_design_ready() -> None:
    report = _report()

    assert report["diagnostic_pass"] is True
    assert report["design_ready"] is False
    assert report["motion_ready"] is False
    assert report["authority"] == {
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def test_blind_lane_has_no_reference_leakage_and_is_not_exact_reference_copy() -> None:
    report = _report()
    lane = report["lanes"]["blind_reconstruction"]

    assert lane["proposal"]["source_ids"] == []
    assert lane["reference_comparison"]["openmanipulator_arm_dof"] == 4
    assert lane["reference_comparison"]["proposed_joint_count"] == 4
    assert lane["reference_comparison"]["openmanipulator_reach_mm"] == 380.0
    assert lane["reference_comparison"]["proposed_chain_length_mm"] == 400.0
    assert lane["axis_aware_oracle"]["hard_failure_count"] == 0


def test_source_assisted_lane_uses_references_without_promoting_stall_torque() -> None:
    report = _report()
    lane = report["lanes"]["source_assisted_reconstruction"]

    assert set(lane["proposal"]["source_ids"]) == set(REFERENCE_SOURCES)
    assert lane["reference_comparison"]["so101_arm_dof"] == 5
    assert lane["reference_comparison"]["proposed_joint_count"] == 5
    assert lane["reference_comparison"]["proposed_chain_length_mm"] == 420.0
    assert report["checks"]["so101_stall_torque_not_promoted_to_continuous_truth"] is True


def test_mutation_lane_refuses_to_pretend_reference_actuation_still_closes() -> None:
    report = _report()
    lane = report["lanes"]["mutated_requirement"]
    shoulder = next(
        row for row in lane["axis_aware_oracle"]["rows"] if row["joint_id"] == "shoulder-pitch"
    )

    assert lane["requirements"]["required_reach_mm"] == 550.0
    assert lane["requirements"]["payload_mass_kg"] == 0.75
    assert shoulder["status"] == "unresolved"
    assert shoulder["actuator_part_id"] is None
    assert report["checks"]["naive_scaled_reference_copy_is_caught"] is True


def test_reference_benchmark_detects_legacy_vertical_yaw_gravity_bug() -> None:
    report = _report()
    diagnostic = report["evaluator_diagnostics"]

    assert report["checks"]["legacy_base_yaw_gravity_referee_defect_detected"] is True
    assert diagnostic["legacy_base_yaw_required_nm"] > 0.0
    assert diagnostic["axis_aware_root_yaw_required_nm"] == 0.0
    assert diagnostic["diagnosis"] == "TOOL_IMPLEMENTATION"


def test_blind_source_leak_turns_benchmark_red() -> None:
    bundle = load_external_proposals(PROPOSALS)
    bundle["blind_reconstruction"]["source_ids"] = ["ref-openmanipulator-x-spec"]
    report = run_reference_robot_arm_benchmark(bundle)

    assert report["diagnostic_pass"] is False
    assert report["checks"]["blind_has_no_reference_leakage"] is False

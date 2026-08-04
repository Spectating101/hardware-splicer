from __future__ import annotations

from hardware_splicer.change_impact import build_change_impact_graph
from hardware_splicer.engineering_analysis import analyze_engineering_candidate
from hardware_splicer.engineering_verification_bridge import bridge_engineering_verification
from hardware_splicer.machine_project import VerificationStatus
from hardware_splicer.machine_project_seed import machine_project_from_intake
from hardware_splicer.robot_machine_projection import project_robot_topology
from hardware_splicer.robot_topology import build_robot_topology


def test_analysis_and_regression_checks_become_canonical_verifications() -> None:
    intake = {
        "project_name": "verification-rover",
        "goal": "Revise the rover after a payload-induced brownout.",
        "mode": "evolve",
        "baseline_revision": 3,
        "available_parts": [
            {"name": "drive motor", "type": "dc_motor", "quantity": 2},
            {"name": "battery", "type": "power_source"},
        ],
        "constraints": {
            "battery_energy_wh": 100,
            "continuous_power_w": 40,
            "runtime_min": 90,
            "supply_current_limit_a": 5,
            "peak_current_a": 12,
        },
        "field_failure": "The logic rail browned out during acceleration.",
    }
    base = machine_project_from_intake(intake)
    topology = build_robot_topology(intake, machine_project=base)
    project = project_robot_topology(base, topology)
    identity_map = {
        "topology_to_machine_component": {
            row.actuator_id: f"robot-actuator-{row.actuator_id}"
            for row in topology.actuators
        }
    }
    analysis = analyze_engineering_candidate(intake, topology=topology)
    impact = build_change_impact_graph(
        intake,
        machine_project=project,
        topology=topology,
    )

    bridged = bridge_engineering_verification(
        project,
        analysis=analysis,
        change_impact=impact,
        identity_map=identity_map,
    )

    verification_ids = {row.verification_id for row in bridged.verifications}
    assert "verification-analysis-runtime" in verification_ids
    assert "verification-analysis-current-margin" in verification_ids
    assert {
        f"verification-{row.check_id}" for row in impact.regression_checks
    }.issubset(verification_ids)
    current = next(
        row for row in bridged.verifications
        if row.verification_id == "verification-analysis-current-margin"
    )
    assert current.status == VerificationStatus.FAILED
    assert current.evidence_ids == ["evidence-analysis-current-margin"]
    evidence = next(row for row in bridged.evidence if row.evidence_id == current.evidence_ids[0])
    assert evidence.simulated is True
    assert evidence.authority.value == "proposed"
    assert bridged.metadata["operational_authority_unchanged"] is True


def test_unknown_blocking_calculation_has_no_fake_evidence() -> None:
    intake = {
        "project_name": "unknown-power-rover",
        "goal": "Build a rover with ninety minute runtime.",
        "available_parts": [{"name": "unknown battery", "type": "power_source"}],
        "constraints": {"runtime_min": 90},
    }
    base = machine_project_from_intake(intake)
    topology = build_robot_topology(intake, machine_project=base)
    project = project_robot_topology(base, topology)
    analysis = analyze_engineering_candidate(intake, topology=topology)
    impact = build_change_impact_graph(intake, machine_project=project, topology=topology)

    bridged = bridge_engineering_verification(
        project,
        analysis=analysis,
        change_impact=impact,
        identity_map={},
    )

    runtime = next(
        row for row in bridged.verifications
        if row.verification_id == "verification-analysis-runtime"
    )
    assert runtime.status == VerificationStatus.BLOCKED
    assert runtime.evidence_ids == []
    assert "Missing inputs" in runtime.procedure

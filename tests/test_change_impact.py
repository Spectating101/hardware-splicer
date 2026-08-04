from __future__ import annotations

from hardware_splicer.change_impact import ChangeMode, ImpactDomain, build_change_impact_graph
from hardware_splicer.engineering_source_graph import build_engineering_source_graph
from hardware_splicer.machine_project_seed import machine_project_from_intake
from hardware_splicer.robot_topology import build_robot_topology


def test_field_failure_propagates_across_mechanical_power_control_and_safety() -> None:
    intake = {
        "project_name": "inspection-rover",
        "goal": "Revise the inspection rover after a field failure caused by a camera mast.",
        "mode": "evolve",
        "baseline_revision": 7,
        "available_parts": [
            {"name": "left drive motor", "type": "dc_motor"},
            {"name": "right drive motor", "type": "dc_motor"},
            {"name": "camera mast", "type": "mechanical_structure"},
            {"name": "depth camera", "type": "camera"},
        ],
        "constraints": {"payload_mass_g": 620, "payload_height_mm": 310},
        "field_failure": {
            "event": "The rover tipped during a turn and the logic rail brownout reset the controller.",
            "environment": "indoor threshold mission",
        },
        "observations": ["Tipping started after the camera mast was installed."],
        "measurements": ["5 V logic rail dropped to 3.1 V during motor startup."],
    }
    source_graph = build_engineering_source_graph(
        [
            {
                "source_id": "field-log",
                "source_type": "test_log",
                "revision": "mission-2026-07-30",
                "authority_ceiling": "observed",
                "claims": ["rover tipped during turn"],
            },
            {
                "source_id": "rail-capture",
                "source_type": "measurement",
                "revision": "scope-capture-12",
                "authority_ceiling": "measured",
                "claims": [
                    {
                        "subject_id": "logic-rail",
                        "predicate": "minimum_voltage_v",
                        "value": 3.1,
                        "authority": "measured",
                    }
                ],
            },
        ]
    )
    project = machine_project_from_intake(intake)
    topology = build_robot_topology(intake, machine_project=project)

    graph = build_change_impact_graph(
        intake,
        machine_project=project,
        topology=topology,
        source_graph=source_graph,
    )

    assert graph.mode == ChangeMode.FIELD_EVOLUTION
    assert graph.baseline_revision == 7
    domains = {row.domain for row in graph.impacts}
    assert {
        ImpactDomain.MECHANICAL,
        ImpactDomain.ELECTRICAL,
        ImpactDomain.CONTROL,
        ImpactDomain.SAFETY,
        ImpactDomain.VERIFICATION,
    }.issubset(domains)
    assert graph.blocking_impacts
    assert len(graph.regression_checks) == len(domains)
    assert all(check.blocking for check in graph.regression_checks)
    assert all(impact.verification_target_ids for impact in graph.impacts)
    assert graph.metadata["impact_analysis_authority"] == "proposed"
    assert graph.metadata["release_authority_preserved"] is False


def test_modification_without_baseline_is_explicitly_unresolved() -> None:
    intake = {
        "goal": "Modify the robot arm by adding a wrist camera.",
        "mode": "modify",
        "available_parts": [
            {"name": "smart servo", "type": "smart_servo", "quantity": 5},
            {"name": "wrist camera", "type": "camera"},
        ],
        "change_request": "Add a camera and wider gripper to the wrist.",
    }

    graph = build_change_impact_graph(intake, topology=build_robot_topology(intake))

    assert graph.mode == ChangeMode.MODIFY
    assert graph.baseline_revision is None
    assert any(row["field"] == "baseline_revision" for row in graph.unresolved)
    assert "mechanical" in graph.affected_domains
    assert "electrical" in graph.affected_domains


def test_greenfield_candidate_does_not_invent_baseline_revision() -> None:
    intake = {
        "goal": "Design a compact indoor inspection rover.",
        "available_parts": [{"name": "drive motor", "type": "dc_motor", "quantity": 2}],
        "constraints": {"width_mm": 250, "runtime_min": 90},
    }

    graph = build_change_impact_graph(intake, topology=build_robot_topology(intake))

    assert graph.mode == ChangeMode.GREENFIELD
    assert graph.baseline_revision is None
    assert not any(row["field"] == "baseline_revision" for row in graph.unresolved)
    assert graph.metadata["release_authority_preserved"] is True

from __future__ import annotations

from hardware_splicer.complete_engineering_planner import plan_complete_engineering_project
from hardware_splicer.machine_project import MachineProject, ReleaseState
from hardware_splicer.machine_project_seed import machine_project_from_intake
from hardware_splicer.robot_machine_projection import project_robot_topology
from hardware_splicer.robot_topology import build_robot_topology


def test_quadruped_projection_creates_first_class_components_and_interfaces() -> None:
    intake = {
        "project_name": "projected-quadruped",
        "goal": "Build a twelve actuator quadruped robot.",
        "available_parts": [
            {"name": "joint actuator", "type": "smart_servo", "quantity": 12},
            {"name": "body IMU", "type": "imu", "quantity": 1},
        ],
        "constraints": {"leg_count": 4, "joints_per_leg": 3, "degrees_of_freedom": 12},
    }
    base = machine_project_from_intake(intake)
    topology = build_robot_topology(intake, machine_project=base)

    project = project_robot_topology(base, topology)

    assert isinstance(project, MachineProject)
    component_ids = {row.component_id for row in project.components}
    interface_ids = {row.interface_id for row in project.interfaces}
    assert "robot-joint-front-left-hip-joint" in component_ids
    assert "robot-actuator-rear-right-knee-actuator" in component_ids
    assert "robot-firmware-channel-front-left-hip-actuator" in component_ids
    assert "robot-sensor-body-imu" in component_ids
    assert "robot-interface-joint-front-left-hip-joint" in interface_ids
    assert "robot-interface-actuator-power-front-left-hip-actuator" in interface_ids
    assert "robot-interface-sensor-firmware-body-imu" in interface_ids
    assert not [
        row for row in project.traceability_issues()
        if row.code in {"invalid_ref", "duplicate_id"}
    ]
    assert any(row.code == "unresolved_interface" for row in project.traceability_issues())
    assessment = project.assess_release(ReleaseState.BUILD_READY)
    assert assessment.allowed is False
    assert assessment.achieved_state != ReleaseState.OPERATIONALLY_AUTHORIZED


def test_robot_projection_is_idempotent() -> None:
    intake = {
        "project_name": "idempotent-rover",
        "goal": "Build a differential drive rover.",
        "available_parts": [
            {"name": "left motor", "type": "dc_motor"},
            {"name": "right motor", "type": "dc_motor"},
            {"name": "camera", "type": "camera"},
        ],
    }
    base = machine_project_from_intake(intake)
    topology = build_robot_topology(intake, machine_project=base)

    first = project_robot_topology(base, topology)
    second = project_robot_topology(first, topology)

    assert len(second.components) == len(first.components)
    assert len(second.interfaces) == len(first.interfaces)
    assert len(second.subsystems) == len(first.subsystems)
    assert second.discipline_payloads["robot_machine_projection"]["projected_component_count"] == 0
    assert second.discipline_payloads["robot_machine_projection"]["projected_interface_count"] == 0


def test_complete_plan_maps_topology_ids_to_machine_components() -> None:
    plan = plan_complete_engineering_project(
        {
            "project_name": "complete-arm",
            "goal": "Build a five degree of freedom robotic arm with a wrist camera.",
            "available_parts": [
                {"name": "joint servo", "type": "smart_servo", "quantity": 5},
                {"name": "wrist camera", "type": "camera", "quantity": 1},
            ],
            "constraints": {"degrees_of_freedom": 5},
        },
        skip_vision=True,
    )

    mapping = plan["engineering_identity_map"]["topology_to_machine_component"]
    assert mapping["shoulder-pan-joint"] == "robot-joint-shoulder-pan-joint"
    assert mapping["wrist-camera"] == "robot-sensor-wrist-camera"
    assert plan["engineering_identity_map"]["topology_objects"]["shoulder-pan-joint"]["machine_component_id"] == "robot-joint-shoulder-pan-joint"
    assert plan["engineering_readiness"]["machine_project_robot_projection_complete"] is True
    assert plan["engineering_readiness"]["projected_component_count"] > 0
    assert plan["engineering_readiness"]["projected_interface_count"] > 0
    project = MachineProject.model_validate(plan["machine_project"])
    assert not [row for row in project.traceability_issues() if row.code == "invalid_ref"]

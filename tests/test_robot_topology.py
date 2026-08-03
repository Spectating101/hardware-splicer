from __future__ import annotations

from hardware_splicer.machine_project_seed import machine_project_from_intake
from hardware_splicer.robot_topology import RobotGenre, build_robot_topology


def test_quadruped_topology_expands_twelve_joint_identities() -> None:
    intake = {
        "project_name": "inspection-quadruped",
        "goal": "Build a twelve actuator quadruped robot for indoor inspection.",
        "available_parts": [
            {"name": "candidate joint actuator", "type": "smart_servo", "quantity": 12},
            {"name": "body IMU", "type": "imu", "quantity": 1},
            {"name": "depth camera", "type": "camera", "quantity": 1},
        ],
        "constraints": {
            "leg_count": 4,
            "joints_per_leg": 3,
            "degrees_of_freedom": 12,
        },
    }
    project = machine_project_from_intake(intake)

    topology = build_robot_topology(intake, machine_project=project)

    assert topology.robot_genre == RobotGenre.QUADRUPED
    assert topology.degree_of_freedom_count == 12
    assert len(topology.joints) == 12
    assert len(topology.actuators) == 12
    assert len(topology.sensors) == 2
    assert {joint.joint_id for joint in topology.joints} >= {
        "front-left-hip-joint",
        "front-left-knee-joint",
        "rear-right-knee-joint",
    }
    assert all(joint.firmware_joint_id for joint in topology.joints)
    assert all(joint.middleware_joint_name for joint in topology.joints)
    assert all(joint.calibration_ref for joint in topology.joints)
    assert any(row["field"] == "limits" for row in topology.unresolved)
    assert topology.metadata["motion_authorized"] is False


def test_serial_manipulator_keeps_ordered_chain() -> None:
    intake = {
        "project_name": "sorting-arm",
        "goal": "Build a five degree of freedom robotic arm with a wrist camera.",
        "available_parts": [
            {"name": "smart servo", "type": "smart_servo", "quantity": 5},
            {"name": "wrist depth camera", "type": "depth_camera", "quantity": 1},
        ],
        "constraints": {"degrees_of_freedom": 5},
    }

    topology = build_robot_topology(intake)

    assert topology.robot_genre == RobotGenre.SERIAL_MANIPULATOR
    assert [joint.joint_id for joint in topology.joints] == [
        "shoulder-pan-joint",
        "shoulder-lift-joint",
        "elbow-joint",
        "wrist-pitch-joint",
        "wrist-roll-joint",
    ]
    for index in range(1, len(topology.joints)):
        previous = topology.joints[index - 1]
        current = topology.joints[index]
        assert current.parent_link_id == previous.child_link_id


def test_rover_and_aerial_topologies_preserve_actuator_cardinality() -> None:
    rover = build_robot_topology(
        {
            "goal": "Build a differential drive indoor rover.",
            "available_parts": [{"name": "drive motor", "type": "dc_motor", "quantity": 2}],
            "constraints": {"drive_type": "differential_drive"},
        }
    )
    aerial = build_robot_topology(
        {
            "goal": "Build a quadcopter aerial robot.",
            "available_parts": [{"name": "brushless motor", "type": "motor", "quantity": 4}],
            "constraints": {"rotor_count": 4},
        }
    )

    assert rover.robot_genre == RobotGenre.ROVER
    assert len(rover.actuators) == 2
    assert aerial.robot_genre == RobotGenre.AERIAL
    assert len(aerial.actuators) == 4
    assert {joint.metadata["spin_direction"] for joint in aerial.joints} == {"cw", "ccw"}


def test_topology_maps_declared_parts_to_machine_components() -> None:
    intake = {
        "project_name": "mapped-rover",
        "goal": "Build a differential drive rover.",
        "available_parts": [
            {"component_id": "motor-left", "name": "left motor", "type": "dc_motor"},
            {"component_id": "motor-right", "name": "right motor", "type": "dc_motor"},
        ],
    }
    project = machine_project_from_intake(intake)

    topology = build_robot_topology(intake, machine_project=project)

    mapped = {row.electrical_component_id for row in topology.actuators}
    assert mapped == {"motor-left", "motor-right"}

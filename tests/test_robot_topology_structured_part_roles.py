from __future__ import annotations

import hardware_splicer.integrations.llm_policy as llm_policy
from hardware_splicer.robot_topology import (
    RobotGenre,
    build_robot_topology,
    detect_robot_genre,
)


def test_model_first_genre_detector_does_not_read_goal_or_part_names(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    genre = detect_robot_genre(
        "Build a rover robot arm quadcopter gripper from these parts.",
        [
            {"component_id": "p-1", "name": "left motor rover wheel"},
            {"component_id": "p-2", "name": "camera sensor drone"},
        ],
    )

    assert genre == RobotGenre.GENERIC


def test_model_first_unknown_named_parts_do_not_become_actuators_or_sensors(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    topology = build_robot_topology(
        {
            "project_name": "name-invariance",
            "goal": "Human-facing labels deliberately contain old trigger words.",
            "available_parts": [
                {
                    "component_id": "unknown-a",
                    "name": "servo motor rover wheel",
                    "type": "unknown_interface",
                },
                {
                    "component_id": "unknown-b",
                    "name": "camera sensor lidar imu",
                    "type": "unknown_interface",
                },
            ],
        },
        hinted_genre="generic_mechatronics",
    )

    assert topology.robot_genre == RobotGenre.GENERIC
    assert topology.actuators == []
    assert topology.sensors == []
    assert topology.metadata["part_role_projection"] == "declared_structured_fields_only"


def test_model_first_structured_roles_bind_stable_part_identities(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    topology = build_robot_topology(
        {
            "project_name": "structured-parts",
            "goal": "Use declared component roles only.",
            "available_parts": [
                {
                    "component_id": "motor-1",
                    "name": "unfamiliar equivalent A",
                    "type": "dc_motor",
                },
                {
                    "component_id": "sensor-1",
                    "name": "unfamiliar equivalent B",
                    "type": "sensor",
                },
            ],
        },
        hinted_genre="generic_mechatronics",
    )

    assert len(topology.actuators) == 1
    assert topology.actuators[0].source_part_id == "motor-1"
    assert topology.actuators[0].metadata["source_part_declared"] is True
    assert len(topology.sensors) == 1
    assert topology.sensors[0].source_part_id == "sensor-1"
    assert topology.sensors[0].metadata["source_part_declared"] is True


def test_declared_rover_topology_exposes_unbound_actuator_slots_when_inventory_is_unknown(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    topology = build_robot_topology(
        {
            "project_name": "declared-rover",
            "goal": "The topology is declared, but actuator inventory is not structurally identified.",
            "available_parts": [
                {"component_id": "mystery-left", "name": "left motor", "type": "unknown"},
                {"component_id": "mystery-right", "name": "right motor", "type": "unknown"},
            ],
        },
        hinted_genre="rover",
    )

    assert topology.robot_genre == RobotGenre.ROVER
    assert len(topology.actuators) == 2
    assert all(row.source_part_id is None for row in topology.actuators)
    unresolved_ids = {
        row["object_id"]
        for row in topology.unresolved
        if row.get("field") == "source_part_id"
    }
    assert unresolved_ids == {row.actuator_id for row in topology.actuators}
    assert topology.metadata["motion_authorized"] is False


def test_offline_compatibility_can_still_project_roles_from_names(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: True)

    topology = build_robot_topology(
        {
            "project_name": "legacy-fixture",
            "goal": "offline fixture",
            "available_parts": [
                {"component_id": "legacy-motor", "name": "left servo motor"},
                {"component_id": "legacy-camera", "name": "front camera sensor"},
            ],
        },
        hinted_genre="generic_mechatronics",
    )

    assert len(topology.actuators) == 1
    assert topology.actuators[0].source_part_id == "legacy-motor"
    assert len(topology.sensors) == 1
    assert topology.sensors[0].source_part_id == "legacy-camera"
    assert topology.metadata["part_role_projection"] == "legacy_name_keyword"

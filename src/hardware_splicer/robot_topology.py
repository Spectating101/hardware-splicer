"""Canonical robot topology for cross-domain identity and robotics scaling.

The topology keeps stable identities for links, joints, actuators, sensors, frames,
electrical components, firmware channels, and middleware names. It describes a candidate
architecture; it does not claim physical fit, calibration, or safe motion. Model-first
part-role projection consumes structured declarations only; names remain labels.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Dict, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .machine_project import AuthorityState, MachineProject
from .structured_part_roles import declared_part_role


ROBOT_TOPOLOGY_SCHEMA = "hardware_splicer.robot_topology.v1"


class RobotGenre(str, Enum):
    ROVER = "rover"
    SERIAL_MANIPULATOR = "robotic_arm"
    QUADRUPED = "quadruped"
    AERIAL = "aerial_robot"
    PAN_TILT = "pan_tilt"
    GRIPPER = "gripper"
    MOBILE_MANIPULATOR = "mobile_manipulator"
    GENERIC = "generic_mechatronics"


class JointType(str, Enum):
    FIXED = "fixed"
    REVOLUTE = "revolute"
    CONTINUOUS = "continuous"
    PRISMATIC = "prismatic"
    FLOATING = "floating"


class TopologyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CoordinateFrame(TopologyModel):
    frame_id: str = Field(min_length=1)
    parent_frame_id: str | None = None
    attached_object_id: str = Field(min_length=1)
    pose: Dict[str, Any] = Field(default_factory=dict)
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RobotLink(TopologyModel):
    link_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    parent_link_id: str | None = None
    frame_id: str = Field(min_length=1)
    mechanical_component_id: str | None = None
    mass_kg: float | None = Field(default=None, ge=0.0)
    center_of_mass: Dict[str, Any] = Field(default_factory=dict)
    collision_geometry_refs: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RobotJoint(TopologyModel):
    joint_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    joint_type: JointType
    parent_link_id: str = Field(min_length=1)
    child_link_id: str = Field(min_length=1)
    axis: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0], min_length=3, max_length=3)
    limits: Dict[str, Any] = Field(default_factory=dict)
    actuator_id: str | None = None
    firmware_joint_id: str | None = None
    middleware_joint_name: str | None = None
    calibration_ref: str | None = None
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RobotActuator(TopologyModel):
    actuator_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    actuator_type: str = Field(min_length=1)
    joint_ids: list[str] = Field(default_factory=list)
    source_part_id: str | None = None
    electrical_component_id: str | None = None
    driver_channel_id: str | None = None
    firmware_channel_id: str | None = None
    command_interface: str | None = None
    feedback_interface: str | None = None
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RobotSensor(TopologyModel):
    sensor_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    sensor_type: str = Field(min_length=1)
    frame_id: str = Field(min_length=1)
    source_part_id: str | None = None
    electrical_component_id: str | None = None
    firmware_sensor_id: str | None = None
    middleware_interfaces: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RobotTopology(TopologyModel):
    schema_version: str = ROBOT_TOPOLOGY_SCHEMA
    topology_id: str = Field(min_length=1)
    robot_genre: RobotGenre
    root_link_id: str = Field(min_length=1)
    frames: list[CoordinateFrame] = Field(default_factory=list)
    links: list[RobotLink] = Field(default_factory=list)
    joints: list[RobotJoint] = Field(default_factory=list)
    actuators: list[RobotActuator] = Field(default_factory=list)
    sensors: list[RobotSensor] = Field(default_factory=list)
    unresolved: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_topology_references(self) -> "RobotTopology":
        collections = {
            "frame": [row.frame_id for row in self.frames],
            "link": [row.link_id for row in self.links],
            "joint": [row.joint_id for row in self.joints],
            "actuator": [row.actuator_id for row in self.actuators],
            "sensor": [row.sensor_id for row in self.sensors],
        }
        for label, values in collections.items():
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} identifier")
        frame_ids = set(collections["frame"])
        link_ids = set(collections["link"])
        joint_ids = set(collections["joint"])
        actuator_ids = set(collections["actuator"])
        all_object_ids = frame_ids | link_ids | joint_ids | actuator_ids | set(collections["sensor"])
        if self.root_link_id not in link_ids:
            raise ValueError("root_link_id must reference a link")
        for frame in self.frames:
            if frame.parent_frame_id and frame.parent_frame_id not in frame_ids:
                raise ValueError(f"frame {frame.frame_id!r} references unknown parent frame")
            if frame.attached_object_id not in all_object_ids:
                raise ValueError(f"frame {frame.frame_id!r} references unknown attached object")
        for link in self.links:
            if link.parent_link_id and link.parent_link_id not in link_ids:
                raise ValueError(f"link {link.link_id!r} references unknown parent link")
            if link.frame_id not in frame_ids:
                raise ValueError(f"link {link.link_id!r} references unknown frame")
        for joint in self.joints:
            if joint.parent_link_id not in link_ids or joint.child_link_id not in link_ids:
                raise ValueError(f"joint {joint.joint_id!r} references unknown link")
            if joint.actuator_id and joint.actuator_id not in actuator_ids:
                raise ValueError(f"joint {joint.joint_id!r} references unknown actuator")
        for actuator in self.actuators:
            missing = sorted(set(actuator.joint_ids) - joint_ids)
            if missing:
                raise ValueError(f"actuator {actuator.actuator_id!r} references unknown joints: {missing}")
        for sensor in self.sensors:
            if sensor.frame_id not in frame_ids:
                raise ValueError(f"sensor {sensor.sensor_id!r} references unknown frame")
        return self

    @property
    def degree_of_freedom_count(self) -> int:
        return sum(row.joint_type != JointType.FIXED for row in self.joints)


_GENRE_ALIASES = {
    "rover": RobotGenre.ROVER,
    "robot_drive_base": RobotGenre.ROVER,
    "robotic_arm": RobotGenre.SERIAL_MANIPULATOR,
    "serial_manipulator": RobotGenre.SERIAL_MANIPULATOR,
    "manipulator": RobotGenre.SERIAL_MANIPULATOR,
    "quadruped": RobotGenre.QUADRUPED,
    "legged_quadruped": RobotGenre.QUADRUPED,
    "aerial": RobotGenre.AERIAL,
    "aerial_robot": RobotGenre.AERIAL,
    "drone": RobotGenre.AERIAL,
    "quadcopter": RobotGenre.AERIAL,
    "pan_tilt": RobotGenre.PAN_TILT,
    "gripper": RobotGenre.GRIPPER,
    "mobile_manipulator": RobotGenre.MOBILE_MANIPULATOR,
    "generic_mechatronics": RobotGenre.GENERIC,
}


def _slug(value: str, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._").lower()
    return token[:96] or fallback


def _stable_id(prefix: str, *values: Any) -> str:
    rendered = json.dumps(values, sort_keys=True, default=str, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(rendered.encode('utf-8')).hexdigest()[:12]}"


def detect_robot_genre(goal: str, parts: Sequence[Mapping[str, Any]], hinted: str | None = None) -> RobotGenre:
    if hinted:
        normalized = str(hinted).strip().lower().replace("-", "_")
        if normalized in _GENRE_ALIASES:
            return _GENRE_ALIASES[normalized]

    from .integrations.llm_policy import offline_salvage_enabled

    if not offline_salvage_enabled():
        return RobotGenre.GENERIC

    text = " ".join(
        [goal]
        + [
            " ".join(str(row.get(key) or "") for key in ("name", "type", "role", "category"))
            for row in parts
        ]
    ).lower()
    if any(token in text for token in ("quadruped", "four leg", "4 leg", "robot dog", "pupper", "spotmicro")):
        return RobotGenre.QUADRUPED
    if any(token in text for token in ("mobile manipulator", "arm on rover", "mobile arm")):
        return RobotGenre.MOBILE_MANIPULATOR
    if any(token in text for token in ("robot arm", "robotic arm", "manipulator", "openmanipulator", "wrist joint")):
        return RobotGenre.SERIAL_MANIPULATOR
    if any(token in text for token in ("quadcopter", "drone", "aerial robot", "crazyflie", "flight controller")):
        return RobotGenre.AERIAL
    if any(token in text for token in ("rover", "wheeled robot", "differential drive", "mecanum", "skid steer", "robot car")):
        return RobotGenre.ROVER
    if any(token in text for token in ("pan tilt", "pan-tilt", "gimbal")):
        return RobotGenre.PAN_TILT
    if any(token in text for token in ("gripper", "robot claw")):
        return RobotGenre.GRIPPER
    return RobotGenre.GENERIC


def _parts(intake: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = intake.get("available_parts") or intake.get("parts") or intake.get("resources") or []
    return [dict(row) for row in raw if isinstance(row, Mapping)] if isinstance(raw, list) else []


def _constraints(intake: Mapping[str, Any]) -> dict[str, Any]:
    raw = intake.get("constraints") or {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _component_lookup(machine_project: MachineProject | None) -> dict[str, str]:
    if machine_project is None:
        return {}
    lookup: dict[str, str] = {}
    for component in machine_project.components:
        lookup[component.component_id.lower()] = component.component_id
        lookup[component.name.lower()] = component.component_id
        intake_part = component.metadata.get("intake_part") if isinstance(component.metadata, Mapping) else None
        if isinstance(intake_part, Mapping):
            for key in ("name", "module_id", "component_id"):
                if intake_part.get(key):
                    lookup[str(intake_part[key]).lower()] = component.component_id
    return lookup


def _part_component_id(part: Mapping[str, Any], lookup: Mapping[str, str]) -> str | None:
    for key in ("component_id", "module_id", "name"):
        value = str(part.get(key) or "").strip().lower()
        if value and value in lookup:
            return lookup[value]
    return None


def _legacy_sensor_parts(parts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    tokens = ("sensor", "camera", "imu", "lidar", "encoder", "depth", "radar", "microphone")
    return [
        row for row in parts
        if any(token in " ".join(str(row.get(key) or "").lower() for key in ("name", "type", "role")) for token in tokens)
    ]


def _legacy_actuator_parts(parts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    tokens = ("motor", "servo", "actuator", "esc", "drive")
    return [
        row for row in parts
        if any(token in " ".join(str(row.get(key) or "").lower() for key in ("name", "type", "role")) for token in tokens)
    ]


def _sensor_parts(parts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    from .integrations.llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        return _legacy_sensor_parts(parts)
    return [row for row in parts if declared_part_role(row)[0] == "sensor"]


def _actuator_parts(parts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    from .integrations.llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        return _legacy_actuator_parts(parts)
    return [row for row in parts if declared_part_role(row)[0] == "actuator"]


def _expanded_part_slots(parts: Sequence[Mapping[str, Any]], count: int, prefix: str) -> list[tuple[str, Mapping[str, Any] | None]]:
    expanded: list[tuple[str, Mapping[str, Any] | None]] = []
    for row in parts:
        quantity = int(row.get("quantity") or 1)
        for _ in range(max(quantity, 1)):
            expanded.append((f"{prefix}-{len(expanded) + 1}", row))
            if len(expanded) >= count:
                return expanded
    while len(expanded) < count:
        expanded.append((f"{prefix}-{len(expanded) + 1}", None))
    return expanded


def _base_link(topology_id: str) -> tuple[list[CoordinateFrame], list[RobotLink]]:
    root = "base-link"
    frame = "base-frame"
    return (
        [CoordinateFrame(frame_id=frame, attached_object_id=root)],
        [RobotLink(link_id=root, name="Base link", frame_id=frame)],
    )


def _add_link(
    frames: list[CoordinateFrame],
    links: list[RobotLink],
    *,
    link_id: str,
    name: str,
    parent_link_id: str,
    parent_frame_id: str,
    mechanical_component_id: str | None = None,
) -> str:
    frame_id = f"{link_id}-frame"
    frames.append(
        CoordinateFrame(
            frame_id=frame_id,
            parent_frame_id=parent_frame_id,
            attached_object_id=link_id,
        )
    )
    links.append(
        RobotLink(
            link_id=link_id,
            name=name,
            parent_link_id=parent_link_id,
            frame_id=frame_id,
            mechanical_component_id=mechanical_component_id,
        )
    )
    return frame_id


def _make_actuator(
    actuator_id: str,
    joint_id: str,
    part: Mapping[str, Any] | None,
    lookup: Mapping[str, str],
) -> RobotActuator:
    part = part or {}
    actuator_type = str(part.get("type") or part.get("role") or "actuator")
    source_part_id = str(part.get("component_id") or part.get("module_id") or "").strip() or None
    return RobotActuator(
        actuator_id=actuator_id,
        name=str(part.get("name") or actuator_id).replace("-", " "),
        actuator_type=actuator_type,
        joint_ids=[joint_id],
        source_part_id=source_part_id,
        electrical_component_id=_part_component_id(part, lookup),
        driver_channel_id=f"driver-{actuator_id}",
        firmware_channel_id=f"fw-{actuator_id}",
        command_interface=f"command/{actuator_id}",
        feedback_interface=f"state/{actuator_id}",
        metadata={"source_part_declared": source_part_id is not None},
    )


def _build_rover(
    topology_id: str,
    parts: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any],
    lookup: Mapping[str, str],
) -> tuple[list[CoordinateFrame], list[RobotLink], list[RobotJoint], list[RobotActuator]]:
    frames, links = _base_link(topology_id)
    drive_type = str(constraints.get("drive_type") or constraints.get("base_type") or "differential_drive").lower()
    wheel_count = int(constraints.get("wheel_count") or (4 if any(token in drive_type for token in ("4wd", "mecanum", "skid")) else 2))
    slots = _expanded_part_slots(_actuator_parts(parts), wheel_count, "wheel-actuator")
    joints: list[RobotJoint] = []
    actuators: list[RobotActuator] = []
    names = ["left", "right"] if wheel_count == 2 else ["front-left", "front-right", "rear-left", "rear-right"]
    for index in range(wheel_count):
        side = names[index] if index < len(names) else f"wheel-{index + 1}"
        link_id = f"{side}-wheel-link"
        _add_link(frames, links, link_id=link_id, name=f"{side} wheel", parent_link_id="base-link", parent_frame_id="base-frame")
        joint_id = f"{side}-wheel-joint"
        actuator_id = f"{side}-drive-actuator"
        joints.append(
            RobotJoint(
                joint_id=joint_id,
                name=f"{side} wheel joint",
                joint_type=JointType.CONTINUOUS,
                parent_link_id="base-link",
                child_link_id=link_id,
                axis=[0.0, 1.0, 0.0],
                actuator_id=actuator_id,
                firmware_joint_id=joint_id.replace("-", "_"),
                middleware_joint_name=joint_id,
            )
        )
        actuators.append(_make_actuator(actuator_id, joint_id, slots[index][1], lookup))
    return frames, links, joints, actuators


def _build_quadruped(
    topology_id: str,
    parts: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any],
    lookup: Mapping[str, str],
) -> tuple[list[CoordinateFrame], list[RobotLink], list[RobotJoint], list[RobotActuator]]:
    frames, links = _base_link(topology_id)
    leg_names = ["front-left", "front-right", "rear-left", "rear-right"]
    joint_names = ["hip", "upper-leg", "knee"]
    leg_count = int(constraints.get("leg_count") or 4)
    joints_per_leg = int(constraints.get("joints_per_leg") or max(int(constraints.get("degrees_of_freedom") or 12) // max(leg_count, 1), 1))
    count = leg_count * joints_per_leg
    slots = _expanded_part_slots(_actuator_parts(parts), count, "leg-actuator")
    joints: list[RobotJoint] = []
    actuators: list[RobotActuator] = []
    slot_index = 0
    for leg_index in range(leg_count):
        leg = leg_names[leg_index] if leg_index < len(leg_names) else f"leg-{leg_index + 1}"
        parent_link = "base-link"
        parent_frame = "base-frame"
        for joint_index in range(joints_per_leg):
            joint_name = joint_names[joint_index] if joint_index < len(joint_names) else f"joint-{joint_index + 1}"
            child_link = f"{leg}-{joint_name}-link"
            child_frame = _add_link(
                frames,
                links,
                link_id=child_link,
                name=f"{leg} {joint_name} link",
                parent_link_id=parent_link,
                parent_frame_id=parent_frame,
            )
            joint_id = f"{leg}-{joint_name}-joint"
            actuator_id = f"{leg}-{joint_name}-actuator"
            joints.append(
                RobotJoint(
                    joint_id=joint_id,
                    name=f"{leg} {joint_name} joint",
                    joint_type=JointType.REVOLUTE,
                    parent_link_id=parent_link,
                    child_link_id=child_link,
                    axis=[1.0, 0.0, 0.0] if joint_index == 0 else [0.0, 1.0, 0.0],
                    actuator_id=actuator_id,
                    firmware_joint_id=joint_id.replace("-", "_").upper(),
                    middleware_joint_name=joint_id,
                    calibration_ref=f"calibration/{joint_id}",
                    metadata={"leg_index": leg_index, "joint_index": joint_index, "mirrored_side": "right" in leg},
                )
            )
            actuators.append(_make_actuator(actuator_id, joint_id, slots[slot_index][1], lookup))
            slot_index += 1
            parent_link = child_link
            parent_frame = child_frame
    return frames, links, joints, actuators


def _build_arm(
    topology_id: str,
    parts: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any],
    lookup: Mapping[str, str],
) -> tuple[list[CoordinateFrame], list[RobotLink], list[RobotJoint], list[RobotActuator]]:
    frames, links = _base_link(topology_id)
    degrees = int(constraints.get("degrees_of_freedom") or constraints.get("joint_count") or 5)
    slots = _expanded_part_slots(_actuator_parts(parts), degrees, "arm-actuator")
    joints: list[RobotJoint] = []
    actuators: list[RobotActuator] = []
    parent_link = "base-link"
    parent_frame = "base-frame"
    standard = ["shoulder-pan", "shoulder-lift", "elbow", "wrist-pitch", "wrist-roll", "tool"]
    for index in range(degrees):
        name = standard[index] if index < len(standard) else f"joint-{index + 1}"
        child_link = f"{name}-link"
        child_frame = _add_link(
            frames,
            links,
            link_id=child_link,
            name=f"{name} link",
            parent_link_id=parent_link,
            parent_frame_id=parent_frame,
        )
        joint_id = f"{name}-joint"
        actuator_id = f"{name}-actuator"
        joints.append(
            RobotJoint(
                joint_id=joint_id,
                name=f"{name} joint",
                joint_type=JointType.REVOLUTE,
                parent_link_id=parent_link,
                child_link_id=child_link,
                axis=[0.0, 0.0, 1.0] if index in {0, 4} else [0.0, 1.0, 0.0],
                actuator_id=actuator_id,
                firmware_joint_id=joint_id.replace("-", "_"),
                middleware_joint_name=joint_id,
                calibration_ref=f"calibration/{joint_id}",
            )
        )
        actuators.append(_make_actuator(actuator_id, joint_id, slots[index][1], lookup))
        parent_link = child_link
        parent_frame = child_frame
    return frames, links, joints, actuators


def _build_aerial(
    topology_id: str,
    parts: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any],
    lookup: Mapping[str, str],
) -> tuple[list[CoordinateFrame], list[RobotLink], list[RobotJoint], list[RobotActuator]]:
    frames, links = _base_link(topology_id)
    rotor_count = int(constraints.get("rotor_count") or 4)
    slots = _expanded_part_slots(_actuator_parts(parts), rotor_count, "rotor-actuator")
    joints: list[RobotJoint] = []
    actuators: list[RobotActuator] = []
    names = ["front-left", "front-right", "rear-right", "rear-left"]
    for index in range(rotor_count):
        name = names[index] if index < len(names) else f"rotor-{index + 1}"
        link_id = f"{name}-rotor-link"
        _add_link(frames, links, link_id=link_id, name=f"{name} rotor", parent_link_id="base-link", parent_frame_id="base-frame")
        joint_id = f"{name}-rotor-joint"
        actuator_id = f"{name}-rotor-actuator"
        joints.append(
            RobotJoint(
                joint_id=joint_id,
                name=f"{name} rotor joint",
                joint_type=JointType.CONTINUOUS,
                parent_link_id="base-link",
                child_link_id=link_id,
                actuator_id=actuator_id,
                firmware_joint_id=f"motor_{index + 1}",
                middleware_joint_name=joint_id,
                metadata={"spin_direction": "ccw" if index % 2 == 0 else "cw", "mixer_index": index},
            )
        )
        actuators.append(_make_actuator(actuator_id, joint_id, slots[index][1], lookup))
    return frames, links, joints, actuators


def _build_generic(
    topology_id: str,
    parts: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any],
    lookup: Mapping[str, str],
) -> tuple[list[CoordinateFrame], list[RobotLink], list[RobotJoint], list[RobotActuator]]:
    frames, links = _base_link(topology_id)
    actuator_parts = _actuator_parts(parts)
    count = sum(max(int(row.get("quantity") or 1), 1) for row in actuator_parts)
    slots = _expanded_part_slots(actuator_parts, count, "actuator")
    joints: list[RobotJoint] = []
    actuators: list[RobotActuator] = []
    for index, (_, part) in enumerate(slots):
        link_id = f"actuated-link-{index + 1}"
        _add_link(frames, links, link_id=link_id, name=link_id.replace("-", " "), parent_link_id="base-link", parent_frame_id="base-frame")
        joint_id = f"candidate-joint-{index + 1}"
        actuator_id = f"candidate-actuator-{index + 1}"
        joints.append(
            RobotJoint(
                joint_id=joint_id,
                name=joint_id.replace("-", " "),
                joint_type=JointType.REVOLUTE,
                parent_link_id="base-link",
                child_link_id=link_id,
                actuator_id=actuator_id,
                metadata={"topology_unresolved": True},
            )
        )
        actuators.append(_make_actuator(actuator_id, joint_id, part, lookup))
    return frames, links, joints, actuators


def build_robot_topology(
    intake: Mapping[str, Any],
    *,
    hinted_genre: str | None = None,
    machine_project: MachineProject | None = None,
) -> RobotTopology:
    body = dict(intake or {})
    parts = _parts(body)
    constraints = _constraints(body)
    goal = str(body.get("goal") or body.get("intent") or body.get("brief") or "robot")
    genre = detect_robot_genre(goal, parts, hinted=hinted_genre)
    project_name = str(body.get("project_name") or body.get("name") or goal)
    topology_id = _stable_id("topology", project_name, genre.value)
    lookup = _component_lookup(machine_project)

    if genre == RobotGenre.ROVER:
        frames, links, joints, actuators = _build_rover(topology_id, parts, constraints, lookup)
    elif genre == RobotGenre.QUADRUPED:
        frames, links, joints, actuators = _build_quadruped(topology_id, parts, constraints, lookup)
    elif genre == RobotGenre.SERIAL_MANIPULATOR:
        frames, links, joints, actuators = _build_arm(topology_id, parts, constraints, lookup)
    elif genre == RobotGenre.AERIAL:
        frames, links, joints, actuators = _build_aerial(topology_id, parts, constraints, lookup)
    else:
        frames, links, joints, actuators = _build_generic(topology_id, parts, constraints, lookup)

    sensors: list[RobotSensor] = []
    for index, part in enumerate(_sensor_parts(parts)):
        sensor_id = _slug(str(part.get("component_id") or part.get("module_id") or part.get("name") or f"sensor-{index + 1}"), f"sensor-{index + 1}")
        frame_id = f"{sensor_id}-frame"
        frames.append(
            CoordinateFrame(
                frame_id=frame_id,
                parent_frame_id="base-frame",
                attached_object_id=sensor_id,
                metadata={"mount_pose_unresolved": True},
            )
        )
        sensors.append(
            RobotSensor(
                sensor_id=sensor_id,
                name=str(part.get("name") or sensor_id),
                sensor_type=str(part.get("type") or part.get("role") or "sensor"),
                frame_id=frame_id,
                source_part_id=str(part.get("component_id") or part.get("module_id") or "").strip() or None,
                electrical_component_id=_part_component_id(part, lookup),
                firmware_sensor_id=f"fw-{sensor_id}",
                middleware_interfaces=[f"sensor/{sensor_id}"],
                metadata={"source_part_declared": bool(part.get("component_id") or part.get("module_id"))},
            )
        )

    unresolved: list[Dict[str, Any]] = []
    for joint in joints:
        if not joint.limits:
            unresolved.append({"object_id": joint.joint_id, "field": "limits", "reason": "Joint limits require design or measurement evidence."})
    for actuator in actuators:
        if not actuator.source_part_id:
            unresolved.append({"object_id": actuator.actuator_id, "field": "source_part_id", "reason": "Topology requires an actuator role, but no declared structured actuator part is bound to this slot."})
    for sensor in sensors:
        if not sensor.source_part_id:
            unresolved.append({"object_id": sensor.sensor_id, "field": "source_part_id", "reason": "Sensor role is structurally declared, but no stable component/module identity is bound."})
        unresolved.append({"object_id": sensor.sensor_id, "field": "mount_pose", "reason": "Sensor pose requires CAD or measured mounting evidence."})
    if genre == RobotGenre.GENERIC:
        unresolved.append({"object_id": topology_id, "field": "robot_genre", "reason": "Native robot topology could not be resolved."})

    from .integrations.llm_policy import offline_salvage_enabled

    return RobotTopology(
        topology_id=topology_id,
        robot_genre=genre,
        root_link_id="base-link",
        frames=frames,
        links=links,
        joints=joints,
        actuators=actuators,
        sensors=sensors,
        unresolved=unresolved,
        metadata={
            "candidate_only": True,
            "physical_fit_verified": False,
            "calibration_verified": False,
            "motion_authorized": False,
            "degree_of_freedom_count": sum(row.joint_type != JointType.FIXED for row in joints),
            "part_role_projection": "legacy_name_keyword" if offline_salvage_enabled() else "declared_structured_fields_only",
        },
    )

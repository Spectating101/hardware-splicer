"""Bounded import of structured robot models into canonical RobotTopology.

URDF, SDF, and MJCF are treated as declared design sources. Parsing preserves model
identity and relationships but does not verify mass properties, collision geometry,
actuator ratings, calibration, or physical agreement with a built robot.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .machine_project import AuthorityState
from .robot_topology import (
    CoordinateFrame,
    JointType,
    RobotActuator,
    RobotGenre,
    RobotJoint,
    RobotLink,
    RobotTopology,
)


ROBOT_MODEL_SCHEMA = "hardware_splicer.parsed_robot_model.v1"
MAX_ROBOT_MODEL_BYTES = 5 * 1024 * 1024


class RobotModelFormat(str, Enum):
    URDF = "urdf"
    SDF = "sdf"
    MJCF = "mjcf"


class RobotModelBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ParsedRobotLink(RobotModelBase):
    link_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    mass_kg: float | None = Field(default=None, ge=0.0)
    inertial_origin: Dict[str, Any] = Field(default_factory=dict)
    visual_refs: list[str] = Field(default_factory=list)
    collision_refs: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ParsedRobotJoint(RobotModelBase):
    joint_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    joint_type: JointType
    parent_link_id: str = Field(min_length=1)
    child_link_id: str = Field(min_length=1)
    axis: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0], min_length=3, max_length=3)
    limits: Dict[str, Any] = Field(default_factory=dict)
    origin: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ParsedRobotActuator(RobotModelBase):
    actuator_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    joint_id: str = Field(min_length=1)
    actuator_type: str = "actuator"
    reduction: float | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ParsedRobotModel(RobotModelBase):
    schema_version: str = ROBOT_MODEL_SCHEMA
    model_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    model_format: RobotModelFormat
    content_hash: str = Field(min_length=1)
    links: list[ParsedRobotLink] = Field(min_length=1)
    joints: list[ParsedRobotJoint] = Field(default_factory=list)
    actuators: list[ParsedRobotActuator] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_model_references(self) -> "ParsedRobotModel":
        link_ids = [row.link_id for row in self.links]
        joint_ids = [row.joint_id for row in self.joints]
        actuator_ids = [row.actuator_id for row in self.actuators]
        for label, values in (("link", link_ids), ("joint", joint_ids), ("actuator", actuator_ids)):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} identifier")
        link_set = set(link_ids)
        joint_set = set(joint_ids)
        for joint in self.joints:
            if joint.parent_link_id not in link_set or joint.child_link_id not in link_set:
                raise ValueError(f"joint {joint.joint_id!r} references an unknown link")
        for actuator in self.actuators:
            if actuator.joint_id not in joint_set:
                raise ValueError(f"actuator {actuator.actuator_id!r} references an unknown joint")
        return self


class RobotModelImportError(ValueError):
    pass


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _first(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in list(element) if _local_name(child.tag) == name), None)


def _slug(value: str, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._").lower()
    return token[:120] or fallback


def _vector(value: str | None, default: list[float]) -> list[float]:
    if not value:
        return list(default)
    try:
        values = [float(item) for item in value.replace(",", " ").split()]
    except ValueError:
        return list(default)
    if len(values) < len(default):
        values.extend(default[len(values) :])
    return values[: len(default)]


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _origin(element: ET.Element | None) -> Dict[str, Any]:
    if element is None:
        return {}
    return {
        "xyz": _vector(element.attrib.get("xyz") or element.attrib.get("pos"), [0.0, 0.0, 0.0]),
        "rpy": _vector(element.attrib.get("rpy") or element.attrib.get("euler"), [0.0, 0.0, 0.0]),
    }


def _joint_type(value: str | None) -> JointType:
    token = str(value or "fixed").strip().lower()
    aliases = {
        "hinge": JointType.REVOLUTE,
        "slide": JointType.PRISMATIC,
        "ball": JointType.FLOATING,
        "free": JointType.FLOATING,
    }
    if token in aliases:
        return aliases[token]
    try:
        return JointType(token)
    except ValueError:
        return JointType.REVOLUTE


def _mesh_refs(element: ET.Element, child_name: str) -> list[str]:
    refs: list[str] = []
    for child in _children(element, child_name):
        geometry = _first(child, "geometry")
        if geometry is None:
            continue
        for primitive in list(geometry):
            tag = _local_name(primitive.tag)
            uri = (
                primitive.attrib.get("filename")
                or primitive.attrib.get("uri")
                or (primitive.text or "").strip()
            )
            refs.append(f"{tag}:{uri}" if uri else tag)
    return refs


def _parse_urdf(root: ET.Element, content_hash: str) -> ParsedRobotModel:
    if _local_name(root.tag) != "robot":
        raise RobotModelImportError("URDF root must be <robot>")
    model_name = root.attrib.get("name") or "urdf-robot"
    links: list[ParsedRobotLink] = []
    joints: list[ParsedRobotJoint] = []
    actuators: list[ParsedRobotActuator] = []
    for index, element in enumerate(_children(root, "link")):
        name = element.attrib.get("name") or f"link-{index + 1}"
        inertial = _first(element, "inertial")
        mass_element = _first(inertial, "mass") if inertial is not None else None
        mass = _number(mass_element.attrib.get("value")) if mass_element is not None else None
        links.append(
            ParsedRobotLink(
                link_id=_slug(name, f"link-{index + 1}"),
                name=name,
                mass_kg=mass,
                inertial_origin=_origin(_first(inertial, "origin") if inertial is not None else None),
                visual_refs=_mesh_refs(element, "visual"),
                collision_refs=_mesh_refs(element, "collision"),
            )
        )
    link_name_to_id = {row.name: row.link_id for row in links}
    link_name_to_id.update({row.link_id: row.link_id for row in links})
    for index, element in enumerate(_children(root, "joint")):
        name = element.attrib.get("name") or f"joint-{index + 1}"
        parent = _first(element, "parent")
        child = _first(element, "child")
        if parent is None or child is None:
            raise RobotModelImportError(f"URDF joint {name!r} is missing parent or child")
        parent_name = parent.attrib.get("link") or ""
        child_name = child.attrib.get("link") or ""
        axis_element = _first(element, "axis")
        limit_element = _first(element, "limit")
        limits = {
            key: value
            for key, value in {
                "lower": _number(limit_element.attrib.get("lower")) if limit_element is not None else None,
                "upper": _number(limit_element.attrib.get("upper")) if limit_element is not None else None,
                "effort": _number(limit_element.attrib.get("effort")) if limit_element is not None else None,
                "velocity": _number(limit_element.attrib.get("velocity")) if limit_element is not None else None,
            }.items()
            if value is not None
        }
        joints.append(
            ParsedRobotJoint(
                joint_id=_slug(name, f"joint-{index + 1}"),
                name=name,
                joint_type=_joint_type(element.attrib.get("type")),
                parent_link_id=link_name_to_id.get(parent_name, _slug(parent_name, "parent-link")),
                child_link_id=link_name_to_id.get(child_name, _slug(child_name, "child-link")),
                axis=_vector(axis_element.attrib.get("xyz") if axis_element is not None else None, [0.0, 0.0, 1.0]),
                limits=limits,
                origin=_origin(_first(element, "origin")),
            )
        )
    for index, transmission in enumerate(_children(root, "transmission")):
        joint_element = _first(transmission, "joint")
        actuator_element = _first(transmission, "actuator")
        joint_name = joint_element.attrib.get("name") if joint_element is not None else None
        actuator_name = actuator_element.attrib.get("name") if actuator_element is not None else None
        if not joint_name:
            continue
        reduction_element = _first(actuator_element, "mechanicalReduction") if actuator_element is not None else None
        actuators.append(
            ParsedRobotActuator(
                actuator_id=_slug(actuator_name or f"actuator-{index + 1}", f"actuator-{index + 1}"),
                name=actuator_name or f"actuator-{index + 1}",
                joint_id=_slug(joint_name, f"joint-{index + 1}"),
                actuator_type="urdf_transmission",
                reduction=_number(reduction_element.text) if reduction_element is not None else None,
                metadata={"transmission_name": transmission.attrib.get("name")},
            )
        )
    return ParsedRobotModel(
        model_id=_slug(model_name, "urdf-robot"),
        name=model_name,
        model_format=RobotModelFormat.URDF,
        content_hash=content_hash,
        links=links,
        joints=joints,
        actuators=actuators,
    )


def _parse_sdf(root: ET.Element, content_hash: str) -> ParsedRobotModel:
    model = root if _local_name(root.tag) == "model" else next(
        (element for element in root.iter() if _local_name(element.tag) == "model"),
        None,
    )
    if model is None:
        raise RobotModelImportError("SDF must contain a <model>")
    model_name = model.attrib.get("name") or "sdf-robot"
    links = [
        ParsedRobotLink(
            link_id=_slug(element.attrib.get("name") or f"link-{index + 1}", f"link-{index + 1}"),
            name=element.attrib.get("name") or f"link-{index + 1}",
            mass_kg=_number((_first(_first(element, "inertial"), "mass").text if _first(element, "inertial") is not None and _first(_first(element, "inertial"), "mass") is not None else None)),
            visual_refs=_mesh_refs(element, "visual"),
            collision_refs=_mesh_refs(element, "collision"),
        )
        for index, element in enumerate(_children(model, "link"))
    ]
    link_map = {row.name: row.link_id for row in links}
    link_map.update({row.link_id: row.link_id for row in links})
    joints: list[ParsedRobotJoint] = []
    for index, element in enumerate(_children(model, "joint")):
        name = element.attrib.get("name") or f"joint-{index + 1}"
        parent_element = _first(element, "parent")
        child_element = _first(element, "child")
        parent_name = (parent_element.text or "").strip() if parent_element is not None else ""
        child_name = (child_element.text or "").strip() if child_element is not None else ""
        axis_element = _first(element, "axis")
        xyz_element = _first(axis_element, "xyz") if axis_element is not None else None
        limit_element = _first(axis_element, "limit") if axis_element is not None else None
        limits = {}
        if limit_element is not None:
            for key in ("lower", "upper", "effort", "velocity"):
                item = _first(limit_element, key)
                value = _number(item.text) if item is not None else None
                if value is not None:
                    limits[key] = value
        joints.append(
            ParsedRobotJoint(
                joint_id=_slug(name, f"joint-{index + 1}"),
                name=name,
                joint_type=_joint_type(element.attrib.get("type")),
                parent_link_id=link_map.get(parent_name, _slug(parent_name, "parent-link")),
                child_link_id=link_map.get(child_name, _slug(child_name, "child-link")),
                axis=_vector(xyz_element.text if xyz_element is not None else None, [0.0, 0.0, 1.0]),
                limits=limits,
            )
        )
    return ParsedRobotModel(
        model_id=_slug(model_name, "sdf-robot"),
        name=model_name,
        model_format=RobotModelFormat.SDF,
        content_hash=content_hash,
        links=links,
        joints=joints,
    )


def _parse_mjcf(root: ET.Element, content_hash: str) -> ParsedRobotModel:
    if _local_name(root.tag) != "mujoco":
        raise RobotModelImportError("MJCF root must be <mujoco>")
    model_name = root.attrib.get("model") or "mjcf-robot"
    worldbody = next((element for element in root.iter() if _local_name(element.tag) == "worldbody"), None)
    if worldbody is None:
        raise RobotModelImportError("MJCF must contain <worldbody>")
    links: list[ParsedRobotLink] = [ParsedRobotLink(link_id="world", name="world")]
    joints: list[ParsedRobotJoint] = []

    def walk(parent_link_id: str, parent: ET.Element) -> None:
        for body_index, body in enumerate(_children(parent, "body")):
            name = body.attrib.get("name") or f"body-{len(links)}"
            link_id = _slug(name, f"body-{len(links)}")
            links.append(
                ParsedRobotLink(
                    link_id=link_id,
                    name=name,
                    metadata={"pos": _vector(body.attrib.get("pos"), [0.0, 0.0, 0.0])},
                )
            )
            body_joints = _children(body, "joint")
            if body_joints:
                for joint_index, element in enumerate(body_joints):
                    joint_name = element.attrib.get("name") or f"{name}-joint-{joint_index + 1}"
                    limits = {}
                    range_values = _vector(element.attrib.get("range"), [])
                    if len(range_values) >= 2:
                        limits = {"lower": range_values[0], "upper": range_values[1]}
                    joints.append(
                        ParsedRobotJoint(
                            joint_id=_slug(joint_name, f"joint-{len(joints) + 1}"),
                            name=joint_name,
                            joint_type=_joint_type(element.attrib.get("type") or "hinge"),
                            parent_link_id=parent_link_id,
                            child_link_id=link_id,
                            axis=_vector(element.attrib.get("axis"), [0.0, 0.0, 1.0]),
                            limits=limits,
                            origin={"xyz": _vector(element.attrib.get("pos"), [0.0, 0.0, 0.0])},
                        )
                    )
            else:
                joints.append(
                    ParsedRobotJoint(
                        joint_id=f"fixed-{parent_link_id}-{link_id}",
                        name=f"fixed {parent_link_id} to {link_id}",
                        joint_type=JointType.FIXED,
                        parent_link_id=parent_link_id,
                        child_link_id=link_id,
                    )
                )
            walk(link_id, body)

    walk("world", worldbody)
    actuators: list[ParsedRobotActuator] = []
    actuator_root = next((element for element in root.iter() if _local_name(element.tag) == "actuator"), None)
    if actuator_root is not None:
        for index, element in enumerate(list(actuator_root)):
            joint_name = element.attrib.get("joint")
            if not joint_name:
                continue
            name = element.attrib.get("name") or f"actuator-{index + 1}"
            actuators.append(
                ParsedRobotActuator(
                    actuator_id=_slug(name, f"actuator-{index + 1}"),
                    name=name,
                    joint_id=_slug(joint_name, f"joint-{index + 1}"),
                    actuator_type=_local_name(element.tag),
                    metadata=dict(element.attrib),
                )
            )
    return ParsedRobotModel(
        model_id=_slug(model_name, "mjcf-robot"),
        name=model_name,
        model_format=RobotModelFormat.MJCF,
        content_hash=content_hash,
        links=links,
        joints=joints,
        actuators=actuators,
    )


def parse_robot_model(content: str | bytes, model_format: str | RobotModelFormat) -> ParsedRobotModel:
    raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    if len(raw) > MAX_ROBOT_MODEL_BYTES:
        raise RobotModelImportError("robot model exceeds maximum accepted size")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise RobotModelImportError("DTD and entity declarations are not accepted")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RobotModelImportError(f"invalid robot model XML: {exc}") from exc
    try:
        resolved_format = model_format if isinstance(model_format, RobotModelFormat) else RobotModelFormat(str(model_format).strip().lower())
    except ValueError as exc:
        raise RobotModelImportError(f"unsupported robot model format: {model_format}") from exc
    content_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    if resolved_format == RobotModelFormat.URDF:
        return _parse_urdf(root, content_hash)
    if resolved_format == RobotModelFormat.SDF:
        return _parse_sdf(root, content_hash)
    return _parse_mjcf(root, content_hash)


def infer_model_genre(model: ParsedRobotModel) -> RobotGenre:
    text = " ".join(
        [model.name]
        + [row.name for row in model.links]
        + [row.name for row in model.joints]
        + [row.name for row in model.actuators]
    ).lower()
    if any(token in text for token in ("wheel", "caster", "mecanum", "track")):
        return RobotGenre.ROVER
    if any(token in text for token in ("rotor", "propeller", "quadrotor")):
        return RobotGenre.AERIAL
    leg_markers = sum(token in text for token in ("front_left", "front-left", "rear_left", "rear-left", "front_right", "front-right", "rear_right", "rear-right"))
    if leg_markers >= 3 or ("hip" in text and "knee" in text and len(model.joints) >= 8):
        return RobotGenre.QUADRUPED
    movable = [row for row in model.joints if row.joint_type != JointType.FIXED]
    child_counts: dict[str, int] = {}
    for joint in movable:
        child_counts[joint.parent_link_id] = child_counts.get(joint.parent_link_id, 0) + 1
    if 3 <= len(movable) <= 12 and max(child_counts.values(), default=0) <= 2:
        return RobotGenre.SERIAL_MANIPULATOR
    return RobotGenre.GENERIC


def topology_from_robot_model(
    model: ParsedRobotModel,
    *,
    robot_genre: RobotGenre | None = None,
) -> RobotTopology:
    genre = robot_genre or infer_model_genre(model)
    parent_by_child = {row.child_link_id: row.parent_link_id for row in model.joints}
    root_candidates = [row.link_id for row in model.links if row.link_id not in parent_by_child]
    root_link_id = root_candidates[0] if root_candidates else model.links[0].link_id
    frames = [
        CoordinateFrame(
            frame_id=f"{row.link_id}-frame",
            parent_frame_id=(f"{parent_by_child[row.link_id]}-frame" if row.link_id in parent_by_child else None),
            attached_object_id=row.link_id,
            authority=AuthorityState.DECLARED,
        )
        for row in model.links
    ]
    links = [
        RobotLink(
            link_id=row.link_id,
            name=row.name,
            parent_link_id=parent_by_child.get(row.link_id),
            frame_id=f"{row.link_id}-frame",
            mass_kg=row.mass_kg,
            collision_geometry_refs=row.collision_refs,
            authority=AuthorityState.DECLARED,
            metadata={
                "source_model_id": model.model_id,
                "visual_refs": row.visual_refs,
                "inertial_origin": row.inertial_origin,
                **row.metadata,
            },
        )
        for row in model.links
    ]
    parsed_actuators = {row.joint_id: row for row in model.actuators}
    actuators: list[RobotActuator] = []
    joints: list[RobotJoint] = []
    for row in model.joints:
        parsed_actuator = parsed_actuators.get(row.joint_id)
        actuator_id = parsed_actuator.actuator_id if parsed_actuator else (
            f"actuator-{row.joint_id}" if row.joint_type != JointType.FIXED else None
        )
        joints.append(
            RobotJoint(
                joint_id=row.joint_id,
                name=row.name,
                joint_type=row.joint_type,
                parent_link_id=row.parent_link_id,
                child_link_id=row.child_link_id,
                axis=row.axis,
                limits=row.limits,
                actuator_id=actuator_id,
                firmware_joint_id=row.joint_id.replace("-", "_"),
                middleware_joint_name=row.name,
                calibration_ref=None,
                authority=AuthorityState.DECLARED,
                metadata={"source_model_id": model.model_id, "origin": row.origin, **row.metadata},
            )
        )
        if actuator_id:
            actuators.append(
                RobotActuator(
                    actuator_id=actuator_id,
                    name=parsed_actuator.name if parsed_actuator else f"Actuator for {row.name}",
                    actuator_type=parsed_actuator.actuator_type if parsed_actuator else "candidate_actuator",
                    joint_ids=[row.joint_id],
                    firmware_channel_id=f"fw-{row.joint_id}",
                    command_interface=f"command/{row.joint_id}",
                    feedback_interface=f"state/{row.joint_id}",
                    authority=AuthorityState.PROPOSED,
                    metadata={
                        "source_model_id": model.model_id,
                        "declared_in_model": parsed_actuator is not None,
                        "reduction": parsed_actuator.reduction if parsed_actuator else None,
                    },
                )
            )
    unresolved: list[Dict[str, Any]] = []
    for row in joints:
        if row.joint_type != JointType.FIXED and not row.limits:
            unresolved.append({"object_id": row.joint_id, "field": "limits", "reason": "Robot model does not declare complete joint limits."})
        if row.joint_type != JointType.FIXED:
            unresolved.append({"object_id": row.joint_id, "field": "calibration_ref", "reason": "Imported design model does not prove physical joint calibration."})
    return RobotTopology(
        topology_id=f"model-{model.model_id}-{model.content_hash.split(':')[-1][:12]}",
        robot_genre=genre,
        root_link_id=root_link_id,
        frames=frames,
        links=links,
        joints=joints,
        actuators=actuators,
        sensors=[],
        unresolved=unresolved,
        metadata={
            "source_model_id": model.model_id,
            "source_model_format": model.model_format.value,
            "source_content_hash": model.content_hash,
            "candidate_only": True,
            "physical_fit_verified": False,
            "calibration_verified": False,
            "motion_authorized": False,
        },
    )

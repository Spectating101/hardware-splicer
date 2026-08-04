"""Bounded URDF, SDF, and MJCF import into canonical robot topology.

Imported XML is declared design evidence. It can establish model relationships and
identifiers, but never proves physical fit, calibration, actuator ratings, or safe
motion on a built machine.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Any, Dict

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
    def validate_references(self) -> "ParsedRobotModel":
        collections = {
            "link": [row.link_id for row in self.links],
            "joint": [row.joint_id for row in self.joints],
            "actuator": [row.actuator_id for row in self.actuators],
        }
        for label, values in collections.items():
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} identifier")
        link_ids = set(collections["link"])
        joint_ids = set(collections["joint"])
        for joint in self.joints:
            if joint.parent_link_id not in link_ids or joint.child_link_id not in link_ids:
                raise ValueError(f"joint {joint.joint_id!r} references an unknown link")
        for actuator in self.actuators:
            if actuator.joint_id not in joint_ids:
                raise ValueError(f"actuator {actuator.actuator_id!r} references an unknown joint")
        return self


class RobotModelImportError(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [child for child in list(element) if _local(child.tag) == name]


def _first(element: ET.Element | None, name: str) -> ET.Element | None:
    return next(iter(_children(element, name)), None)


def _descendant(element: ET.Element, name: str) -> ET.Element | None:
    return next((row for row in element.iter() if _local(row.tag) == name), None)


def _slug(value: str, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._").lower()
    return token[:120] or fallback


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _floats(value: str | None) -> list[float]:
    if not value:
        return []
    try:
        return [float(item) for item in value.replace(",", " ").split()]
    except ValueError:
        return []


def _vector(value: str | None, default: tuple[float, float, float]) -> list[float]:
    values = _floats(value)
    if len(values) != 3:
        return list(default)
    return values


def _range(value: str | None) -> Dict[str, float]:
    values = _floats(value)
    return {"lower": values[0], "upper": values[1]} if len(values) >= 2 else {}


def _origin(element: ET.Element | None) -> Dict[str, Any]:
    if element is None:
        return {}
    return {
        "xyz": _vector(element.attrib.get("xyz") or element.attrib.get("pos"), (0.0, 0.0, 0.0)),
        "rpy": _vector(element.attrib.get("rpy") or element.attrib.get("euler"), (0.0, 0.0, 0.0)),
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


def _geometry_refs(element: ET.Element, wrapper_name: str) -> list[str]:
    refs: list[str] = []
    for wrapper in _children(element, wrapper_name):
        geometry = _first(wrapper, "geometry")
        for primitive in list(geometry) if geometry is not None else []:
            kind = _local(primitive.tag)
            uri = primitive.attrib.get("filename") or primitive.attrib.get("uri")
            if not uri:
                uri_child = _first(primitive, "uri")
                uri = (uri_child.text or "").strip() if uri_child is not None else ""
            refs.append(f"{kind}:{uri}" if uri else kind)
    return refs


def _limits_from_attributes(element: ET.Element | None) -> Dict[str, float]:
    if element is None:
        return {}
    result: Dict[str, float] = {}
    for key in ("lower", "upper", "effort", "velocity"):
        value = _number(element.attrib.get(key))
        if value is not None:
            result[key] = value
    return result


def _limits_from_children(element: ET.Element | None) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for key in ("lower", "upper", "effort", "velocity"):
        child = _first(element, key)
        value = _number(child.text) if child is not None else None
        if value is not None:
            result[key] = value
    return result


def _parse_urdf(root: ET.Element, content_hash: str) -> ParsedRobotModel:
    if _local(root.tag) != "robot":
        raise RobotModelImportError("URDF root must be <robot>")
    model_name = root.attrib.get("name") or "urdf-robot"
    links: list[ParsedRobotLink] = []
    for index, element in enumerate(_children(root, "link")):
        name = element.attrib.get("name") or f"link-{index + 1}"
        inertial = _first(element, "inertial")
        mass_element = _first(inertial, "mass")
        links.append(
            ParsedRobotLink(
                link_id=_slug(name, f"link-{index + 1}"),
                name=name,
                mass_kg=_number(mass_element.attrib.get("value")) if mass_element is not None else None,
                inertial_origin=_origin(_first(inertial, "origin")),
                visual_refs=_geometry_refs(element, "visual"),
                collision_refs=_geometry_refs(element, "collision"),
            )
        )
    link_map = {row.name: row.link_id for row in links} | {row.link_id: row.link_id for row in links}
    joints: list[ParsedRobotJoint] = []
    for index, element in enumerate(_children(root, "joint")):
        name = element.attrib.get("name") or f"joint-{index + 1}"
        parent = _first(element, "parent")
        child = _first(element, "child")
        parent_name = parent.attrib.get("link") if parent is not None else None
        child_name = child.attrib.get("link") if child is not None else None
        if not parent_name or not child_name:
            raise RobotModelImportError(f"URDF joint {name!r} is missing parent or child")
        joints.append(
            ParsedRobotJoint(
                joint_id=_slug(name, f"joint-{index + 1}"),
                name=name,
                joint_type=_joint_type(element.attrib.get("type")),
                parent_link_id=link_map.get(parent_name, _slug(parent_name, "parent-link")),
                child_link_id=link_map.get(child_name, _slug(child_name, "child-link")),
                axis=_vector((_first(element, "axis") or ET.Element("axis")).attrib.get("xyz"), (0.0, 0.0, 1.0)),
                limits=_limits_from_attributes(_first(element, "limit")),
                origin=_origin(_first(element, "origin")),
            )
        )
    joint_ids = {row.name: row.joint_id for row in joints} | {row.joint_id: row.joint_id for row in joints}
    actuators: list[ParsedRobotActuator] = []
    for index, transmission in enumerate(_children(root, "transmission")):
        joint_element = _first(transmission, "joint")
        actuator_element = _first(transmission, "actuator")
        joint_name = joint_element.attrib.get("name") if joint_element is not None else None
        if not joint_name:
            continue
        actuator_name = actuator_element.attrib.get("name") if actuator_element is not None else None
        reduction = _first(actuator_element, "mechanicalReduction")
        actuators.append(
            ParsedRobotActuator(
                actuator_id=_slug(actuator_name or f"actuator-{index + 1}", f"actuator-{index + 1}"),
                name=actuator_name or f"actuator-{index + 1}",
                joint_id=joint_ids.get(joint_name, _slug(joint_name, f"joint-{index + 1}")),
                actuator_type="urdf_transmission",
                reduction=_number(reduction.text) if reduction is not None else None,
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
    model = root if _local(root.tag) == "model" else _descendant(root, "model")
    if model is None:
        raise RobotModelImportError("SDF must contain a <model>")
    model_name = model.attrib.get("name") or "sdf-robot"
    links: list[ParsedRobotLink] = []
    for index, element in enumerate(_children(model, "link")):
        name = element.attrib.get("name") or f"link-{index + 1}"
        inertial = _first(element, "inertial")
        mass_element = _first(inertial, "mass")
        links.append(
            ParsedRobotLink(
                link_id=_slug(name, f"link-{index + 1}"),
                name=name,
                mass_kg=_number(mass_element.text) if mass_element is not None else None,
                visual_refs=_geometry_refs(element, "visual"),
                collision_refs=_geometry_refs(element, "collision"),
            )
        )
    link_map = {row.name: row.link_id for row in links} | {row.link_id: row.link_id for row in links}
    joints: list[ParsedRobotJoint] = []
    for index, element in enumerate(_children(model, "joint")):
        name = element.attrib.get("name") or f"joint-{index + 1}"
        parent_element = _first(element, "parent")
        child_element = _first(element, "child")
        parent_name = (parent_element.text or "").strip() if parent_element is not None else ""
        child_name = (child_element.text or "").strip() if child_element is not None else ""
        if not parent_name or not child_name:
            raise RobotModelImportError(f"SDF joint {name!r} is missing parent or child")
        axis = _first(element, "axis")
        xyz = _first(axis, "xyz")
        joints.append(
            ParsedRobotJoint(
                joint_id=_slug(name, f"joint-{index + 1}"),
                name=name,
                joint_type=_joint_type(element.attrib.get("type")),
                parent_link_id=link_map.get(parent_name, _slug(parent_name, "parent-link")),
                child_link_id=link_map.get(child_name, _slug(child_name, "child-link")),
                axis=_vector(xyz.text if xyz is not None else None, (0.0, 0.0, 1.0)),
                limits=_limits_from_children(_first(axis, "limit")),
                origin={"pose": _floats((_first(element, "pose") or ET.Element("pose")).text)},
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
    if _local(root.tag) != "mujoco":
        raise RobotModelImportError("MJCF root must be <mujoco>")
    model_name = root.attrib.get("model") or "mjcf-robot"
    worldbody = _descendant(root, "worldbody")
    if worldbody is None:
        raise RobotModelImportError("MJCF must contain <worldbody>")
    links: list[ParsedRobotLink] = [ParsedRobotLink(link_id="world", name="world")]
    joints: list[ParsedRobotJoint] = []

    def walk(parent_link_id: str, parent: ET.Element) -> None:
        for body in _children(parent, "body"):
            name = body.attrib.get("name") or f"body-{len(links)}"
            link_id = _slug(name, f"body-{len(links)}")
            links.append(
                ParsedRobotLink(
                    link_id=link_id,
                    name=name,
                    metadata={"pos": _vector(body.attrib.get("pos"), (0.0, 0.0, 0.0))},
                )
            )
            body_joints = _children(body, "joint")
            if body_joints:
                for element in body_joints:
                    joint_name = element.attrib.get("name") or f"{name}-joint-{len(joints) + 1}"
                    joints.append(
                        ParsedRobotJoint(
                            joint_id=_slug(joint_name, f"joint-{len(joints) + 1}"),
                            name=joint_name,
                            joint_type=_joint_type(element.attrib.get("type") or "hinge"),
                            parent_link_id=parent_link_id,
                            child_link_id=link_id,
                            axis=_vector(element.attrib.get("axis"), (0.0, 0.0, 1.0)),
                            limits=_range(element.attrib.get("range")),
                            origin={"xyz": _vector(element.attrib.get("pos"), (0.0, 0.0, 0.0))},
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
    joint_map = {row.name: row.joint_id for row in joints} | {row.joint_id: row.joint_id for row in joints}
    actuators: list[ParsedRobotActuator] = []
    actuator_root = _descendant(root, "actuator")
    for index, element in enumerate(list(actuator_root) if actuator_root is not None else []):
        joint_name = element.attrib.get("joint")
        if not joint_name:
            continue
        name = element.attrib.get("name") or f"actuator-{index + 1}"
        actuators.append(
            ParsedRobotActuator(
                actuator_id=_slug(name, f"actuator-{index + 1}"),
                name=name,
                joint_id=joint_map.get(joint_name, _slug(joint_name, f"joint-{index + 1}")),
                actuator_type=_local(element.tag),
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
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise RobotModelImportError("DTD and entity declarations are not accepted")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RobotModelImportError(f"invalid robot model XML: {exc}") from exc
    try:
        resolved = model_format if isinstance(model_format, RobotModelFormat) else RobotModelFormat(str(model_format).strip().lower())
    except ValueError as exc:
        raise RobotModelImportError(f"unsupported robot model format: {model_format}") from exc
    content_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    if resolved == RobotModelFormat.URDF:
        return _parse_urdf(root, content_hash)
    if resolved == RobotModelFormat.SDF:
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
    leg_markers = sum(
        token in text
        for token in (
            "front_left",
            "front-left",
            "rear_left",
            "rear-left",
            "front_right",
            "front-right",
            "rear_right",
            "rear-right",
        )
    )
    if leg_markers >= 3 or ("hip" in text and "knee" in text and len(model.joints) >= 8):
        return RobotGenre.QUADRUPED
    movable = [row for row in model.joints if row.joint_type != JointType.FIXED]
    child_counts: dict[str, int] = {}
    for joint in movable:
        child_counts[joint.parent_link_id] = child_counts.get(joint.parent_link_id, 0) + 1
    if 1 <= len(movable) <= 12 and max(child_counts.values(), default=0) <= 2:
        return RobotGenre.SERIAL_MANIPULATOR
    return RobotGenre.GENERIC


def topology_from_robot_model(
    model: ParsedRobotModel,
    *,
    robot_genre: RobotGenre | None = None,
) -> RobotTopology:
    genre = robot_genre or infer_model_genre(model)
    parent_by_child = {row.child_link_id: row.parent_link_id for row in model.joints}
    roots = [row.link_id for row in model.links if row.link_id not in parent_by_child]
    root_link_id = roots[0] if roots else model.links[0].link_id
    frames = [
        CoordinateFrame(
            frame_id=f"{row.link_id}-frame",
            parent_frame_id=f"{parent_by_child[row.link_id]}-frame" if row.link_id in parent_by_child else None,
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
    actuator_by_joint = {row.joint_id: row for row in model.actuators}
    joints: list[RobotJoint] = []
    actuators: list[RobotActuator] = []
    for row in model.joints:
        parsed_actuator = actuator_by_joint.get(row.joint_id)
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
            unresolved.append(
                {
                    "object_id": row.joint_id,
                    "field": "limits",
                    "reason": "Robot model does not declare complete joint limits.",
                }
            )
        if row.joint_type != JointType.FIXED:
            unresolved.append(
                {
                    "object_id": row.joint_id,
                    "field": "calibration_ref",
                    "reason": "Imported design model does not prove physical joint calibration.",
                }
            )
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

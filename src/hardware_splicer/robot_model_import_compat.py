"""Compatibility corrections for bounded robot-model import.

ElementTree leaf elements are false-y, so expressions using ``element or fallback``
can discard a valid URDF axis or SDF pose. Some older source records also omit an
explicit format even though the XML root unambiguously identifies URDF, SDF, or
MJCF. This wrapper corrects both compatibility cases while leaving validation and
authority behavior owned by :mod:`hardware_splicer.robot_model_import`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from . import robot_model_import as _target


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [row for row in list(element) if _local(row.tag) == name]


def _first(element: ET.Element | None, name: str) -> ET.Element | None:
    return next(iter(_children(element, name)), None)


def _floats(value: str | None) -> list[float]:
    if not value:
        return []
    try:
        return [float(item) for item in value.replace(",", " ").split()]
    except ValueError:
        return []


def _vector(value: str | None, default: list[float]) -> list[float]:
    values = _floats(value)
    return values if len(values) == len(default) else list(default)


def _raw_bytes(content: str | bytes) -> bytes:
    return content.encode("utf-8") if isinstance(content, str) else bytes(content)


def _infer_model_format(root: ET.Element) -> str:
    root_name = _local(root.tag).strip().lower()
    if root_name == "robot":
        return "urdf"
    if root_name in {"sdf", "model"}:
        return "sdf"
    if root_name == "mujoco":
        return "mjcf"
    return ""


def _correct_urdf(model: Any, root: ET.Element) -> Any:
    axis_by_name: dict[str, list[float]] = {}
    for joint in _children(root, "joint"):
        name = joint.attrib.get("name")
        axis = _first(joint, "axis")
        if name and axis is not None and axis.attrib.get("xyz"):
            axis_by_name[name] = _vector(axis.attrib.get("xyz"), [0.0, 0.0, 1.0])
    if not axis_by_name:
        return model
    joints = [
        row.model_copy(update={"axis": axis_by_name.get(row.name, row.axis)}, deep=True)
        for row in model.joints
    ]
    return model.model_copy(update={"joints": joints}, deep=True)


def _correct_sdf(model: Any, root: ET.Element) -> Any:
    model_element = root if _local(root.tag) == "model" else next(
        (row for row in root.iter() if _local(row.tag) == "model"),
        None,
    )
    if model_element is None:
        return model
    corrections: dict[str, dict[str, Any]] = {}
    for joint in _children(model_element, "joint"):
        name = joint.attrib.get("name")
        if not name:
            continue
        axis_element = _first(joint, "axis")
        xyz = _first(axis_element, "xyz")
        pose = _first(joint, "pose")
        correction: dict[str, Any] = {}
        if xyz is not None and xyz.text:
            correction["axis"] = _vector(xyz.text, [0.0, 0.0, 1.0])
        if pose is not None and pose.text:
            correction["origin"] = {"pose": _floats(pose.text)}
        if correction:
            corrections[name] = correction
    if not corrections:
        return model
    joints = [
        row.model_copy(update=corrections.get(row.name, {}), deep=True)
        for row in model.joints
    ]
    return model.model_copy(update={"joints": joints}, deep=True)


def install_robot_model_leaf_compatibility() -> None:
    if getattr(_target, "_leaf_element_compatibility_installed", False):
        return
    original = _target.parse_robot_model

    def parse_robot_model(content: str | bytes, model_format: Any):
        try:
            root = ET.fromstring(_raw_bytes(content))
        except ET.ParseError:
            return original(content, model_format)

        requested_format = model_format
        if not isinstance(model_format, _target.RobotModelFormat) and not str(model_format or "").strip():
            inferred_format = _infer_model_format(root)
            if inferred_format:
                requested_format = inferred_format

        model = original(content, requested_format)
        resolved = str(getattr(model.model_format, "value", model.model_format)).lower()
        if resolved == "urdf":
            return _correct_urdf(model, root)
        if resolved == "sdf":
            return _correct_sdf(model, root)
        return model

    _target.parse_robot_model = parse_robot_model
    _target._leaf_element_compatibility_installed = True


install_robot_model_leaf_compatibility()

"""Bounded mechanical pose, clearance, and fastener-stack checks.

These checks operate on declared mount normals, axis-aligned bounding boxes in one
explicit frame, and declared fastener dimensions. They do not claim full BREP
collision, deformation, thread strength, vibration endurance, or structural safety.
"""

from __future__ import annotations

from enum import Enum
from math import acos, degrees, sqrt
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .step_geometry import DeclaredMountInterface, MechanicalGeometryReport


MECHANICAL_FIT_SCHEMA = "hardware_splicer.mechanical_fit.v1"


class FitBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FitStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class ClearanceBox(FitBase):
    object_id: str = Field(min_length=1)
    frame_id: str = Field(min_length=1)
    minimum_mm: list[float] = Field(min_length=3, max_length=3)
    maximum_mm: list[float] = Field(min_length=3, max_length=3)
    source_model_id: str | None = None
    state: str = "declared"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def minimum_must_not_exceed_maximum(self) -> "ClearanceBox":
        if any(
            self.minimum_mm[index] > self.maximum_mm[index]
            for index in range(3)
        ):
            raise ValueError("clearance box minimum must not exceed maximum")
        return self


class ClearanceRequirement(FitBase):
    requirement_id: str = Field(min_length=1)
    first_object_id: str = Field(min_length=1)
    second_object_id: str = Field(min_length=1)
    minimum_clearance_mm: float = Field(default=0.0, ge=0.0)
    applicable_states: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FastenerStack(FitBase):
    stack_id: str = Field(min_length=1)
    fastener_spec: str = Field(min_length=1)
    fastener_length_mm: float = Field(gt=0.0)
    clamped_thicknesses_mm: list[float] = Field(min_length=1)
    non_thread_allowance_mm: float = Field(default=0.0, ge=0.0)
    required_thread_engagement_mm: float = Field(gt=0.0)
    maximum_thread_protrusion_mm: float | None = Field(default=None, ge=0.0)
    target_ids: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def thicknesses_must_be_positive(self) -> "FastenerStack":
        if any(value <= 0 for value in self.clamped_thicknesses_mm):
            raise ValueError("clamped thicknesses must be positive")
        return self


class MechanicalFitCheck(FitBase):
    check_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    status: FitStatus
    message: str = Field(min_length=1)
    target_ids: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    blocking: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MechanicalFitReport(FitBase):
    schema_version: str = MECHANICAL_FIT_SCHEMA
    project_id: str
    geometry_report_schema: str
    clearance_boxes: list[ClearanceBox] = Field(default_factory=list)
    clearance_requirements: list[ClearanceRequirement] = Field(default_factory=list)
    fastener_stacks: list[FastenerStack] = Field(default_factory=list)
    checks: list[MechanicalFitCheck] = Field(default_factory=list)
    status: str
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def blocking_checks(self) -> list[MechanicalFitCheck]:
        return [row for row in self.checks if row.blocking and row.status != FitStatus.PASS]


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-") or "item"


def _check(
    check_id: str,
    category: str,
    *,
    status: FitStatus,
    message: str,
    target_ids: Iterable[str] = (),
    unresolved_fields: Iterable[str] = (),
    blocking: bool = True,
    metadata: Mapping[str, Any] | None = None,
) -> MechanicalFitCheck:
    return MechanicalFitCheck(
        check_id=check_id,
        category=category,
        status=status,
        message=message,
        target_ids=list(dict.fromkeys(str(value) for value in target_ids if value)),
        unresolved_fields=list(dict.fromkeys(str(value) for value in unresolved_fields if value)),
        blocking=blocking,
        metadata=dict(metadata or {}),
    )


def _unit(vector: list[float] | None) -> list[float] | None:
    if vector is None:
        return None
    magnitude = sqrt(sum(value * value for value in vector))
    if magnitude <= 1e-12:
        return None
    return [value / magnitude for value in vector]


def _orientation_check(
    left: DeclaredMountInterface,
    right: DeclaredMountInterface,
    *,
    tolerance_deg: float,
) -> MechanicalFitCheck:
    left_normal = _unit(left.normal)
    right_normal = _unit(right.normal)
    check_id = f"mount-normal-{_slug(left.interface_id)}-{_slug(right.interface_id)}"
    if left_normal is None or right_normal is None:
        return _check(
            check_id,
            "mount_orientation",
            status=FitStatus.UNKNOWN,
            message="Mating surface normals are missing or degenerate.",
            target_ids=[left.interface_id, right.interface_id],
            unresolved_fields=["normal"],
        )
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(left_normal, right_normal))))
    angle = degrees(acos(dot))
    deviation = abs(180.0 - angle)
    passed = deviation <= tolerance_deg
    return _check(
        check_id,
        "mount_orientation",
        status=FitStatus.PASS if passed else FitStatus.FAIL,
        message=(
            f"Mating normals are anti-parallel within {tolerance_deg:g} degrees."
            if passed
            else f"Mating normals deviate {deviation:.3f} degrees from anti-parallel alignment."
        ),
        target_ids=[left.interface_id, right.interface_id],
        metadata={
            "angle_between_normals_deg": angle,
            "anti_parallel_deviation_deg": deviation,
            "tolerance_deg": tolerance_deg,
            "left_normal_unit": left_normal,
            "right_normal_unit": right_normal,
        },
    )


def _aabb_clearance(first: ClearanceBox, second: ClearanceBox) -> tuple[float, Dict[str, Any]]:
    separations = [
        max(
            second.minimum_mm[index] - first.maximum_mm[index],
            first.minimum_mm[index] - second.maximum_mm[index],
            0.0,
        )
        for index in range(3)
    ]
    if any(value > 0 for value in separations):
        clearance = sqrt(sum(value * value for value in separations))
        return clearance, {
            "separations_mm": separations,
            "overlap": False,
            "penetration_mm": 0.0,
        }
    overlap_depths = [
        min(first.maximum_mm[index], second.maximum_mm[index])
        - max(first.minimum_mm[index], second.minimum_mm[index])
        for index in range(3)
    ]
    if all(value > 0 for value in overlap_depths):
        penetration = min(overlap_depths)
        return -penetration, {
            "separations_mm": separations,
            "overlap": True,
            "penetration_mm": penetration,
            "overlap_depths_mm": overlap_depths,
        }
    return 0.0, {
        "separations_mm": separations,
        "overlap": False,
        "touching": True,
        "penetration_mm": 0.0,
    }


def _clearance_check(
    requirement: ClearanceRequirement,
    boxes: Mapping[str, ClearanceBox],
) -> MechanicalFitCheck:
    first = boxes.get(requirement.first_object_id)
    second = boxes.get(requirement.second_object_id)
    check_id = f"clearance-{_slug(requirement.requirement_id)}"
    if first is None or second is None:
        missing = [
            value
            for value, box in (
                (requirement.first_object_id, first),
                (requirement.second_object_id, second),
            )
            if box is None
        ]
        return _check(
            check_id,
            "aabb_clearance",
            status=FitStatus.UNKNOWN,
            message=f"Clearance boxes are missing for: {', '.join(missing)}.",
            target_ids=[requirement.first_object_id, requirement.second_object_id],
            unresolved_fields=["clearance_box"],
        )
    if first.frame_id != second.frame_id:
        return _check(
            check_id,
            "aabb_clearance",
            status=FitStatus.UNKNOWN,
            message=(
                f"Clearance boxes use different frames {first.frame_id!r} and {second.frame_id!r}; "
                "a relative transform is required."
            ),
            target_ids=[first.object_id, second.object_id],
            unresolved_fields=["relative_transform"],
        )
    applicable_states = set(requirement.applicable_states)
    if applicable_states and (
        first.state not in applicable_states or second.state not in applicable_states
    ):
        return _check(
            check_id,
            "aabb_clearance",
            status=FitStatus.UNKNOWN,
            message="Declared clearance boxes do not represent every required operating state.",
            target_ids=[first.object_id, second.object_id],
            unresolved_fields=["applicable_state_envelope"],
            metadata={
                "required_states": sorted(applicable_states),
                "first_state": first.state,
                "second_state": second.state,
            },
        )
    clearance, details = _aabb_clearance(first, second)
    passed = clearance >= requirement.minimum_clearance_mm
    return _check(
        check_id,
        "aabb_clearance",
        status=FitStatus.PASS if passed else FitStatus.FAIL,
        message=(
            f"AABB clearance {clearance:.3f} mm meets the {requirement.minimum_clearance_mm:.3f} mm requirement."
            if passed
            else f"AABB clearance {clearance:.3f} mm is below the {requirement.minimum_clearance_mm:.3f} mm requirement."
        ),
        target_ids=[first.object_id, second.object_id],
        metadata={
            **details,
            "clearance_mm": clearance,
            "minimum_clearance_mm": requirement.minimum_clearance_mm,
            "frame_id": first.frame_id,
            "aabb_only": True,
        },
    )


def _fastener_check(stack: FastenerStack) -> MechanicalFitCheck:
    clamped = sum(stack.clamped_thicknesses_mm)
    engagement = stack.fastener_length_mm - clamped - stack.non_thread_allowance_mm
    engagement_ok = engagement >= stack.required_thread_engagement_mm
    protrusion = max(0.0, engagement - stack.required_thread_engagement_mm)
    protrusion_ok = (
        stack.maximum_thread_protrusion_mm is None
        or protrusion <= stack.maximum_thread_protrusion_mm
    )
    passed = engagement_ok and protrusion_ok
    failures: list[str] = []
    if not engagement_ok:
        failures.append("thread engagement")
    if not protrusion_ok:
        failures.append("thread protrusion")
    return _check(
        f"fastener-stack-{_slug(stack.stack_id)}",
        "fastener_stack",
        status=FitStatus.PASS if passed else FitStatus.FAIL,
        message=(
            f"Fastener stack {stack.stack_id} provides {engagement:.3f} mm calculated engagement."
            if passed
            else f"Fastener stack {stack.stack_id} fails: {', '.join(failures)}."
        ),
        target_ids=[stack.stack_id, *stack.target_ids],
        metadata={
            "fastener_spec": stack.fastener_spec,
            "fastener_length_mm": stack.fastener_length_mm,
            "clamped_thickness_mm": clamped,
            "non_thread_allowance_mm": stack.non_thread_allowance_mm,
            "calculated_thread_engagement_mm": engagement,
            "required_thread_engagement_mm": stack.required_thread_engagement_mm,
            "calculated_thread_protrusion_mm": protrusion,
            "maximum_thread_protrusion_mm": stack.maximum_thread_protrusion_mm,
            "thread_strength_verified": False,
            "torque_verified": False,
        },
    )


def build_mechanical_fit_report(
    geometry: MechanicalGeometryReport | Mapping[str, Any],
    *,
    clearance_boxes: Iterable[ClearanceBox | Mapping[str, Any]] = (),
    clearance_requirements: Iterable[ClearanceRequirement | Mapping[str, Any]] = (),
    fastener_stacks: Iterable[FastenerStack | Mapping[str, Any]] = (),
    normal_tolerance_deg: float = 5.0,
) -> MechanicalFitReport:
    """Evaluate bounded fit checks from one mechanical geometry report."""

    if normal_tolerance_deg < 0 or normal_tolerance_deg > 90:
        raise ValueError("normal_tolerance_deg must be between 0 and 90")
    resolved_geometry = (
        geometry
        if isinstance(geometry, MechanicalGeometryReport)
        else MechanicalGeometryReport.model_validate(geometry)
    )
    boxes = [
        value if isinstance(value, ClearanceBox) else ClearanceBox.model_validate(value)
        for value in clearance_boxes
    ]
    requirements = [
        value
        if isinstance(value, ClearanceRequirement)
        else ClearanceRequirement.model_validate(value)
        for value in clearance_requirements
    ]
    stacks = [
        value if isinstance(value, FastenerStack) else FastenerStack.model_validate(value)
        for value in fastener_stacks
    ]
    checks: list[MechanicalFitCheck] = []
    mounts = {row.interface_id: row for row in resolved_geometry.mounts}
    visited: set[tuple[str, str]] = set()
    for mount in resolved_geometry.mounts:
        if not mount.mates_with or mount.mates_with not in mounts:
            continue
        mate = mounts[mount.mates_with]
        pair = tuple(sorted((mount.interface_id, mate.interface_id)))
        if pair in visited:
            continue
        checks.append(
            _orientation_check(mount, mate, tolerance_deg=normal_tolerance_deg)
        )
        visited.add(pair)

    box_by_id = {row.object_id: row for row in boxes}
    duplicate_box_ids = {
        row.object_id for row in boxes if sum(item.object_id == row.object_id for item in boxes) > 1
    }
    for object_id in sorted(duplicate_box_ids):
        checks.append(
            _check(
                f"clearance-box-identity-{_slug(object_id)}",
                "identity_collision",
                status=FitStatus.FAIL,
                message=f"Clearance box identity {object_id!r} is declared more than once.",
                target_ids=[object_id],
                unresolved_fields=["selected_clearance_box"],
            )
        )
    checks.extend(_clearance_check(row, box_by_id) for row in requirements)
    checks.extend(_fastener_check(row) for row in stacks)

    blocking = [row for row in checks if row.blocking and row.status != FitStatus.PASS]
    required_evidence = [
        {
            "check_id": row.check_id,
            "category": row.category,
            "target_ids": row.target_ids,
            "request": f"Capture fit evidence closing: {row.message}",
            "required_fields": row.unresolved_fields,
        }
        for row in blocking
    ]
    return MechanicalFitReport(
        project_id=resolved_geometry.project_id,
        geometry_report_schema=resolved_geometry.schema_version,
        clearance_boxes=boxes,
        clearance_requirements=requirements,
        fastener_stacks=stacks,
        checks=checks,
        status="blocked" if blocking else "candidate",
        required_evidence=required_evidence,
        metadata={
            "normal_tolerance_deg": normal_tolerance_deg,
            "orientation_check_count": len([row for row in checks if row.category == "mount_orientation"]),
            "clearance_check_count": len([row for row in checks if row.category == "aabb_clearance"]),
            "fastener_check_count": len([row for row in checks if row.category == "fastener_stack"]),
            "blocking_check_count": len(blocking),
            "aabb_only": True,
            "full_brep_collision": False,
            "deformation_analysis": False,
            "thread_strength_verified": False,
            "fabrication_authorized": False,
            "release_authorized": False,
        },
    )

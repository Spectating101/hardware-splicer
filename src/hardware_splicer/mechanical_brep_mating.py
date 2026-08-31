"""Pairwise mating geometry over exact, placed BREP surface anchors.

This module deliberately evaluates only geometry already established by two ready
surface-anchor reports. It does not infer connector protocol, pin compatibility,
engagement mechanics, retention, electrical safety, or fabrication authority.

The evaluator owns the math for:
- common-frame anchor separation;
- opposing surface-normal error;
- axial offset along either a declared mating axis or the first anchor normal;
- lateral offset relative to that axis;
- optional declared-axis alignment; and
- optional declared engagement-depth requirements.

A passing report means only "the supplied exact BREP anchors are within the declared
geometric tolerances." It never sets connector_mating_verified=True.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


BREP_MATING_SCHEMA = "hardware_splicer.brep_anchor_mating.v1"
MAX_MATING_DISTANCE_MM = 10_000.0
MAX_ANGLE_DEG = 180.0
_VECTOR_EPS = 1e-12


class BrepMatingStatus(str, Enum):
    READY = "ready"
    UNKNOWN = "unknown"


class BrepMatingBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BrepMatingAnchor(BrepMatingBase):
    anchor_id: str = Field(min_length=1)
    interface_id: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    placement_id: str = Field(min_length=1)
    frame_id: str = Field(min_length=1)
    anchor_point_mm: tuple[float, float, float]
    outward_normal: tuple[float, float, float]
    face_index: int = Field(ge=0)
    face_geom_type: str = Field(min_length=1)
    authority: Literal["declared"] = "declared"
    status: Literal["ready"] = "ready"
    kernel_surface_snap: Literal[True] = True
    connector_mating_verified: Literal[False] = False
    physical_measurement: Literal[False] = False
    fabrication_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_geometry(self) -> "BrepMatingAnchor":
        for field_name, values in (
            ("anchor_point_mm", self.anchor_point_mm),
            ("outward_normal", self.outward_normal),
        ):
            if not all(math.isfinite(float(value)) for value in values):
                raise ValueError(f"{field_name} must contain finite values")
        length = math.sqrt(sum(float(value) ** 2 for value in self.outward_normal))
        if abs(length - 1.0) > 1e-5:
            raise ValueError("outward_normal must be unit length")
        return self


class BrepMatingRequirements(BrepMatingBase):
    max_normal_opposition_error_deg: float = Field(default=5.0, ge=0, le=MAX_ANGLE_DEG)
    max_lateral_offset_mm: float = Field(default=0.5, ge=0, le=MAX_MATING_DISTANCE_MM)
    target_axial_offset_mm: float = Field(default=0.0, ge=-MAX_MATING_DISTANCE_MM, le=MAX_MATING_DISTANCE_MM)
    axial_offset_tolerance_mm: float = Field(default=0.5, ge=0, le=MAX_MATING_DISTANCE_MM)
    declared_mating_axis: tuple[float, float, float] | None = None
    max_axis_alignment_error_deg: float = Field(default=5.0, ge=0, le=MAX_ANGLE_DEG)
    required_engagement_depth_mm: float | None = Field(default=None, ge=0, le=MAX_MATING_DISTANCE_MM)
    declared_engagement_depth_mm: float | None = Field(default=None, ge=0, le=MAX_MATING_DISTANCE_MM)

    @model_validator(mode="after")
    def validate_requirements(self) -> "BrepMatingRequirements":
        if self.declared_mating_axis is not None:
            if not all(math.isfinite(float(value)) for value in self.declared_mating_axis):
                raise ValueError("declared_mating_axis must contain finite values")
            length = math.sqrt(sum(float(value) ** 2 for value in self.declared_mating_axis))
            if length <= _VECTOR_EPS:
                raise ValueError("declared_mating_axis must have non-zero length")
        if self.declared_engagement_depth_mm is not None and self.required_engagement_depth_mm is None:
            raise ValueError(
                "declared_engagement_depth_mm is only meaningful when required_engagement_depth_mm is supplied"
            )
        return self


class BrepAnchorMatingReport(BrepMatingBase):
    schema_version: str = BREP_MATING_SCHEMA
    project_id: str = Field(min_length=1)
    mating_id: str = Field(min_length=1)
    interface_id: str = Field(min_length=1)
    frame_id: str = Field(min_length=1)
    first_anchor_id: str = Field(min_length=1)
    second_anchor_id: str = Field(min_length=1)
    first_object_id: str = Field(min_length=1)
    second_object_id: str = Field(min_length=1)
    status: BrepMatingStatus
    geometric_mating_passed: bool | None = None
    anchor_separation_mm: float | None = Field(default=None, ge=0)
    normal_opposition_error_deg: float | None = Field(default=None, ge=0, le=MAX_ANGLE_DEG)
    mating_axis: tuple[float, float, float] | None = None
    mating_axis_source: Literal["declared", "first_anchor_normal"] | None = None
    signed_axial_offset_mm: float | None = None
    target_axial_offset_mm: float | None = None
    axial_offset_error_mm: float | None = Field(default=None, ge=0)
    axial_offset_passed: bool | None = None
    lateral_offset_mm: float | None = Field(default=None, ge=0)
    lateral_offset_passed: bool | None = None
    normal_opposition_passed: bool | None = None
    declared_axis_alignment_evaluated: bool = False
    first_axis_alignment_error_deg: float | None = Field(default=None, ge=0, le=MAX_ANGLE_DEG)
    second_axis_alignment_error_deg: float | None = Field(default=None, ge=0, le=MAX_ANGLE_DEG)
    axis_alignment_passed: bool | None = None
    coaxiality_evaluated: bool = False
    coaxial_offset_mm: float | None = Field(default=None, ge=0)
    engagement_evaluated: bool = False
    required_engagement_depth_mm: float | None = Field(default=None, ge=0)
    declared_engagement_depth_mm: float | None = Field(default=None, ge=0)
    engagement_passed: bool | None = None
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _vector(values: tuple[float, float, float]) -> tuple[float, float, float]:
    row = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in row):
        raise ValueError("vector values must be finite")
    return row


def _sub(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(left[index] - right[index] for index in range(3))  # type: ignore[return-value]


def _scale(
    vector: tuple[float, float, float],
    scalar: float,
) -> tuple[float, float, float]:
    return tuple(value * scalar for value in vector)  # type: ignore[return-value]


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(left[index] * right[index] for index in range(3))


def _norm(vector: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = _norm(vector)
    if length <= _VECTOR_EPS:
        raise ValueError("mating axis must have non-zero length")
    return tuple(value / length for value in vector)  # type: ignore[return-value]


def _angle_deg(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    cosine = max(-1.0, min(1.0, _dot(_normalize(left), _normalize(right))))
    return math.degrees(math.acos(cosine))


def _axis_alignment_error_deg(
    normal: tuple[float, float, float],
    axis: tuple[float, float, float],
) -> float:
    direct = _angle_deg(normal, axis)
    reverse = _angle_deg(normal, _scale(axis, -1.0))
    return min(direct, reverse)


def _base_metadata() -> Dict[str, Any]:
    return {
        "scope": "pairwise_exact_brep_surface_anchor_geometry",
        "input_anchor_authority": "declared",
        "connector_mating_verified": False,
        "protocol_compatibility_verified": False,
        "pin_compatibility_verified": False,
        "retention_verified": False,
        "engagement_kernel_inferred": False,
        "swept_engagement_collision": False,
        "whole_assembly_collision": False,
        "physical_measurement": False,
        "manufacturing_authorized": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def evaluate_brep_anchor_mating(
    *,
    project_id: str,
    mating_id: str,
    first: BrepMatingAnchor | Dict[str, Any],
    second: BrepMatingAnchor | Dict[str, Any],
    requirements: BrepMatingRequirements | Dict[str, Any] | None = None,
) -> BrepAnchorMatingReport:
    if not project_id.strip() or not mating_id.strip():
        raise ValueError("project_id and mating_id are required")
    first_anchor = first if isinstance(first, BrepMatingAnchor) else BrepMatingAnchor.model_validate(first)
    second_anchor = second if isinstance(second, BrepMatingAnchor) else BrepMatingAnchor.model_validate(second)
    resolved = (
        requirements
        if isinstance(requirements, BrepMatingRequirements)
        else BrepMatingRequirements.model_validate(requirements or {})
    )

    if first_anchor.anchor_id == second_anchor.anchor_id:
        raise ValueError("mating requires two distinct anchor identities")
    if first_anchor.object_id == second_anchor.object_id:
        raise ValueError("mating requires anchors on two distinct placed objects")
    if first_anchor.interface_id != second_anchor.interface_id:
        raise ValueError("mating anchors must bind the same interface_id")
    if first_anchor.frame_id != second_anchor.frame_id:
        return BrepAnchorMatingReport(
            project_id=project_id,
            mating_id=mating_id,
            interface_id=first_anchor.interface_id,
            frame_id=first_anchor.frame_id,
            first_anchor_id=first_anchor.anchor_id,
            second_anchor_id=second_anchor.anchor_id,
            first_object_id=first_anchor.object_id,
            second_object_id=second_anchor.object_id,
            status=BrepMatingStatus.UNKNOWN,
            required_evidence=[{
                "field": "common_frame",
                "reason": (
                    f"anchor frames differ: {first_anchor.frame_id!r} vs {second_anchor.frame_id!r}"
                ),
            }],
            metadata={**_base_metadata(), "common_frame": False},
        )

    first_point = _vector(first_anchor.anchor_point_mm)
    second_point = _vector(second_anchor.anchor_point_mm)
    first_normal = _normalize(_vector(first_anchor.outward_normal))
    second_normal = _normalize(_vector(second_anchor.outward_normal))
    delta = _sub(second_point, first_point)

    axis_source: Literal["declared", "first_anchor_normal"]
    if resolved.declared_mating_axis is not None:
        axis = _normalize(_vector(resolved.declared_mating_axis))
        axis_source = "declared"
    else:
        axis = first_normal
        axis_source = "first_anchor_normal"

    separation = _norm(delta)
    normal_opposition_error = _angle_deg(first_normal, _scale(second_normal, -1.0))
    normal_pass = normal_opposition_error <= resolved.max_normal_opposition_error_deg + 1e-12
    signed_axial = _dot(delta, axis)
    axial_error = abs(signed_axial - resolved.target_axial_offset_mm)
    axial_pass = axial_error <= resolved.axial_offset_tolerance_mm + 1e-12
    lateral_vector = _sub(delta, _scale(axis, signed_axial))
    lateral_offset = _norm(lateral_vector)
    lateral_pass = lateral_offset <= resolved.max_lateral_offset_mm + 1e-12

    axis_evaluated = resolved.declared_mating_axis is not None
    first_axis_error = _axis_alignment_error_deg(first_normal, axis) if axis_evaluated else None
    second_axis_error = _axis_alignment_error_deg(second_normal, axis) if axis_evaluated else None
    axis_pass = (
        first_axis_error is not None
        and second_axis_error is not None
        and first_axis_error <= resolved.max_axis_alignment_error_deg + 1e-12
        and second_axis_error <= resolved.max_axis_alignment_error_deg + 1e-12
    ) if axis_evaluated else None

    engagement_required = resolved.required_engagement_depth_mm is not None
    engagement_evaluated = engagement_required and resolved.declared_engagement_depth_mm is not None
    engagement_pass = (
        resolved.declared_engagement_depth_mm >= resolved.required_engagement_depth_mm - 1e-12
        if engagement_evaluated
        and resolved.declared_engagement_depth_mm is not None
        and resolved.required_engagement_depth_mm is not None
        else None
    )

    required_evidence: list[Dict[str, Any]] = []
    if engagement_required and not engagement_evaluated:
        required_evidence.append({
            "field": "declared_engagement_depth_mm",
            "reason": (
                "required_engagement_depth_mm was supplied, but anchor geometry alone cannot infer actual engagement depth"
            ),
        })

    checks: list[bool] = [normal_pass, axial_pass, lateral_pass]
    if axis_evaluated and axis_pass is not None:
        checks.append(axis_pass)
    if engagement_required:
        if engagement_pass is None:
            geometric_pass: bool | None = None
        else:
            checks.append(engagement_pass)
            geometric_pass = all(checks)
    else:
        geometric_pass = all(checks)

    return BrepAnchorMatingReport(
        project_id=project_id,
        mating_id=mating_id,
        interface_id=first_anchor.interface_id,
        frame_id=first_anchor.frame_id,
        first_anchor_id=first_anchor.anchor_id,
        second_anchor_id=second_anchor.anchor_id,
        first_object_id=first_anchor.object_id,
        second_object_id=second_anchor.object_id,
        status=BrepMatingStatus.UNKNOWN if geometric_pass is None else BrepMatingStatus.READY,
        geometric_mating_passed=geometric_pass,
        anchor_separation_mm=separation,
        normal_opposition_error_deg=normal_opposition_error,
        mating_axis=axis,
        mating_axis_source=axis_source,
        signed_axial_offset_mm=signed_axial,
        target_axial_offset_mm=resolved.target_axial_offset_mm,
        axial_offset_error_mm=axial_error,
        axial_offset_passed=axial_pass,
        lateral_offset_mm=lateral_offset,
        lateral_offset_passed=lateral_pass,
        normal_opposition_passed=normal_pass,
        declared_axis_alignment_evaluated=axis_evaluated,
        first_axis_alignment_error_deg=first_axis_error,
        second_axis_alignment_error_deg=second_axis_error,
        axis_alignment_passed=axis_pass,
        coaxiality_evaluated=axis_evaluated,
        coaxial_offset_mm=lateral_offset if axis_evaluated else None,
        engagement_evaluated=engagement_evaluated,
        required_engagement_depth_mm=resolved.required_engagement_depth_mm,
        declared_engagement_depth_mm=resolved.declared_engagement_depth_mm,
        engagement_passed=engagement_pass,
        required_evidence=required_evidence,
        metadata={
            **_base_metadata(),
            "common_frame": True,
            "mating_axis_source": axis_source,
            "coaxiality_requires_declared_axis": True,
            "engagement_depth_source": (
                "declared" if engagement_evaluated else "not_evaluated"
            ),
        },
    )

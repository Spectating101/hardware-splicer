"""Declared rigid placement for bounded STEP envelopes.

This module supplies the missing frame bridge between an imported STEP point envelope
and the mechanical fit engine. Placements are explicit declarations only: they can
move/rotate the eight corners of a coarse STEP AABB into one target frame, but they do
not establish BREP validity, collision truth, physical measurement, or fabrication
authority.
"""

from __future__ import annotations

from itertools import product
from math import cos, isfinite, radians, sin
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .machine_project import AuthorityState
from .mechanical_fit import ClearanceBox
from .step_geometry import StepModelSummary


PLACEMENT_SCHEMA = "hardware_splicer.declared_geometry_placement.v1"


class PlacementBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class DeclaredGeometryPlacement(PlacementBase):
    schema_version: str = PLACEMENT_SCHEMA
    placement_id: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    target_frame: str = Field(default="assembly", min_length=1)
    translation_mm: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    rotation_deg_xyz: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def placement_must_remain_declared_and_finite(self) -> "DeclaredGeometryPlacement":
        if self.authority != AuthorityState.DECLARED:
            raise ValueError("interactive geometry placement is declaration-only")
        if not all(isfinite(value) for value in [*self.translation_mm, *self.rotation_deg_xyz]):
            raise ValueError("placement translation and rotation must be finite")
        return self


def _bbox_mm(model: StepModelSummary) -> tuple[list[float], list[float]]:
    bbox = model.bounding_box
    if bbox is None:
        raise ValueError(f"STEP model {model.model_id!r} has no Cartesian-point bounding envelope")
    factor = 1.0 if bbox.units == "mm" else 1000.0 if bbox.units == "m" else None
    if factor is None:
        raise ValueError(
            f"STEP model {model.model_id!r} uses {bbox.units!r}; explicit mm or m units are required for placement"
        )
    return (
        [float(value) * factor for value in bbox.minimum],
        [float(value) * factor for value in bbox.maximum],
    )


def _rotation_matrix_xyz(rotation_deg_xyz: list[float]) -> list[list[float]]:
    """Return Rz * Ry * Rx for intrinsic XYZ angles, operating in canonical STEP XYZ."""

    rx, ry, rz = (radians(float(value)) for value in rotation_deg_xyz)
    cx, sx = cos(rx), sin(rx)
    cy, sy = cos(ry), sin(ry)
    cz, sz = cos(rz), sin(rz)
    return [
        [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
        [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
        [-sy, cy * sx, cy * cx],
    ]


def _transform_point(
    point: tuple[float, float, float],
    matrix: list[list[float]],
    translation: list[float],
) -> list[float]:
    return [
        sum(matrix[row][column] * point[column] for column in range(3)) + translation[row]
        for row in range(3)
    ]


def build_declared_placement_box(
    model: StepModelSummary,
    placement: DeclaredGeometryPlacement,
) -> ClearanceBox:
    """Transform one STEP AABB into a target-frame AABB using a declared rigid pose."""

    if placement.model_id != model.model_id:
        raise ValueError(
            f"placement {placement.placement_id!r} targets model {placement.model_id!r}, not {model.model_id!r}"
        )
    minimum, maximum = _bbox_mm(model)
    matrix = _rotation_matrix_xyz(placement.rotation_deg_xyz)
    corners = [
        _transform_point((x, y, z), matrix, placement.translation_mm)
        for x, y, z in product(
            (minimum[0], maximum[0]),
            (minimum[1], maximum[1]),
            (minimum[2], maximum[2]),
        )
    ]
    placed_minimum = [min(point[index] for point in corners) for index in range(3)]
    placed_maximum = [max(point[index] for point in corners) for index in range(3)]
    return ClearanceBox(
        object_id=placement.object_id,
        frame_id=placement.target_frame,
        minimum_mm=placed_minimum,
        maximum_mm=placed_maximum,
        source_model_id=model.model_id,
        state="declared_placement",
        metadata={
            "placement_id": placement.placement_id,
            "placement_authority": placement.authority.value,
            "translation_mm": list(placement.translation_mm),
            "rotation_deg_xyz": list(placement.rotation_deg_xyz),
            "rotation_convention": "Rz*Ry*Rx; canonical STEP XYZ",
            "source_content_hash": model.content_hash,
            "source_envelope_only": True,
            "full_brep_collision": False,
            "physical_measurement": False,
            "fabrication_authorized": False,
        },
    )

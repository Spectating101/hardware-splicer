"""Declared interface anchors and access envelopes over placed mechanical AABBs.

This module gives semantic machine interfaces a bounded spatial representation without
claiming a CAD/BREP kernel. An access declaration chooses a face on an already placed
object, locates an interface anchor on that face, and extrudes an axis-aligned access
prism outward from the object. The prism can be fed into the existing mechanical-fit
engine as a clearance box.

The primitive is deliberately narrow:
- the parent object must already be a ``declared_placement`` box;
- anchors are declaration-only and cannot be verified/authorized by this transform;
- the access prism is an AABB keep-out, not cable routing, connector mating, BREP
  collision truth, service ergonomics, or fabrication authority.
"""

from __future__ import annotations

from enum import Enum
from math import isfinite
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .machine_project import AuthorityState
from .mechanical_fit import ClearanceBox


INTERFACE_ACCESS_SCHEMA = "hardware_splicer.declared_interface_access.v1"


class AccessBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AccessFace(str, Enum):
    POS_X = "+x"
    NEG_X = "-x"
    POS_Y = "+y"
    NEG_Y = "-y"
    POS_Z = "+z"
    NEG_Z = "-z"


class DeclaredInterfaceAccess(AccessBase):
    schema_version: str = INTERFACE_ACCESS_SCHEMA
    access_id: str = Field(min_length=1)
    interface_id: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    frame_id: str = Field(default="assembly", min_length=1)
    face: AccessFace
    width_mm: float = Field(gt=0.0)
    height_mm: float = Field(gt=0.0)
    depth_mm: float = Field(gt=0.0)
    offset_u_mm: float = 0.0
    offset_v_mm: float = 0.0
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def access_must_remain_declared_and_finite(self) -> "DeclaredInterfaceAccess":
        if self.authority != AuthorityState.DECLARED:
            raise ValueError("interactive interface access geometry is declaration-only")
        values = [
            self.width_mm,
            self.height_mm,
            self.depth_mm,
            self.offset_u_mm,
            self.offset_v_mm,
        ]
        if not all(isfinite(value) for value in values):
            raise ValueError("interface access dimensions and offsets must be finite")
        return self


# face -> (normal axis, normal sign, tangent-u axis, tangent-v axis)
_FACE_AXES: dict[AccessFace, tuple[int, int, int, int]] = {
    AccessFace.POS_X: (0, 1, 1, 2),
    AccessFace.NEG_X: (0, -1, 1, 2),
    AccessFace.POS_Y: (1, 1, 0, 2),
    AccessFace.NEG_Y: (1, -1, 0, 2),
    AccessFace.POS_Z: (2, 1, 0, 1),
    AccessFace.NEG_Z: (2, -1, 0, 1),
}


def _center(minimum: list[float], maximum: list[float], axis: int) -> float:
    return (minimum[axis] + maximum[axis]) / 2.0


def build_declared_access_box(
    placed_box: ClearanceBox,
    access: DeclaredInterfaceAccess,
) -> ClearanceBox:
    """Build one outward access AABB from an explicitly placed parent object."""

    if placed_box.object_id != access.object_id:
        raise ValueError(
            f"access {access.access_id!r} targets object {access.object_id!r}, not {placed_box.object_id!r}"
        )
    if placed_box.frame_id != access.frame_id:
        raise ValueError(
            f"access {access.access_id!r} uses frame {access.frame_id!r}, not parent frame {placed_box.frame_id!r}"
        )
    if placed_box.state != "declared_placement":
        raise ValueError("interface access envelopes require an explicit declared-placement parent box")

    minimum = [float(value) for value in placed_box.minimum_mm]
    maximum = [float(value) for value in placed_box.maximum_mm]
    normal_axis, normal_sign, u_axis, v_axis = _FACE_AXES[access.face]

    anchor = [_center(minimum, maximum, axis) for axis in range(3)]
    anchor[normal_axis] = maximum[normal_axis] if normal_sign > 0 else minimum[normal_axis]
    anchor[u_axis] += access.offset_u_mm
    anchor[v_axis] += access.offset_v_mm

    if not (minimum[u_axis] <= anchor[u_axis] <= maximum[u_axis]):
        raise ValueError(
            f"access {access.access_id!r} anchor offset_u_mm places the anchor outside the parent face"
        )
    if not (minimum[v_axis] <= anchor[v_axis] <= maximum[v_axis]):
        raise ValueError(
            f"access {access.access_id!r} anchor offset_v_mm places the anchor outside the parent face"
        )

    access_minimum = list(anchor)
    access_maximum = list(anchor)
    access_minimum[u_axis] = anchor[u_axis] - access.width_mm / 2.0
    access_maximum[u_axis] = anchor[u_axis] + access.width_mm / 2.0
    access_minimum[v_axis] = anchor[v_axis] - access.height_mm / 2.0
    access_maximum[v_axis] = anchor[v_axis] + access.height_mm / 2.0
    if normal_sign > 0:
        access_minimum[normal_axis] = anchor[normal_axis]
        access_maximum[normal_axis] = anchor[normal_axis] + access.depth_mm
    else:
        access_minimum[normal_axis] = anchor[normal_axis] - access.depth_mm
        access_maximum[normal_axis] = anchor[normal_axis]

    normal = [0.0, 0.0, 0.0]
    normal[normal_axis] = float(normal_sign)
    return ClearanceBox(
        object_id=f"access:{access.access_id}",
        frame_id=access.frame_id,
        minimum_mm=access_minimum,
        maximum_mm=access_maximum,
        source_model_id=placed_box.source_model_id,
        state="declared_access_envelope",
        metadata={
            "schema_version": access.schema_version,
            "access_id": access.access_id,
            "interface_id": access.interface_id,
            "parent_object_id": access.object_id,
            "parent_placement_id": placed_box.metadata.get("placement_id"),
            "access_authority": access.authority.value,
            "face": access.face.value,
            "anchor_point_mm": anchor,
            "outward_normal": normal,
            "width_mm": access.width_mm,
            "height_mm": access.height_mm,
            "depth_mm": access.depth_mm,
            "offset_u_mm": access.offset_u_mm,
            "offset_v_mm": access.offset_v_mm,
            "aabb_only": True,
            "cable_routing_verified": False,
            "connector_mating_verified": False,
            "service_access_verified": False,
            "full_brep_collision": False,
            "physical_measurement": False,
            "fabrication_authorized": False,
        },
    )

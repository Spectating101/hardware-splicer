from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ServoDims:
    name: str
    body_w_mm: float
    body_h_mm: float
    body_d_mm: float
    flange_w_mm: float
    flange_h_mm: float
    flange_thickness_mm: float
    flange_hole_spacing_x_mm: float
    flange_hole_spacing_y_mm: float
    stall_torque_kg_cm: float


def get_servo_dims(kind: Literal["sg90", "mg996r"]) -> ServoDims:
    """
    Conservative reference dimensions.
    Treat these as defaults—always verify against your specific servo batch/datasheet.
    """
    if kind == "sg90":
        # Typical SG90 micro servo (approx)
        return ServoDims(
            name="SG90",
            body_w_mm=22.8,
            body_h_mm=12.2,
            body_d_mm=22.5,
            flange_w_mm=32.2,
            flange_h_mm=12.2,
            flange_thickness_mm=2.0,
            flange_hole_spacing_x_mm=27.0,
            flange_hole_spacing_y_mm=0.0,
            stall_torque_kg_cm=1.8,
        )
    # Typical MG996R standard servo (approx)
    return ServoDims(
        name="MG996R",
        body_w_mm=40.7,
        body_h_mm=19.7,
        body_d_mm=42.9,
        flange_w_mm=54.0,
        flange_h_mm=19.7,
        flange_thickness_mm=2.5,
        flange_hole_spacing_x_mm=49.0,
        flange_hole_spacing_y_mm=0.0,
        stall_torque_kg_cm=10.0,
    )


def torque_nm(dims: ServoDims) -> float:
    # 1 kgf*cm ≈ 0.0980665 N·m
    return dims.stall_torque_kg_cm * 0.0980665

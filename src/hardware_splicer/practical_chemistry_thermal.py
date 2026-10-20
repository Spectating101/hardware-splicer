"""Conservative one-dimensional thermal-interface lower-bound estimate.

Ideal conduction Q*L/(k*A) omits contact resistance, thickness variation,
heat-spreading, pressure, ageing, interfaces and system cooling. Therefore
even an optimistic passing threshold NEVER establishes thermal sufficiency.
"""
from __future__ import annotations

import math
from typing import Any


def thermal_interface_screen(
    *, thickness_mm: float, contact_area_mm2: float, heat_load_w: float,
    bulk_conductivity_w_mk: float, allowable_rise_c: float | None = None,
) -> dict[str, Any]:
    for name, value in (
        ("thickness_mm", thickness_mm), ("contact_area_mm2", contact_area_mm2),
        ("heat_load_w", heat_load_w), ("bulk_conductivity_w_mk", bulk_conductivity_w_mk),
    ):
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and strictly positive")
    if not 0.001 <= thickness_mm <= 10 or not 1 <= contact_area_mm2 <= 1e7:
        raise ValueError("Thermal geometry outside bounded screening envelope")
    if not 0 < heat_load_w <= 10000 or not 0 < bulk_conductivity_w_mk <= 1000:
        raise ValueError("Thermal values outside bounded screening envelope")
    if allowable_rise_c is not None and (
        isinstance(allowable_rise_c, bool) or not isinstance(allowable_rise_c, (float, int))
        or not math.isfinite(allowable_rise_c) or allowable_rise_c <= 0 or allowable_rise_c > 1000
    ):
        raise ValueError("Allowable rise outside bounded finite envelope")
    area_m2 = contact_area_mm2 * 1e-6
    thickness_m = thickness_mm * 1e-3
    ideal_r = thickness_m / (bulk_conductivity_w_mk * area_m2)
    ideal_rise = ideal_r * heat_load_w
    if not math.isfinite(ideal_rise):
        raise ValueError("Thermal conduction calculation overflow")
    impossible_under_ideal_bulk_bound = (
        allowable_rise_c is not None and ideal_rise > allowable_rise_c
    )
    return {
        "formula": "Q * thickness_m / (bulk_k_w_mk * contact_area_m2)",
        "bulk_only_ideal_resistance_k_per_w": round(ideal_r, 8),
        "bulk_only_ideal_delta_t_c": round(ideal_rise, 8),
        "user_allowable_rise_c": allowable_rise_c,
        "fails_even_idealized_screen": impossible_under_ideal_bulk_bound,
        "prediction_is_full_device_thermal_model": False,
        "thermal_geometry_model_is_idealized": True,
        "thermal_paste_thick_gap_veto_is_internal_screening_heuristic": True,
        "actual_contact_resistance_accounted_for": False,
        "actual_gap_and_compression_verified": False,
        "requires_measured_interface_impedance_and_system_thermal_test": True,
        "interpretation": (
            "Even optimistic bulk-only thermal conduction exceeds the caller's rise criterion"
            if impossible_under_ideal_bulk_bound
            else "Optimistic bulk-only value; actual interface and system may be worse"
        ),
    }

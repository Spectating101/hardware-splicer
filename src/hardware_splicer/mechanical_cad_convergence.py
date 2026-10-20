"""Bounded global mesh-refinement sensitivity evidence for CAD-to-FEM screening.

Numerical stability is a necessary check, not independent validation of
geometry, material properties, boundary conditions, stress or fabrication.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal, Sequence

from .mechanical_cad_fem import AxisPlane, LocalRefinement, run_cad_screening


def _validate_study_parameters(
    sizes: Sequence[float],
    displacement_tolerance: float,
    stress_tolerance: float,
    geometry_volume_tolerance: float,
    minimum_refinement_growth: float,
) -> list[float]:
    if not 3 <= len(sizes) <= 4:
        raise ValueError("provide 3 or 4 mesh sizes, coarse to fine")
    values = [float(v) for v in sizes]
    if not all(math.isfinite(v) and 0.5 <= v <= 500 for v in values):
        raise ValueError("mesh sizes must be finite values in [0.5, 500] mm")
    if not all(a > b for a, b in zip(values, values[1:])):
        raise ValueError("mesh sizes must be strictly decreasing coarse to fine")
    for name, value in (
        ("displacement_tolerance", displacement_tolerance),
        ("stress_tolerance", stress_tolerance),
        ("geometry_volume_tolerance", geometry_volume_tolerance),
    ):
        if not math.isfinite(value) or not (0 < value <= 0.25):
            raise ValueError(f"{name} must be finite and in (0, 0.25]")
    if not math.isfinite(minimum_refinement_growth) or not (
        1.0 < minimum_refinement_growth <= 2.0
    ):
        raise ValueError("minimum_refinement_growth must be in (1, 2]")
    return values


def _relative_difference(coarse: float, fine: float) -> float:
    return abs(fine - coarse) / max(abs(fine), abs(coarse), 1e-15)


def run_cad_mesh_sensitivity(
    path: str | Path,
    *,
    mesh_sizes_mm: Sequence[float],
    stl_units: Literal["mm"] | None,
    fixed_plane: AxisPlane,
    loaded_plane: AxisPlane,
    total_force_n: list[float],
    youngs_modulus_pa: float,
    poisson_ratio: float,
    yield_strength_pa: float | None = None,
    displacement_tolerance: float = 0.02,
    stress_tolerance: float = 0.03,
    geometry_volume_tolerance: float = 0.01,
    minimum_refinement_growth: float = 1.10,
    global_mesh_size_mm: float | None = None,
    local_radius_mm: float | None = None,
    refine_circular_edges: bool = False,
    hotspot_centers_mm: tuple[tuple[float, float, float], ...] = (),
) -> dict[str, Any]:
    """Repeat one load case on 3-4 globally refined meshes.

    Failed meshing / physics raises; it cannot skip a failed refinement level
    and claim convergence. Peak element stress near singular geometry remains
    questionable even when adjacent samples agree.
    """
    sizes = _validate_study_parameters(
        mesh_sizes_mm, displacement_tolerance, stress_tolerance,
        geometry_volume_tolerance, minimum_refinement_growth,
    )
    local_study = global_mesh_size_mm is not None
    if local_study:
        if not (
            math.isfinite(global_mesh_size_mm)
            and 0.5 < global_mesh_size_mm <= 500
        ):
            raise ValueError("global_mesh_size_mm must be finite in (0.5, 500]")
        if sizes[0] >= global_mesh_size_mm:
            raise ValueError("local mesh sizes must all be smaller than the global mesh size")
        if local_radius_mm is None or not math.isfinite(local_radius_mm) or not (
            0.5 <= local_radius_mm <= 500
        ):
            raise ValueError("local_radius_mm must be finite in [0.5, 500]")
        if not refine_circular_edges and not hotspot_centers_mm:
            raise ValueError("local study needs circular edges or hotspot centers")
    elif (
        local_radius_mm is not None or refine_circular_edges or hotspot_centers_mm
    ):
        raise ValueError("local options require global_mesh_size_mm")

    levels: list[dict[str, Any]] = []
    source_hash = None
    for mesh_size in sizes:
        screening_kwargs: dict[str, Any] = {
            "mesh_target_mm": global_mesh_size_mm if local_study else mesh_size,
            "stl_units": stl_units,
            "fixed_plane": fixed_plane,
            "loaded_plane": loaded_plane,
            "total_force_n": total_force_n,
            "youngs_modulus_pa": youngs_modulus_pa,
            "poisson_ratio": poisson_ratio,
            "yield_strength_pa": yield_strength_pa,
        }
        if local_study:
            screening_kwargs["local_refinement"] = LocalRefinement(
                target_size_mm=mesh_size,
                radius_mm=local_radius_mm,
                refine_circular_edges=refine_circular_edges,
                hotspot_centers_mm=hotspot_centers_mm,
            )
        result = run_cad_screening(path, **screening_kwargs)
        cad, analysis = result["cad"], result["analysis"]
        if source_hash is not None and cad["source_sha256"] != source_hash:
            raise ValueError("CAD source changed during mesh-sensitivity study")
        source_hash = cad["source_sha256"]
        levels.append({
            "target_mesh_size_mm": mesh_size,
            "node_count": analysis["node_count"],
            "element_count": analysis["element_count"],
            "near_feature_node_count": (
                cad["local_refinement"]["influence_region_node_count"]
                if local_study else None
            ),
            "mesh_volume_m3": cad["mesh_volume_m3"],
            "cad_kernel_volume_m3": cad["cad_kernel_volume_m3"],
            "mesh_volume_error_fraction": cad["mesh_volume_error_fraction"],
            "max_displacement_m": analysis["max_displacement_m"],
            "max_von_mises_pa": analysis["max_von_mises_pa"],
            "peak_stress_centroid_m": analysis["peak_stress_centroid_m"],
            "raw_yield_safety_factor": analysis["yield_safety_factor"],
            "force_equilibrium_residual_n": analysis["force_equilibrium_residual_n"],
            "fixed_face_area_m2": result["boundary_conditions"]["fixed_face_area_m2"],
            "loaded_face_area_m2": result["boundary_conditions"]["loaded_face_area_m2"],
        })

    comparisons: list[dict[str, Any]] = []
    for left, right in zip(levels, levels[1:]):
        effective_key = (
            "near_feature_node_count" if local_study else "element_count"
        )
        growth = right[effective_key] / left[effective_key]
        disp_change = _relative_difference(
            left["max_displacement_m"], right["max_displacement_m"]
        )
        stress_change = _relative_difference(
            left["max_von_mises_pa"], right["max_von_mises_pa"]
        )
        comparisons.append({
            "coarse_mesh_size_mm": left["target_mesh_size_mm"],
            "fine_mesh_size_mm": right["target_mesh_size_mm"],
            "element_count_growth": (
                right["element_count"] / left["element_count"]
            ),
            "near_feature_node_count_growth": (
                growth if local_study else None
            ),
            "effective_refinement_growth": growth,
            "displacement_relative_change": disp_change,
            "peak_stress_relative_change": stress_change,
            "mesh_volume_relative_change": _relative_difference(
                left["mesh_volume_m3"], right["mesh_volume_m3"]
            ),
            # Historical field retained for global callers; use the explicit
            # strategy-specific density field for local-refinement studies.
            "sufficient_element_refinement": (
                growth >= minimum_refinement_growth if not local_study else None
            ),
            "sufficient_effective_refinement": growth >= minimum_refinement_growth,
            "displacement_tolerance_met": disp_change <= displacement_tolerance,
            "stress_tolerance_met": stress_change <= stress_tolerance,
        })

    blockers: list[str] = []
    if any(not x["sufficient_effective_refinement"] for x in comparisons):
        blockers.append("insufficient_effective_refinement")
    if any(not x["displacement_tolerance_met"] for x in comparisons):
        blockers.append("displacement_changes_with_refinement")
    if any(not x["stress_tolerance_met"] for x in comparisons):
        blockers.append("peak_stress_changes_with_refinement")
    if any(
        level["mesh_volume_error_fraction"] is not None and
        level["mesh_volume_error_fraction"] > geometry_volume_tolerance
        for level in levels
    ):
        blockers.append("cad_mesh_volume_discrepancy")

    observed_stable = not blockers
    return {
        "schema_version": "hardware_splicer.mechanical_cad_sensitivity.v1",
        "status": (
            "numerically_stable_screening" if observed_stable
            else "inconclusive_refinement"
        ),
        "source_sha256": source_hash,
        "mesh_sizes_mm": sizes,
        "refinement_strategy": (
            "local_features" if local_study else "global_uniform"
        ),
        "global_mesh_size_mm": global_mesh_size_mm,
        "local_radius_mm": local_radius_mm,
        "refine_circular_edges": refine_circular_edges,
        "hotspot_centers_mm": [list(x) for x in hotspot_centers_mm],
        "load_case": {
            "fixed_plane": fixed_plane,
            "loaded_plane": loaded_plane,
            "total_force_n": total_force_n,
            "youngs_modulus_pa": youngs_modulus_pa,
            "poisson_ratio": poisson_ratio,
            "yield_strength_pa": yield_strength_pa,
        },
        "criteria": {
            "displacement_max_relative_change": displacement_tolerance,
            "peak_stress_max_relative_change": stress_tolerance,
            "cad_mesh_volume_max_relative_error": geometry_volume_tolerance,
            "minimum_element_growth_between_levels": (
                minimum_refinement_growth if not local_study else None
            ),
            "minimum_near_feature_node_growth": (
                minimum_refinement_growth if local_study else None
            ),
        },
        "levels": levels,
        "adjacent_mesh_comparisons": comparisons,
        "sensitivity_blockers": blockers,
        "mesh_sensitivity_observed_stable": observed_stable,
        "fine_mesh_raw_yield_safety_factor": levels[-1]["raw_yield_safety_factor"],
        "yield_margin_usable_for_engineering_release": False,
        "geometry_reference_available": all(
            x["cad_kernel_volume_m3"] is not None for x in levels
        ),
        "mesh_convergence_verified": False,
        "physical_validation_required": True,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
        "claim_boundary": (
            "Mesh-sensitivity evidence only; even stable numbers do not "
            "validate load-case assumptions, notch stress singularities, "
            "material behavior, physical strength or manufacturing suitability."
        ),
    }

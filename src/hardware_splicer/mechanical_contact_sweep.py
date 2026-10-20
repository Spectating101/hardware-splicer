"""Force/displacement curve under the E11 rigid two-pin contact model.

This is a *numerical prediction* to compare against future physical tests,
not a verified material load-displacement curve or allowable loading.
"""
from __future__ import annotations
import math
from pathlib import Path
from typing import Any, Sequence


def run_contact_displacement_sweep(
    step_path: str | Path, *,
    centers_xy_mm: Sequence[Sequence[float]],
    hole_d_mm: float,
    thickness_mm: float,
    pin_drives_mm: Sequence[float] = (0., .01, .02, .04),
    mesh_target_mm: float = 8.,
    radial_clearance_mm: float = .005,
) -> dict[str, Any]:
    from .mechanical_two_pin_contact import solve_two_pin_contact

    drives = [float(x) for x in pin_drives_mm]
    if (
        len(drives) not in range(3,7)
        or not all(math.isfinite(x) and 0 <= x <= .1 for x in drives)
        or not all(a < b for a,b in zip(drives,drives[1:]))
    ):
        raise ValueError("contact displacement sweep requires 3–6 strictly increasing 0..0.1 mm drives")
    levels = []
    for drive in drives:
        r=solve_two_pin_contact(
            step_path,
            mesh_target_mm=mesh_target_mm,
            centers_xy_mm=centers_xy_mm,
            hole_d_mm=hole_d_mm,
            thickness_mm=thickness_mm,
            right_pin_drive_mm=drive,
            radial_clearance_mm=radial_clearance_mm,
        )
        levels.append({
            "pin_drive_mm": drive,
            "force_transferred_n": r["transmitted_force_scale_n"],
            "first_pin_contact_nodes": r["per_pin"][0]["active_contact_node_count"],
            "second_pin_contact_nodes": r["per_pin"][1]["active_contact_node_count"],
            "global_sampled_peak_stress_pa": r["global_peak_sampled_von_mises_pa"],
            "maximum_tested_nodal_gap_violation_m": r["nodal_max_gap_violation_m"],
        })
    forces = [x["force_transferred_n"] for x in levels]
    blockers = []
    if len({level["pin_drive_mm"] for level in levels}) != len(levels):
        blockers.append("nonunique_drive_levels")
    if any(
        later < earlier - max(.01,earlier*.005)
        for earlier,later in zip(forces,forces[1:])
    ):
        blockers.append("nonmonotonic_force_displacement_prediction")
    if len({level["maximum_tested_nodal_gap_violation_m"]<=5e-10
            for level in levels}) > 1 or any(
        level["maximum_tested_nodal_gap_violation_m"] > 5e-10
        for level in levels
    ):
        blockers.append("contact_gap_feasibility_failure")
    return {
        "schema_version":"hardware_splicer.two_pin_displacement_sweep.v1",
        "status":(
            "bounded_numerical_contact_sweep_only" if not blockers
            else "inconclusive_contact_displacement_sweep"
        ),
        "mesh_target_mm":mesh_target_mm,
        "radial_clearance_mm_assumed":radial_clearance_mm,
        "levels":levels,
        "blockers":blockers,
        "physical_force_displacement_curve_measured":False,
        "material_anisotropy_tested":False,
        "failure_load_calibrated":False,
        "structural_safety_verified":False,
        "fabrication_authorized":False,
        "release_authorized":False,
    }

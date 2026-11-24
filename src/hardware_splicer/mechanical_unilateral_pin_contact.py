"""Bounded unilateral rigid-pin / elastic bore *penalty* contact screening.

This is an iterated active-set small-strain frictionless normal contact law:
    p = penalty * max(0, prescribed_pin_radial_motion - bore_u_radial - clearance)
on the SECOND bore. A simplified fully clamped semicylindrical FIRST bore
still anchors the structure. Loads are displacement-controlled, not forcibly
prescribed. Pressure cannot pull, and the contact patch changes with u.

Limitations: rigid pin; positive penalty penetration; no exact Signorini
multipliers, geometry nonlinearity, bolt preload or sliding/fretting, pin
clearance uncertainty, printed-polymer anisotropy, manufacturing authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


def _input_checks(
    *,
    centers_xy_mm: Sequence[Sequence[float]],
    hole_d_mm: float,
    thickness_mm: float,
    drive_mm: float,
    clearance_mm: float,
    penalty_pa_per_m: float,
    youngs_pa: float,
    poisson: float,
    mesh_target_mm: float,
) -> list[tuple[float, float]]:
    from .mechanical_fastener_bearing import _validate_inputs

    centers = _validate_inputs(
        centers_xy_mm, hole_d_mm, thickness_mm, 30.,
        youngs_pa, poisson, 3.,
    )
    for label, value in (
        ("drive_mm", drive_mm),
        ("clearance_mm", clearance_mm),
        ("penalty_pa_per_m", penalty_pa_per_m),
        ("mesh_target_mm", mesh_target_mm),
    ):
        if not math.isfinite(value):
            raise ValueError(f"{label} must be finite")
    if not 0 <= drive_mm <= .20:
        raise ValueError("drive_mm must lie within [0,0.20] mm")
    if not 0 <= clearance_mm <= .05 or clearance_mm >= hole_d_mm / 2:
        raise ValueError("clearance_mm must be nonnegative and below pin radius")
    if not 1e9 <= penalty_pa_per_m <= 2e13:
        raise ValueError("contact penalty must lie within [1e9,2e13] Pa/m")
    if not 1 <= mesh_target_mm <= 15:
        raise ValueError("mesh_target_mm must be within [1,15] mm")
    return centers


def analytic_unilateral_spring(
    *,
    stiffness_n_per_m: float,
    contact_penalty_n_per_m: float,
    pin_drive_m: float,
    clearance_m: float,
) -> dict[str, float]:
    """One-DOF independent closed-form check for the active-set contact law."""
    for label, number in (
        ("stiffness", stiffness_n_per_m),
        ("penalty", contact_penalty_n_per_m),
        ("drive", pin_drive_m),
        ("clearance", clearance_m),
    ):
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{label} must be finite and nonnegative")
    if stiffness_n_per_m <= 0 or contact_penalty_n_per_m <= 0:
        raise ValueError("1D spring stiffness/penalty must be positive")
    overtravel = max(0., pin_drive_m - clearance_m)
    u = contact_penalty_n_per_m * overtravel / (
        stiffness_n_per_m + contact_penalty_n_per_m
    )
    force = stiffness_n_per_m * u
    return {
        "displacement_m": u,
        "reaction_force_n": force,
        "penetration_m": max(0., overtravel - u),
        "contact_active": force > 0,
    }


def solve_pin_to_bore_contact(
    step_path: str | Path,
    *,
    mesh_target_mm: float,
    centers_xy_mm: Sequence[Sequence[float]],
    hole_d_mm: float,
    thickness_mm: float,
    drive_mm: float = .02,
    clearance_mm: float = .005,
    penalty_pa_per_m: float = 5e11,
    youngs_pa: float = 2e9,
    poisson: float = .25,
    max_iterations: int = 20,
) -> dict[str, Any]:
    import numpy as np
    from skfem import (
        MeshTet, MeshTet2, ElementVector, ElementTetP2,
        Basis, FacetBasis, BilinearForm, LinearForm, asm, solve, condense,
    )
    from skfem.models.elasticity import lame_parameters, linear_elasticity
    from .mechanical_cad_fem import mesh_cad_solid
    from .mechanical_quadratic_fem import (
        _validated_curved_jacobian, MAX_QUADRATIC_DOF,
    )

    centers = _input_checks(
        centers_xy_mm=centers_xy_mm, hole_d_mm=hole_d_mm,
        thickness_mm=thickness_mm, drive_mm=drive_mm,
        clearance_mm=clearance_mm, penalty_pa_per_m=penalty_pa_per_m,
        youngs_pa=youngs_pa, poisson=poisson,
        mesh_target_mm=mesh_target_mm,
    )
    if not isinstance(max_iterations, int) or not 2 <= max_iterations <= 50:
        raise ValueError("maximum active-set iterations must be [2,50]")

    solid = mesh_cad_solid(
        step_path, mesh_target_mm=mesh_target_mm, geometry_order=2
    )
    base = MeshTet2.from_mesh(MeshTet(
        np.asarray(solid.nodes_m, dtype=float).T,
        np.asarray(solid.elements, dtype=int).T,
    ))
    gmsh_edges = {
        tuple(pair): np.asarray(mid, dtype=float)
        for pair, mid in zip(
            solid.quadratic_edge_vertices, solid.quadratic_edge_midpoints_m
        )
    }
    if len(gmsh_edges) != base.edges.shape[1]:
        raise ValueError("incomplete high-order edge geometry")
    curved_nodes = base.doflocs.copy()
    for i, (a, b) in enumerate(base.edges.T):
        key = tuple(sorted((int(a), int(b))))
        if key not in gmsh_edges:
            raise ValueError("missing high-order Gmsh tetrahedral edge")
        curved_nodes[:, int(base.dofs.edge_dofs[0, i])] = gmsh_edges[key]
    mesh = MeshTet2(curved_nodes, base.t)
    elem = ElementVector(ElementTetP2())
    basis = Basis(mesh, elem)
    if basis.N > MAX_QUADRATIC_DOF:
        raise ValueError("unilateral pin contact P2 DOF cap exceeded")
    min_jac, _ = _validated_curved_jacobian(mesh, basis.X)
    volume = float(np.sum(basis.dx))
    if solid.cad_kernel_volume_m3 is None or abs(
        volume / solid.cad_kernel_volume_m3 - 1
    ) > .01:
        raise ValueError("curved bore mesh volume differs from STEP solid")
    if not math.isclose(
        float(mesh.p[2].max() - mesh.p[2].min()),
        thickness_mm * .001, abs_tol=5e-5,
    ):
        raise ValueError("bracket mesh thickness mismatches hole specification")

    exterior = mesh.boundary_facets()
    p = mesh.p[:, mesh.facets[:, exterior]]
    R = hole_d_mm * .0005
    hole_faces = []
    full_areas = []
    for cx_mm, cy_mm in centers:
        dist = np.hypot(
            p[0] - cx_mm * .001, p[1] - cy_mm * .001
        )
        mask = np.all(abs(dist - R) < .00012, axis=0)
        wall_faces = exterior[mask]
        if len(wall_faces) < 12:
            raise ValueError("incomplete nominal pin bore wall")
        full_fb = FacetBasis(mesh, elem, facets=wall_faces, dofs=basis.dofs)
        area = float(np.sum(full_fb.dx))
        ideal = math.pi * hole_d_mm * .001 * thickness_mm * .001
        if not .94 <= area / ideal <= 1.06:
            raise ValueError("pin bore wall area mismatches declared cylinder")
        hole_faces.append(wall_faces)
        full_areas.append(area)
    if set(hole_faces[0]).intersection(hole_faces[1]):
        raise ValueError("nominal bores share boundary faces")

    anchor_vertices = mesh.p[0, mesh.facets[:, hole_faces[0]]]
    anchor_faces = hole_faces[0][
        np.mean(anchor_vertices, axis=0) <
        centers[0][0] * .001 - .1 * R
    ]
    clamped = basis.get_dofs(facets=anchor_faces).flatten()
    if len(clamped) < 9:
        raise ValueError("insufficient simplified anchor DOFs")
    contact_basis = FacetBasis(
        mesh, elem, facets=hole_faces[1], dofs=basis.dofs,
    )
    coords = np.asarray(contact_basis.global_coordinates())
    radial_distance = np.hypot(
        coords[0] - centers[1][0] * .001,
        coords[1] - centers[1][1] * .001,
    )
    if float(radial_distance.min()) <= 0:
        raise ValueError("invalid radial normals on hole wall")
    ex = (coords[0] - centers[1][0] * .001) / radial_distance
    ey = (coords[1] - centers[1][1] * .001) / radial_distance

    lam, mu = lame_parameters(youngs_pa, poisson)
    bulk = asm(linear_elasticity(Lambda=lam, Mu=mu), basis)
    displacement = np.zeros(basis.N)
    old_active = None
    converged = False
    drive = drive_mm * .001
    clearance = clearance_mm * .001
    for iteration in range(max_iterations):
        displacement_at_contact = np.asarray(
            contact_basis.interpolate(displacement)
        )
        outward = (
            displacement_at_contact[0] * ex +
            displacement_at_contact[1] * ey
        )
        open_overlap = drive * ex - outward - clearance
        active = open_overlap > 0
        # For a fixed active set, the contact law is linear.
        @BilinearForm
        def active_stiffness(u, v, w):
            return (
                penalty_pa_per_m * active *
                (u[0] * ex + u[1] * ey) *
                (v[0] * ex + v[1] * ey)
            )

        @LinearForm
        def active_drive(v, w):
            return (
                penalty_pa_per_m * active * (drive * ex - clearance) *
                (v[0] * ex + v[1] * ey)
            )

        trial = solve(*condense(
            bulk + asm(active_stiffness, contact_basis),
            asm(active_drive, contact_basis), D=clamped,
        ))
        if not np.all(np.isfinite(trial)):
            raise ValueError("nonfinite pin-contact displacement field")
        diff = float(np.linalg.norm(trial - displacement))
        if (
            old_active is not None
            and np.array_equal(active, old_active)
            and diff <= 1e-11
        ):
            displacement = trial
            converged = True
            break
        displacement = trial
        old_active = active.copy()
    if not converged:
        raise ValueError(
            "unilateral contact active set did not converge; "
            "do not use its stress estimate"
        )

    displacement_at_contact = np.asarray(
        contact_basis.interpolate(displacement)
    )
    radial_displacement = (
        displacement_at_contact[0] * ex +
        displacement_at_contact[1] * ey
    )
    penetration = np.maximum(
        0., drive * ex - radial_displacement - clearance
    )
    pressure = penalty_pa_per_m * penetration
    active = pressure > 0

    @LinearForm
    def final_contact_traction(v, w):
        return pressure * (ex * v[0] + ey * v[1])

    load = asm(final_contact_traction, contact_basis)

    def resultant(distributed):
        return np.asarray([
            float(distributed[basis.nodal_dofs[a]].sum()) +
            float(distributed[basis.edge_dofs[a]].sum())
            for a in range(3)
        ])
    applied = resultant(load)
    if np.any(np.isnan(applied)):
        raise ValueError("invalid pin contact reaction")
    if drive <= clearance and float(np.max(pressure)) > 1e-5:
        raise ValueError("pin is not closing clearance yet but contact activated")
    if drive > clearance and applied[0] <= 1e-6:
        raise ValueError("driven pin failed to engage its bore")

    residual = bulk @ displacement - load
    free = np.setdiff1d(np.arange(basis.N), clamped)
    free_residual = float(np.linalg.norm(residual[free]))
    supports = resultant(residual)
    reaction_error = float(np.linalg.norm(supports + applied))
    tolerance_force = 1e-6 * max(1., float(np.linalg.norm(applied)))
    if free_residual > tolerance_force or reaction_error > tolerance_force:
        raise ValueError("final nonlinear contact equilibrium has not converged")
    if applied[0] > 0 and abs(applied[1]) / applied[0] > .05:
        raise ValueError("excessive lateral contact force on test bracket")

    strain_grad = basis.interpolate(displacement).grad
    strain = .5 * (strain_grad + np.swapaxes(strain_grad, 0, 1))
    stress = (
        lam * np.eye(3)[:, :, None, None] *
        np.trace(strain, axis1=0, axis2=1)[None, None, :, :] +
        2 * mu * strain
    )
    deviator = stress - np.eye(3)[:, :, None, None] * (
        np.trace(stress, axis1=0, axis2=1)[None, None, :, :] / 3
    )
    vm = np.sqrt(
        1.5 * np.einsum("ijeq,ijeq->eq", deviator, deviator)
    )
    if not np.all(np.isfinite(vm)):
        raise ValueError("nonfinite nonlinear-contact von Mises samples")
    xyz = mesh.mapping().F(basis.X)
    per_hole = []
    for h, (cx_mm, cy_mm) in enumerate(centers):
        rr = np.hypot(
            xyz[0] - cx_mm * .001, xyz[1] - cy_mm * .001
        )
        region = (rr >= R * .985) & (rr <= R + .003)
        if int(np.count_nonzero(region)) < 10:
            raise ValueError("insufficient stress quadrature samples near pin hole")
        wvm = np.where(region, vm, -np.inf)
        loc = np.unravel_index(int(np.argmax(wvm)), vm.shape)
        per_hole.append({
            "hole_index": h,
            "center_xy_mm": [cx_mm, cy_mm],
            "peak_von_mises_pa": float(vm[loc]),
            "peak_xyz_m": [float(xyz[j][loc]) for j in range(3)],
            "weighted_rms_von_mises_pa": float(np.sqrt(
                np.sum(basis.dx * np.where(region, vm**2, 0.)) /
                max(float(np.sum(basis.dx * region)), 1e-18)
            )),
            "quadrature_sample_count": int(np.count_nonzero(region)),
        })

    return {
        "schema_version": "hardware_splicer.unilateral_rigid_pin_penalty.v1",
        "status": "unilateral_penalty_contact_screen_only",
        "source_step_sha256": solid.source_sha256,
        "mesh_target_mm": mesh_target_mm,
        "tetrahedron_count": len(solid.elements),
        "quadratic_dof_count": int(basis.N),
        "min_sampled_geometry_jacobian_m3": min_jac,
        "bore_surface_area_m2": full_areas,
        "rigid_pin_drive_mm": drive_mm,
        "rigid_pin_radial_clearance_mm": clearance_mm,
        "contact_penalty_pa_per_m": penalty_pa_per_m,
        "contact_iteration_count": iteration + 1,
        "active_contact_qp_count": int(active.sum()),
        "total_bore_contact_qp_count": int(active.size),
        "active_contact_area_m2": float(np.sum(
            contact_basis.dx * active
        )),
        "peak_compressive_contact_pressure_pa": float(np.max(pressure)),
        "max_regularized_penetration_mm": float(
            np.max(penetration) * 1000
        ),
        "pin_to_bore_resultant_n": applied.tolist(),
        "simplified_anchor_reaction_n": supports.tolist(),
        "free_dof_force_residual_n": free_residual,
        "global_reaction_balance_error_n": reaction_error,
        "global_peak_sampled_von_mises_pa": float(np.max(vm)),
        "per_hole_stress": per_hole,
        "body_strain_energy_j": float(.5 * displacement @ (bulk @ displacement)),
        "full_nonlinear_contact_verified": False,
        "mesh_convergence_verified": False,
        "yield_margin_usable_for_engineering_release": False,
        "small_displacement_unilateral_penalty": True,
        "contact_patch_changes_with_displacement": True,
        "penalty_penetration_present": bool(np.max(penetration) > 0),
        "true_anchor_bolt_contact_validated": False,
        "friction_and_preload_modeled": False,
        "printed_material_properties_measured": False,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
        "claim_boundary": (
            "An active-set unilateral normal penalty law on a rigid displaced "
            "pin at bore two, with an over-stiff clamped semicylindrical anchor "
            "at bore one; no exact hard contact, pin compliance, nonlinear "
            "kinematics or measured material properties."
        ),
    }


def run_pin_contact_mesh_series(
    step_path: str | Path,
    *,
    mesh_sizes_mm: Sequence[float] = (8, 6, 5),
    centers_xy_mm: Sequence[Sequence[float]],
    hole_d_mm: float,
    thickness_mm: float,
    drive_mm: float = .02,
    clearance_mm: float = .005,
    penalty_pa_per_m: float = 5e11,
    youngs_pa: float = 2e9,
    poisson: float = .25,
    force_relative_tolerance: float = .04,
    peak_stress_relative_tolerance: float = .12,
    rms_stress_relative_tolerance: float = .06,
) -> dict[str, Any]:
    sizes = tuple(float(s) for s in mesh_sizes_mm)
    if len(sizes) not in (3, 4) or not all(
        math.isfinite(s) and 1 <= s <= 15 for s in sizes
    ) or not all(a > b for a, b in zip(sizes, sizes[1:])):
        raise ValueError("need 3–4 finite strictly decreasing mesh sizes")
    for label, tol in (
        ("force_relative_tolerance", force_relative_tolerance),
        ("peak_stress_relative_tolerance", peak_stress_relative_tolerance),
        ("rms_stress_relative_tolerance", rms_stress_relative_tolerance),
    ):
        if not math.isfinite(tol) or not 0 < tol <= .25:
            raise ValueError(f"{label} must be finite and within (0,0.25]")
    levels = [
        solve_pin_to_bore_contact(
            step_path,
            mesh_target_mm=size,
            centers_xy_mm=centers_xy_mm,
            hole_d_mm=hole_d_mm,
            thickness_mm=thickness_mm,
            drive_mm=drive_mm,
            clearance_mm=clearance_mm,
            penalty_pa_per_m=penalty_pa_per_m,
            youngs_pa=youngs_pa,
            poisson=poisson,
        )
        for size in sizes
    ]
    if len({level["source_step_sha256"] for level in levels}) != 1:
        raise ValueError("STEP changed during nonlinear contact series")
    comparisons = []
    blockers = []
    if any(item["active_contact_qp_count"] == 0 for item in levels):
        blockers.append("no_active_contact_in_mesh_series")
    for a, b in zip(levels, levels[1:]):
        va, vb = a["pin_to_bore_resultant_n"][0], b["pin_to_bore_resultant_n"][0]
        force_change = abs(vb - va) / max(abs(va), abs(vb), 1e-9)
        per_hole = []
        for left, right in zip(a["per_hole_stress"], b["per_hole_stress"]):
            peak_change = abs(
                right["peak_von_mises_pa"] - left["peak_von_mises_pa"]
            ) / max(left["peak_von_mises_pa"], right["peak_von_mises_pa"], 1e-9)
            rms_change = abs(
                right["weighted_rms_von_mises_pa"] -
                left["weighted_rms_von_mises_pa"]
            ) / max(
                right["weighted_rms_von_mises_pa"],
                left["weighted_rms_von_mises_pa"], 1e-9
            )
            if peak_change > peak_stress_relative_tolerance:
                blockers.append(f"hole_{left['hole_index']}_peak_contact_stress_unstable")
            if rms_change > rms_stress_relative_tolerance:
                blockers.append(f"hole_{left['hole_index']}_rms_contact_stress_unstable")
            per_hole.append({
                "hole_index": left["hole_index"],
                "peak_relative_change": peak_change,
                "rms_relative_change": rms_change,
            })
        if force_change > force_relative_tolerance:
            blockers.append("contact_force_mesh_sensitive")
        if b["quadratic_dof_count"] / a["quadratic_dof_count"] < 1.08:
            blockers.append("insufficient_quadratic_refinement")
        comparisons.append({
            "coarse_mesh_mm": a["mesh_target_mm"],
            "fine_mesh_mm": b["mesh_target_mm"],
            "contact_force_relative_change": force_change,
            "per_hole": per_hole,
        })
    blockers = sorted(set(blockers))
    return {
        "schema_version": "hardware_splicer.unilateral_penalty_contact_series.v1",
        "status": (
            "numerically_stable_unilateral_contact_screen"
            if not blockers else "inconclusive_unilateral_contact_refinement"
        ),
        "source_step_sha256": levels[0]["source_step_sha256"],
        "levels": levels,
        "adjacent_comparisons": comparisons,
        "blockers": blockers,
        "nonlinear_contact_approximation": "small-strain active-set normal penalty",
        "actual_pin_clearance_measured": False,
        "full_assembly_contact_verified": False,
        "physical_validation_required": True,
        "mesh_convergence_verified": False,
        "yield_margin_usable_for_engineering_release": False,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }


def run_penalty_stiffness_sensitivity(
    step_path: str | Path,
    *,
    mesh_target_mm: float,
    centers_xy_mm: Sequence[Sequence[float]],
    hole_d_mm: float,
    thickness_mm: float,
    drive_mm: float,
    clearance_mm: float,
    baseline_penalty_pa_per_m: float,
    force_relative_tolerance: float = .10,
) -> dict[str, Any]:
    """Fail closed if contact force still depends materially on penalty scale."""
    penalties = [
        baseline_penalty_pa_per_m / 5.,
        baseline_penalty_pa_per_m,
        baseline_penalty_pa_per_m * 2.,
    ]
    if not all(math.isfinite(x) and 1e9 <= x <= 2e13 for x in penalties):
        raise ValueError("penalty series outside bounded numerical stiffness range")
    if not math.isfinite(force_relative_tolerance) or not (
        0 < force_relative_tolerance <= .25
    ):
        raise ValueError("force_relative_tolerance must lie in (0,0.25]")

    measurements = []
    fingerprints = set()
    for stiffness in penalties:
        r = solve_pin_to_bore_contact(
            step_path, mesh_target_mm=mesh_target_mm,
            centers_xy_mm=centers_xy_mm,
            hole_d_mm=hole_d_mm,
            thickness_mm=thickness_mm,
            drive_mm=drive_mm,
            clearance_mm=clearance_mm,
            penalty_pa_per_m=stiffness,
        )
        fingerprints.add(r["source_step_sha256"])
        measurements.append({
            "penalty_pa_per_m": stiffness,
            "contact_force_x_n": r["pin_to_bore_resultant_n"][0],
            "active_contact_area_m2": r["active_contact_area_m2"],
            "maximum_regularized_penetration_mm": r[
                "max_regularized_penetration_mm"
            ],
            "iterations": r["contact_iteration_count"],
        })
    if len(fingerprints) != 1:
        raise ValueError("contact STEP source changed during penalty series")
    comparisons = []
    blockers = []
    if any(item["contact_force_x_n"] <= 0 for item in measurements):
        blockers.append("no_active_contact_in_penalty_series")
    for a, b in zip(measurements, measurements[1:]):
        change = abs(
            b["contact_force_x_n"] - a["contact_force_x_n"]
        ) / max(
            abs(b["contact_force_x_n"]), abs(a["contact_force_x_n"]), 1e-12
        )
        comparisons.append({
            "penalty_coarse_pa_per_m": a["penalty_pa_per_m"],
            "penalty_fine_pa_per_m": b["penalty_pa_per_m"],
            "contact_force_relative_change": change,
        })
        if change > force_relative_tolerance:
            blockers.append("contact_force_sensitive_to_penalty_stiffness")
    blockers = sorted(set(blockers))
    return {
        "schema_version": "hardware_splicer.contact_penalty_sensitivity.v1",
        "status": (
            "penalty_force_screen_pass"
            if not blockers else "inconclusive_penalty_parameter_dependence"
        ),
        "source_step_sha256": next(iter(fingerprints)),
        "mesh_target_mm": mesh_target_mm,
        "levels": measurements,
        "comparisons": comparisons,
        "contact_force_relative_tolerance": force_relative_tolerance,
        "blockers": blockers,
        "penalty_independence_mathematically_proven": False,
        "physical_validation_required": True,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    from .mechanical_bracket_screening import generate_bracket_reference_step

    parser = argparse.ArgumentParser(
        description="Screen simplified unilateral frictionless pin/bore penalty contact"
    )
    parser.add_argument("--spec-json", type=Path, required=True)
    parser.add_argument("--step-out", type=Path, required=True)
    parser.add_argument("--mesh-study-mm", type=float, nargs="+", default=[8, 6, 5])
    parser.add_argument("--drive-mm", type=float, default=.02)
    parser.add_argument("--clearance-mm", type=float, default=.005)
    parser.add_argument("--penalty-pa-per-m", type=float, default=5e11)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args(argv)
    spec_data = json.loads(a.spec_json.read_text(encoding="utf-8"))
    spec = spec_data.get("bracket", spec_data)
    export = generate_bracket_reference_step(spec, a.step_out)
    numbers = export["geometry_dimensions_mm"]
    common = {
        "centers_xy_mm": export["cylindrical_through_hole_centers_xy_mm"],
        "hole_d_mm": numbers["hole_d_mm"],
        "thickness_mm": numbers["t_mm"],
        "drive_mm": a.drive_mm,
        "clearance_mm": a.clearance_mm,
    }
    mesh_series = run_pin_contact_mesh_series(
        a.step_out, mesh_sizes_mm=a.mesh_study_mm,
        penalty_pa_per_m=a.penalty_pa_per_m,
        **common,
    )
    penalty_series = run_penalty_stiffness_sensitivity(
        a.step_out, mesh_target_mm=float(a.mesh_study_mm[0]),
        baseline_penalty_pa_per_m=a.penalty_pa_per_m,
        **common,
    )
    blockers = sorted(set(
        mesh_series["blockers"] + penalty_series["blockers"]
    ))
    report = {
        "schema_version": "hardware_splicer.contact_joint_evidence.v1",
        "status": (
            "inconclusive_joint_contact_screening"
            if blockers else "bounded_contact_screening_only"
        ),
        "generated_step_provenance": export,
        "source_spec_sha256": "sha256:" + hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "mesh_sensitivity": mesh_series,
        "penalty_sensitivity": penalty_series,
        "blockers": blockers,
        "true_pin_joint_strength_verified": False,
        "measured_material_properties_available": False,
        "physical_validation_required": True,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Pin/bore status={report['status']}; blockers={report['blockers']}")
    return 2 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())

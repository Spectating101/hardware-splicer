"""Kirsch circular-hole stress: closed form and independent 2-D FEM benchmark.

The Kirsch reference is for an infinite *plane-stress* continuum subject
to remote uniaxial tension. We compare an annular domain using exact
Kirsch stresses as outer *traction*, a traction-free hole, and no body forces.

This validates a separately assembled 2-D FEM against an analytical field.
It NEVER certifies finite 3-D brackets, clamps, printed materials or joints.
"""

from __future__ import annotations

import argparse
import json
import math
from typing import Any, Sequence


def kirsch_stress(
    x_m: Any, y_m: Any, *, hole_radius_m: float, remote_tension_pa: float
) -> dict[str, Any]:
    """Kirsch plane-stress tensor under far-field SIGMA_XX = remote_tension_pa.

    Components are numpy arrays in Cartesian coordinates and polar
    coordinates about the hole origin. The hole interior is invalid.
    """
    import numpy as np

    if not math.isfinite(hole_radius_m) or hole_radius_m <= 0:
        raise ValueError("hole radius must be positive and finite")
    if not math.isfinite(remote_tension_pa) or remote_tension_pa <= 0:
        raise ValueError("remote tensile stress must be positive and finite")
    x = np.asarray(x_m, dtype=float)
    y = np.asarray(y_m, dtype=float)
    radius = np.hypot(x, y)
    if np.any(~np.isfinite(radius)) or np.any(
        radius < hole_radius_m * (1 - 1e-9)
    ):
        raise ValueError("Kirsch stress is undefined inside circular hole")
    cos_theta = x / radius
    sin_theta = y / radius
    cos_2theta = cos_theta**2 - sin_theta**2
    sin_2theta = 2 * cos_theta * sin_theta
    a2_over_r2 = (hole_radius_m / radius) ** 2
    a4_over_r4 = a2_over_r2 ** 2
    half_tension = remote_tension_pa / 2
    sigma_rr = half_tension * (
        (1 - a2_over_r2) +
        (1 - 4 * a2_over_r2 + 3 * a4_over_r4) * cos_2theta
    )
    sigma_tt = half_tension * (
        (1 + a2_over_r2) -
        (1 + 3 * a4_over_r4) * cos_2theta
    )
    sigma_rt = -half_tension * (
        1 + 2 * a2_over_r2 - 3 * a4_over_r4
    ) * sin_2theta
    sigma_xx = (
        sigma_rr * cos_theta**2 +
        sigma_tt * sin_theta**2 -
        2 * sigma_rt * sin_theta * cos_theta
    )
    sigma_yy = (
        sigma_rr * sin_theta**2 +
        sigma_tt * cos_theta**2 +
        2 * sigma_rt * sin_theta * cos_theta
    )
    sigma_xy = (
        (sigma_rr - sigma_tt) * cos_theta * sin_theta +
        sigma_rt * cos_2theta
    )
    return {
        "sigma_rr_pa": sigma_rr,
        "sigma_tt_pa": sigma_tt,
        "tau_rt_pa": sigma_rt,
        "sigma_xx_pa": sigma_xx,
        "sigma_yy_pa": sigma_yy,
        "tau_xy_pa": sigma_xy,
    }


def run_kirsch_annulus_reference(
    *,
    hole_radius_mm: float = 3.0,
    outer_radius_mm: float = 18.0,
    mesh_target_mm: float = 1.7,
    remote_tension_pa: float = 1e6,
    youngs_modulus_pa: float = 2e9,
    poisson_ratio: float = .25,
    near_hole_ratio: float = 2.0,
    relative_error_tolerance: float = .12,
) -> dict[str, Any]:
    """2D P2 curved annulus with exact outer Kirsch traction.

    Pinning three rigid DOFs does not represent a clamp; exact outer
    tractions correspond to restricting the analytical infinite-domain
    solution to an annulus. A pass applies only to this reference problem.
    """
    import numpy as np

    for name, value in (
        ("hole_radius_mm", hole_radius_mm),
        ("outer_radius_mm", outer_radius_mm),
        ("mesh_target_mm", mesh_target_mm),
        ("remote_tension_pa", remote_tension_pa),
        ("youngs_modulus_pa", youngs_modulus_pa),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if outer_radius_mm < 5 * hole_radius_mm:
        raise ValueError("outer annulus radius must be at least 5 hole radii")
    if not .4 <= mesh_target_mm < hole_radius_mm:
        raise ValueError("mesh target must be in [0.4, hole radius) mm")
    if not -.5 < poisson_ratio < .49:
        raise ValueError("Poisson ratio must be in (-0.5, 0.49)")
    if not 1 < near_hole_ratio <= 3:
        raise ValueError("near_hole_ratio must be in (1, 3]")
    if not 0 < relative_error_tolerance <= .3:
        raise ValueError("relative_error_tolerance must be in (0, 0.3]")

    try:
        import gmsh
        import skfem
        from skfem import (
            Basis, ElementTriP2, ElementVector, FacetBasis,
            LinearForm, MeshTri, MeshTri2, asm, condense, solve,
        )
        from skfem.models.elasticity import linear_elasticity
    except ImportError as exc:
        raise RuntimeError(
            "Kirsch FEM reference needs optional Gmsh and scikit-fem"
        ) from exc

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("hs-kirsch-analytical-annulus")
        outer = gmsh.model.occ.addDisk(
            0, 0, 0, outer_radius_mm, outer_radius_mm
        )
        hole = gmsh.model.occ.addDisk(
            0, 0, 0, hole_radius_mm, hole_radius_mm
        )
        gmsh.model.occ.cut(
            [(2, outer)], [(2, hole)],
            removeObject=True, removeTool=True,
        )
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeMin", mesh_target_mm)
        gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_target_mm)
        gmsh.model.mesh.generate(2)
        gmsh.model.mesh.setOrder(2)
        gmsh.model.mesh.optimize("HighOrder", force=True)

        kinds, _, connectivity = gmsh.model.mesh.getElements(dim=2)
        if len(kinds) != 1 or int(kinds[0]) != 9:
            raise ValueError("expected quadratic Gmsh six-node triangles")
        triangles = np.asarray(connectivity[0], dtype=int).reshape((-1, 6))
        if len(triangles) < 30 or len(triangles) > 7000:
            raise ValueError("bounded Kirsch reference triangle count exceeded")
        tags, flat_positions, _ = gmsh.model.mesh.getNodes()
        positions = np.asarray(flat_positions).reshape((-1, 3))
        tag_positions = {
            int(tag): positions[i, :2] * .001
            for i, tag in enumerate(tags)
        }
        corners = sorted(set(int(tag) for tag in triangles[:, :3].ravel()))
        corner_index = {tag: i for i, tag in enumerate(corners)}
        vertices = np.asarray([tag_positions[tag] for tag in corners]).T
        cells = np.asarray([
            [corner_index[int(v)] for v in row[:3]]
            for row in triangles
        ]).T
        original = MeshTri2.from_mesh(MeshTri(vertices, cells))
        edge_midpoints = {}
        for tri in triangles:
            for j, (a, b) in enumerate(((0, 1), (1, 2), (2, 0))):
                pair = tuple(sorted(
                    (corner_index[int(tri[a])], corner_index[int(tri[b])])
                ))
                midpoint = tag_positions[int(tri[3 + j])]
                if pair in edge_midpoints and not np.allclose(
                    edge_midpoints[pair], midpoint, atol=1e-12, rtol=0
                ):
                    raise ValueError("inconsistent curved triangular edge")
                edge_midpoints[pair] = midpoint
        points = original.doflocs.copy()
        if len(edge_midpoints) != original.facets.shape[1]:
            raise ValueError("curved triangle edge topology is incomplete")
        for j, (a, b) in enumerate(original.facets.T):
            pair = tuple(sorted((int(a), int(b))))
            points[:, int(original.dofs.facet_dofs[0, j])] = (
                edge_midpoints[pair]
            )
        mesh = MeshTri2(points, original.t)
        basis = Basis(mesh, ElementVector(ElementTriP2()))
        if basis.N > 12000:
            raise ValueError("bounded Kirsch reference P2 DOF cap exceeded")

        jacobian = np.asarray(mesh.mapping().detDF(basis.X))
        # Triangles may be stored clockwise or counter-clockwise.
        # Signed Jacobian orientation can differ BETWEEN elements, but must
        # be consistent WITHIN each element and nonzero throughout sampling.
        if (
            not np.all(np.isfinite(jacobian))
            or np.any(np.min(jacobian, axis=1) * np.max(jacobian, axis=1) <= 0)
            or float(np.min(np.abs(jacobian))) <= 1e-15
        ):
            raise ValueError("Kirsch curved annulus has folded or singular Jacobians")
        boundary = mesh.boundary_facets()
        radii = np.linalg.norm(
            mesh.p[:, mesh.facets[:, boundary]], axis=0
        )
        outer_facets = boundary[
            np.all(np.abs(radii - outer_radius_mm * .001) < 1e-8, axis=0)
        ]
        inner_facets = boundary[
            np.all(np.abs(radii - hole_radius_mm * .001) < 1e-8, axis=0)
        ]
        if len(outer_facets) < 8 or len(inner_facets) < 6 or (
            len(outer_facets) + len(inner_facets) != len(boundary)
        ):
            raise ValueError("outer/hole boundary classification is incomplete")

        outer_basis = FacetBasis(
            mesh, ElementVector(ElementTriP2()),
            facets=outer_facets, dofs=basis.dofs,
        )

        @LinearForm
        def exact_outer_traction(v, w):
            stress = kirsch_stress(
                w.x[0], w.x[1],
                hole_radius_m=hole_radius_mm * .001,
                remote_tension_pa=remote_tension_pa,
            )
            tx = (
                stress["sigma_xx_pa"] * w.n[0] +
                stress["tau_xy_pa"] * w.n[1]
            )
            ty = (
                stress["tau_xy_pa"] * w.n[0] +
                stress["sigma_yy_pa"] * w.n[1]
            )
            return tx * v[0] + ty * v[1]

        load = asm(exact_outer_traction, outer_basis)
        # Plane-stress elasticity: 2D Lamé lambda differs from 3D.
        mu = youngs_modulus_pa / (2 * (1 + poisson_ratio))
        lam_plane_stress = (
            youngs_modulus_pa * poisson_ratio /
            (1 - poisson_ratio**2)
        )
        stiffness = asm(
            linear_elasticity(Lambda=lam_plane_stress, Mu=mu),
            basis,
        )
        vertices_only = mesh.p[:, :len(corners)]
        first = int(np.argmin(
            (vertices_only[0] - outer_radius_mm * .001)**2 +
            vertices_only[1]**2
        ))
        second = int(np.argmin(
            vertices_only[0]**2 +
            (vertices_only[1] - outer_radius_mm * .001)**2
        ))
        if first == second:
            raise ValueError("rigid-motion anchoring requires distinct nodes")
        rigid_pins = np.asarray([
            basis.nodal_dofs[0, first],
            basis.nodal_dofs[1, first],
            basis.nodal_dofs[0, second],
        ], dtype=int)
        displacement = solve(*condense(
            stiffness, load, D=rigid_pins
        ))
        if not np.all(np.isfinite(displacement)):
            raise ValueError("Kirsch reference produced nonfinite displacements")
        strain_gradient = basis.interpolate(displacement).grad
        strain = .5 * (strain_gradient + strain_gradient.swapaxes(0, 1))
        trace = strain[0, 0] + strain[1, 1]
        numerical_xx = lam_plane_stress * trace + 2 * mu * strain[0, 0]
        numerical_yy = lam_plane_stress * trace + 2 * mu * strain[1, 1]
        numerical_xy = 2 * mu * strain[0, 1]
        qcoords = mesh.mapping().F(basis.X)
        expected = kirsch_stress(
            qcoords[0], qcoords[1],
            hole_radius_m=hole_radius_mm * .001,
            remote_tension_pa=remote_tension_pa,
        )
        error_sq = (
            (numerical_xx - expected["sigma_xx_pa"])**2 +
            (numerical_yy - expected["sigma_yy_pa"])**2 +
            2 * (numerical_xy - expected["tau_xy_pa"])**2
        )
        reference_sq = (
            expected["sigma_xx_pa"]**2 + expected["sigma_yy_pa"]**2 +
            2 * expected["tau_xy_pa"]**2
        )
        radial_positions = np.hypot(qcoords[0], qcoords[1])
        near = radial_positions <= hole_radius_mm * .001 * near_hole_ratio
        if int(near.sum()) < 20:
            raise ValueError("insufficient near-hole quadrature samples")

        def norm_error(mask):
            weights = np.where(mask, basis.dx, 0)
            return float(np.sqrt(
                np.sum(weights * error_sq) /
                max(np.sum(weights * reference_sq), 1e-20)
            ))

        near_err = norm_error(near)
        total_err = norm_error(
            np.ones(radial_positions.shape, dtype=bool)
        )
        work = float(.5 * load @ displacement)
        energy = float(.5 * displacement @ (stiffness @ displacement))
        if not math.isclose(work, energy, rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError("Kirsch 2D numerical work-energy identity failed")
        return {
            "schema_version": "hardware_splicer.kirsch_reference.v1",
            "status": (
                "analytical_plane_stress_reference_pass"
                if near_err <= relative_error_tolerance
                else "analytical_plane_stress_reference_inconclusive"
            ),
            "reference": "Kirsch infinite plate, exact outer traction restricted to annulus",
            "theoretical_infinite_plate_peak_hoop_over_remote": 3.0,
            "hole_radius_mm": hole_radius_mm,
            "outer_radius_mm": outer_radius_mm,
            "mesh_target_mm": mesh_target_mm,
            "remote_uniaxial_tension_pa": remote_tension_pa,
            "material_assumption": {
                "youngs_modulus_pa": youngs_modulus_pa,
                "poisson_ratio": poisson_ratio,
                "stress_state": "plane_stress",
            },
            "scikit_fem_version": skfem.__version__,
            "triangle_count": len(triangles),
            "quadratic_displacement_dof_count": int(basis.N),
            "outer_boundary_facets": len(outer_facets),
            "hole_boundary_facets": len(inner_facets),
            "min_abs_sampled_curved_jacobian_m2": float(np.abs(jacobian).min()),
            "near_hole_radius_ratio": near_hole_ratio,
            "near_hole_quadrature_sample_count": int(near.sum()),
            "near_hole_weighted_stress_l2_relative_error": near_err,
            "whole_annulus_weighted_stress_l2_relative_error": total_err,
            "near_hole_error_tolerance": relative_error_tolerance,
            "strain_energy_j_per_m_thickness": energy,
            "work_energy_relative_difference": abs(work - energy) / max(
                abs(work), abs(energy), 1e-15
            ),
            "benchmark_validated_for_this_ideal_2d_case": (
                near_err <= relative_error_tolerance
            ),
            "applies_directly_to_finite_3d_bracket": False,
            "physical_validation_required": True,
            "structural_safety_verified": False,
            "fabrication_authorized": False,
            "release_authorized": False,
            "claim_boundary": (
                "An independent 2D plane-stress FE field compared to an exact "
                "Kirsch stress solution under exact outer traction; not an "
                "approval of the finite 3D bracket FEM, real fixtures or prints."
            ),
        }
    finally:
        gmsh.finalize()


def run_kirsch_reference_series(
    *, mesh_targets_mm: Sequence[float] = (2.3, 1.7, 1.3),
    relative_error_tolerance: float = .12,
) -> dict[str, Any]:
    sizes = tuple(float(x) for x in mesh_targets_mm)
    if (
        len(sizes) not in (3, 4) or
        not all(math.isfinite(s) and s >= .4 for s in sizes) or
        not all(a > b for a, b in zip(sizes, sizes[1:]))
    ):
        raise ValueError("supply 3 or 4 finite decreasing mesh sizes >=0.4 mm")
    levels = [
        run_kirsch_annulus_reference(
            mesh_target_mm=size,
            relative_error_tolerance=relative_error_tolerance,
        )
        for size in sizes
    ]
    errors = [
        x["near_hole_weighted_stress_l2_relative_error"] for x in levels
    ]
    decreasing = all(
        next_err < previous for previous, next_err in zip(errors, errors[1:])
    )
    blockers = []
    if not decreasing:
        blockers.append("near_hole_stress_field_error_not_decreasing")
    if any(x["status"] != "analytical_plane_stress_reference_pass" for x in levels):
        blockers.append("analytical_near_hole_error_tolerance_not_met")
    if any(
        b["quadratic_displacement_dof_count"] <= a["quadratic_displacement_dof_count"]
        for a, b in zip(levels, levels[1:])
    ):
        blockers.append("quadratic_dof_count_not_increasing")
    return {
        "schema_version": "hardware_splicer.kirsch_reference_series.v1",
        "status": (
            "analytical_plane_stress_series_pass" if not blockers
            else "inconclusive_kirsch_reference_series"
        ),
        "levels": levels,
        "blockers": blockers,
        "finite_3d_geometry_strength_verified": False,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Reproduce Kirsch exact-traction 2D annulus reference benchmark"
    )
    p.add_argument("--mesh-study-mm", type=float, nargs="+", default=[2.3, 1.7, 1.3])
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    result = run_kirsch_reference_series(mesh_targets_mm=args.mesh_study_mm)
    from pathlib import Path
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Kirsch status: {result['status']}; report={output}")
    return 0 if result["status"] == "analytical_plane_stress_series_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())

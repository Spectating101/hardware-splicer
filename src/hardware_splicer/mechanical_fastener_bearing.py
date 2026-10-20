"""Auditable reduced-order bearing-load model for a two-hole STEP bracket.

Not nonlinear unilateral bolt contact. One hole's selected semicylindrical
wall is fully constrained (over-stiff approximation). The other receives a
cosine-weighted *compressive-normal* pressure on its opposite semicylinder.
The load is integrated with curved P2 surface quadrature, normalized to the
requested axial force, and checked for spurious transverse resultant.

The model reports separately sampled neighborhood stress around BOTH holes;
global peak switching is not mistaken for one hole's stress nonconvergence.
All fabrication and structural-release authority remains false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

MAX_DOF = 8000


def _validate_inputs(
    centers_xy_mm: Sequence[Sequence[float]],
    hole_d_mm: float,
    thickness_mm: float,
    force_n: float,
    youngs_pa: float,
    poisson: float,
    neighborhood_mm: float,
) -> list[tuple[float, float]]:
    if len(centers_xy_mm) != 2:
        raise ValueError("exactly two through-hole centers are required")
    centers = []
    for center in centers_xy_mm:
        if len(center) != 2 or not all(math.isfinite(float(v)) for v in center):
            raise ValueError("hole centers must contain two finite XY coordinates")
        centers.append((float(center[0]), float(center[1])))
    if centers[0][0] >= centers[1][0]:
        raise ValueError("hole centers must be ordered in increasing X")
    for key, number in [
        ("hole_d_mm", hole_d_mm),
        ("thickness_mm", thickness_mm),
        ("force_n", force_n),
        ("youngs_pa", youngs_pa),
        ("neighborhood_mm", neighborhood_mm),
    ]:
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f"{key} must be finite positive")
    if not 1 <= hole_d_mm <= 50 or not 1 <= thickness_mm <= 100:
        raise ValueError("unreasonable bracket dimensions")
    if not 0 < force_n <= 1000:
        raise ValueError("force_n must be <=1000 N")
    if not 1e6 <= youngs_pa <= 1e12:
        raise ValueError("Young's modulus outside bounded range")
    if not -.5 < poisson < .49:
        raise ValueError("Poisson ratio outside physical range")
    if not .5 <= neighborhood_mm <= 20:
        raise ValueError("stress neighborhood must be [0.5,20] mm")
    if math.dist(centers[0], centers[1]) <= (
        hole_d_mm + 2 * neighborhood_mm
    ):
        raise ValueError("hole stress neighborhoods overlap")
    return centers


def solve_bore_bearing_case(
    step_path: str | Path,
    *,
    mesh_target_mm: float,
    centers_xy_mm: Sequence[Sequence[float]],
    hole_d_mm: float,
    thickness_mm: float,
    force_n: float = 30.0,
    youngs_pa: float = 2e9,
    poisson: float = .25,
    stress_neighborhood_mm: float = 3.,
) -> dict[str, Any]:
    """Bounded P2 curved FEM with hole-specific bearing/anchor approximations."""
    import numpy as np
    from skfem import (
        MeshTet, MeshTet2, Basis, ElementTetP2, ElementVector,
        FacetBasis, LinearForm, asm, solve, condense,
    )
    from skfem.models.elasticity import lame_parameters, linear_elasticity
    from .mechanical_cad_fem import mesh_cad_solid
    from .mechanical_quadratic_fem import _validated_curved_jacobian

    centers = _validate_inputs(
        centers_xy_mm, hole_d_mm, thickness_mm, force_n,
        youngs_pa, poisson, stress_neighborhood_mm,
    )
    if not math.isfinite(mesh_target_mm) or not 1 <= mesh_target_mm <= 15:
        raise ValueError("mesh target must be [1, 15] mm")
    m = mesh_cad_solid(
        step_path, mesh_target_mm=mesh_target_mm, geometry_order=2
    )
    corners = np.asarray(m.nodes_m, dtype=float).T
    cells = np.asarray(m.elements, dtype=int).T
    base = MeshTet2.from_mesh(MeshTet(corners, cells))
    mids = {
        tuple(edge): np.asarray(xyz, dtype=float)
        for edge, xyz in zip(
            m.quadratic_edge_vertices, m.quadratic_edge_midpoints_m
        )
    }
    if len(mids) != base.edges.shape[1]:
        raise ValueError("incomplete curved midside STEP geometry")
    coords = base.doflocs.copy()
    for i, (a, b) in enumerate(base.edges.T):
        key = tuple(sorted((int(a), int(b))))
        if key not in mids:
            raise ValueError("missing curved tetrahedral edge")
        coords[:, base.dofs.edge_dofs[0, i]] = mids[key]
    fem_mesh = MeshTet2(coords, base.t)
    vector_element = ElementVector(ElementTetP2())
    basis = Basis(fem_mesh, vector_element)
    if basis.N > MAX_DOF:
        raise ValueError("fastener-bearing quadratic DOF cap exceeded")
    min_jac, jac_ratio = _validated_curved_jacobian(
        fem_mesh, basis.X
    )

    integrated_volume = float(np.sum(basis.dx))
    cad_volume = m.cad_kernel_volume_m3
    if cad_volume is None or abs(integrated_volume / cad_volume - 1) > .01:
        raise ValueError("curved mesh volume disagrees with exact CAD BREP")
    if not math.isclose(
        float(fem_mesh.p[2].max() - fem_mesh.p[2].min()),
        thickness_mm * .001,
        abs_tol=.00005,
    ):
        raise ValueError("STEP thickness mismatch")
    exterior = fem_mesh.boundary_facets()
    facet_xyz = fem_mesh.p[:, fem_mesh.facets[:, exterior]]
    hole_radius = hole_d_mm * .0005
    wall_masks = []
    wall_areas = []
    for cx_mm, cy_mm in centers:
        cx = cx_mm * .001
        cy = cy_mm * .001
        distances = np.hypot(
            facet_xyz[0] - cx, facet_xyz[1] - cy
        )
        # Every corner of a cylinder triangle must lie on that hole's
        # CAD circle, not an adjacent top/bottom planar face.
        mask = np.all(
            np.abs(distances - hole_radius) < .00012, axis=0
        )
        wall_masks.append(mask)
        faces = exterior[mask]
        if len(faces) < 12:
            raise ValueError("too few complete hole wall facets")
        face_basis = FacetBasis(
            fem_mesh, vector_element, facets=faces, dofs=basis.dofs
        )
        full_area = float(np.sum(face_basis.dx))
        ideal_area = math.pi * hole_d_mm * .001 * thickness_mm * .001
        if not .94 <= full_area / ideal_area <= 1.06:
            raise ValueError(
                "cylindrical wall area mismatches declared hole geometry"
            )
        wall_areas.append(full_area)

    if np.any(wall_masks[0] & wall_masks[1]):
        raise ValueError("two hole walls overlap in facet classification")
    # Left/anchor bore: fully restrain only the left-facing semicylinder,
    # not the entire end face. It is still NOT a bolt/contact simulation.
    left_x = np.mean(facet_xyz[0][:,wall_masks[0]], axis=0)
    anchor_faces = exterior[wall_masks[0]][
        left_x < centers[0][0] * .001 - hole_radius * .1
    ]
    right_x = np.mean(facet_xyz[0][:,wall_masks[1]], axis=0)
    load_faces = exterior[wall_masks[1]][
        right_x > centers[1][0] * .001 + hole_radius * .1
    ]
    if len(anchor_faces) < 6 or len(load_faces) < 6:
        raise ValueError("insufficient bore bearing faces for this mesh")
    anchor_dofs = basis.get_dofs(facets=anchor_faces).flatten()
    if len(anchor_dofs) < 9:
        raise ValueError("underconstrained simplified bore support")
    pressure_basis = FacetBasis(
        fem_mesh, vector_element, facets=load_faces, dofs=basis.dofs
    )
    area = float(np.sum(pressure_basis.dx))
    # Bearing pressure = p0 * max(0, -n_x), pointing into bracket
    # along (-n). Normalize exact assembled x-resultant to force_n.
    @LinearForm
    def bearing_unit_pressure(v, w):
        influence = np.maximum(0., -w.n[0])
        return -influence * (
            w.n[0] * v[0] + w.n[1] * v[1] + w.n[2] * v[2]
        )

    unit_load = asm(bearing_unit_pressure, pressure_basis)
    def force_resultant(vec):
        return np.asarray([
            float(vec[basis.nodal_dofs[axis]].sum()) +
            float(vec[basis.edge_dofs[axis]].sum())
            for axis in range(3)
        ])

    per_pa_resultant = force_resultant(unit_load)
    if not per_pa_resultant[0] > area * .15:
        raise ValueError("invalid bore normal or pressure direction")
    scale_pa = force_n / per_pa_resultant[0]
    forcing = unit_load * scale_pa
    applied_resultant = force_resultant(forcing)
    lateral_ratio = float(np.linalg.norm(
        applied_resultant[1:]
    ) / force_n)
    if lateral_ratio > .05:
        raise ValueError(
            "bearing traction produces >5% lateral force; refine mesh"
        )

    mu, lam = lame_parameters(youngs_pa, poisson)
    stiffness = asm(
        linear_elasticity(Lambda=lam, Mu=mu), basis
    )
    solution = solve(*condense(
        stiffness, forcing, D=anchor_dofs
    ))
    if not np.all(np.isfinite(solution)):
        raise ValueError("nonfinite fastener-bearing FE solution")
    residual = stiffness @ solution - forcing
    unconstrained = np.setdiff1d(
        np.arange(basis.N), anchor_dofs
    )
    free_residual = float(np.linalg.norm(residual[unconstrained]))
    if free_residual > 1e-7 * max(1, force_n):
        raise ValueError("unbalanced free FE DOF residual")
    reaction = force_resultant(residual)
    balance_err = float(np.linalg.norm(
        reaction + applied_resultant
    ))
    if balance_err > 1e-7 * max(1, force_n):
        raise ValueError("bearing reaction balance failed")

    gradient = basis.interpolate(solution).grad
    strain = .5 * (gradient + np.swapaxes(gradient, 0, 1))
    sigma = (
        lam * np.eye(3)[:, :, None, None] *
        np.trace(strain, axis1=0, axis2=1)[None, None, :, :] +
        2 * mu * strain
    )
    dev = sigma - np.eye(3)[:, :, None, None] * (
        np.trace(sigma, axis1=0, axis2=1)[None, None, :, :] / 3
    )
    vm = np.sqrt(1.5 * np.einsum(
        "ijeq,ijeq->eq", dev, dev
    ))
    if not np.all(np.isfinite(vm)):
        raise ValueError("invalid sampled von Mises stress")
    qcoords = fem_mesh.mapping().F(basis.X)
    neighborhoods = []
    for index, (cx_mm, cy_mm) in enumerate(centers):
        r = np.hypot(
            qcoords[0] - cx_mm * .001,
            qcoords[1] - cy_mm * .001,
        )
        # Physical annulus immediately outside nominal bore.
        inside = (r >= hole_radius * .985) & (
            r <= hole_radius + stress_neighborhood_mm * .001
        )
        if int(inside.sum()) < 10:
            raise ValueError("insufficient quadrature samples per hole")
        local_vm = np.where(inside, vm, -np.inf)
        peak_index = np.unravel_index(
            int(np.argmax(local_vm)), vm.shape
        )
        neighborhoods.append({
            "hole_index": index,
            "center_xy_mm": [cx_mm, cy_mm],
            "quadrature_sample_count": int(inside.sum()),
            "peak_sampled_von_mises_pa": float(
                vm[peak_index]
            ),
            "peak_sample_location_m": [
                float(qcoords[axis][peak_index])
                for axis in range(3)
            ],
            "weighted_rms_von_mises_pa": float(np.sqrt(
                np.sum(basis.dx * np.where(inside, vm**2, 0.)) /
                max(np.sum(basis.dx * inside), 1e-18)
            )),
        })

    energy = float(.5 * solution @ (stiffness @ solution))
    half_work = float(.5 * forcing @ solution)
    if not math.isclose(energy, half_work, rel_tol=1e-7, abs_tol=1e-11):
        raise ValueError("fastener FEM energy/work mismatch")
    return {
        "schema_version": "hardware_splicer.bore_bearing_case.v1",
        "status": "reduced_order_bore_bearing_screen_only",
        "source_step_sha256": m.source_sha256,
        "mesh_target_mm": mesh_target_mm,
        "tetrahedron_count": len(m.elements),
        "quadratic_dof_count": int(basis.N),
        "hole_wall_full_area_m2": wall_areas,
        "anchor_half_wall_facet_count": int(len(anchor_faces)),
        "load_half_wall_facet_count": int(len(load_faces)),
        "load_half_wall_area_m2": area,
        "bearing_pressure_scale_pa": float(scale_pa),
        "nominal_bearing_pressure_pa": (
            force_n / (hole_d_mm * .001 * thickness_mm * .001)
        ),
        "integrated_bearing_resultant_n": applied_resultant.tolist(),
        "support_reaction_n": reaction.tolist(),
        "resultant_lateral_fraction": lateral_ratio,
        "force_balance_error_n": balance_err,
        "unconstrained_dof_residual_n": free_residual,
        "min_curved_jacobian": min_jac,
        "jacobian_ratio": jac_ratio,
        "curved_vs_step_volume_error": abs(
            integrated_volume / cad_volume - 1
        ),
        "strain_energy_j": energy,
        "external_half_work_j": half_work,
        "peak_sampled_von_mises_pa": float(np.max(vm)),
        "hole_neighborhood_width_mm": stress_neighborhood_mm,
        "per_hole_stress": neighborhoods,
        "applied_force_n": force_n,
        "boundary_assumptions": {
            "support": "fully-fixed left-facing semicylindrical wall of first hole",
            "bearing": "cosine-weighted frictionless-style radial pressure on right-facing semicylindrical wall of second hole",
            "contact_is_unilateral_nonlinear": False,
            "bolt_shank_or_clearance_modeled": False,
            "bolt_preload_or_friction_modeled": False,
            "material_is_isotropic_homogeneous_linear_elastic": True,
        },
        "stress_convergence_verified": False,
        "material_properties_measured": False,
        "joint_strength_verified": False,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }


def run_fastener_bearing_mesh_series(
    step_path: str | Path,
    *,
    mesh_targets_mm: Sequence[float],
    centers_xy_mm: Sequence[Sequence[float]],
    hole_d_mm: float,
    thickness_mm: float,
    force_n: float = 30.,
    youngs_pa: float = 2e9,
    poisson: float = .25,
    per_hole_stress_tolerance: float = .05,
    per_hole_rms_tolerance: float = .03,
    hotspot_angle_tolerance_deg: float = 45.,
) -> dict[str, Any]:
    sizes = [float(s) for s in mesh_targets_mm]
    if (
        len(sizes) not in (3, 4)
        or not all(math.isfinite(s) and 1 <= s <= 15 for s in sizes)
        or not all(a > b for a, b in zip(sizes, sizes[1:]))
    ):
        raise ValueError("need 3–4 decreasing mesh targets in [1,15] mm")
    for key, value, hi in (
        ("per_hole_stress_tolerance", per_hole_stress_tolerance, .25),
        ("per_hole_rms_tolerance", per_hole_rms_tolerance, .25),
        ("hotspot_angle_tolerance_deg", hotspot_angle_tolerance_deg, 180),
    ):
        if not math.isfinite(value) or not 0 < value <= hi:
            raise ValueError(f"{key} must be in (0,{hi}]")
    levels = [
        solve_bore_bearing_case(
            step_path, mesh_target_mm=size,
            centers_xy_mm=centers_xy_mm,
            hole_d_mm=hole_d_mm, thickness_mm=thickness_mm,
            force_n=force_n, youngs_pa=youngs_pa, poisson=poisson,
        )
        for size in sizes
    ]
    hashes = {item["source_step_sha256"] for item in levels}
    if len(hashes) != 1:
        raise ValueError("source STEP changed during hole-bearing study")
    comparisons = []
    blockers = []
    for coarse, fine in zip(levels, levels[1:]):
        compare = {
            "coarse_mesh_mm": coarse["mesh_target_mm"],
            "fine_mesh_mm": fine["mesh_target_mm"],
            "quadratic_dof_growth": (
                fine["quadratic_dof_count"] /
                coarse["quadratic_dof_count"]
            ),
            "holes": [],
        }
        if compare["quadratic_dof_growth"] < 1.08:
            blockers.append("insufficient_bearing_mesh_refinement")
        for before, after in zip(
            coarse["per_hole_stress"], fine["per_hole_stress"]
        ):
            p1, p2 = (
                before["peak_sampled_von_mises_pa"],
                after["peak_sampled_von_mises_pa"],
            )
            rms1, rms2 = (
                before["weighted_rms_von_mises_pa"],
                after["weighted_rms_von_mises_pa"],
            )
            peak_change = abs(p2 - p1) / max(p1, p2, 1e-6)
            rms_change = abs(rms2 - rms1) / max(rms1, rms2, 1e-6)
            cx, cy = before["center_xy_mm"]
            a = before["peak_sample_location_m"]
            b = after["peak_sample_location_m"]
            angle1 = math.degrees(math.atan2(
                a[1] * 1e3 - cy, a[0] * 1e3 - cx
            ))
            angle2 = math.degrees(math.atan2(
                b[1] * 1e3 - cy, b[0] * 1e3 - cx
            ))
            angle_diff = abs((angle2 - angle1 + 180) % 360 - 180)
            check = {
                "hole_index": before["hole_index"],
                "peak_stress_relative_change": peak_change,
                "rms_stress_relative_change": rms_change,
                "peak_angle_shift_deg": angle_diff,
                "peak_tolerance_met": peak_change <= per_hole_stress_tolerance,
                "rms_tolerance_met": rms_change <= per_hole_rms_tolerance,
                "angle_tolerance_met": angle_diff <= hotspot_angle_tolerance_deg,
            }
            compare["holes"].append(check)
            if not check["peak_tolerance_met"]:
                blockers.append(
                    f"hole_{before['hole_index']}_peak_stress_unstable"
                )
            if not check["rms_tolerance_met"]:
                blockers.append(
                    f"hole_{before['hole_index']}_rms_stress_unstable"
                )
            if not check["angle_tolerance_met"]:
                blockers.append(
                    f"hole_{before['hole_index']}_hotspot_angle_unstable"
                )
        comparisons.append(compare)
    blockers = sorted(set(blockers))
    return {
        "schema_version": "hardware_splicer.bore_bearing_study.v1",
        "status": (
            "inconclusive_bore_bearing_refinement"
            if blockers else "numerically_stable_reduced_order_bearing_screen"
        ),
        "source_step_sha256": levels[0]["source_step_sha256"],
        "mesh_targets_mm": sizes,
        "levels": levels,
        "adjacent_comparisons": comparisons,
        "blockers": blockers,
        "per_hole_stress_tolerance": per_hole_stress_tolerance,
        "per_hole_rms_tolerance": per_hole_rms_tolerance,
        "hotspot_angle_tolerance_deg": hotspot_angle_tolerance_deg,
        "nonlinear_bolt_contact_verified": False,
        "true_joint_bearing_strength_verified": False,
        "material_properties_measured": False,
        "stress_convergence_verified": False,
        "physical_validation_required": True,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
        "claim_boundary": (
            "Prescribed semi-bore support and compressive-normal traction, "
            "not nonlinear bolt contact. Per-hole FEM field screening cannot "
            "establish real printed-part strength or fabrication suitability."
        ),
    }


def screen_mecha_bracket_bearing(
    *,
    spec: Mapping[str, Any],
    step_path: str | Path,
    mesh_targets_mm: Sequence[float] = (8, 6, 5),
    force_n: float = 30.,
    youngs_pa: float = 2e9,
    poisson: float = .25,
) -> dict[str, Any]:
    """Create a provenance-bound STEP from actual Mecha bracket parameters."""
    from .mechanical_bracket_screening import (
        _check_bracket_spec, generate_bracket_reference_step,
    )

    numbers = _check_bracket_spec(spec)
    geometry = generate_bracket_reference_step(spec, step_path)
    centers = geometry["cylindrical_through_hole_centers_xy_mm"]
    series = run_fastener_bearing_mesh_series(
        step_path, mesh_targets_mm=mesh_targets_mm,
        centers_xy_mm=centers,
        hole_d_mm=numbers["hole_d_mm"],
        thickness_mm=numbers["t_mm"],
        force_n=force_n, youngs_pa=youngs_pa, poisson=poisson,
    )
    canonical = json.dumps(
        {"name": str(spec.get("name", "bracket")), "numbers": numbers},
        sort_keys=True, separators=(",", ":"),
    )
    return {
        "schema_version": "hardware_splicer.mecha_fastener_bearing.v1",
        "status": (
            "inconclusive_mecha_fastener_bearing"
            if series["blockers"]
            else "numerically_stable_reduced_order_mecha_bearing_screen"
        ),
        "mecha_source_spec_sha256": "sha256:" + hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
        "geometry": geometry,
        "bearing_study": series,
        "true_bolt_contact_validated": False,
        "screw_hole_bearing_strength_verified": False,
        "printing_direction_characterized": False,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Screen reduced-order hole bearing on a trusted two-hole STEP"
    )
    p.add_argument("step", type=Path, nargs="?")
    p.add_argument("--spec-json", type=Path, help="Mecha bracket template/spec")
    p.add_argument("--step-out", type=Path, help="New STEP for --spec-json")
    p.add_argument("--centers-xy-mm", nargs=4, type=float)
    p.add_argument("--hole-d-mm", type=float)
    p.add_argument("--thickness-mm", type=float)
    p.add_argument("--mesh-study-mm", nargs="+", type=float, default=[8, 6, 5])
    p.add_argument("--force-n", type=float, default=30)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    if args.spec_json is not None:
        if args.step is not None or args.step_out is None:
            p.error("--spec-json requires --step-out, without positional STEP")
        content = json.loads(args.spec_json.read_text(encoding="utf-8"))
        spec = content.get("bracket", content)
        report = screen_mecha_bracket_bearing(
            spec=spec, step_path=args.step_out,
            mesh_targets_mm=args.mesh_study_mm, force_n=args.force_n,
        )
        study = report["bearing_study"]
    else:
        if (
            args.step is None or args.centers_xy_mm is None
            or args.hole_d_mm is None or args.thickness_mm is None
        ):
            p.error("positional STEP requires hole centers, diameter, and thickness")
        report = run_fastener_bearing_mesh_series(
            args.step,
            centers_xy_mm=[
                args.centers_xy_mm[:2], args.centers_xy_mm[2:]
            ],
            hole_d_mm=args.hole_d_mm,
            thickness_mm=args.thickness_mm,
            mesh_targets_mm=args.mesh_study_mm,
            force_n=args.force_n,
        )
        study = report
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Bore-bearing status={report['status']}; "
        f"blockers={study['blockers']}; report={args.out}"
    )
    return 2 if study["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

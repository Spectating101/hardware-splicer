"""Opt-in second-order displacement FEM for the bounded CAD screening pathway.

scikit-fem P2 vector basis on Gmsh *linear-geometry* tetrahedral meshes.
The curved STEP surface is approximated by straight tetrahedral faces: this
is NOT an isoparametric high-order CAD geometry discretization.

No physical authorization, fabrication approval, or automated safety margin.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Literal, Sequence

from .mechanical_cad_fem import (
    AxisPlane, LocalRefinement, build_face_loaded_case, mesh_cad_solid,
)
from .mechanical_fem import solve_linear_tetra_fem

MAX_QUADRATIC_DOF = 8000


def _load_backend() -> tuple[Any, ...]:
    try:
        import numpy as np
        from skfem import (
            Basis, ElementTetP2, ElementVector, FacetBasis, LinearForm,
            MeshTet, asm, condense, solve,
        )
        from skfem.models.elasticity import lame_parameters, linear_elasticity
        import skfem
    except ImportError as exc:
        raise RuntimeError(
            "Quadratic screening requires optional scikit-fem; "
            "install '.[physics,physics-validation,cad-meshing]'"
        ) from exc
    return (
        np, skfem, Basis, ElementTetP2, ElementVector,
        FacetBasis, LinearForm, MeshTet, asm, condense, solve,
        lame_parameters, linear_elasticity,
    )


def run_quadratic_cad_screening(
    path: str | Path,
    *,
    mesh_target_mm: float,
    stl_units: Literal["mm"] | None,
    fixed_plane: AxisPlane,
    loaded_plane: AxisPlane,
    total_force_n: list[float],
    youngs_modulus_pa: float,
    poisson_ratio: float,
    yield_strength_pa: float | None = None,
    local_refinement: LocalRefinement | None = None,
    analytic_bar_benchmark: Literal["axial", "cantilever"] | None = None,
    benchmark_relative_tolerance: float = 0.05,
) -> dict[str, Any]:
    """Solve a static linear-elastic P2 displacement problem, with strict bounds.

    Report P1 baseline on precisely the same conforming straight-sided
    tetrahedral geometry. The P2 traction is integrated on all selected
    planar boundary facets with quadratic basis functions.
    """
    (
        np, skfem, Basis, ElementTetP2, ElementVector,
        FacetBasis, LinearForm, MeshTet, asm, condense, solve,
        lame_parameters, linear_elasticity,
    ) = _load_backend()
    mesh = mesh_cad_solid(
        path, mesh_target_mm=mesh_target_mm, stl_units=stl_units,
        local_refinement=local_refinement,
    )
    case, bc = build_face_loaded_case(
        mesh, fixed_plane=fixed_plane, loaded_plane=loaded_plane,
        total_force_n=total_force_n, youngs_modulus_pa=youngs_modulus_pa,
        poisson_ratio=poisson_ratio, yield_strength_pa=yield_strength_pa,
    )
    baseline = solve_linear_tetra_fem(case)

    points = np.asarray(mesh.nodes_m, dtype=float).T
    cells = np.asarray(mesh.elements, dtype=int).T
    scmesh = MeshTet(points, cells)
    basis_element = ElementVector(ElementTetP2())
    basis = Basis(scmesh, basis_element)
    if basis.N > MAX_QUADRATIC_DOF:
        raise ValueError(
            f"quadratic FEM has {basis.N} degrees of freedom; "
            f"bounded cap is {MAX_QUADRATIC_DOF}; enlarge mesh target"
        )

    def surface_facets(plane: AxisPlane):
        axis = "xyz".index(plane[0])
        is_min = plane.endswith("_min")
        extreme = float(
            scmesh.p[axis].min() if is_min else scmesh.p[axis].max()
        )
        # Require an actual planar exterior face rather than a guess
        # based on a singular mesh vertex.
        tolerance = max(1e-9, mesh_target_mm * 1e-9)
        return scmesh.facets_satisfying(
            lambda x: np.abs(x[axis] - extreme) < tolerance,
            boundaries_only=True,
        )

    clamp_faces = surface_facets(fixed_plane)
    load_faces = surface_facets(loaded_plane)
    if len(clamp_faces) == 0 or len(load_faces) == 0:
        raise ValueError("support/load plane has no actual mesh surface facets")
    fixed = basis.get_dofs(facets=clamp_faces).flatten()
    loaded = FacetBasis(
        scmesh, basis_element, facets=load_faces, dofs=basis.dofs
    )
    face_area = float(np.sum(loaded.dx))
    if not math.isclose(
        face_area, bc["loaded_face_area_m2"], rel_tol=1e-5, abs_tol=1e-12
    ):
        raise ValueError("quadratic load face differs from CAD mesh boundary")
    if not math.isfinite(face_area) or face_area <= 0:
        raise ValueError("quadratic FEM requires nonzero planar load face area")
    traction = np.asarray(total_force_n, dtype=float) / face_area

    @LinearForm
    def uniform_traction(v, w):
        return traction[0] * v[0] + traction[1] * v[1] + traction[2] * v[2]

    force = asm(uniform_traction, loaded)
    # Every P2 vertex/edge DOF participates, unlike an incorrect P1 nodal-only
    # load applied to a quadratic stiffness system.
    force_per_axis = np.asarray([
        float(force[basis.nodal_dofs[axis]].sum()) +
        float(force[basis.edge_dofs[axis]].sum())
        for axis in range(3)
    ])
    if not np.allclose(
        force_per_axis, np.asarray(total_force_n), rtol=1e-8, atol=1e-9
    ):
        raise ValueError("quadratic face traction failed force conservation")

    mu, lam = lame_parameters(
        case.youngs_modulus_pa, case.poisson_ratio
    )
    stiffness = asm(
        linear_elasticity(Lambda=lam, Mu=mu), basis
    )
    displacement = solve(*condense(stiffness, force, D=fixed))
    if not np.all(np.isfinite(displacement)):
        raise ValueError("quadratic solver returned nonfinite displacements")
    free = np.setdiff1d(
        np.arange(basis.N), fixed, assume_unique=False
    )
    residual = stiffness @ displacement - force
    free_residual = float(np.linalg.norm(residual[free]))
    if free_residual > 1e-7 * max(1.0, float(np.linalg.norm(force))):
        raise ValueError("quadratic unconstrained equilibrium residual too large")
    reaction_force = np.asarray([
        float(residual[basis.nodal_dofs[axis]].sum()) +
        float(residual[basis.edge_dofs[axis]].sum())
        for axis in range(3)
    ])
    equilibrium_error = float(np.linalg.norm(
        reaction_force + force_per_axis
    ))
    if equilibrium_error > 1e-7 * max(
        1.0, float(np.linalg.norm(force_per_axis))
    ):
        raise ValueError("quadratic support reaction equilibrium failed")

    gradient = basis.interpolate(displacement).grad
    if gradient.ndim != 4 or gradient.shape[:2] != (3, 3):
        raise ValueError("unexpected P2 gradient tensor shape")
    strain = 0.5 * (gradient + np.swapaxes(gradient, 0, 1))
    trace = np.trace(strain, axis1=0, axis2=1)
    ident = np.eye(3)
    stress = (
        lam * ident[:, :, None, None] * trace[None, None, :, :] +
        2 * mu * strain
    )
    mean = np.trace(stress, axis1=0, axis2=1) / 3
    deviator = stress - ident[:, :, None, None] * mean[None, None, :, :]
    vm = np.sqrt(
        1.5 * np.einsum("ijeq,ijeq->eq", deviator, deviator)
    )
    if not np.all(np.isfinite(vm)):
        raise ValueError("quadratic solver returned nonfinite stresses")

    nodal = displacement[basis.nodal_dofs].T
    edge = displacement[basis.edge_dofs].T
    all_qnodes = np.concatenate((nodal, edge), axis=0)
    max_qnode_disp = float(np.linalg.norm(all_qnodes, axis=1).max())
    half_work = float(0.5 * (force @ displacement))
    strain_energy = float(0.5 * (displacement @ (stiffness @ displacement)))
    energy_discrepancy = abs(strain_energy - half_work) / max(
        abs(strain_energy), abs(half_work), 1e-14
    )
    if energy_discrepancy > 1e-7:
        raise ValueError("quadratic stiffness energy-work identity failed")
    force_norm = float(np.linalg.norm(total_force_n))
    load_work_conjugate_deflection = 2 * half_work / force_norm

    # Stress from P2 varies inside each tetrahedron; explicitly return
    # quadrature-point maxima, not a misleading constant-element stress.
    p2_peak_stress = float(np.max(vm))
    result: dict[str, Any] = {
        "schema_version": "hardware_splicer.quadratic_fem.v1",
        "status": "quadratic_numerical_screening_only",
        "source_name": mesh.source_name,
        "source_cad_sha256": mesh.source_sha256,
        "source_format": mesh.source_format,
        "mesh_target_mm": mesh_target_mm,
        "mesh_volume_m3": mesh.volume_m3,
        "mesh_to_cad_volume_relative_error": mesh.mesh_volume_error_fraction,
        "local_refinement": mesh.local_refinement,
        "geometry_interpolation_order": 1,
        "displacement_interpolation_order": 2,
        "backend": "scikit-fem",
        "backend_version": skfem.__version__,
        "tetrahedron_count": len(mesh.elements),
        "geometry_vertex_count": len(mesh.nodes_m),
        "quadratic_displacement_dof_count": int(basis.N),
        "quadratic_solution_node_count": len(all_qnodes),
        "stress_sampling": "P2 Gauss quadrature points on linear-geometry tetrahedra",
        "stress_quadrature_points_per_element": int(vm.shape[1]),
        "p2_max_displacement_at_nodes_m": max_qnode_disp,
        "p2_load_work_conjugate_deflection_m": load_work_conjugate_deflection,
        "p2_peak_quadrature_von_mises_pa": p2_peak_stress,
        "p2_quadrature_peak_stress_per_element_pa": np.max(vm, axis=1).tolist(),
        "p1_load_work_conjugate_deflection_m": (
            sum(
                float(np.dot(
                    np.asarray(loading.force_n),
                    np.asarray(baseline["nodal_displacements_m"])[loading.node],
                ))
                for loading in case.loads_n
            ) / force_norm
        ),
        "p1_peak_element_von_mises_pa": baseline["max_von_mises_pa"],
        "force_n": list(total_force_n),
        "total_applied_face_force_n": force_per_axis.tolist(),
        "support_reaction_n": reaction_force.tolist(),
        "free_dof_force_residual_n": free_residual,
        "global_force_equilibrium_error_n": equilibrium_error,
        "strain_energy_j": strain_energy,
        "half_external_work_j": half_work,
        "energy_relative_error": energy_discrepancy,
        "fixed_plane": fixed_plane,
        "loaded_plane": loaded_plane,
        "load_face_area_m2": face_area,
        "youngs_modulus_pa": youngs_modulus_pa,
        "poisson_ratio": poisson_ratio,
        "assumed_yield_strength_pa": yield_strength_pa,
        "mesh_convergence_verified": False,
        "independent_physical_model_verified": False,
        "structural_safety_verified": False,
        "yield_margin_usable_for_engineering_release": False,
        "physical_validation_required": True,
        "fabrication_authorized": False,
        "release_authorized": False,
        "limitations": [
            "P2 displacement basis but P1 straight-sided mesh geometry, including curved CAD hole approximation",
            "Small-strain static linear isotropic elasticity only",
            "Ideal fully clamped surface and assumed uniform end traction",
            "Peak stress sampled at quadrature points; singularities and unmeasured material behaviour remain unresolved",
            "Numerical success cannot authorize fabrication or mechanical strength",
        ],
    }

    if analytic_bar_benchmark is not None:
        from .mechanical_fem_crosscheck import _rectangular_bar_analytic_benchmark
        reference = _rectangular_bar_analytic_benchmark(
            case=case,
            mesh=mesh,
            mode=analytic_bar_benchmark,
            fixed_plane=fixed_plane,
            loaded_plane=loaded_plane,
            total_force_n=total_force_n,
            measured_displacement_m=load_work_conjugate_deflection,
            relative_tolerance=benchmark_relative_tolerance,
        )
        result["analytic_reference"] = reference
        if not reference["within_declared_tolerance"]:
            result["status"] = "analytic_benchmark_disagreement"
    return result


def run_quadratic_mesh_benchmark(
    path: str | Path,
    *,
    mesh_targets_mm: Sequence[float],
    stl_units: Literal["mm"] | None,
    fixed_plane: AxisPlane,
    loaded_plane: AxisPlane,
    total_force_n: list[float],
    youngs_modulus_pa: float,
    poisson_ratio: float,
    analytic_bar_benchmark: Literal["axial", "cantilever"],
    benchmark_relative_tolerance: float = 0.05,
    displacement_change_tolerance: float = 0.02,
) -> dict[str, Any]:
    """Three/four-level evidence for P2 bending/axial accuracy on known bars."""
    sizes = tuple(float(x) for x in mesh_targets_mm)
    if len(sizes) not in {3, 4} or not all(
        math.isfinite(s) and .5 <= s <= 500 for s in sizes
    ) or not all(a > b for a, b in zip(sizes, sizes[1:])):
        raise ValueError("provide 3 or 4 strictly decreasing finite mesh sizes (0.5..500 mm)")
    if not 0 < displacement_change_tolerance <= .25:
        raise ValueError("displacement_change_tolerance must be in (0, 0.25]")
    levels = []
    sha = None
    for size in sizes:
        out = run_quadratic_cad_screening(
            path,
            mesh_target_mm=size,
            stl_units=stl_units,
            fixed_plane=fixed_plane,
            loaded_plane=loaded_plane,
            total_force_n=total_force_n,
            youngs_modulus_pa=youngs_modulus_pa,
            poisson_ratio=poisson_ratio,
            analytic_bar_benchmark=analytic_bar_benchmark,
            benchmark_relative_tolerance=benchmark_relative_tolerance,
        )
        if sha is not None and out["source_cad_sha256"] != sha:
            raise ValueError("CAD source changed during quadratic benchmark")
        sha = out["source_cad_sha256"]
        levels.append({
            "mesh_target_mm": size,
            "tetrahedron_count": out["tetrahedron_count"],
            "quadratic_dof_count": out["quadratic_displacement_dof_count"],
            "p1_displacement_m": out["p1_load_work_conjugate_deflection_m"],
            "p2_displacement_m": out["p2_load_work_conjugate_deflection_m"],
            "p2_peak_quadrature_stress_pa": out["p2_peak_quadrature_von_mises_pa"],
            "analytic_reference_m": out["analytic_reference"]["reference_displacement_m"],
            "p2_analytic_relative_error": out["analytic_reference"]["relative_error"],
            "analytic_gate_pass": out["analytic_reference"]["within_declared_tolerance"],
        })
    comparisons = []
    for a, b in zip(levels, levels[1:]):
        change = abs(b["p2_displacement_m"] - a["p2_displacement_m"]) / max(
            abs(b["p2_displacement_m"]), abs(a["p2_displacement_m"]), 1e-15
        )
        growth = float(b["quadratic_dof_count"] / a["quadratic_dof_count"])
        comparisons.append({
            "coarse_mesh_mm": a["mesh_target_mm"],
            "fine_mesh_mm": b["mesh_target_mm"],
            "quadratic_dof_growth": growth,
            "p2_displacement_relative_change": change,
            "relative_change_tolerance_met": change <= displacement_change_tolerance,
            "effective_refinement": growth > 1.10,
        })
    blockers = []
    if any(not x["effective_refinement"] for x in comparisons):
        blockers.append("insufficient_quadratic_dof_growth")
    if any(not x["relative_change_tolerance_met"] for x in comparisons):
        blockers.append("p2_displacement_changes_with_refinement")
    if any(not x["analytic_gate_pass"] for x in levels):
        blockers.append("p2_analytic_reference_disagreement")
    passed = not blockers
    return {
        "schema_version": "hardware_splicer.quadratic_mesh_benchmark.v1",
        "status": (
            "analytical_and_mesh_displacement_screen_pass" if passed
            else "inconclusive_quadratic_benchmark"
        ),
        "source_cad_sha256": sha,
        "benchmark": analytic_bar_benchmark,
        "mesh_sizes_mm": list(sizes),
        "levels": levels,
        "adjacent_comparisons": comparisons,
        "blockers": blockers,
        "p2_numerically_stable_against_declared_reference": passed,
        "p2_peak_stress_convergence_verified": False,
        "mesh_convergence_verified": False,
        "independent_physical_model_verified": False,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
        "claim_boundary": (
            "Displacement convergence within finite samples and agreement "
            "with idealized beam theory only; no physical or structural approval."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Run bounded P2 tetrahedral elasticity and beam benchmarks"
    )
    p.add_argument("cad_file", type=Path)
    p.add_argument("--mesh-size-mm", type=float, default=8)
    p.add_argument("--mesh-study-mm", nargs="+", type=float)
    p.add_argument("--stl-units", choices=["mm"])
    faces = ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]
    p.add_argument("--fixed-plane", choices=faces, required=True)
    p.add_argument("--loaded-plane", choices=faces, required=True)
    p.add_argument("--force-n", nargs=3, type=float, required=True)
    p.add_argument("--youngs-pa", type=float, required=True)
    p.add_argument("--poisson", type=float, required=True)
    p.add_argument("--yield-pa", type=float)
    p.add_argument("--analytic-bar-benchmark", choices=["axial", "cantilever"])
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    if args.mesh_study_mm is not None:
        if args.analytic_bar_benchmark is None:
            p.error("--mesh-study-mm requires --analytic-bar-benchmark")
        report = run_quadratic_mesh_benchmark(
            args.cad_file, mesh_targets_mm=args.mesh_study_mm,
            stl_units=args.stl_units,
            fixed_plane=args.fixed_plane, loaded_plane=args.loaded_plane,
            total_force_n=args.force_n, youngs_modulus_pa=args.youngs_pa,
            poisson_ratio=args.poisson,
            analytic_bar_benchmark=args.analytic_bar_benchmark,
        )
        good = report["status"] == "analytical_and_mesh_displacement_screen_pass"
    else:
        report = run_quadratic_cad_screening(
            args.cad_file, mesh_target_mm=args.mesh_size_mm,
            stl_units=args.stl_units,
            fixed_plane=args.fixed_plane, loaded_plane=args.loaded_plane,
            total_force_n=args.force_n, youngs_modulus_pa=args.youngs_pa,
            poisson_ratio=args.poisson, yield_strength_pa=args.yield_pa,
            analytic_bar_benchmark=args.analytic_bar_benchmark,
        )
        good = report["status"] == "quadratic_numerical_screening_only"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Quadratic FEM status={report['status']}; report={args.out}")
    return 0 if good else 2


if __name__ == "__main__":
    raise SystemExit(main())

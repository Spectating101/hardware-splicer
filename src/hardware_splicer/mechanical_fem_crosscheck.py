"""Independent numerical cross-check using scikit-fem (optional verifier).

An independently assembled FEM system on the *same* mesh and load case is a
valuable implementation check, not proof of physical model accuracy.
No manufacturing or structural safety authority is generated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Literal

from .mechanical_fem import FemInput, solve_linear_tetra_fem

SCHEMA_VERSION = "hardware_splicer.mechanical_fem_crosscheck.v1"


def _independent_scikit_fem(case: FemInput) -> dict[str, Any]:
    try:
        import numpy as np
        import skfem
        from skfem import Basis, ElementTetP1, ElementVector, MeshTet, asm, condense, solve
        from skfem.models.elasticity import lame_parameters, linear_elasticity
    except ImportError as exc:
        raise RuntimeError(
            "Independent cross-check requires optional scikit-fem; "
            "install '[physics,physics-validation]'"
        ) from exc

    mesh = MeshTet(
        np.asarray(case.nodes_m, dtype=float).T,
        np.asarray(case.elements, dtype=int).T,
    )
    basis = Basis(mesh, ElementVector(ElementTetP1()))
    lam, mu = lame_parameters(
        case.youngs_modulus_pa, case.poisson_ratio
    )
    stiffness = asm(linear_elasticity(Lambda=lam, Mu=mu), basis)

    forces = np.zeros(basis.N, dtype=float)
    for loading in case.loads_n:
        for axis, newtons in enumerate(loading.force_n):
            forces[basis.nodal_dofs[axis, loading.node]] += newtons

    fixed_dofs = np.unique([
        int(basis.nodal_dofs[axis, constraint.node])
        for constraint in case.constraints
        for axis, fixed in enumerate(constraint.axes)
        if fixed
    ])
    with np.errstate(over="raise", invalid="raise"):
        displacement = solve(
            *condense(stiffness, forces, D=fixed_dofs)
        )
    if not np.all(np.isfinite(displacement)):
        raise ValueError("independent solver returned nonfinite displacement")

    nodal_displacements = np.stack(
        [displacement[basis.nodal_dofs[axis]] for axis in range(3)],
        axis=1,
    )
    # skfem independently supplies the global shape-function gradient
    # (3 output dimensions × 3 spatial derivatives × element × quadrature).
    gradient = basis.interpolate(displacement).grad[:, :, :, 0]
    strain = .5 * (gradient + gradient.swapaxes(0, 1))
    trace = np.trace(strain, axis1=0, axis2=1)
    identity = np.eye(3)
    stress = (
        lam * identity[:, :, None] * trace[None, None, :] +
        2 * mu * strain
    )
    deviator = stress - (
        identity[:, :, None] *
        np.trace(stress, axis1=0, axis2=1)[None, None, :] / 3
    )
    vm = np.sqrt(
        1.5 * np.einsum("ije,ije->e", deviator, deviator)
    )
    reactions = stiffness @ displacement - forces
    support_reactions = np.stack(
        [reactions[basis.nodal_dofs[axis]] for axis in range(3)],
        axis=1,
    )
    energy_j = float(.5 * displacement @ (stiffness @ displacement))
    work_j = float(.5 * forces @ displacement)
    return {
        "solver": "scikit-fem",
        "version": skfem.__version__,
        "formulation": "independent_P1_vector_linear_elasticity",
        "nodal_displacements_m": nodal_displacements.tolist(),
        "element_von_mises_pa": vm.tolist(),
        "max_displacement_m": float(np.linalg.norm(nodal_displacements, axis=1).max()),
        "max_von_mises_pa": float(vm.max()),
        "total_strain_energy_j": energy_j,
        "external_half_work_j": work_j,
        "support_reactions_n": support_reactions.tolist(),
    }


def _relative_error(lhs: float, rhs: float, scale: float = 0.0) -> float:
    return abs(lhs - rhs) / max(abs(lhs), abs(rhs), scale, 1e-18)


def crosscheck_fem_case(
    case: FemInput | dict[str, Any],
    *,
    relative_tolerance: float = 1e-6,
) -> dict[str, Any]:
    """Cross-check HS vs independently assembled scikit-fem on one identical mesh.

    No mutating machine or engineering authority. Fails closed if verifier is
    missing, throws, or disagrees. Returned evidence is still screening only.
    """
    if not math.isfinite(relative_tolerance) or not (
        0 < relative_tolerance <= 0.05
    ):
        raise ValueError("relative_tolerance must be finite in (0, 0.05]")
    if not isinstance(case, FemInput):
        case = FemInput.model_validate(case)

    import numpy as np

    hs = solve_linear_tetra_fem(case)
    independent = _independent_scikit_fem(case)
    hs_displacement = np.asarray(hs["nodal_displacements_m"])
    other_displacement = np.asarray(independent["nodal_displacements_m"])
    hs_stress = np.asarray(hs["element_von_mises_pa"])
    other_stress = np.asarray(independent["element_von_mises_pa"])
    hs_reactions = np.asarray(hs["support_reactions_n"])
    other_reactions = np.asarray(independent["support_reactions_n"])

    if hs_displacement.shape != other_displacement.shape:
        raise ValueError("solvers returned different displacement field shapes")
    if hs_stress.shape != other_stress.shape:
        raise ValueError("solvers returned different stress field shapes")
    if hs_reactions.shape != other_reactions.shape:
        raise ValueError("solvers returned different reaction field shapes")

    nodal_l2_relative = float(
        np.linalg.norm(hs_displacement - other_displacement) /
        max(
            np.linalg.norm(hs_displacement),
            np.linalg.norm(other_displacement), 1e-15
        )
    )
    stress_l2_relative = float(
        np.linalg.norm(hs_stress - other_stress) /
        max(np.linalg.norm(hs_stress), np.linalg.norm(other_stress), 1e-6)
    )
    reactions_l2_relative = float(
        np.linalg.norm(hs_reactions - other_reactions) /
        max(
            np.linalg.norm(hs_reactions), np.linalg.norm(other_reactions), 1e-6
        )
    )
    half_work_hs = .5 * sum(
        float(np.dot(
            np.asarray(row.force_n), hs_displacement[row.node]
        ))
        for row in case.loads_n
    )
    energy_rel = _relative_error(
        half_work_hs, independent["total_strain_energy_j"], 1e-12
    )
    independent_self_equilibrium = _relative_error(
        independent["total_strain_energy_j"],
        independent["external_half_work_j"],
        1e-12,
    )

    metrics = {
        "max_displacement_relative_error": _relative_error(
            hs["max_displacement_m"], independent["max_displacement_m"],
            1e-15,
        ),
        "max_stress_relative_error": _relative_error(
            hs["max_von_mises_pa"], independent["max_von_mises_pa"],
            1e-6,
        ),
        "nodal_displacement_l2_relative_error": nodal_l2_relative,
        "element_von_mises_l2_relative_error": stress_l2_relative,
        "support_reactions_l2_relative_error": reactions_l2_relative,
        "strain_energy_relative_error": energy_rel,
        "independent_energy_work_balance_relative_error": independent_self_equilibrium,
    }
    blockers = [
        metric for metric, value in metrics.items()
        if not math.isfinite(value) or value > relative_tolerance
    ]
    case_payload = case.model_dump(mode="json", exclude_none=False)
    content = json.dumps(case_payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    net_force = np.sum(
        [np.asarray(load.force_n) for load in case.loads_n], axis=0
    )
    force_magnitude = float(np.linalg.norm(net_force))
    conjugate_deflection_m = float(
        2.0 * half_work_hs / max(force_magnitude, 1e-15)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "independent_numerical_agreement"
            if not blockers else "independent_numerical_disagreement"
        ),
        "validated_case_sha256": f"sha256:{digest}",
        "node_count": len(case.nodes_m),
        "tetrahedron_count": len(case.elements),
        "reference_solver": "scikit-fem",
        "reference_solver_version": independent["version"],
        "relative_tolerance": relative_tolerance,
        "comparison_metrics": metrics,
        "disagreement_blockers": blockers,
        "hardware_splicer_summary": {
            "max_displacement_m": hs["max_displacement_m"],
            "max_von_mises_pa": hs["max_von_mises_pa"],
            "strain_energy_from_half_work_j": half_work_hs,
            "load_work_conjugate_deflection_m": conjugate_deflection_m,
        },
        "independent_solver_summary": {
            "max_displacement_m": independent["max_displacement_m"],
            "max_von_mises_pa": independent["max_von_mises_pa"],
            "total_strain_energy_j": independent["total_strain_energy_j"],
            "external_half_work_j": independent["external_half_work_j"],
        },
        "agrees_with_same_model_and_mesh_only": not blockers,
        "independent_physical_model_verified": False,
        "yield_margin_usable_for_engineering_release": False,
        "mesh_convergence_verified": False,
        "structural_safety_verified": False,
        "physical_validation_required": True,
        "fabrication_authorized": False,
        "release_authorized": False,
        "claim_boundary": (
            "This cross-check compares two FEM implementations on identical "
            "geometry, loads, mesh, material and boundary conditions. Numerical "
            "agreement does not independently validate their shared physical "
            "assumptions or approve fabrication, stress margins or release."
        ),
    }


def _rectangular_bar_analytic_benchmark(
    *,
    case: FemInput,
    mesh: Any,
    mode: Literal["axial", "cantilever"],
    fixed_plane: str,
    loaded_plane: str,
    total_force_n: list[float],
    measured_displacement_m: float,
    relative_tolerance: float,
) -> dict[str, Any]:
    """Idealized rectangular beam reference (not a general stress proof).

    Classical Euler–Bernoulli bending + rectangular Timoshenko shear
    correction. This benchmark intentionally rejects drilled or complex parts.
    """
    if not math.isfinite(relative_tolerance) or not (
        0 < relative_tolerance <= 0.25
    ):
        raise ValueError("benchmark_relative_tolerance must be in (0, 0.25]")
    if mode not in {"axial", "cantilever"}:
        raise ValueError("unsupported analytic rectangular beam benchmark")
    if fixed_plane != "x_min" or loaded_plane != "x_max":
        raise ValueError("rectangular reference requires x_min clamp and x_max load")

    bounds = mesh.bounding_box_m
    length, width, height = (
        float(bounds[1][i] - bounds[0][i]) for i in range(3)
    )
    if min(length, width, height) <= 0:
        raise ValueError("invalid rectangular bar bounds")
    rectangular_volume = length * width * height
    if (
        mesh.cad_kernel_volume_m3 is None
        or abs(mesh.cad_kernel_volume_m3 - rectangular_volume)
        / rectangular_volume > 0.001
    ):
        raise ValueError(
            "analytical rectangular reference requires an unperforated "
            "STEP bar; holes and approximate STL solids are unsupported"
        )
    if length < 8 * max(width, height):
        raise ValueError(
            "beam reference requires length at least eight times cross-section"
        )
    fx, fy, fz = total_force_n
    if mode == "axial":
        if fx == 0 or fy != 0 or fz != 0:
            raise ValueError("axial benchmark requires x-directed force only")
        nominal_displacement = abs(fx) * length / (
            case.youngs_modulus_pa * width * height
        )
        reference = "F L / E A"
    else:
        if fx != 0 or (fy == 0) == (fz == 0):
            raise ValueError(
                "cantilever benchmark requires exactly one transverse force"
            )
        bending_about_y = fz != 0
        force = abs(fz) if bending_about_y else abs(fy)
        inertia = (
            width * height**3 / 12 if bending_about_y
            else height * width**3 / 12
        )
        beam_bending = force * length**3 / (
            3 * case.youngs_modulus_pa * inertia
        )
        shear_modulus = case.youngs_modulus_pa / (
            2 * (1 + case.poisson_ratio)
        )
        nominal_displacement = beam_bending + force * length / (
            (5 / 6) * shear_modulus * width * height
        )
        reference = "Euler-Bernoulli end bending + Timoshenko shear correction"

    discrepancy = _relative_error(
        measured_displacement_m, nominal_displacement, 1e-15
    )
    return {
        "benchmark": f"rectangular_bar_{mode}",
        "reference_formula": reference,
        "reference_displacement_m": nominal_displacement,
        "hs_work_conjugate_deflection_m": measured_displacement_m,
        "relative_error": discrepancy,
        "declared_tolerance": relative_tolerance,
        "within_declared_tolerance": discrepancy <= relative_tolerance,
        "limits": (
            "Reference valid only for idealized straight long rectangular "
            "homogeneous prismatic members under small-deformation loads. "
            "Does not cover local stress, clamp compliance or physical tests."
        ),
    }


def validate_cad_with_independent_solver(
    path: str | Path,
    *,
    mesh_target_mm: float,
    stl_units: Literal["mm"] | None,
    fixed_plane: Literal["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"],
    loaded_plane: Literal["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"],
    total_force_n: list[float],
    youngs_modulus_pa: float,
    poisson_ratio: float,
    yield_strength_pa: float | None = None,
    relative_tolerance: float = 1e-6,
    analytic_bar_benchmark: Literal["axial", "cantilever"] | None = None,
    benchmark_relative_tolerance: float = 0.10,
) -> dict[str, Any]:
    from .mechanical_cad_fem import build_face_loaded_case, mesh_cad_solid

    mesh = mesh_cad_solid(
        path, mesh_target_mm=mesh_target_mm, stl_units=stl_units
    )
    case, boundary = build_face_loaded_case(
        mesh,
        fixed_plane=fixed_plane,
        loaded_plane=loaded_plane,
        total_force_n=total_force_n,
        youngs_modulus_pa=youngs_modulus_pa,
        poisson_ratio=poisson_ratio,
        yield_strength_pa=yield_strength_pa,
    )
    report = crosscheck_fem_case(
        case, relative_tolerance=relative_tolerance
    )
    if analytic_bar_benchmark is not None:
        analytic = _rectangular_bar_analytic_benchmark(
            case=case,
            mesh=mesh,
            mode=analytic_bar_benchmark,
            fixed_plane=fixed_plane,
            loaded_plane=loaded_plane,
            total_force_n=total_force_n,
            measured_displacement_m=report["hardware_splicer_summary"][
                "load_work_conjugate_deflection_m"
            ],
            relative_tolerance=benchmark_relative_tolerance,
        )
        report["analytic_reference"] = analytic
        if (
            not analytic["within_declared_tolerance"]
            and report["status"] == "independent_numerical_agreement"
        ):
            report["status"] = "analytic_benchmark_disagreement"
    return {
        **report,
        "source_cad_sha256": mesh.source_sha256,
        "source_name": mesh.source_name,
        "source_format": mesh.source_format,
        "mesh_target_mm": mesh_target_mm,
        "boundary_conditions": boundary,
        "mesh_volume_m3": mesh.volume_m3,
        "mesh_to_cad_volume_relative_error": mesh.mesh_volume_error_fraction,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Independently cross-check HS bounded CAD/FEM against scikit-fem"
    )
    p.add_argument("cad_file", type=Path)
    p.add_argument("--mesh-size-mm", type=float, default=8.0)
    p.add_argument("--stl-units", choices=["mm"])
    faces = ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]
    p.add_argument("--fixed-plane", choices=faces, required=True)
    p.add_argument("--loaded-plane", choices=faces, required=True)
    p.add_argument("--force-n", type=float, nargs=3, required=True)
    p.add_argument("--youngs-pa", type=float, required=True)
    p.add_argument("--poisson", type=float, required=True)
    p.add_argument("--yield-pa", type=float)
    p.add_argument("--relative-tolerance", type=float, default=1e-6)
    p.add_argument("--analytic-bar-benchmark", choices=["axial", "cantilever"])
    p.add_argument("--benchmark-relative-tolerance", type=float, default=0.10)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    report = validate_cad_with_independent_solver(
        args.cad_file,
        mesh_target_mm=args.mesh_size_mm,
        stl_units=args.stl_units,
        fixed_plane=args.fixed_plane,
        loaded_plane=args.loaded_plane,
        total_force_n=args.force_n,
        youngs_modulus_pa=args.youngs_pa,
        poisson_ratio=args.poisson,
        yield_strength_pa=args.yield_pa,
        relative_tolerance=args.relative_tolerance,
        analytic_bar_benchmark=args.analytic_bar_benchmark,
        benchmark_relative_tolerance=args.benchmark_relative_tolerance,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Independent FEM {report['status']}: "
        f"{len(report['disagreement_blockers'])} discrepancies; "
        f"report={args.out}"
    )
    return 0 if report["status"] == "independent_numerical_agreement" else 2


if __name__ == "__main__":
    raise SystemExit(main())

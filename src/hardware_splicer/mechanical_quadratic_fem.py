"""Opt-in second-order displacement FEM for the bounded CAD screening pathway.

scikit-fem P2 vector basis on Gmsh *linear-geometry* tetrahedral meshes.
The curved STEP surface is approximated by straight tetrahedral faces: this
is NOT an isoparametric high-order CAD geometry discretization.

No physical authorization, fabrication approval, or automated safety margin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal, Sequence

from .mechanical_cad_fem import (
    AxisPlane, CadTetraMesh, LocalRefinement, build_face_loaded_case, mesh_cad_solid,
)
from .mechanical_fem import solve_linear_tetra_fem

MAX_QUADRATIC_DOF = 8000


def _validated_curved_jacobian(
    scmesh: Any, quadrature_points: Any
) -> tuple[float, float]:
    """Fail closed on nonpositive curved Jacobians at multiple sample sets.

    Even this multi-point check is not a mathematical proof of positivity
    *everywhere* in a polynomial curved tetrahedral element.
    """
    import numpy as np
    from skfem.quadrature import get_quadrature_tet

    corners_and_center = np.asarray([
        [0.0, 1.0, 0.0, 0.0, 0.25],
        [0.0, 0.0, 1.0, 0.0, 0.25],
        [0.0, 0.0, 0.0, 1.0, 0.25],
    ])
    probes = [
        quadrature_points,
        get_quadrature_tet(5)[0],
        corners_and_center,
    ]
    smallest = float("inf")
    largest = float("-inf")
    for points in probes:
        determinants = np.asarray(scmesh.mapping().detDF(points))
        if not np.all(np.isfinite(determinants)):
            raise ValueError("curved mesh has nonfinite Jacobians")
        smallest = min(smallest, float(determinants.min()))
        largest = max(largest, float(determinants.max()))
    if smallest <= 0 or smallest / max(largest, 1e-30) < 1e-9:
        raise ValueError(
            "inverted or near-singular curved tetrahedral Jacobian; "
            "decrease mesh size or improve mesh quality"
        )
    return smallest, smallest / largest


def _load_backend() -> tuple[Any, ...]:
    try:
        import numpy as np
        from skfem import (
            Basis, ElementTetP2, ElementVector, FacetBasis, LinearForm,
            MeshTet, MeshTet2, asm, condense, solve,
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
        FacetBasis, LinearForm, MeshTet, MeshTet2, asm, condense, solve,
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
    geometry_order: Literal[1, 2] = 1,
    _pre_meshed: CadTetraMesh | None = None,
) -> dict[str, Any]:
    """Solve a static linear-elastic P2 displacement problem, with strict bounds.

    Report P1 baseline on precisely the same conforming straight-sided
    tetrahedral geometry. The P2 traction is integrated on all selected
    planar boundary facets with quadratic basis functions.
    """
    (
        np, skfem, Basis, ElementTetP2, ElementVector,
        FacetBasis, LinearForm, MeshTet, MeshTet2, asm, condense, solve,
        lame_parameters, linear_elasticity,
    ) = _load_backend()
    mesh = _pre_meshed
    if mesh is None:
        mesh = mesh_cad_solid(
            path, mesh_target_mm=mesh_target_mm, stl_units=stl_units,
            local_refinement=local_refinement, geometry_order=geometry_order,
        )
    if mesh.geometry_interpolation_order != geometry_order:
        raise ValueError("pre-meshed geometry interpolation order mismatch")
    case, bc = build_face_loaded_case(
        mesh, fixed_plane=fixed_plane, loaded_plane=loaded_plane,
        total_force_n=total_force_n, youngs_modulus_pa=youngs_modulus_pa,
        poisson_ratio=poisson_ratio, yield_strength_pa=yield_strength_pa,
    )
    baseline = solve_linear_tetra_fem(case)

    points = np.asarray(mesh.nodes_m, dtype=float).T
    cells = np.asarray(mesh.elements, dtype=int).T
    straight_mesh = MeshTet(points, cells)
    mesh_topology = hashlib.sha256(json.dumps(
        {"nodes_m": mesh.nodes_m, "elements": mesh.elements},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    curved_edges = 0
    max_midpoint_deviation = 0.0
    if geometry_order == 2:
        if (
            mesh.geometry_interpolation_order != 2
            or mesh.quadratic_edge_vertices is None
            or mesh.quadratic_edge_midpoints_m is None
        ):
            raise ValueError("Gmsh did not provide complete curved geometry")
        sc_base = MeshTet2.from_mesh(straight_mesh)
        source_edge_mids = {
            tuple(pair): np.asarray(mid, dtype=float)
            for pair, mid in zip(
                mesh.quadratic_edge_vertices, mesh.quadratic_edge_midpoints_m
            )
        }
        if len(source_edge_mids) != len(sc_base.edges.T):
            raise ValueError("curved geometry edge count disagrees with P2 basis")
        doflocs = sc_base.doflocs.copy()
        for idx, (a, b) in enumerate(sc_base.edges.T):
            pair = tuple(sorted((int(a), int(b))))
            if pair not in source_edge_mids:
                raise ValueError("missing curved midside node for tetrahedral edge")
            midpoint = source_edge_mids[pair]
            chord_midpoint = (points[:, a] + points[:, b]) * .5
            deviation = float(np.linalg.norm(midpoint - chord_midpoint))
            max_midpoint_deviation = max(max_midpoint_deviation, deviation)
            if deviation > 1e-10:
                curved_edges += 1
            doflocs[:, int(sc_base.dofs.edge_dofs[0, idx])] = midpoint
        scmesh = MeshTet2(doflocs, sc_base.t)
    else:
        scmesh = straight_mesh
    basis_element = ElementVector(ElementTetP2())
    basis = Basis(scmesh, basis_element)
    if basis.N > MAX_QUADRATIC_DOF:
        raise ValueError(
            f"quadratic FEM has {basis.N} degrees of freedom; "
            f"bounded cap is {MAX_QUADRATIC_DOF}; enlarge mesh target"
        )
    curved_volume = None
    jacobian_ratio = None
    min_jacobian = None
    curved_volume_error = None
    if geometry_order == 2:
        # A high-order mesh can contain inverted/near-singular Jacobians even
        # if its total volume looks excellent. Never solve such elements.
        min_jacobian, jacobian_ratio = _validated_curved_jacobian(
            scmesh, basis.X
        )
        curved_volume = float(np.sum(basis.dx))
        if (
            not math.isfinite(curved_volume)
            or curved_volume <= 0
            or mesh.cad_kernel_volume_m3 is None
        ):
            raise ValueError("invalid curved mesh integrated volume")
        curved_volume_error = abs(
            curved_volume - mesh.cad_kernel_volume_m3
        ) / mesh.cad_kernel_volume_m3
        if curved_volume_error > .01:
            raise ValueError(
                "curved tetrahedral integrated volume differs from exact "
                "STEP CAD kernel volume by more than 1%"
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

    lam, mu = lame_parameters(
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
    peak_tet, peak_quadrature = np.unravel_index(
        int(np.argmax(vm)), vm.shape
    )
    physical_quadrature_positions = scmesh.mapping().F(basis.X)
    peak_stress_location_m = [
        float(physical_quadrature_positions[axis, peak_tet, peak_quadrature])
        for axis in range(3)
    ]
    result: dict[str, Any] = {
        "schema_version": "hardware_splicer.quadratic_fem.v1",
        "status": "quadratic_numerical_screening_only",
        "source_name": mesh.source_name,
        "source_cad_sha256": mesh.source_sha256,
        "linear_geometry_topology_sha256": f"sha256:{mesh_topology}",
        "source_format": mesh.source_format,
        "mesh_target_mm": mesh_target_mm,
        "mesh_volume_m3": mesh.volume_m3,
        "mesh_to_cad_volume_relative_error": mesh.mesh_volume_error_fraction,
        "local_refinement": mesh.local_refinement,
        "geometry_interpolation_order": geometry_order,
        "displacement_interpolation_order": 2,
        "geometry_mapping": (
            "Gmsh_10_node_curved_isoparametric"
            if geometry_order == 2 else "linear_tetrahedra_straight_sided"
        ),
        "high_order_gmsh_optimization": (
            "HighOrder" if geometry_order == 2 else None
        ),
        "non_chord_midside_node_count": curved_edges,
        "max_curved_edge_chord_deviation_m": max_midpoint_deviation,
        "min_sampled_jacobian_determinant_m3": min_jacobian,
        "min_to_max_sampled_jacobian_ratio": jacobian_ratio,
        "curved_integrated_volume_m3": curved_volume,
        "curved_vs_cad_volume_error_fraction": curved_volume_error,
        "backend": "scikit-fem",
        "backend_version": skfem.__version__,
        "tetrahedron_count": len(mesh.elements),
        "geometry_vertex_count": len(mesh.nodes_m),
        "quadratic_displacement_dof_count": int(basis.N),
        "quadratic_solution_node_count": len(all_qnodes),
        "stress_sampling": (
            "P2 Gauss quadrature points on curved-geometry tetrahedra"
            if geometry_order == 2 else
            "P2 Gauss quadrature points on linear-geometry tetrahedra"
        ),
        "stress_quadrature_points_per_element": int(vm.shape[1]),
        "p2_max_displacement_at_nodes_m": max_qnode_disp,
        "p2_load_work_conjugate_deflection_m": load_work_conjugate_deflection,
        "p2_peak_quadrature_von_mises_pa": p2_peak_stress,
        "p2_peak_stress_quadrature_location_m": peak_stress_location_m,
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
            (
                "P2 curved isoparametric geometry sampled at FE quadrature "
                "points; quality and accuracy are not certified"
                if geometry_order == 2 else
                "P2 displacement basis but P1 straight-sided mesh geometry, "
                "including curved CAD hole approximation"
            ),
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


def compare_curved_geometry(
    path: str | Path,
    *,
    mesh_target_mm: float,
    fixed_plane: AxisPlane,
    loaded_plane: AxisPlane,
    total_force_n: list[float],
    youngs_modulus_pa: float,
    poisson_ratio: float,
    stress_difference_alert: float = 0.03,
    local_refinement: LocalRefinement | None = None,
) -> dict[str, Any]:
    """Compare straight and curved P2 *on identical corner-mesh topology*.

    This is geometric *sensitivity* rather than stress-convergence proof.
    The CAD should contain curved features for the comparison to be useful.
    Refuse silently mismatched meshes.
    """
    if not (
        math.isfinite(stress_difference_alert)
        and 0 < stress_difference_alert <= .25
    ):
        raise ValueError("stress_difference_alert must be in (0, 0.25]")
    args = {
        "mesh_target_mm": mesh_target_mm,
        "stl_units": None,
        "fixed_plane": fixed_plane,
        "loaded_plane": loaded_plane,
        "total_force_n": total_force_n,
        "youngs_modulus_pa": youngs_modulus_pa,
        "poisson_ratio": poisson_ratio,
        "local_refinement": local_refinement,
    }
    # Gmsh's high-order optimizer may move linear geometry vertices to
    # untangle a curved element. Solve both on the *same post-optimization*
    # corner mesh so the comparison isolates isoparametric midside geometry.
    curved_mesh = mesh_cad_solid(
        path, mesh_target_mm=mesh_target_mm,
        stl_units=None, local_refinement=local_refinement,
        geometry_order=2,
    )
    flattened_mesh = replace(
        curved_mesh, geometry_interpolation_order=1,
        quadratic_edge_vertices=None, quadratic_edge_midpoints_m=None,
    )
    straight = run_quadratic_cad_screening(
        path, geometry_order=1, _pre_meshed=flattened_mesh, **args
    )
    curved = run_quadratic_cad_screening(
        path, geometry_order=2, _pre_meshed=curved_mesh, **args
    )
    if (
        straight["source_cad_sha256"] != curved["source_cad_sha256"]
        or straight["linear_geometry_topology_sha256"]
        != curved["linear_geometry_topology_sha256"]
    ):
        raise ValueError(
            "straight and curved mesh corner topology is not identical; "
            "comparison would be confounded by unrelated remeshing"
        )
    peak1 = straight["p2_peak_quadrature_von_mises_pa"]
    peak2 = curved["p2_peak_quadrature_von_mises_pa"]
    stress_relative_difference = abs(peak2 - peak1) / max(
        abs(peak1), abs(peak2), 1e-6
    )
    disp1 = straight["p2_load_work_conjugate_deflection_m"]
    disp2 = curved["p2_load_work_conjugate_deflection_m"]
    displacement_relative_difference = abs(disp2 - disp1) / max(
        abs(disp1), abs(disp2), 1e-15
    )
    curved_source_present = curved["non_chord_midside_node_count"] > 0
    blockers = []
    if not curved_source_present:
        blockers.append("no_nonchord_midside_nodes")
    if stress_relative_difference > stress_difference_alert:
        blockers.append("peak_stress_sensitive_to_curved_geometry")
    return {
        "schema_version": "hardware_splicer.curved_fem_comparison.v1",
        "status": (
            "geometry_sensitive_screening" if blockers
            else "geometry_comparison_within_declared_threshold"
        ),
        "source_cad_sha256": curved["source_cad_sha256"],
        "linear_geometry_topology_sha256": curved[
            "linear_geometry_topology_sha256"
        ],
        "identical_vertex_mesh_topology_confirmed": True,
        "tetrahedron_count": curved["tetrahedron_count"],
        "mesh_target_mm": mesh_target_mm,
        "straight_p2_peak_von_mises_pa": peak1,
        "curved_p2_peak_von_mises_pa": peak2,
        "peak_stress_relative_geometry_difference": stress_relative_difference,
        "p2_displacement_relative_geometry_difference": displacement_relative_difference,
        "straight_p2_load_work_conjugate_deflection_m": disp1,
        "curved_p2_load_work_conjugate_deflection_m": disp2,
        "straight_p1_mesh_volume_m3": straight["mesh_volume_m3"],
        "curved_integrated_volume_m3": curved["curved_integrated_volume_m3"],
        "straight_vs_cad_volume_error_fraction": straight[
            "mesh_to_cad_volume_relative_error"
        ],
        "curved_vs_cad_volume_error_fraction": curved[
            "curved_vs_cad_volume_error_fraction"
        ],
        "non_chord_midside_node_count": curved[
            "non_chord_midside_node_count"
        ],
        "max_midside_chord_deviation_m": curved[
            "max_curved_edge_chord_deviation_m"
        ],
        "minimum_curved_jacobian_determinant_m3": curved[
            "min_sampled_jacobian_determinant_m3"
        ],
        "stress_difference_alert": stress_difference_alert,
        "geometry_sensitivity_blockers": blockers,
        "stress_convergence_verified": False,
        "mesh_convergence_verified": False,
        "physical_validation_required": True,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
        "claim_boundary": (
            "Matched-mesh geometry sensitivity only. Curved boundary "
            "representation and lower volume error do not by themselves "
            "validate peak stress, supports, material behavior or strength."
        ),
    }


def run_curved_stress_sensitivity(
    path: str | Path,
    *,
    mesh_targets_mm: Sequence[float],
    fixed_plane: AxisPlane,
    loaded_plane: AxisPlane,
    total_force_n: list[float],
    youngs_modulus_pa: float,
    poisson_ratio: float,
    stress_tolerance: float = .03,
    displacement_tolerance: float = .02,
    hotspot_location_tolerance_mm: float = 5.0,
    local_refinement: LocalRefinement | None = None,
) -> dict[str, Any]:
    """Bounded 3–4-mesh P2 curved stress sensitivity; never certifies strength."""
    sizes = [float(x) for x in mesh_targets_mm]
    if (
        len(sizes) not in (3, 4)
        or not all(math.isfinite(s) and .5 <= s <= 500 for s in sizes)
        or not all(a > b for a, b in zip(sizes, sizes[1:]))
    ):
        raise ValueError(
            "curved stress study needs 3–4 decreasing finite mesh sizes (0.5..500 mm)"
        )
    if not math.isfinite(stress_tolerance) or not 0 < stress_tolerance <= .25:
        raise ValueError("stress_tolerance must be finite in (0, 0.25]")
    if not math.isfinite(displacement_tolerance) or not (
        0 < displacement_tolerance <= .25
    ):
        raise ValueError("displacement_tolerance must be finite in (0, 0.25]")
    if not (
        math.isfinite(hotspot_location_tolerance_mm)
        and .1 <= hotspot_location_tolerance_mm <= 100
    ):
        raise ValueError(
            "hotspot_location_tolerance_mm must be finite in [0.1, 100]"
        )

    levels = []
    source_hash = None
    for size in sizes:
        out = run_quadratic_cad_screening(
            path, mesh_target_mm=size, stl_units=None,
            fixed_plane=fixed_plane, loaded_plane=loaded_plane,
            total_force_n=total_force_n,
            youngs_modulus_pa=youngs_modulus_pa,
            poisson_ratio=poisson_ratio,
            local_refinement=local_refinement, geometry_order=2,
        )
        if (
            source_hash is not None
            and out["source_cad_sha256"] != source_hash
        ):
            raise ValueError("CAD source changed during curved stress study")
        source_hash = out["source_cad_sha256"]
        levels.append({
            "mesh_target_mm": size,
            "tetrahedron_count": out["tetrahedron_count"],
            "quadratic_dof_count": out["quadratic_displacement_dof_count"],
            "peak_sampled_von_mises_pa": out["p2_peak_quadrature_von_mises_pa"],
            "peak_sample_location_m": out["p2_peak_stress_quadrature_location_m"],
            "load_work_conjugate_deflection_m": out[
                "p2_load_work_conjugate_deflection_m"
            ],
            "curved_mesh_volume_m3": out["curved_integrated_volume_m3"],
            "curved_vs_cad_volume_error_fraction": out[
                "curved_vs_cad_volume_error_fraction"
            ],
            "minimum_curved_jacobian_m3": out[
                "min_sampled_jacobian_determinant_m3"
            ],
        })
    comparisons = []
    for coarse, fine in zip(levels, levels[1:]):
        stress_relative = abs(
            fine["peak_sampled_von_mises_pa"] -
            coarse["peak_sampled_von_mises_pa"]
        ) / max(
            fine["peak_sampled_von_mises_pa"],
            coarse["peak_sampled_von_mises_pa"], 1e-6
        )
        disp_relative = abs(
            fine["load_work_conjugate_deflection_m"] -
            coarse["load_work_conjugate_deflection_m"]
        ) / max(
            abs(fine["load_work_conjugate_deflection_m"]),
            abs(coarse["load_work_conjugate_deflection_m"]), 1e-15
        )
        from math import dist

        hotspot_shift_mm = dist(
            coarse["peak_sample_location_m"],
            fine["peak_sample_location_m"],
        ) * 1000
        comparisons.append({
            "peak_hotspot_shift_mm": hotspot_shift_mm,
            "peak_hotspot_location_consistent": (
                hotspot_shift_mm <= hotspot_location_tolerance_mm
            ),
            "coarse_mesh_mm": coarse["mesh_target_mm"],
            "fine_mesh_mm": fine["mesh_target_mm"],
            "quadratic_dof_growth": (
                fine["quadratic_dof_count"] / coarse["quadratic_dof_count"]
            ),
            "peak_stress_relative_change": stress_relative,
            "displacement_relative_change": disp_relative,
            "peak_stress_tolerance_met": stress_relative <= stress_tolerance,
            "displacement_tolerance_met": disp_relative <= displacement_tolerance,
        })
    blockers = []
    if any(x["quadratic_dof_growth"] < 1.10 for x in comparisons):
        blockers.append("insufficient_quadratic_refinement")
    if any(not x["peak_stress_tolerance_met"] for x in comparisons):
        blockers.append("p2_peak_stress_changes_with_curved_mesh_refinement")
    if any(not x["displacement_tolerance_met"] for x in comparisons):
        blockers.append("p2_displacement_changes_with_curved_mesh_refinement")
    if any(not x["peak_hotspot_location_consistent"] for x in comparisons):
        blockers.append("p2_peak_hotspot_moves_with_curved_mesh_refinement")
    if any(
        x["curved_vs_cad_volume_error_fraction"] > .01 for x in levels
    ):
        blockers.append("curved_geometry_volume_mismatch")
    return {
        "schema_version": "hardware_splicer.curved_stress_sensitivity.v1",
        "status": (
            "curved_stress_numerical_screen_pass" if not blockers
            else "inconclusive_curved_stress_refinement"
        ),
        "source_cad_sha256": source_hash,
        "mesh_targets_mm": sizes,
        "levels": levels,
        "adjacent_mesh_comparisons": comparisons,
        "stress_tolerance": stress_tolerance,
        "displacement_tolerance": displacement_tolerance,
        "hotspot_location_tolerance_mm": hotspot_location_tolerance_mm,
        "blockers": blockers,
        "peak_stress_convergence_verified": False,
        "mesh_convergence_verified": False,
        "structural_safety_verified": False,
        "physical_validation_required": True,
        "fabrication_authorized": False,
        "release_authorized": False,
        "claim_boundary": (
            "P2 curved isoparametric mesh refinement evidence at finite "
            "sampling points only, not validated convergence or safe strength."
        ),
    }


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
    geometry_order: Literal[1, 2] = 1,
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
            geometry_order=geometry_order,
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
        "geometry_interpolation_order": geometry_order,
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
    p.add_argument(
        "--curved-stress-study-mm", nargs="+", type=float,
        help="3–4 decreasing mesh targets for P2 curved stress sensitivity",
    )
    p.add_argument(
        "--curved-geometry", action="store_true",
        help="Use Gmsh optimized 10-node isoparametric CAD geometry (STEP only)",
    )
    p.add_argument(
        "--compare-curved", action="store_true",
        help="Compare P2 curved and P2 straight on matched vertex topology",
    )
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
    if sum(
        option is not None and option is not False for option in (
            args.mesh_study_mm, args.curved_stress_study_mm, args.compare_curved
        )
    ) > 1:
        p.error("select only one mesh study/comparison operation")
    if args.compare_curved and args.analytic_bar_benchmark is not None:
        p.error("--compare-curved is incompatible with the analytic benchmark")
    if (
        args.curved_stress_study_mm is not None
        and args.analytic_bar_benchmark is not None
    ):
        p.error("--curved-stress-study-mm is not an analytic bar benchmark")
    if args.curved_stress_study_mm is not None:
        report = run_curved_stress_sensitivity(
            args.cad_file, mesh_targets_mm=args.curved_stress_study_mm,
            fixed_plane=args.fixed_plane, loaded_plane=args.loaded_plane,
            total_force_n=args.force_n,
            youngs_modulus_pa=args.youngs_pa, poisson_ratio=args.poisson,
        )
        good = report["status"] == "curved_stress_numerical_screen_pass"
    elif args.compare_curved:
        report = compare_curved_geometry(
            args.cad_file, mesh_target_mm=args.mesh_size_mm,
            fixed_plane=args.fixed_plane, loaded_plane=args.loaded_plane,
            total_force_n=args.force_n,
            youngs_modulus_pa=args.youngs_pa, poisson_ratio=args.poisson,
        )
        good = report["status"] == "geometry_comparison_within_declared_threshold"
    elif args.mesh_study_mm is not None:
        if args.analytic_bar_benchmark is None:
            p.error("--mesh-study-mm requires --analytic-bar-benchmark")
        report = run_quadratic_mesh_benchmark(
            args.cad_file, mesh_targets_mm=args.mesh_study_mm,
            stl_units=args.stl_units,
            fixed_plane=args.fixed_plane, loaded_plane=args.loaded_plane,
            total_force_n=args.force_n, youngs_modulus_pa=args.youngs_pa,
            poisson_ratio=args.poisson,
            analytic_bar_benchmark=args.analytic_bar_benchmark,
            geometry_order=2 if args.curved_geometry else 1,
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
            geometry_order=2 if args.curved_geometry else 1,
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

"""Two-hole, node-collocated frictionless rigid-pin contact on curved STEP.

Both pin/bore interfaces are unilateral KKT inequalities; neither bore
is rigidly fixed. A tiny documented elastic gauge regularization removes
global rigid-body null modes, and the resulting *gauge reaction* is measured
and must be negligible. Out-of-plane motion is stabilized by the same
regularization, not interpreted as a mechanical fastener fixture.

This is a mathematical/numerical screening tool only.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence


def solve_two_pin_contact(
    step_file: str | Path, *,
    mesh_target_mm: float,
    centers_xy_mm: Sequence[Sequence[float]],
    hole_d_mm: float,
    thickness_mm: float,
    right_pin_drive_mm: float = .02,
    radial_clearance_mm: float = .005,
    youngs_pa: float = 2e9,
    poisson: float = .25,
    numerical_gauge_n_per_m: float = .01,
    active_selection_n_per_m: float = 1e7,
    local_mesh_target_mm: float | None = None,
    local_radius_mm: float = 4.,
) -> dict[str, Any]:
    import numpy as np
    from scipy import sparse
    from skfem import MeshTet, MeshTet2, ElementTetP2, ElementVector, Basis, asm
    from skfem.models.elasticity import lame_parameters, linear_elasticity
    from .mechanical_cad_fem import mesh_cad_solid
    from .mechanical_quadratic_fem import _validated_curved_jacobian
    from .mechanical_fastener_bearing import _validate_inputs
    from .mechanical_contact_complementarity import (
        solve_contact_quadratic_program,
    )

    centers = _validate_inputs(
        centers_xy_mm, hole_d_mm, thickness_mm,
        30., youngs_pa, poisson, 3.,
    )
    if not math.isfinite(mesh_target_mm) or not 1 <= mesh_target_mm <= 15:
        raise ValueError("invalid two-pin mesh size")
    if not math.isfinite(right_pin_drive_mm) or not 0 <= right_pin_drive_mm <= .1:
        raise ValueError("pin displacement must lie within [0,0.1] mm")
    if not math.isfinite(radial_clearance_mm) or not (
        0 <= radial_clearance_mm <= .05
    ):
        raise ValueError("invalid pin radial clearance")
    if not math.isfinite(numerical_gauge_n_per_m) or not (
        1e-4 <= numerical_gauge_n_per_m <= 1e3
    ):
        raise ValueError("invalid numerical rigid-mode stabilization")
    if local_mesh_target_mm is not None:
        from .mechanical_cad_fem import LocalRefinement
        refinement = LocalRefinement(
            target_size_mm=local_mesh_target_mm,
            radius_mm=local_radius_mm,
            refine_circular_edges=True,
        )
    else:
        refinement = None
    m = mesh_cad_solid(
        step_file, mesh_target_mm=mesh_target_mm,
        geometry_order=2, local_refinement=refinement,
    )
    bare = MeshTet2.from_mesh(MeshTet(
        np.asarray(m.nodes_m).T, np.asarray(m.elements).T,
    ))
    edge_map = {
        tuple(edge): np.asarray(x, dtype=float)
        for edge, x in zip(m.quadratic_edge_vertices, m.quadratic_edge_midpoints_m)
    }
    if len(edge_map) != bare.edges.shape[1]:
        raise ValueError("missing high-order edge geometry")
    points = bare.doflocs.copy()
    for i, (a, b) in enumerate(bare.edges.T):
        points[:, int(bare.dofs.edge_dofs[0, i])] = edge_map[
            tuple(sorted((int(a), int(b))))
        ]
    mesh = MeshTet2(points, bare.t)
    element = ElementVector(ElementTetP2())
    basis = Basis(mesh, element)
    if basis.N > 8000:
        raise ValueError("bounded quadratic DOF limit exceeded")
    min_jac, _ = _validated_curved_jacobian(mesh, basis.X)
    if m.cad_kernel_volume_m3 is None or abs(
        np.sum(basis.dx) / m.cad_kernel_volume_m3 - 1
    ) > .01:
        raise ValueError("curved STEP geometry volume discrepancy")
    if not math.isclose(
        float(mesh.p[2].max() - mesh.p[2].min()),
        thickness_mm * .001, abs_tol=5e-5,
    ):
        raise ValueError("bracket thickness differs from spec")

    exterior = mesh.boundary_facets()
    faces_xyz = mesh.p[:, mesh.facets[:, exterior]]
    radius = hole_d_mm * .0005
    all_triplets = np.concatenate(
        (basis.nodal_dofs, basis.edge_dofs), axis=1
    ).T
    contact_data = []
    chosen_global_dofs = set()
    area_per_hole = []
    for hole_id, (cx, cy) in enumerate(centers):
        distances = np.hypot(
            faces_xyz[0] - cx * .001,
            faces_xyz[1] - cy * .001,
        )
        mask = np.all(abs(distances - radius) < .00012, axis=0)
        wall = exterior[mask]
        if len(wall) < 12:
            raise ValueError("incomplete high-order hole wall")
        from skfem import FacetBasis
        fb = FacetBasis(mesh, element, facets=wall, dofs=basis.dofs)
        area = float(np.sum(fb.dx))
        ideal = math.pi * hole_d_mm * .001 * thickness_mm * .001
        if not .94 <= area / ideal <= 1.06:
            raise ValueError("hole surface area inconsistent with CAD")
        area_per_hole.append(area)
        wall_dofs = set(int(j) for j in basis.get_dofs(facets=wall).flatten())
        for dof_triplet in all_triplets:
            dx, dy, dz = (int(d) for d in dof_triplet)
            if not {dx, dy, dz} <= wall_dofs:
                continue
            x, y, z = basis.doflocs[:, dx]
            vx = x - cx * .001
            vy = y - cy * .001
            distance = math.hypot(vx, vy)
            if not abs(distance-radius) < .00012:
                continue
            if dx in chosen_global_dofs:
                raise ValueError("two holes share a contact node")
            chosen_global_dofs.add(dx)
            contact_data.append({
                "hole": hole_id,
                "point": (float(x), float(y), float(z)),
                "dofs": (dx, dy, dz),
                "nx": vx / distance,
                "ny": vy / distance,
                "threshold": (
                    right_pin_drive_mm*.001 * vx/distance
                    if hole_id == 1 else 0.
                ) - radial_clearance_mm * .001,
            })
    if not 12 <= len(contact_data) <= 400:
        raise ValueError("two-pin contact node count outside bounded range")
    if not all(sum(int(node["hole"] == h) for node in contact_data) >= 12 for h in (0,1)):
        raise ValueError("insufficient nodes for one pin")

    row_ids, column_ids, coefficients = [], [], []
    rhs = []
    for row, node in enumerate(contact_data):
        dx, dy, _ = node["dofs"]
        row_ids.extend((row, row))
        column_ids.extend((dx, dy))
        coefficients.extend((node["nx"], node["ny"]))
        rhs.append(node["threshold"])
    C = sparse.coo_matrix(
        (coefficients, (row_ids, column_ids)),
        shape=(len(contact_data), basis.N),
    ).tocsr()
    lam, mu = lame_parameters(youngs_pa, poisson)
    physical_stiffness = asm(
        linear_elasticity(Lambda=lam, Mu=mu), basis,
    ).tocsc()
    # Tiny, explicitly measured full-system numerical gauge stiffness.
    # Not physical support, and result is refused if its force is significant.
    gauge_stiffness = sparse.eye(basis.N, format="csc") * numerical_gauge_n_per_m
    kkt = solve_contact_quadratic_program(
        physical_stiffness + gauge_stiffness,
        C, np.asarray(rhs),
        activation_stiffness_n_m=active_selection_n_per_m,
    )
    u = kkt["nodal_displacement_m"]
    lamcontact = kkt["contact_lambda_n"]
    per_hole = []
    total_contact = np.zeros(3)
    for hole in (0, 1):
        reactions = np.asarray([
            [v * node["nx"], v * node["ny"], 0.]
            for v, node in zip(lamcontact, contact_data)
            if node["hole"] == hole
        ])
        force = reactions.sum(axis=0)
        total_contact += force
        per_hole.append({
            "hole_index": hole,
            "contact_node_count": sum(node["hole"] == hole for node in contact_data),
            "active_contact_node_count": int(sum(
                v > 1e-7 for v,node in zip(lamcontact,contact_data)
                if node["hole"] == hole
            )),
            "integrated_nodal_contact_resultant_n": force.tolist(),
            "peak_nodal_normal_contact_multiplier_n": float(max(
                v for v,node in zip(lamcontact,contact_data)
                if node["hole"] == hole
            )),
        })
    # Probe contact at actual quadratic face quadrature points, not only
    # collocated surface nodes. These probes are diagnostic only: finite
    # sampling cannot guarantee contact everywhere on the continuous BREP.
    from skfem import FacetBasis
    surface_contact_probes = []
    for pin_index, (cx, cy) in enumerate(centers):
        wall = exterior[
            np.all(
                abs(
                    np.hypot(
                        faces_xyz[0] - cx * .001,
                        faces_xyz[1] - cy * .001,
                    ) - radius
                ) < .00012,
                axis=0,
            )
        ]
        fb = FacetBasis(mesh, element, facets=wall, dofs=basis.dofs)
        sample_xyz = np.asarray(fb.global_coordinates())
        radial = np.hypot(
            sample_xyz[0] - cx*.001,
            sample_xyz[1] - cy*.001,
        )
        nx = (sample_xyz[0] - cx*.001)/radial
        ny = (sample_xyz[1] - cy*.001)/radial
        displacement_samples = np.asarray(fb.interpolate(u))
        physical_gap = (
            displacement_samples[0]*nx + displacement_samples[1]*ny
            - (right_pin_drive_mm*.001*nx if pin_index == 1 else 0.)
            + radial_clearance_mm*.001
        )
        min_gap = float(physical_gap.min())
        negative = np.maximum(-physical_gap, 0.)
        surface_contact_probes.append({
            "hole_index": pin_index,
            "quadrature_sample_count": int(physical_gap.size),
            "minimum_quadrature_gap_m": min_gap,
            "largest_sampled_between_node_penetration_m": float(negative.max()),
            "sampled_penetrating_area_m2": float(
                np.sum(fb.dx * (negative > 1e-12))
            ),
            "continuous_surface_nonpenetration_proven": False,
        })
    gauge_force = numerical_gauge_n_per_m * u
    gauge_resultant = np.asarray([
        gauge_force[basis.nodal_dofs[a]].sum() +
        gauge_force[basis.edge_dofs[a]].sum()
        for a in range(3)
    ],dtype=float)
    # Both pin reactions SHOULD cancel: inspect each bore's transmitted
    # force, not the vector sum (which is near zero in equilibrium).
    transmitted_force = max(
        float(np.linalg.norm(row["integrated_nodal_contact_resultant_n"]))
        for row in per_hole
    )
    gauge_error = float(np.linalg.norm(gauge_resultant))
    if right_pin_drive_mm > 2 * radial_clearance_mm and transmitted_force < 1e-3:
        raise ValueError("two pins failed to transmit load after clearance")
    if right_pin_drive_mm > 2 * radial_clearance_mm and any(
        node["active_contact_node_count"] == 0 for node in per_hole
    ):
        raise ValueError("one pin has not developed compressive contact")
    if transmitted_force > 1e-3 and gauge_error > .01 * transmitted_force:
        raise ValueError("numerical gauge reactions materially support the load")

    gradient = basis.interpolate(u).grad
    strain = .5*(gradient + np.swapaxes(gradient,0,1))
    stress = (
        lam*np.eye(3)[:,:,None,None] *
        np.trace(strain,axis1=0,axis2=1)[None,None,:,:] +
        2*mu*strain
    )
    dev = stress - np.eye(3)[:,:,None,None]*(
        np.trace(stress,axis1=0,axis2=1)[None,None,:,:] / 3
    )
    vm = np.sqrt(1.5*np.einsum("ijeq,ijeq->eq",dev,dev))
    if not np.all(np.isfinite(vm)):
        raise ValueError("nonfinite complementarity stress")
    qxyz = mesh.mapping().F(basis.X)
    per_hole_stress = []
    for index, (cx, cy) in enumerate(centers):
        rr = np.hypot(qxyz[0] - cx*.001, qxyz[1] - cy*.001)
        region = (rr >= radius*.985) & (rr <= radius + .003)
        if int(np.count_nonzero(region)) < 10:
            raise ValueError("insufficient quadrature samples at pin bore")
        local = np.where(region, vm, -np.inf)
        location = np.unravel_index(int(np.argmax(local)), vm.shape)
        per_hole_stress.append({
            "hole_index": index,
            "peak_sampled_von_mises_pa": float(vm[location]),
            "peak_location_m": [
                float(qxyz[a][location]) for a in range(3)
            ],
            "quadrature_sample_count": int(np.count_nonzero(region)),
            "weighted_rms_von_mises_pa": float(np.sqrt(
                np.sum(basis.dx*np.where(region, vm**2, 0.)) /
                max(float(np.sum(basis.dx*region)),1e-18)
            )),
            "p95_quadrature_von_mises_pa": float(
                np.percentile(vm[region], 95)
            ),
            "p90_quadrature_von_mises_pa": float(
                np.percentile(vm[region], 90)
            ),
        })
    return {
        "schema_version": "hardware_splicer.two_bore_nodal_kkt.v1",
        "status": "nodal_two_pin_complementarity_screen_only",
        "source_step_sha256": m.source_sha256,
        "mesh_target_mm": mesh_target_mm,
        "local_refinement": m.local_refinement,
        "geometry_order": 2,
        "tetrahedron_count": len(m.elements),
        "quadratic_dof_count": int(basis.N),
        "min_curved_geometry_jacobian": min_jac,
        "hole_wall_areas_m2": area_per_hole,
        "contact_node_count": len(contact_data),
        "pin_drive_mm": right_pin_drive_mm,
        "clearance_mm": radial_clearance_mm,
        "numerical_gauge_n_per_m": numerical_gauge_n_per_m,
        "numerical_gauge_resultant_n": gauge_resultant.tolist(),
        "contact_resultant_sum_n": total_contact.tolist(),
        "relative_gauge_reaction": gauge_error/max(transmitted_force,1e-12),
        "transmitted_force_scale_n": transmitted_force,
        "per_pin": per_hole,
        "between_node_surface_gap_probes": surface_contact_probes,
        "per_hole_stress": per_hole_stress,
        "global_peak_sampled_von_mises_pa": float(vm.max()),
        "nodal_max_gap_violation_m": kkt["max_negative_gap_m"],
        "min_contact_multiplier_n": kkt["min_contact_lambda_n"],
        "max_complementarity_n_m": kkt["max_complementarity_n_m"],
        "contact_iterations": kkt["contact_iterations"],
        "penalty_stiffness_used_in_physics": False,
        "both_pin_surfaces_use_unilateral_constraints": True,
        "continuous_surface_nonpenetration_proven": False,
        "numerical_gauge_negligible_checked": True,
        "joint_strength_verified": False,
        "physical_validation_required": True,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }

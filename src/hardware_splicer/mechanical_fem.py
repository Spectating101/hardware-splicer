"""Bounded, auditable small-strain 3D linear-tetrahedron elasticity solver.

Inputs are explicitly SI: node coordinates in metres, forces in newtons, material
properties in pascals. Tetrahedral volume meshes must be supplied by the caller.
This is a numerical *screening* model, never physical test or fabrication proof.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "hardware_splicer.mechanical_fem.v1"


class FemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes_m: list[list[float]] = Field(min_length=4, max_length=2000)
    elements: list[list[int]] = Field(min_length=1, max_length=5000)
    loads_n: list["FemLoad"] = Field(min_length=1, max_length=2000)
    constraints: list["FemConstraint"] = Field(min_length=1, max_length=2000)
    youngs_modulus_pa: float = Field(gt=0, allow_inf_nan=False)
    poisson_ratio: float = Field(ge=0, lt=0.5, allow_inf_nan=False)
    yield_strength_pa: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    units: str = "SI"

    @model_validator(mode="after")
    def validate_shape(self) -> "FemInput":
        if self.units != "SI":
            raise ValueError("units must be 'SI' (metres, newtons, pascals)")
        if any(len(point) != 3 or not all(math.isfinite(v) for v in point)
               for point in self.nodes_m):
            raise ValueError("every node must have three finite coordinates in metres")
        n = len(self.nodes_m)
        if any(len(element) != 4 or len(set(element)) != 4
               or any(not isinstance(idx, int) or isinstance(idx, bool) or idx < 0 or idx >= n
                      for idx in element)
               for element in self.elements):
            raise ValueError("each element must contain four distinct valid node indices")
        for row in [*self.loads_n, *self.constraints]:
            if row.node < 0 or row.node >= n:
                raise ValueError("load/constraint node index outside mesh")
        fixed = {(row.node, axis) for row in self.constraints
                 for axis, enabled in enumerate(row.axes) if enabled}
        if not fixed:
            raise ValueError("at least one displacement degree of freedom must be constrained")
        if not any(any(abs(v) > 0 for v in load.force_n) for load in self.loads_n):
            raise ValueError("at least one nonzero nodal force is required")
        return self


class FemLoad(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node: int = Field(ge=0)
    force_n: list[float] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def valid_force(self) -> "FemLoad":
        if not all(math.isfinite(v) for v in self.force_n):
            raise ValueError("force components must be finite")
        return self


class FemConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node: int = Field(ge=0)
    axes: list[bool] = Field(default_factory=lambda: [True, True, True], min_length=3, max_length=3)


def solve_linear_tetra_fem(request: FemInput | dict[str, Any]) -> dict[str, Any]:
    """Compute constrained elastic response; raise ValueError on invalid/singular meshes.

    The tetrahedron is a *linear* constant-strain element; stresses are per-element
    averages. No thermal effects, contacts, plasticity, buckling, fatigue or dynamic
    loads are modelled. Structural/fabrication authorization always remains closed.
    """
    if not isinstance(request, FemInput):
        request = FemInput.model_validate(request)
    try:
        import numpy as np
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import splu
    except ImportError as exc:
        raise RuntimeError("FEM requires optional numpy and scipy; install the physics extra") from exc

    nodes = np.asarray(request.nodes_m, dtype=float)
    mu = request.youngs_modulus_pa / (2.0 * (1.0 + request.poisson_ratio))
    lam = (
        request.youngs_modulus_pa * request.poisson_ratio /
        ((1.0 + request.poisson_ratio) * (1.0 - 2.0 * request.poisson_ratio))
    )
    dmat = np.zeros((6, 6), dtype=float)
    dmat[:3, :3] = lam
    np.fill_diagonal(dmat[:3, :3], lam + 2.0 * mu)
    dmat[3, 3] = dmat[4, 4] = dmat[5, 5] = mu

    stiffness_rows: list[int] = []
    stiffness_cols: list[int] = []
    stiffness_values: list[float] = []
    element_matrices: list[tuple[np.ndarray, np.ndarray, float]] = []
    used_nodes: set[int] = set()
    total_volume = 0.0

    for element_number, element in enumerate(request.elements):
        ids = np.asarray(element, dtype=int)
        used_nodes.update(element)
        xyz = nodes[ids]
        coords = np.column_stack((np.ones(4), xyz))
        det = float(np.linalg.det(coords))
        # Scale-aware degeneracy check; never turn a flat tetra into stiffness.
        edges = xyz[:, None, :] - xyz[None, :, :]
        largest_edge = float(np.max(np.linalg.norm(edges, axis=2)))
        if largest_edge <= 0 or abs(det) <= 1e-10 * largest_edge**3:
            raise ValueError(f"element {element_number} is degenerate or near-coplanar")
        grads = np.linalg.inv(coords)[1:, :]
        volume = abs(det) / 6.0
        bmat = np.zeros((6, 12), dtype=float)
        for i in range(4):
            x, y, z = grads[:, i]
            j = 3 * i
            bmat[0, j] = x
            bmat[1, j + 1] = y
            bmat[2, j + 2] = z
            bmat[3, j + 1] = z
            bmat[3, j + 2] = y
            bmat[4, j] = z
            bmat[4, j + 2] = x
            bmat[5, j] = y
            bmat[5, j + 1] = x
        ke = volume * (bmat.T @ dmat @ bmat)
        dofs = np.array([3 * int(node) + axis for node in ids for axis in range(3)])
        stiffness_rows.extend(np.repeat(dofs, 12).tolist())
        stiffness_cols.extend(np.tile(dofs, 12).tolist())
        stiffness_values.extend(ke.ravel().tolist())
        element_matrices.append((bmat, dofs, volume))
        total_volume += volume

    if len(used_nodes) != len(nodes):
        raise ValueError("isolated nodes are not supported; every node must belong to a tetrahedron")

    fixed_dofs = sorted({
        3 * constraint.node + axis
        for constraint in request.constraints
        for axis, active in enumerate(constraint.axes) if active
    })
    # Sparse LU may return finite but meaningless huge displacements for
    # theoretically singular systems because of roundoff. Check all six rigid
    # body modes explicitly *per disconnected tetrahedral component*.
    parents = list(range(len(nodes)))
    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for element in request.elements:
        anchor = root(element[0])
        for node in element[1:]:
            parents[root(node)] = anchor

    components: dict[int, list[int]] = {}
    for node in range(len(nodes)):
        components.setdefault(root(node), []).append(node)

    constrained = set(fixed_dofs)
    for connected_nodes in components.values():
        centre = nodes[connected_nodes].mean(axis=0)
        rigid_rows = []
        for node in connected_nodes:
            x, y, z = nodes[node] - centre
            rigid_basis = (
                (1.0, 0.0, 0.0, 0.0, z, -y),
                (0.0, 1.0, 0.0, -z, 0.0, x),
                (0.0, 0.0, 1.0, y, -x, 0.0),
            )
            for axis in range(3):
                if 3 * node + axis in constrained:
                    rigid_rows.append(rigid_basis[axis])
        if len(rigid_rows) < 6 or np.linalg.matrix_rank(
            np.asarray(rigid_rows), tol=1e-10
        ) < 6:
            raise ValueError(
                "singular supports: every connected solid needs constraints "
                "removing all six rigid-body modes"
            )

    free_dofs = np.setdiff1d(np.arange(3 * len(nodes)), fixed_dofs, assume_unique=True)
    force = np.zeros(3 * len(nodes), dtype=float)
    for load in request.loads_n:
        force[3 * load.node:3 * load.node + 3] += np.asarray(load.force_n)
    if not len(free_dofs) or not np.any(np.abs(force[free_dofs]) > 0):
        raise ValueError(
            "all loads act on fixed degrees of freedom; no deformational "
            "response can be evaluated"
        )
    matrix = coo_matrix(
        (stiffness_values, (stiffness_rows, stiffness_cols)),
        shape=(3 * len(nodes), 3 * len(nodes))
    ).tocsc()

    displacements = np.zeros(3 * len(nodes), dtype=float)
    if len(free_dofs):
        try:
            factor = splu(matrix[free_dofs, :][:, free_dofs].tocsc())
            displacements[free_dofs] = factor.solve(force[free_dofs])
        except RuntimeError as exc:
            raise ValueError("singular stiffness: insufficient supports or disconnected mechanism") from exc
        if not np.all(np.isfinite(displacements)):
            raise ValueError("nonfinite displacement: invalid material or singular mesh")

    stress_rows = []
    vm_rows = []
    for bmat, dofs, _volume in element_matrices:
        stress = dmat @ (bmat @ displacements[dofs])
        sx, sy, sz, tyz, txz, txy = stress
        vm = math.sqrt(
            max(0.0, 0.5 * ((sx-sy)**2 + (sy-sz)**2 + (sz-sx)**2) +
                3.0 * (txy*txy + txz*txz + tyz*tyz))
        )
        stress_rows.append(stress.tolist())
        vm_rows.append(float(vm))
    max_displacement = float(np.max(np.linalg.norm(displacements.reshape(-1, 3), axis=1)))
    # Reactions plus external nodal loads must satisfy global force equilibrium.
    reactions = np.asarray(matrix @ displacements - force).reshape(-1, 3)
    net_force = np.sum(reactions, axis=0) + np.sum(force.reshape(-1, 3), axis=0)
    equilibrium_residual = float(np.linalg.norm(net_force))
    applied_force_magnitude = float(np.linalg.norm(force))
    if equilibrium_residual > 1e-6 * max(1.0, applied_force_magnitude):
        raise ValueError("FEM force equilibrium check failed")
    max_von_mises = max(vm_rows)
    peak_stress_element = int(max(range(len(vm_rows)), key=vm_rows.__getitem__))
    peak_nodes = request.elements[peak_stress_element]
    peak_stress_centroid_m = nodes[peak_nodes].mean(axis=0).tolist()
    yield_sf = (
        float(request.yield_strength_pa / max_von_mises)
        if request.yield_strength_pa is not None and max_von_mises > 0
        else None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "computed_screening_only",
        "model": "isotropic_linear_elastic_constant_strain_tetra",
        "input_units": {"coordinates": "m", "forces": "N", "stress": "Pa", "displacement": "m"},
        "node_count": len(nodes),
        "element_count": len(request.elements),
        "volume_m3": total_volume,
        "max_displacement_m": max_displacement,
        "nodal_displacements_m": displacements.reshape(-1, 3).tolist(),
        "element_stress_pa": stress_rows,
        "element_von_mises_pa": vm_rows,
        "max_von_mises_pa": max_von_mises,
        "peak_stress_element_index": peak_stress_element,
        "peak_stress_centroid_m": peak_stress_centroid_m,
        "yield_safety_factor": yield_sf,
        "support_reactions_n": reactions.tolist(),
        "force_equilibrium_residual_n": equilibrium_residual,
        "limitations": [
            "Explicit conforming tetrahedral volume mesh required",
            "Small-strain static isotropic elasticity; no plasticity, buckling, contacts or fatigue",
            "Mesh convergence, load cases, material and boundary conditions require independent validation",
            "No physical testing or manufacturing approval"
        ],
        "physical_validation_required": True,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }


FemInput.model_rebuild()

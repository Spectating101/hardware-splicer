"""Nodal complementarity for curved FEM rigid-pin contact.

Discretized contact constraints C*u >= q, lambda >= 0 with lambda * gap = 0.
This enforces node-collocated contact without penalty penetration, not
continuum-exact surface Signorini conditions. Non-authorizing screen.
"""
from __future__ import annotations
import math
from typing import Any, Sequence


def solve_contact_quadratic_program(
    stiffness: Any, contact_rows: Any, thresholds_m: Any, *,
    external_load_n: Any = None, fixed_dofs: Sequence[int] = (),
    activation_stiffness_n_m: float = 1e7,
    max_iterations: int = 50,
    gap_tolerance_m: float = 5e-10,
    multiplier_tolerance_n: float = 1e-7,
) -> dict[str, Any]:
    """Active-set sparse KKT equilibrium for K*u = f + C.T*lambda."""
    import numpy as np
    from scipy import sparse
    from scipy.sparse.linalg import spsolve, MatrixRankWarning
    import warnings

    K = sparse.csc_matrix(stiffness, dtype=float)
    C = sparse.csr_matrix(contact_rows, dtype=float)
    q = np.asarray(thresholds_m, dtype=float)
    n = K.shape[0]
    m = C.shape[0]
    if K.shape != (n, n) or C.shape[1] != n:
        raise ValueError("contact dimensions do not match")
    if not 0 < m <= 400:
        raise ValueError("bounded contact node count exceeded")
    if q.shape != (m,) or not np.all(np.isfinite(q)):
        raise ValueError("invalid contact gap vector")
    if not np.all(np.isfinite(K.data)) or not np.all(np.isfinite(C.data)):
        raise ValueError("nonfinite contact matrices")
    if not math.isfinite(activation_stiffness_n_m) or not (
        1e4 <= activation_stiffness_n_m <= 1e12
    ):
        raise ValueError("invalid active-set selection parameter")
    if not isinstance(max_iterations, int) or not 2 <= max_iterations <= 50:
        raise ValueError("invalid contact iteration limit")
    if not 0 < gap_tolerance_m <= 1e-7:
        raise ValueError("invalid nodal gap tolerance")
    if not 0 < multiplier_tolerance_n <= 1e-3:
        raise ValueError("invalid multiplier tolerance")
    f = np.zeros(n) if external_load_n is None else np.asarray(
        external_load_n, dtype=float
    )
    if f.shape != (n,) or not np.all(np.isfinite(f)):
        raise ValueError("nonfinite external contact forces")
    fixed = np.unique(np.asarray(fixed_dofs, dtype=int))
    if np.any(fixed < 0) or np.any(fixed >= n):
        raise ValueError("invalid fixed degree of freedom")
    free = np.setdiff1d(np.arange(n), fixed)
    if not len(free):
        raise ValueError("contact problem contains no free degrees")
    A = K[free, :][:, free].tocsc()
    B = C[:, free].tocsr()
    if np.any(np.diff(B.indptr) == 0):
        raise ValueError("a contact constraint is fully fixed")
    rhs = f[free]
    displacement = np.zeros(n)
    multipliers = np.zeros(m)
    active = q > 0
    converged = False
    iterations = 0
    for it in range(max_iterations):
        iterations = it + 1
        chosen = np.flatnonzero(active)
        if len(chosen):
            BA = B[chosen].tocsc()
            saddle = sparse.bmat(
                [[A, -BA.T], [BA, None]], format="csc"
            )
            source = np.concatenate((rhs, q[chosen]))
        else:
            saddle = A
            source = rhs
        with warnings.catch_warnings():
            warnings.simplefilter("error", MatrixRankWarning)
            try:
                solution = spsolve(saddle, source)
            except (MatrixRankWarning, RuntimeError) as exc:
                raise ValueError("contact KKT system rank deficient") from exc
        if not np.all(np.isfinite(solution)):
            raise ValueError("nonfinite contact multiplier solution")
        trial_u = np.zeros(n)
        trial_u[free] = solution[:len(free)]
        trial_lam = np.zeros(m)
        if len(chosen):
            trial_lam[chosen] = solution[len(free):]
        gap = np.asarray(C @ trial_u).ravel() - q
        next_active = (
            trial_lam - activation_stiffness_n_m * gap
        ) > 0
        if np.array_equal(next_active, active):
            displacement, multipliers = trial_u, trial_lam
            converged = True
            break
        active = next_active
    if not converged:
        raise ValueError("contact KKT active set did not converge")
    gap = np.asarray(C @ displacement).ravel() - q
    complementarity = np.abs(multipliers * gap)
    residual = np.asarray(
        K @ displacement - f - C.T @ multipliers
    ).ravel()
    scale = max(
        1., float(np.linalg.norm(f[free])),
        float(np.linalg.norm(C.T @ multipliers)),
    )
    if float(gap.min()) < -gap_tolerance_m:
        raise ValueError("negative gap violates unilateral KKT feasibility")
    if float(multipliers.min()) < -multiplier_tolerance_n:
        raise ValueError("tensile multiplier violates unilateral KKT feasibility")
    if float(np.linalg.norm(residual[free])) > 1e-6 * scale:
        raise ValueError("KKT equilibrium residual too large")
    if float(np.max(complementarity)) > 1e-8:
        raise ValueError("KKT complementarity residual too large")
    return {
        "nodal_displacement_m": displacement,
        "contact_lambda_n": multipliers,
        "nodal_gap_m": gap,
        "contact_reaction_dofs_n": np.asarray(C.T @ multipliers).ravel(),
        "support_reaction_dofs_n": residual,
        "active_constraint_indices": np.flatnonzero(
            multipliers > multiplier_tolerance_n
        ),
        "contact_iterations": iterations,
        "max_negative_gap_m": max(0., float(-gap.min())),
        "min_contact_lambda_n": float(multipliers.min()),
        "max_complementarity_n_m": float(complementarity.max()),
        "free_equilibrium_l2_n": float(np.linalg.norm(residual[free])),
        "penalty_stiffness_used_in_physics": False,
        "activation_stiffness_only_selects_active_set": activation_stiffness_n_m,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }


def benchmark_contact_spring(
    *, spring_n_per_m: float = 1e6,
    pin_drive_mm: float = .5, clearance_mm: float = .1,
    activation_stiffness_n_m: float = 1e7,
) -> dict[str, Any]:
    """Independent exact 1D spring-contact benchmark."""
    import numpy as np
    from scipy import sparse
    if not all(math.isfinite(v) and v > 0 for v in (
        spring_n_per_m, activation_stiffness_n_m,
    )):
        raise ValueError("invalid spring/contact stiffness")
    if not all(math.isfinite(v) and v >= 0 for v in (
        pin_drive_mm, clearance_mm
    )):
        raise ValueError("invalid spring drive or clearance")
    result = solve_contact_quadratic_program(
        sparse.diags([spring_n_per_m], format="csr"),
        sparse.csr_matrix([[1.]]),
        np.asarray([(pin_drive_mm - clearance_mm) * .001]),
        activation_stiffness_n_m=activation_stiffness_n_m,
    )
    expected_u = max(0., (pin_drive_mm - clearance_mm) * .001)
    actual = float(result["nodal_displacement_m"][0])
    if abs(actual - expected_u) > 1e-12:
        raise ValueError("analytical unilateral spring result mismatch")
    return {
        "status": "analytical_unilateral_spring_pass",
        "expected_displacement_m": expected_u,
        "actual_displacement_m": actual,
        "expected_compressive_force_n": spring_n_per_m * expected_u,
        "actual_compressive_force_n": float(result["contact_lambda_n"][0]),
        "nodal_gap_m": float(result["nodal_gap_m"][0]),
        "iterations": result["contact_iterations"],
        "fabrication_authorized": False,
    }

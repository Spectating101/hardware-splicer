"""Linear-tetrahedron screening is non-conservative in bending, and says so.

Probe on main: a 60x20x3 mm PLA cantilever with a 1 N tip load, solved with the linear constant-strain
tetrahedron, reached only 0.15, 0.38 and 0.52 of the Euler-Bernoulli tip deflection on three structured
meshes (volumetric and shear locking). Stress is under-predicted the same way, so yield_safety_factor reads
better than the truth. Quadratic elements (mechanical_quadratic_fem) need the optional scikit-fem package,
which is not a core dependency, so the linear solver cannot default to them. Instead its result carries an
explicit non-conservative flag and screening blocker so it cannot read as a pass.

Tolerance this test states and meets: on these meshes the linear solver reaches 0.10 to 0.60 of beam theory,
never above it, and it improves as the mesh is refined. It is NOT a tolerance for accuracy.
"""

from __future__ import annotations

import itertools

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

import numpy as np

from hardware_splicer.mechanical_fem import solve_linear_tetra_fem

L, W, T = 0.050, 0.020, 0.003  # m
E, NU, FORCE_N = 3.5e9, 0.36, 1.0
BEAM_TIP_M = FORCE_N * L**3 / (3 * E * (W * T**3 / 12))
MESHES = [(10, 2, 1), (20, 4, 2), (25, 5, 3)]


def _cantilever(nx: int, ny: int, nz: int) -> dict:
    xs, ys, zs = np.linspace(0, L, nx + 1), np.linspace(0, W, ny + 1), np.linspace(0, T, nz + 1)
    index, nodes = {}, []
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            for k, z in enumerate(zs):
                index[(i, j, k)] = len(nodes)
                nodes.append([x, y, z])
    elements = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                for perm in itertools.permutations(range(3)):  # Kuhn split: six conforming tets per cell
                    p = [i, j, k]
                    ids = [index[tuple(p)]]
                    for axis in perm:
                        p[axis] += 1
                        ids.append(index[tuple(p)])
                    elements.append(ids)
    fixed = [{"node": index[(0, j, k)]} for j in range(ny + 1) for k in range(nz + 1)]
    tip = [index[(nx, j, k)] for j in range(ny + 1) for k in range(nz + 1)]
    return {
        "nodes_m": nodes,
        "elements": elements,
        "loads_n": [{"node": n, "force_n": [0, 0, -FORCE_N / len(tip)]} for n in tip],
        "constraints": fixed,
        "youngs_modulus_pa": E,
        "poisson_ratio": NU,
        "yield_strength_pa": 40e6,
    }


@pytest.fixture(scope="module")
def ratios_and_results() -> list[tuple[float, dict]]:
    out = []
    for mesh in MESHES:
        result = solve_linear_tetra_fem(_cantilever(*mesh))
        out.append((result["max_displacement_m"] / BEAM_TIP_M, result))
    return out


def test_linear_tetrahedra_stay_between_a_tenth_and_six_tenths_of_beam_theory(ratios_and_results) -> None:
    ratios = [r for r, _ in ratios_and_results]

    assert all(0.10 <= r <= 0.60 for r in ratios), ratios
    assert ratios == sorted(ratios), f"refining the mesh should not make it stiffer: {ratios}"


def test_linear_tetrahedra_never_over_predict_the_beam_deflection(ratios_and_results) -> None:
    assert all(r < 1.0 for r, _ in ratios_and_results)


def test_every_linear_tetrahedron_result_is_flagged_non_conservative_with_a_blocker(ratios_and_results) -> None:
    for _, result in ratios_and_results:
        assert result["conservative"] is False
        assert result["screening_verdict"] == "not_a_pass"
        [blocker] = result["screening_blockers"]
        assert "linear" in blocker.lower() and "under-predict" in blocker.lower()
        assert any("non-conservative" in w.lower() for w in result["warnings"])
        # The numbers are still reported, but the authority fields stay closed.
        assert result["structural_safety_verified"] is False
        assert result["fabrication_authorized"] is False


def test_the_flag_is_on_the_single_tetra_case_too() -> None:
    result = solve_linear_tetra_fem(
        {
            "nodes_m": [[0, 0, 0], [0.1, 0, 0], [0, 0.1, 0], [0, 0, 0.1]],
            "elements": [[0, 1, 2, 3]],
            "loads_n": [{"node": 1, "force_n": [10.0, 0.0, 0.0]}],
            "constraints": [{"node": n} for n in (0, 2, 3)],
            "youngs_modulus_pa": 2.0e9,
            "poisson_ratio": 0.25,
        }
    )

    assert result["conservative"] is False and result["screening_blockers"]

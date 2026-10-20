"""Numerical and authority regression tests for bounded structural FEM."""

from __future__ import annotations

import math

import pytest

from hardware_splicer.mechanical_fem import FemInput, solve_linear_tetra_fem


def _simple_tetra(*, youngs: float = 2.0e9, constraints=None):
    # 0.1-m right tetrahedron. Three base nodes fixed, one node loaded.
    return {
        "nodes_m": [
            [0.0, 0.0, 0.0],
            [0.1, 0.0, 0.0],
            [0.0, 0.1, 0.0],
            [0.0, 0.0, 0.1],
        ],
        "elements": [[0, 1, 2, 3]],
        "loads_n": [{"node": 1, "force_n": [10.0, 0.0, 0.0]}],
        "constraints": constraints or [
            {"node": n} for n in (0, 2, 3)
        ],
        "youngs_modulus_pa": youngs,
        "poisson_ratio": 0.25,
        "yield_strength_pa": 100e6,
    }


def test_single_tetra_agrees_with_closed_form_under_fixed_base():
    req = _simple_tetra()
    out = solve_linear_tetra_fem(req)
    youngs, nu = 2e9, 0.25
    lam = youngs * nu / ((1 + nu) * (1 - 2 * nu))
    mu = youngs / (2 * (1 + nu))
    expected_x = 6 * 10 / (0.1 * (lam + 2 * mu))
    assert out["nodal_displacements_m"][1][0] == pytest.approx(expected_x, rel=1e-9)
    assert out["nodal_displacements_m"][1][1:] == pytest.approx([0, 0], abs=1e-15)
    assert out["volume_m3"] == pytest.approx(0.1**3 / 6, rel=1e-12)
    expected_vm = 2 * mu * (expected_x / 0.1)
    assert out["max_von_mises_pa"] == pytest.approx(expected_vm, rel=1e-9)
    assert out["yield_safety_factor"] == pytest.approx(100e6 / expected_vm)
    assert out["force_equilibrium_residual_n"] < 1e-7
    assert sum(row[0] for row in out["support_reactions_n"]) == pytest.approx(-10.0)
    assert out["structural_safety_verified"] is False
    assert out["fabrication_authorized"] is False
    assert out["release_authorized"] is False


def test_reversing_element_winding_does_not_change_answer():
    forward = solve_linear_tetra_fem(_simple_tetra())
    reversed_mesh = _simple_tetra()
    reversed_mesh["elements"] = [[0, 2, 1, 3]]
    backward = solve_linear_tetra_fem(reversed_mesh)
    assert backward["max_displacement_m"] == pytest.approx(forward["max_displacement_m"])
    assert backward["max_von_mises_pa"] == pytest.approx(forward["max_von_mises_pa"])


def test_double_modulus_halves_displacement_under_force_loading():
    soft = solve_linear_tetra_fem(_simple_tetra(youngs=2e9))
    stiff = solve_linear_tetra_fem(_simple_tetra(youngs=4e9))
    assert soft["max_displacement_m"] == pytest.approx(2 * stiff["max_displacement_m"])
    assert soft["max_von_mises_pa"] == pytest.approx(stiff["max_von_mises_pa"])


@pytest.mark.parametrize("mutation,pattern", [
    ({"elements": [[0, 1, 1, 3]]}, "distinct"),
    ({"elements": [[0, 1, 2, 9]]}, "node indices"),
    ({"units": "mm"}, "SI"),
    ({"youngs_modulus_pa": -1.0}, "greater than 0"),
    ({"poisson_ratio": 0.5}, "less than 0.5"),
    ({"loads_n": [{"node": 1, "force_n": [0.0, 0.0, 0.0]}]}, "nonzero"),
])
def test_invalid_inputs_fail_closed(mutation, pattern):
    data = _simple_tetra()
    data.update(mutation)
    with pytest.raises(ValueError, match=pattern):
        solve_linear_tetra_fem(data)


def test_degenerate_volume_rejected():
    data = _simple_tetra()
    data["nodes_m"][3] = [0.03, 0.04, 0.0]
    with pytest.raises(ValueError, match="degenerate"):
        solve_linear_tetra_fem(data)


def test_underconstrained_tetra_rejected_as_singular():
    data = _simple_tetra()
    data["constraints"] = [{"node": 0}]
    with pytest.raises(ValueError, match="singular"):
        solve_linear_tetra_fem(data)


def test_isolated_unused_node_rejected():
    data = _simple_tetra()
    data["nodes_m"].append([0.2, 0.2, 0.2])
    with pytest.raises(ValueError, match="isolated"):
        solve_linear_tetra_fem(data)


def test_bounded_api_returns_non_authorizing_report():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from hardware_splicer.mechanical_api import create_mechanical_router

    app = FastAPI()
    app.include_router(create_mechanical_router())
    client = TestClient(app)
    schema = client.get("/v1/engineering/mechanical/schema")
    assert schema.status_code == 200
    assert schema.json()["bounded_linear_tetra_fem"] is True
    response = client.post("/v1/engineering/mechanical/physics/linear-elasticity", json=_simple_tetra())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["structural_screening"]["status"] == "computed_screening_only"
    assert data["fabrication_authorized"] is False
    assert data["motion_authorized"] is False


def test_bounded_api_rejects_singular_system():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from hardware_splicer.mechanical_api import create_mechanical_router

    app = FastAPI()
    app.include_router(create_mechanical_router())
    bad = _simple_tetra()
    bad["constraints"] = [{"node": 0}]
    response = TestClient(app).post("/v1/engineering/mechanical/physics/linear-elasticity", json=bad)
    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_fem_model"


def test_fully_clamped_load_cannot_claim_zero_stress_as_safe():
    case = _simple_tetra()
    case["loads_n"] = [{"node": 0, "force_n": [10.0, 0.0, 0.0]}]
    with pytest.raises(ValueError, match="all loads act on fixed"):
        solve_linear_tetra_fem(case)


def test_disconnected_tetra_without_its_own_support_is_rejected():
    case = _simple_tetra()
    offset = len(case["nodes_m"])
    case["nodes_m"].extend([
        [0.3, 0.0, 0.0], [0.4, 0.0, 0.0],
        [0.3, 0.1, 0.0], [0.3, 0.0, 0.1],
    ])
    case["elements"].append([offset, offset+1, offset+2, offset+3])
    with pytest.raises(ValueError, match="singular supports"):
        solve_linear_tetra_fem(case)

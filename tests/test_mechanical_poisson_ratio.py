"""The FEM modules must be correct for any Poisson's ratio, not only 0.25.

scikit-fem's lame_parameters returns (lambda, mu). At nu = 0.25 the two are equal, so a
swapped unpacking is invisible there, and every other mechanical test fixes nu at 0.25.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

gmsh = pytest.importorskip("gmsh")
pytest.importorskip("skfem")

from hardware_splicer.mechanical_cad_fem import mesh_cad_solid  # noqa: E402,F401
from hardware_splicer.mechanical_fem_crosscheck import validate_cad_with_independent_solver  # noqa: E402
from hardware_splicer.mechanical_quadratic_fem import run_quadratic_cad_screening  # noqa: E402

E = 2e9


@pytest.fixture(scope="module")
def beam_step(tmp_path_factory):
    path = tmp_path_factory.mktemp("poisson") / "beam.step"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("beam")
        gmsh.model.occ.addBox(0, 0, 0, 100, 10, 10)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    return path


@pytest.fixture(scope="module")
def bracket_step(tmp_path_factory):
    from hardware_splicer.mechanical_bracket_screening import generate_bracket_reference_step

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "mecha-splicer" / "src"))
    from mecha_splicer.templates.mint_templates import spec_for_template

    path = tmp_path_factory.mktemp("poisson-bracket") / "two_hole.step"
    generate_bracket_reference_step(spec_for_template("simple_plate_bracket")["bracket"], path)
    return path


@pytest.fixture
def lame_constants_used(monkeypatch):
    """Record the (Lambda, Mu) each solver really hands to scikit-fem, then run the real thing."""
    import skfem.models.elasticity as elasticity

    seen: list[tuple[float, float]] = []
    real = elasticity.linear_elasticity

    def spy(*, Lambda, Mu):
        seen.append((float(Lambda), float(Mu)))
        return real(Lambda=Lambda, Mu=Mu)

    monkeypatch.setattr(elasticity, "linear_elasticity", spy)
    return seen


def _textbook_lame(nu: float) -> tuple[float, float]:
    return E * nu / ((1 + nu) * (1 - 2 * nu)), E / (2 * (1 + nu))


@pytest.mark.parametrize("nu", [0.1, 0.3, 0.45])
def test_quadratic_cantilever_matches_beam_theory_for_any_poisson_ratio(beam_step, nu) -> None:
    result = run_quadratic_cad_screening(
        beam_step, mesh_target_mm=8, stl_units=None, fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=[0, 0, -1], youngs_modulus_pa=E, poisson_ratio=nu, yield_strength_pa=1e8,
        analytic_bar_benchmark="cantilever", benchmark_relative_tolerance=0.05,
    )

    assert result["analytic_reference"]["relative_error"] < 0.05


def test_independent_solver_agrees_with_the_hs_solver_at_a_realistic_poisson_ratio(beam_step) -> None:
    report = validate_cad_with_independent_solver(
        beam_step, mesh_target_mm=8, stl_units=None, fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=[100, 0, 0], youngs_modulus_pa=E, poisson_ratio=0.3, yield_strength_pa=1e8,
        analytic_bar_benchmark="axial", benchmark_relative_tolerance=0.10,
    )

    assert report["status"] == "independent_numerical_agreement"
    assert report["comparison_metrics"]["max_displacement_relative_error"] < 1e-6


def _assert_textbook(seen, nu) -> None:
    lam, mu = _textbook_lame(nu)
    assert seen, "the solver never reached scikit-fem's elasticity form"
    for got_lambda, got_mu in seen:
        assert got_lambda == pytest.approx(lam, rel=1e-12)
        assert got_mu == pytest.approx(mu, rel=1e-12)


def test_fastener_bearing_hands_the_right_lame_constants_to_the_solver(bracket_step, lame_constants_used) -> None:
    from hardware_splicer.mechanical_fastener_bearing import solve_bore_bearing_case

    solve_bore_bearing_case(
        bracket_step, mesh_target_mm=8.0, centers_xy_mm=((10.0, 10.0), (50.0, 10.0)),
        hole_d_mm=3.2, thickness_mm=4.0, force_n=30.0, youngs_pa=E, poisson=0.3,
    )

    _assert_textbook(lame_constants_used, 0.3)


def test_unilateral_pin_contact_hands_the_right_lame_constants_to_the_solver(bracket_step, lame_constants_used) -> None:
    from hardware_splicer.mechanical_unilateral_pin_contact import solve_pin_to_bore_contact

    solve_pin_to_bore_contact(
        bracket_step, mesh_target_mm=8, centers_xy_mm=((10.0, 10.0), (50.0, 10.0)), hole_d_mm=3.2,
        thickness_mm=4.0, drive_mm=0.02, clearance_mm=0.005, penalty_pa_per_m=5e11,
        youngs_pa=E, poisson=0.3,
    )

    _assert_textbook(lame_constants_used, 0.3)


def test_two_pin_contact_hands_the_right_lame_constants_to_the_solver(bracket_step, lame_constants_used) -> None:
    from hardware_splicer.mechanical_two_pin_contact import solve_two_pin_contact

    solve_two_pin_contact(
        bracket_step, mesh_target_mm=8, centers_xy_mm=((10.0, 10.0), (50.0, 10.0)), hole_d_mm=3.2,
        thickness_mm=4.0, youngs_pa=E, poisson=0.3,
    )

    _assert_textbook(lame_constants_used, 0.3)

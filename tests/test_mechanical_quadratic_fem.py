"""Higher-order tetrahedral FEM benchmarks and non-authorizing regression gates."""

from __future__ import annotations

import json
import math

import pytest

from hardware_splicer.mechanical_quadratic_fem import (
    run_quadratic_cad_screening,
    run_quadratic_mesh_benchmark,
)


@pytest.fixture(scope="module")
def beam_fixtures(tmp_path_factory):
    gmsh = pytest.importorskip("gmsh")
    pytest.importorskip("skfem")
    root = tmp_path_factory.mktemp("quadratic_fem")
    plain = root / "plain.step"
    drilled = root / "drilled.step"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("plain")
        gmsh.model.occ.addBox(0, 0, 0, 100, 10, 10)
        gmsh.model.occ.synchronize()
        gmsh.write(str(plain))
        gmsh.clear()
        gmsh.model.add("drilled")
        stock = gmsh.model.occ.addBox(0, 0, 0, 100, 20, 10)
        cutter = gmsh.model.occ.addCylinder(50, 10, 0, 0, 0, 10, 3)
        gmsh.model.occ.cut(
            [(3, stock)], [(3, cutter)],
            removeObject=True, removeTool=True,
        )
        gmsh.model.occ.synchronize()
        gmsh.write(str(drilled))
    finally:
        gmsh.finalize()
    return plain, drilled


def _run(path, *, mesh_size=8, force=None, benchmark=None, threshold=.05):
    return run_quadratic_cad_screening(
        path, mesh_target_mm=mesh_size, stl_units=None,
        fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=force or [0, 0, -1],
        youngs_modulus_pa=2e9, poisson_ratio=.25,
        yield_strength_pa=1e8,
        analytic_bar_benchmark=benchmark,
        benchmark_relative_tolerance=threshold,
    )


def test_p2_bending_fixes_p1_locking_without_fabrication_authority(beam_fixtures):
    result = _run(beam_fixtures[0], benchmark="cantilever")
    beam_ref = result["analytic_reference"]
    assert beam_ref["reference_displacement_m"] == pytest.approx(.0002015)
    assert result["status"] == "quadratic_numerical_screening_only"
    assert result["p1_load_work_conjugate_deflection_m"] == pytest.approx(
        8.40084395656e-5, rel=.03
    )
    assert result["p2_load_work_conjugate_deflection_m"] == pytest.approx(
        0.0002015, rel=.02
    )
    assert beam_ref["relative_error"] < .02
    assert beam_ref["within_declared_tolerance"] is True
    assert result["p2_load_work_conjugate_deflection_m"] > (
        result["p1_load_work_conjugate_deflection_m"] * 2
    )
    assert result["geometry_interpolation_order"] == 1
    assert result["displacement_interpolation_order"] == 2
    assert result["quadratic_displacement_dof_count"] > (
        result["geometry_vertex_count"] * 3
    )
    assert result["stress_quadrature_points_per_element"] > 1
    assert len(result["p2_quadrature_peak_stress_per_element_pa"]) == (
        result["tetrahedron_count"]
    )
    assert result["structural_safety_verified"] is False
    assert result["mesh_convergence_verified"] is False
    assert result["fabrication_authorized"] is False
    assert result["release_authorized"] is False


def test_p2_axial_force_conservation_and_energy(beam_fixtures):
    result = _run(
        beam_fixtures[0], force=[100, 0, 0], benchmark="axial"
    )
    assert result["status"] == "quadratic_numerical_screening_only"
    assert result["analytic_reference"]["relative_error"] < .02
    assert result["p2_load_work_conjugate_deflection_m"] == pytest.approx(
        5e-5, rel=.02
    )
    assert result["total_applied_face_force_n"] == pytest.approx([100, 0, 0])
    assert result["support_reaction_n"] == pytest.approx(
        [-100, 0, 0], abs=1e-6
    )
    assert result["global_force_equilibrium_error_n"] < 1e-7
    assert result["free_dof_force_residual_n"] < 1e-7
    assert result["strain_energy_j"] == pytest.approx(
        result["half_external_work_j"], rel=1e-8
    )


def test_p2_bending_study_stable_and_matches_analytical_reference(beam_fixtures):
    result = run_quadratic_mesh_benchmark(
        beam_fixtures[0],
        mesh_targets_mm=[12, 8, 6, 4],
        stl_units=None, fixed_plane="x_min",
        loaded_plane="x_max", total_force_n=[0, 0, -1],
        youngs_modulus_pa=2e9, poisson_ratio=.25,
        analytic_bar_benchmark="cantilever",
    )
    assert result["status"] == "analytical_and_mesh_displacement_screen_pass"
    assert result["p2_numerically_stable_against_declared_reference"] is True
    assert result["blockers"] == []
    levels = result["levels"]
    assert len(levels) == 4
    assert levels[0]["quadratic_dof_count"] < levels[-1]["quadratic_dof_count"]
    assert levels[0]["tetrahedron_count"] < levels[-1]["tetrahedron_count"]
    assert all(x["p2_analytic_relative_error"] < .02 for x in levels)
    assert all(
        abs(x["p1_displacement_m"] - x["analytic_reference_m"]) /
        x["analytic_reference_m"] > .2 for x in levels
    )
    assert all(x["relative_change_tolerance_met"] for x in result["adjacent_comparisons"])
    assert all(x["effective_refinement"] for x in result["adjacent_comparisons"])
    assert result["p2_peak_stress_convergence_verified"] is False
    assert result["mesh_convergence_verified"] is False
    assert result["structural_safety_verified"] is False


def test_analytic_failure_in_threshold_fails_closed(beam_fixtures):
    result = _run(
        beam_fixtures[0], benchmark="cantilever", threshold=.0001
    )
    assert result["status"] == "analytic_benchmark_disagreement"
    assert result["analytic_reference"]["within_declared_tolerance"] is False
    assert result["yield_margin_usable_for_engineering_release"] is False


def test_detailed_stress_report_on_drilled_solid_is_only_screening(beam_fixtures):
    result = _run(
        beam_fixtures[1], force=[100, 0, 0], benchmark=None
    )
    assert result["tetrahedron_count"] > 100
    assert result["p2_peak_quadrature_von_mises_pa"] > 0
    assert result["stress_sampling"].startswith("P2 Gauss")
    assert result["mesh_convergence_verified"] is False
    assert result["fabrication_authorized"] is False
    assert result["independent_physical_model_verified"] is False


def test_drilled_geometry_cannot_claim_analytic_prism(beam_fixtures):
    with pytest.raises(ValueError, match="unperforated STEP bar"):
        _run(
            beam_fixtures[1],
            force=[100, 0, 0],
            benchmark="axial",
        )


def test_mesh_benchmark_fails_its_analytic_gate_if_tolerance_too_strict(beam_fixtures):
    result = run_quadratic_mesh_benchmark(
        beam_fixtures[0],
        mesh_targets_mm=[12, 8, 6],
        stl_units=None, fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=[0, 0, -1],
        youngs_modulus_pa=2e9, poisson_ratio=.25,
        analytic_bar_benchmark="cantilever",
        benchmark_relative_tolerance=.0001,
    )
    assert result["status"] == "inconclusive_quadratic_benchmark"
    assert "p2_analytic_reference_disagreement" in result["blockers"]
    assert result["fabrication_authorized"] is False


@pytest.mark.parametrize("sizes", [
    [8, 6], [8, 6, 6], [8, 9, 4], [8, 6, math.nan], [8, 6, 4, 2, 1]
])
def test_invalid_mesh_series_rejected_before_loading_files(sizes):
    with pytest.raises(ValueError, match="3 or 4 strictly decreasing"):
        run_quadratic_mesh_benchmark(
            "/tmp/does-not-exist.step", mesh_targets_mm=sizes,
            stl_units=None, fixed_plane="x_min", loaded_plane="x_max",
            total_force_n=[100, 0, 0],
            youngs_modulus_pa=2e9, poisson_ratio=.25,
            analytic_bar_benchmark="axial",
        )


def test_missing_optional_solver_is_fatal_not_silent(beam_fixtures, monkeypatch):
    from hardware_splicer import mechanical_quadratic_fem as quad

    def unavailable():
        raise RuntimeError("scikit-fem unavailable")
    monkeypatch.setattr(quad, "_load_backend", unavailable)
    with pytest.raises(RuntimeError, match="unavailable"):
        _run(beam_fixtures[0], benchmark="cantilever")


def test_dof_budget_is_enforced_before_solve(beam_fixtures, monkeypatch):
    from hardware_splicer import mechanical_quadratic_fem as quad

    monkeypatch.setattr(quad, "MAX_QUADRATIC_DOF", 100)
    with pytest.raises(ValueError, match="bounded cap"):
        _run(beam_fixtures[0], benchmark="cantilever")


def test_cli_writes_auditable_benchmark_report(beam_fixtures, tmp_path):
    from hardware_splicer.mechanical_quadratic_fem import main
    out = tmp_path / "p2_bending_study.json"
    rc = main([
        str(beam_fixtures[0]),
        "--mesh-study-mm", "12", "8", "6", "4",
        "--fixed-plane", "x_min", "--loaded-plane", "x_max",
        "--force-n", "0", "0", "-1",
        "--youngs-pa", "2000000000", "--poisson", ".25",
        "--analytic-bar-benchmark", "cantilever",
        "--out", str(out),
    ])
    assert rc == 0
    report = json.loads(out.read_text())
    assert report["status"] == "analytical_and_mesh_displacement_screen_pass"
    assert len(report["levels"]) == 4
    assert report["mesh_convergence_verified"] is False


def test_cli_does_not_report_study_as_signed_off(beam_fixtures, tmp_path):
    from hardware_splicer.mechanical_quadratic_fem import main
    out = tmp_path / "p2_single.json"
    assert main([
        str(beam_fixtures[0]), "--mesh-size-mm", "8",
        "--fixed-plane", "x_min", "--loaded-plane", "x_max",
        "--force-n", "0", "0", "-1",
        "--youngs-pa", "2000000000", "--poisson", ".25",
        "--analytic-bar-benchmark", "cantilever",
        "--out", str(out),
    ]) == 0
    report = json.loads(out.read_text())
    assert report["status"] == "quadratic_numerical_screening_only"
    assert report["fabrication_authorized"] is False

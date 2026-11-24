"""Curved high-order geometry: correspondence, quality gates, and honest status."""

from __future__ import annotations

import json
import math

import pytest

# Structural/FEM extras are opt-in. Generic HS CI deliberately installs
# only the core dependencies; the dedicated CAD/FEM job exercises this suite.
np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from hardware_splicer.mechanical_cad_fem import mesh_cad_solid
from hardware_splicer.mechanical_quadratic_fem import (
    _validated_curved_jacobian,
    compare_curved_geometry,
    run_curved_stress_sensitivity,
    run_quadratic_cad_screening,
)


@pytest.fixture(scope="module")
def curved_fixtures(tmp_path_factory):
    gmsh = pytest.importorskip("gmsh")
    pytest.importorskip("skfem")
    root = tmp_path_factory.mktemp("curved_fem_fixtures")
    bar = root / "simple_bar.step"
    drilled = root / "cylindrical_hole.step"
    stl = root / "simple_bar.stl"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("simple")
        gmsh.model.occ.addBox(0, 0, 0, 100, 10, 10)
        gmsh.model.occ.synchronize()
        gmsh.write(str(bar))
        gmsh.model.mesh.generate(2)
        gmsh.write(str(stl))
        gmsh.clear()
        gmsh.model.add("with-through-hole")
        stock = gmsh.model.occ.addBox(0, 0, 0, 100, 20, 10)
        cutter = gmsh.model.occ.addCylinder(50, 10, 0, 0, 0, 10, 3)
        gmsh.model.occ.cut([(3, stock)], [(3, cutter)],
                           removeObject=True, removeTool=True)
        gmsh.model.occ.synchronize()
        gmsh.write(str(drilled))
    finally:
        gmsh.finalize()
    return bar, drilled, stl


def _screen(path, *, size=8, order=2, force=None):
    return run_quadratic_cad_screening(
        path, mesh_target_mm=size, geometry_order=order, stl_units=None,
        fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=force or [100, 0, 0],
        youngs_modulus_pa=2e9, poisson_ratio=.25,
        yield_strength_pa=1e8,
    )


def test_gmsh_second_order_edge_mapping_from_actual_step(curved_fixtures):
    _, drilled, _ = curved_fixtures
    curved = mesh_cad_solid(drilled, mesh_target_mm=8, geometry_order=2)
    assert curved.geometry_interpolation_order == 2
    assert len(curved.quadratic_edge_vertices) > len(curved.nodes_m)
    assert len(curved.quadratic_edge_vertices) == len(
        curved.quadratic_edge_midpoints_m
    )
    assert all(len(edge) == 2 for edge in curved.quadratic_edge_vertices)
    assert all(len(point) == 3 for point in curved.quadratic_edge_midpoints_m)
    assert len(set(tuple(x) for x in curved.quadratic_edge_vertices)) == len(
        curved.quadratic_edge_vertices
    )
    assert curved.cad_kernel_volume_m3 is not None


def test_curved_cad_integrated_volume_improves_drilled_geometry(curved_fixtures):
    _, drilled, _ = curved_fixtures
    straight = _screen(drilled, size=6, order=1)
    curved = _screen(drilled, size=6, order=2)
    assert straight["geometry_interpolation_order"] == 1
    assert curved["geometry_interpolation_order"] == 2
    assert curved["curved_integrated_volume_m3"] > 0
    assert curved["curved_vs_cad_volume_error_fraction"] < .0002
    assert curved["curved_vs_cad_volume_error_fraction"] < (
        straight["mesh_to_cad_volume_relative_error"] / 20
    )
    assert curved["min_sampled_jacobian_determinant_m3"] > 0
    assert curved["min_to_max_sampled_jacobian_ratio"] > 0
    assert curved["non_chord_midside_node_count"] > 0
    assert curved["max_curved_edge_chord_deviation_m"] > 0
    assert len(curved["p2_peak_stress_quadrature_location_m"]) == 3
    assert curved["stress_sampling"].startswith(
        "P2 Gauss quadrature points on curved"
    )
    assert curved["fabrication_authorized"] is False
    assert curved["mesh_convergence_verified"] is False
    assert curved["structural_safety_verified"] is False


def test_match_mesh_geom_comparison_flags_drilled_peak_stress(curved_fixtures):
    _, drilled, _ = curved_fixtures
    report = compare_curved_geometry(
        drilled, mesh_target_mm=8, fixed_plane="x_min",
        loaded_plane="x_max", total_force_n=[100, 0, 0],
        youngs_modulus_pa=2e9, poisson_ratio=.25,
    )
    assert report["identical_vertex_mesh_topology_confirmed"] is True
    assert report["tetrahedron_count"] > 100
    assert report["peak_stress_relative_geometry_difference"] > .03
    assert "peak_stress_sensitive_to_curved_geometry" in report[
        "geometry_sensitivity_blockers"
    ]
    assert report["status"] == "geometry_sensitive_screening"
    assert report["curved_vs_cad_volume_error_fraction"] < (
        report["straight_vs_cad_volume_error_fraction"]
    )
    assert report["fabrication_authorized"] is False
    assert report["stress_convergence_verified"] is False


def test_geometry_sensitivity_study_detects_nonconverged_stress(curved_fixtures):
    _, drilled, _ = curved_fixtures
    report = run_curved_stress_sensitivity(
        drilled, mesh_targets_mm=[8, 7, 6], fixed_plane="x_min",
        loaded_plane="x_max", total_force_n=[100, 0, 0],
        youngs_modulus_pa=2e9, poisson_ratio=.25,
    )
    assert report["status"] == "inconclusive_curved_stress_refinement"
    assert "p2_peak_stress_changes_with_curved_mesh_refinement" in report[
        "blockers"
    ]
    assert len(report["levels"]) == 3
    assert all(x["minimum_curved_jacobian_m3"] > 0 for x in report["levels"])
    assert all(x["curved_vs_cad_volume_error_fraction"] < .01 for x in report["levels"])
    assert report["peak_stress_convergence_verified"] is False
    assert report["release_authorized"] is False


def test_unperforated_rectangular_beam_remains_accurate_with_curved_mapping(curved_fixtures):
    bar, _, _ = curved_fixtures
    report = run_quadratic_cad_screening(
        bar, mesh_target_mm=8, geometry_order=2, stl_units=None,
        fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=[0, 0, -1],
        youngs_modulus_pa=2e9, poisson_ratio=.25,
        analytic_bar_benchmark="cantilever",
    )
    assert report["status"] == "quadratic_numerical_screening_only"
    assert report["analytic_reference"]["relative_error"] < .02
    assert report["fabrication_authorized"] is False


def test_inverted_high_order_jacobian_is_blocked():
    class BadMapping:
        def detDF(self, points):
            return np.asarray([[-1., 3.]])

    class BadMesh:
        def mapping(self):
            return BadMapping()

    with pytest.raises(ValueError, match="inverted or near-singular"):
        _validated_curved_jacobian(
            BadMesh(), np.asarray([[.25], [.25], [.25]])
        )


def test_nonfinite_high_order_jacobian_is_blocked():
    class BrokenMapping:
        def detDF(self, points):
            return np.asarray([[math.nan]])

    class BadMesh:
        def mapping(self):
            return BrokenMapping()

    with pytest.raises(ValueError, match="nonfinite"):
        _validated_curved_jacobian(
            BadMesh(), np.asarray([[.25], [.25], [.25]])
        )


def test_curved_geometry_cannot_be_made_from_faceted_stl(curved_fixtures):
    _, _, stl = curved_fixtures
    with pytest.raises(ValueError, match="requires STEP"):
        mesh_cad_solid(stl, mesh_target_mm=8, stl_units="mm", geometry_order=2)


def test_invalid_geometry_order_fails_before_marching(curved_fixtures):
    bar, _, _ = curved_fixtures
    with pytest.raises(ValueError, match="geometry_order must be 1 or 2"):
        mesh_cad_solid(bar, geometry_order=3)


def test_dof_limit_protects_large_curved_mesh(curved_fixtures):
    _, drilled, _ = curved_fixtures
    with pytest.raises(ValueError, match="bounded cap"):
        _screen(drilled, size=4, order=2)


@pytest.mark.parametrize("sizes", [
    [8, 6], [8, 8, 6], [8, 9, 6], [8, 7, math.nan]
])
def test_invalid_curved_sensitivity_series_fails_before_mesh(sizes):
    with pytest.raises(ValueError, match="3–4 decreasing"):
        run_curved_stress_sensitivity(
            "/tmp/nonexistent.step",
            mesh_targets_mm=sizes, fixed_plane="x_min",
            loaded_plane="x_max", total_force_n=[100, 0, 0],
            youngs_modulus_pa=2e9, poisson_ratio=.25,
        )


def test_curved_cli_failure_preserves_json_evidence(curved_fixtures, tmp_path):
    from hardware_splicer.mechanical_quadratic_fem import main
    _, drilled, _ = curved_fixtures
    report = tmp_path / "curved-failed-study.json"
    code = main([
        str(drilled), "--curved-stress-study-mm", "8", "7", "6",
        "--fixed-plane", "x_min", "--loaded-plane", "x_max",
        "--force-n", "100", "0", "0",
        "--youngs-pa", "2000000000", "--poisson", ".25",
        "--out", str(report),
    ])
    assert code == 2
    result = json.loads(report.read_text())
    assert "p2_peak_stress_changes_with_curved_mesh_refinement" in result["blockers"]
    assert result["mesh_convergence_verified"] is False


def test_curved_cli_single_result_has_explicit_geometry_order(curved_fixtures, tmp_path):
    from hardware_splicer.mechanical_quadratic_fem import main
    _, drilled, _ = curved_fixtures
    report = tmp_path / "curved-single.json"
    code = main([
        str(drilled), "--mesh-size-mm", "6",
        "--curved-geometry",
        "--fixed-plane", "x_min", "--loaded-plane", "x_max",
        "--force-n", "100", "0", "0",
        "--youngs-pa", "2000000000", "--poisson", ".25",
        "--out", str(report),
    ])
    assert code == 0
    result = json.loads(report.read_text())
    assert result["geometry_interpolation_order"] == 2
    assert result["high_order_gmsh_optimization"] == "HighOrder"
    assert result["physical_validation_required"] is True


def test_curved_comparison_cli_writes_failure_report(curved_fixtures, tmp_path):
    from hardware_splicer.mechanical_quadratic_fem import main
    _, drilled, _ = curved_fixtures
    report = tmp_path / "curved-compare.json"
    code = main([
        str(drilled), "--compare-curved", "--mesh-size-mm", "8",
        "--fixed-plane", "x_min", "--loaded-plane", "x_max",
        "--force-n", "100", "0", "0",
        "--youngs-pa", "2000000000", "--poisson", ".25",
        "--out", str(report),
    ])
    assert code == 2
    data = json.loads(report.read_text())
    assert data["identical_vertex_mesh_topology_confirmed"] is True
    assert data["status"] == "geometry_sensitive_screening"
    assert data["stress_convergence_verified"] is False
    assert data["fabrication_authorized"] is False

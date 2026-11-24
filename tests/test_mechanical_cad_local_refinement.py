"""Geometry-directed Gmsh refinement must be explicit, audited and fail closed."""

from __future__ import annotations

import json

import pytest

from hardware_splicer.mechanical_cad_fem import (
    LocalRefinement, mesh_cad_solid, run_cad_screening,
)
from hardware_splicer.mechanical_cad_convergence import run_cad_mesh_sensitivity


@pytest.fixture(scope="module")
def local_fixture(tmp_path_factory):
    gmsh = pytest.importorskip("gmsh")
    root = tmp_path_factory.mktemp("cad_local_refinement")
    solid = root / "bar.step"
    drilled = root / "perforated.step"
    mesh = root / "bar.stl"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("bar")
        gmsh.model.occ.addBox(0, 0, 0, 100, 10, 10)
        gmsh.model.occ.synchronize()
        gmsh.write(str(solid))
        gmsh.model.mesh.generate(2)
        gmsh.write(str(mesh))
        gmsh.clear()
        gmsh.model.add("drilled")
        stock = gmsh.model.occ.addBox(0, 0, 0, 100, 20, 10)
        cutter = gmsh.model.occ.addCylinder(50, 10, 0, 0, 0, 10, 3)
        gmsh.model.occ.cut(
            [(3, stock)], [(3, cutter)], removeObject=True, removeTool=True
        )
        gmsh.model.occ.synchronize()
        gmsh.write(str(drilled))
    finally:
        gmsh.finalize()
    return solid, drilled, mesh


def _screen(path, *, refinement, stl_units=None):
    return run_cad_screening(
        path, mesh_target_mm=8, stl_units=stl_units,
        local_refinement=refinement,
        fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=[100, 0, 0], youngs_modulus_pa=2e9,
        poisson_ratio=0.25, yield_strength_pa=100e6,
    )


def test_step_circular_edges_are_detected_and_hotspot_mesh_is_real(local_fixture):
    _, drilled, _ = local_fixture
    global_mesh = mesh_cad_solid(drilled, mesh_target_mm=8)
    adaptive = mesh_cad_solid(
        drilled, mesh_target_mm=8,
        local_refinement=LocalRefinement(
            target_size_mm=1.5, radius_mm=8, refine_circular_edges=True
        ),
    )
    assert adaptive.local_refinement["circular_edge_count"] == 2
    assert adaptive.local_refinement["influence_region_node_count"] > 80
    assert adaptive.local_refinement["physical_accuracy_verified"] is False
    assert len(adaptive.elements) != len(global_mesh.elements)
    assert adaptive.volume_m3 == pytest.approx(
        global_mesh.volume_m3, rel=.01
    )


def test_explicit_ball_hotspot_supported_on_closed_stl(local_fixture):
    _, _, stl = local_fixture
    result = _screen(
        stl, stl_units="mm",
        refinement=LocalRefinement(
            target_size_mm=3, radius_mm=10,
            refine_circular_edges=False,
            hotspot_centers_mm=((50.0, 5.0, 5.0),),
        ),
    )
    assert result["status"] == "cad_to_fem_screening_only"
    assert result["cad"]["local_refinement"]["circular_edge_count"] == 0
    assert result["cad"]["local_refinement"]["influence_region_node_count"] > 0
    assert result["analysis"]["release_authorized"] is False


def test_local_three_mesh_study_identifies_unstable_peak_stress(local_fixture):
    _, drilled, _ = local_fixture
    report = run_cad_mesh_sensitivity(
        drilled,
        mesh_sizes_mm=[1.5, 1.0, 0.8],
        global_mesh_size_mm=8,
        local_radius_mm=8,
        refine_circular_edges=True,
        stl_units=None,
        fixed_plane="x_min",
        loaded_plane="x_max",
        total_force_n=[100, 0, 0],
        youngs_modulus_pa=2e9,
        poisson_ratio=.25,
        yield_strength_pa=100e6,
    )
    assert report["refinement_strategy"] == "local_features"
    assert report["status"] == "inconclusive_refinement"
    assert "peak_stress_changes_with_refinement" in report["sensitivity_blockers"]
    influence = [
        row["near_feature_node_count"] for row in report["levels"]
    ]
    assert influence[0] < influence[1] < influence[2]
    assert all(c["sufficient_effective_refinement"] for c in report["adjacent_mesh_comparisons"])
    assert all(c["sufficient_element_refinement"] is None for c in report["adjacent_mesh_comparisons"])
    assert report["fine_mesh_raw_yield_safety_factor"] > 0
    assert report["yield_margin_usable_for_engineering_release"] is False
    assert report["mesh_convergence_verified"] is False
    assert report["fabrication_authorized"] is False


def test_local_mesh_requires_real_target_and_real_units(local_fixture):
    plain, drilled, stl = local_fixture
    with pytest.raises(ValueError, match="no circular edges"):
        mesh_cad_solid(
            plain, mesh_target_mm=8,
            local_refinement=LocalRefinement(
                target_size_mm=2, radius_mm=8
            )
        )
    with pytest.raises(ValueError, match="requires STEP"):
        mesh_cad_solid(
            stl, stl_units="mm", mesh_target_mm=8,
            local_refinement=LocalRefinement(
                target_size_mm=2, radius_mm=8
            )
        )
    with pytest.raises(ValueError, match="smaller than global"):
        mesh_cad_solid(
            drilled, mesh_target_mm=8,
            local_refinement=LocalRefinement(
                target_size_mm=8, radius_mm=8
            )
        )
    with pytest.raises(ValueError, match="bounding box"):
        mesh_cad_solid(
            plain, mesh_target_mm=8,
            local_refinement=LocalRefinement(
                target_size_mm=2, radius_mm=8,
                refine_circular_edges=False,
                hotspot_centers_mm=((500.0, 2.0, 2.0),),
            )
        )


def test_local_study_requires_global_target_and_radius_before_meshing():
    base = dict(
        path="does-not-exist.step",
        mesh_sizes_mm=[3, 2, 1],
        stl_units=None,
        fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=[100, 0, 0],
        youngs_modulus_pa=2e9, poisson_ratio=.25,
    )
    with pytest.raises(ValueError, match="smaller than the global"):
        run_cad_mesh_sensitivity(
            **base, global_mesh_size_mm=2, local_radius_mm=5,
            refine_circular_edges=True,
        )
    with pytest.raises(ValueError, match="local_radius_mm"):
        run_cad_mesh_sensitivity(
            **base, global_mesh_size_mm=8,
            refine_circular_edges=True,
        )
    with pytest.raises(ValueError, match="local options require"):
        run_cad_mesh_sensitivity(
            **base, refine_circular_edges=True
        )


def test_local_cli_reports_inconclusive_without_hiding_raw_stress(local_fixture, tmp_path):
    from hardware_splicer.mechanical_cad_fem import main
    _, drilled, _ = local_fixture
    out = tmp_path / "local-study.json"
    assert main([
        str(drilled), "--mesh-size-mm", "8",
        "--local-study-mm", "1.5", "1", "0.8",
        "--local-radius-mm", "8", "--refine-circular-edges",
        "--fixed-plane", "x_min", "--loaded-plane", "x_max",
        "--force-n", "100", "0", "0",
        "--youngs-pa", "2000000000", "--poisson", "0.25",
        "--out", str(out),
    ]) == 0
    data = json.loads(out.read_text())
    assert data["status"] == "inconclusive_refinement"
    assert data["refinement_strategy"] == "local_features"
    assert data["mesh_convergence_verified"] is False

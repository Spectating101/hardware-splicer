"""CAD-to-FEM boundary, conservation and Gmsh integration regression tests."""

from __future__ import annotations

import json
import math

import pytest

from hardware_splicer.mechanical_cad_fem import (
    _validate_volume_boundary,
    build_face_loaded_case,
    mesh_cad_solid,
    run_cad_screening,
)


def _tet_faces(a=0, b=1, c=2, d=3):
    return [[a, b, c], [a, b, d], [a, c, d], [b, c, d]]


def test_closed_tetra_boundary_is_watertight():
    _validate_volume_boundary([[0, 1, 2, 3]], _tet_faces())


def test_open_surface_or_mismatched_mesh_must_fail():
    with pytest.raises(ValueError, match="exactly match"):
        _validate_volume_boundary([[0, 1, 2, 3]], _tet_faces()[:-1])


def test_disconnected_shells_fail_closed():
    with pytest.raises(ValueError, match="multiple disconnected"):
        _validate_volume_boundary(
            [[0, 1, 2, 3], [4, 5, 6, 7]],
            _tet_faces() + _tet_faces(4, 5, 6, 7),
        )


def test_multiple_tetrahedra_sharing_same_face_are_rejected():
    with pytest.raises(ValueError, match="nonmanifold tetrahedral"):
        _validate_volume_boundary(
            [[0, 1, 2, 3], [0, 1, 2, 4], [0, 1, 2, 5]],
            _tet_faces(),
        )


def test_explicit_stl_units_and_meshing_limits(tmp_path):
    source = tmp_path / "box.stl"
    source.write_text("solid invalid\nendsolid invalid\n")
    with pytest.raises(ValueError, match="explicitly declare"):
        mesh_cad_solid(source)
    with pytest.raises(ValueError, match="0.5..500"):
        mesh_cad_solid(source, mesh_target_mm=0.01, stl_units="mm")
    invalid_extension = tmp_path / "wrong.txt"
    invalid_extension.write_text("not CAD")
    with pytest.raises(ValueError, match="only STEP"):
        mesh_cad_solid(invalid_extension, mesh_target_mm=8)


@pytest.fixture(scope="module")
def cad_box(tmp_path_factory):
    gmsh = pytest.importorskip("gmsh")
    parent = tmp_path_factory.mktemp("cad_fem_geometry")
    step = parent / "prismatic_bar.step"
    stl = parent / "prismatic_bar.stl"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("test-bar")
        gmsh.model.occ.addBox(0, 0, 0, 100, 10, 10)
        gmsh.model.occ.synchronize()
        gmsh.write(str(step))
        gmsh.model.mesh.generate(2)
        gmsh.write(str(stl))
    finally:
        gmsh.finalize()
    return step, stl


@pytest.mark.parametrize("kind", ["step", "stl"])
def test_real_cad_meshing_preserves_geometry_and_boundary(cad_box, kind):
    source = cad_box[0 if kind == "step" else 1]
    mesh = mesh_cad_solid(source, mesh_target_mm=8, stl_units="mm" if kind == "stl" else None)
    assert 4 < len(mesh.nodes_m) <= 2000
    assert 1 < len(mesh.elements) <= 5000
    assert len(mesh.surface_triangles) > 0
    assert mesh.source_sha256.startswith("sha256:")
    assert mesh.bounding_box_m[1][0] - mesh.bounding_box_m[0][0] == pytest.approx(.1, abs=1e-8)
    assert mesh.volume_m3 == pytest.approx(1e-5, rel=0.001)
    if kind == "step":
        assert mesh.cad_kernel_volume_m3 == pytest.approx(1e-5)
        assert mesh.mesh_volume_error_fraction < .001
    else:
        assert mesh.cad_kernel_volume_m3 is None
    request, boundary = build_face_loaded_case(
        mesh, fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=[100, 0, 0], youngs_modulus_pa=2e9,
        poisson_ratio=0.25, yield_strength_pa=100e6,
    )
    assert sum(x.force_n[0] for x in request.loads_n) == pytest.approx(100)
    assert boundary["fixed_face_area_m2"] == pytest.approx(1e-4, rel=0.005)
    assert boundary["loaded_face_area_m2"] == pytest.approx(1e-4, rel=0.005)
    assert len(request.constraints) >= 3


@pytest.mark.parametrize("kind", ["step", "stl"])
def test_real_cad_to_fem_matches_axial_bar_reference(cad_box, kind):
    source = cad_box[0 if kind == "step" else 1]
    result = run_cad_screening(
        source,
        mesh_target_mm=8,
        stl_units="mm" if kind == "stl" else None,
        fixed_plane="x_min", loaded_plane="x_max", total_force_n=[100, 0, 0],
        youngs_modulus_pa=2e9, poisson_ratio=0.25, yield_strength_pa=100e6,
    )
    actual = result["analysis"]
    # 100N * 0.1m / (2GPa * (0.01m)^2) = 5e-5m.
    reference_displacement_m = 5e-5
    assert actual["max_displacement_m"] == pytest.approx(reference_displacement_m, rel=0.10)
    assert actual["max_von_mises_pa"] == pytest.approx(100 / 1e-4, rel=0.20)
    assert actual["force_equilibrium_residual_n"] < 1e-7
    assert result["mesh_convergence_verified"] is False
    assert result["fabrication_authorized"] is False
    assert result["release_authorized"] is False
    assert actual["structural_safety_verified"] is False


def test_load_and_support_on_same_face_rejected(cad_box):
    mesh = mesh_cad_solid(cad_box[0], mesh_target_mm=8)
    with pytest.raises(ValueError, match="must differ"):
        build_face_loaded_case(
            mesh, fixed_plane="x_min", loaded_plane="x_min",
            total_force_n=[10, 0, 0], youngs_modulus_pa=2e9, poisson_ratio=0.25,
        )


def test_open_stl_rejected(tmp_path):
    gmsh = pytest.importorskip("gmsh")
    path = tmp_path / "open_sheet.stl"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("open")
        a = gmsh.model.geo.addPoint(0, 0, 0, 10)
        b = gmsh.model.geo.addPoint(10, 0, 0, 10)
        c = gmsh.model.geo.addPoint(0, 10, 0, 10)
        lines = [gmsh.model.geo.addLine(x, y) for x, y in ((a, b), (b, c), (c, a))]
        gmsh.model.geo.addPlaneSurface([gmsh.model.geo.addCurveLoop(lines)])
        gmsh.model.geo.synchronize()
        gmsh.model.mesh.generate(2)
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    with pytest.raises(ValueError, match="closed"):
        mesh_cad_solid(path, stl_units="mm")


def test_multiple_step_solids_rejected(tmp_path):
    gmsh = pytest.importorskip("gmsh")
    path = tmp_path / "two_solids.step"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("two-boxes")
        gmsh.model.occ.addBox(0, 0, 0, 10, 10, 10)
        gmsh.model.occ.addBox(20, 0, 0, 10, 10, 10)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    with pytest.raises(ValueError, match="exactly one closed 3D solid"):
        mesh_cad_solid(path, mesh_target_mm=5)

def test_cli_writes_auditable_report(cad_box, tmp_path):
    from hardware_splicer.mechanical_cad_fem import main
    output = tmp_path / "screening.json"
    assert main([
        str(cad_box[0]), "--mesh-size-mm", "8",
        "--fixed-plane", "x_min", "--loaded-plane", "x_max",
        "--force-n", "100", "0", "0",
        "--youngs-pa", "2000000000", "--poisson", "0.25",
        "--yield-pa", "100000000", "--out", str(output),
    ]) == 0
    report = json.loads(output.read_text())
    assert report["cad"]["source_sha256"].startswith("sha256:")
    assert report["boundary_conditions"]["loaded_face_area_m2"] == pytest.approx(1e-4, rel=0.01)
    assert report["analysis"]["fabrication_authorized"] is False


def test_step_through_hole_is_meshable_and_preserves_removed_volume(tmp_path):
    gmsh = pytest.importorskip("gmsh")
    source = tmp_path / "drilled_bar.step"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("drilled-prism")
        box = gmsh.model.occ.addBox(0, 0, 0, 100, 20, 10)
        cylinder = gmsh.model.occ.addCylinder(50, 10, 0, 0, 0, 10, 3)
        gmsh.model.occ.cut([(3, box)], [(3, cylinder)],
                           removeObject=True, removeTool=True)
        gmsh.model.occ.synchronize()
        gmsh.write(str(source))
    finally:
        gmsh.finalize()

    mesh = mesh_cad_solid(source, mesh_target_mm=6)
    expected_volume = (100 * 20 * 10 - math.pi * 3**2 * 10) * 1e-9
    # Curved through-hole meshing approximates the CAD surface; it cannot
    # reproduce the exact cylindrical volume at a coarse target element size.
    assert mesh.volume_m3 == pytest.approx(expected_volume, rel=.01)
    assert mesh.cad_kernel_volume_m3 == pytest.approx(expected_volume, rel=1e-8)
    assert mesh.mesh_volume_error_fraction is not None
    assert mesh.mesh_volume_error_fraction < .01
    # Removing the through-hole changes actual volume, unlike a bounding-box
    # approximation.
    assert mesh.volume_m3 < 100 * 20 * 10 * 1e-9
    request, boundary = build_face_loaded_case(
        mesh, fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=[100, 0, 0], youngs_modulus_pa=2e9, poisson_ratio=.25,
    )
    assert request.elements
    assert boundary["loaded_face_area_m2"] == pytest.approx(.02 * .01, rel=.005)

"""Distinguish numerical sensitivity evidence from actual strength verification."""

from __future__ import annotations

import json

import pytest

from hardware_splicer.mechanical_cad_convergence import run_cad_mesh_sensitivity


@pytest.fixture(scope="module")
def reference_parts(tmp_path_factory):
    gmsh = pytest.importorskip("gmsh")
    root = tmp_path_factory.mktemp("cad_refinement_fixtures")
    box = root / "box.step"
    hole = root / "hole.step"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("bar")
        gmsh.model.occ.addBox(0, 0, 0, 100, 10, 10)
        gmsh.model.occ.synchronize()
        gmsh.write(str(box))
        gmsh.clear()
        gmsh.model.add("perforated-bar")
        stock = gmsh.model.occ.addBox(0, 0, 0, 100, 20, 10)
        drill = gmsh.model.occ.addCylinder(50, 10, 0, 0, 0, 10, 3)
        gmsh.model.occ.cut(
            [(3, stock)], [(3, drill)], removeObject=True, removeTool=True
        )
        gmsh.model.occ.synchronize()
        gmsh.write(str(hole))
    finally:
        gmsh.finalize()
    return box, hole


def _study(source, **overrides):
    options = dict(
        mesh_sizes_mm=[8, 6, 4],
        stl_units=None,
        fixed_plane="x_min",
        loaded_plane="x_max",
        total_force_n=[100.0, 0.0, 0.0],
        youngs_modulus_pa=2e9,
        poisson_ratio=0.25,
        yield_strength_pa=100e6,
    )
    options.update(overrides)
    return run_cad_mesh_sensitivity(source, **options)


def test_bar_refinement_numerically_stable_without_certifying_strength(reference_parts):
    result = _study(reference_parts[0])
    assert result["status"] == "numerically_stable_screening"
    assert result["mesh_sensitivity_observed_stable"] is True
    assert not result["sensitivity_blockers"]
    assert len(result["levels"]) == 3
    assert len(result["adjacent_mesh_comparisons"]) == 2
    assert all(level["peak_stress_centroid_m"] for level in result["levels"])
    assert [x["target_mesh_size_mm"] for x in result["levels"]] == [8, 6, 4]
    assert all(x["stress_tolerance_met"] for x in result["adjacent_mesh_comparisons"])
    assert result["geometry_reference_available"] is True
    assert result["fine_mesh_raw_yield_safety_factor"] is not None
    assert result["yield_margin_usable_for_engineering_release"] is False
    assert result["mesh_convergence_verified"] is False
    assert result["physical_validation_required"] is True
    assert result["structural_safety_verified"] is False
    assert result["fabrication_authorized"] is False
    assert result["release_authorized"] is False
    assert result["levels"][-1]["max_displacement_m"] == pytest.approx(5e-5, rel=.10)


def test_drilled_part_flags_peak_stress_instability(reference_parts):
    result = _study(reference_parts[1])
    assert result["status"] == "inconclusive_refinement"
    assert result["mesh_sensitivity_observed_stable"] is False
    assert "peak_stress_changes_with_refinement" in result["sensitivity_blockers"]
    assert all(
        x["displacement_tolerance_met"] for x in result["adjacent_mesh_comparisons"]
    )
    assert any(
        not x["stress_tolerance_met"] for x in result["adjacent_mesh_comparisons"]
    )
    assert result["fine_mesh_raw_yield_safety_factor"] is not None
    assert result["yield_margin_usable_for_engineering_release"] is False


@pytest.mark.parametrize("sizes,match", [
    ([12, 8], "3 or 4"),
    ([12, 8, 6, 4, 2], "3 or 4"),
    ([8, 12, 6], "strictly decreasing"),
    ([8, 8, 6], "strictly decreasing"),
    ([8, 6, 0], "finite values"),
    ([8, 6, float("nan")], "finite values"),
])
def test_invalid_study_sizes_rejected_before_meshing(sizes, match):
    with pytest.raises(ValueError, match=match):
        _study("does-not-exist.step", mesh_sizes_mm=sizes)


@pytest.mark.parametrize("override,match", [
    ({"displacement_tolerance": 0}, "displacement_tolerance"),
    ({"stress_tolerance": float("nan")}, "stress_tolerance"),
    ({"geometry_volume_tolerance": .3}, "geometry_volume_tolerance"),
    ({"minimum_refinement_growth": 1}, "minimum_refinement_growth"),
])
def test_invalid_criteria_fail_closed(override, match):
    with pytest.raises(ValueError, match=match):
        _study("does-not-exist.step", **override)


def test_missing_mesh_levels_cannot_produce_false_pass(monkeypatch):
    from hardware_splicer import mechanical_cad_convergence as convergence

    counter = 0

    def fake_run(*args, **kwargs):
        nonlocal counter
        counter += 1
        if counter == 2:
            raise ValueError("meshing failure")
        if counter != 1:
            raise AssertionError("third level must not be attempted")
        return {
            "cad": {
                "source_sha256": "same",
                "mesh_volume_m3": 1e-5, "cad_kernel_volume_m3": 1e-5,
                "mesh_volume_error_fraction": 0.0,
            },
            "analysis": {
                "node_count": 100, "element_count": 200,
                "max_displacement_m": 5e-5, "max_von_mises_pa": 1e6,
                "peak_stress_centroid_m": [0.05, 0.005, 0.005],
                "yield_safety_factor": 100,
                "force_equilibrium_residual_n": 0,
            },
            "boundary_conditions": {
                "fixed_face_area_m2": 1e-4, "loaded_face_area_m2": 1e-4,
            },
        }

    monkeypatch.setattr(convergence, "run_cad_screening", fake_run)
    with pytest.raises(ValueError, match="meshing failure"):
        _study("missing-level")
    assert counter == 2


def test_source_mutation_between_mesh_levels_is_not_accepted(monkeypatch):
    from hardware_splicer import mechanical_cad_convergence as convergence

    calls = 0
    def fake_run(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {
            "cad": {
                "source_sha256": str(calls),
                "mesh_volume_m3": 1e-5,
                "cad_kernel_volume_m3": 1e-5,
                "mesh_volume_error_fraction": 0,
            },
            "analysis": {
                "node_count": 100, "element_count": 200 * calls,
                "max_displacement_m": 5e-5,
                "max_von_mises_pa": 1e6,
                "peak_stress_centroid_m": [0.05, 0.005, 0.005],
                "yield_safety_factor": 100,
                "force_equilibrium_residual_n": 0,
            },
            "boundary_conditions": {
                "fixed_face_area_m2": 1e-4, "loaded_face_area_m2": 1e-4,
            },
        }

    monkeypatch.setattr(convergence, "run_cad_screening", fake_run)
    with pytest.raises(ValueError, match="source changed"):
        _study("source-mutation")


def test_cli_study_serializes_result(reference_parts, tmp_path):
    from hardware_splicer.mechanical_cad_fem import main
    out = tmp_path / "sensitivity.json"
    assert main([
        str(reference_parts[0]),
        "--mesh-study-mm", "8", "6", "4",
        "--fixed-plane", "x_min",
        "--loaded-plane", "x_max",
        "--force-n", "100", "0", "0",
        "--youngs-pa", "2000000000",
        "--poisson", "0.25",
        "--yield-pa", "100000000",
        "--out", str(out),
    ]) == 0
    result = json.loads(out.read_text())
    assert result["status"] == "numerically_stable_screening"
    assert result["mesh_convergence_verified"] is False


def test_identical_element_count_across_meshes_is_not_stability_evidence(monkeypatch):
    from hardware_splicer import mechanical_cad_convergence as convergence

    counter = 0

    def fake_run(*args, **kwargs):
        nonlocal counter
        counter += 1
        return {
            "cad": {
                "source_sha256": "same",
                "mesh_volume_m3": 1e-5, "cad_kernel_volume_m3": 1e-5,
                "mesh_volume_error_fraction": 0.0,
            },
            "analysis": {
                "node_count": 100, "element_count": 200,
                "max_displacement_m": 5e-5, "max_von_mises_pa": 1e6,
                "peak_stress_centroid_m": [0.05, 0.005, 0.005],
                "yield_safety_factor": 100,
                "force_equilibrium_residual_n": 0.0,
            },
            "boundary_conditions": {
                "fixed_face_area_m2": 1e-4, "loaded_face_area_m2": 1e-4,
            },
        }

    monkeypatch.setattr(convergence, "run_cad_screening", fake_run)
    report = _study("identical-output")
    assert counter == 3
    assert report["mesh_sensitivity_observed_stable"] is False
    assert report["status"] == "inconclusive_refinement"
    assert "insufficient_effective_refinement" in report["sensitivity_blockers"]
    assert report["yield_margin_usable_for_engineering_release"] is False

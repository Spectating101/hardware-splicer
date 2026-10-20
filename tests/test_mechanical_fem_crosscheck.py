"""Independent scikit-fem cross-check, analytical references, and fail-closed gates."""

from __future__ import annotations

import json
import math

import pytest

from hardware_splicer.mechanical_fem import FemInput
from hardware_splicer.mechanical_fem_crosscheck import (
    crosscheck_fem_case,
    validate_cad_with_independent_solver,
)


def _tetra() -> FemInput:
    return FemInput.model_validate({
        "nodes_m": [
            [0, 0, 0], [0.1, 0, 0],
            [0, 0.1, 0], [0, 0, 0.1],
        ],
        "elements": [[0, 1, 2, 3]],
        "loads_n": [{"node": 1, "force_n": [10.0, 0.0, 0.0]}],
        "constraints": [{"node": i} for i in [0, 2, 3]],
        "youngs_modulus_pa": 2e9,
        "poisson_ratio": 0.25,
        "yield_strength_pa": 1e8,
    })


def test_single_tetra_independent_assembly_agrees_numerically():
    pytest.importorskip("skfem")
    report = crosscheck_fem_case(_tetra())
    assert report["status"] == "independent_numerical_agreement"
    assert report["tetrahedron_count"] == 1
    assert report["reference_solver"] == "scikit-fem"
    assert report["comparison_metrics"]
    assert max(report["comparison_metrics"].values()) < 1e-8
    assert report["validated_case_sha256"].startswith("sha256:")
    assert report["independent_physical_model_verified"] is False
    assert report["mesh_convergence_verified"] is False
    assert report["structural_safety_verified"] is False
    assert report["fabrication_authorized"] is False
    assert report["release_authorized"] is False
    assert report["yield_margin_usable_for_engineering_release"] is False


def test_reversing_tet_orientation_keeps_agreement():
    pytest.importorskip("skfem")
    case = _tetra().model_dump(mode="json")
    case["elements"] = [[0, 2, 1, 3]]
    assert crosscheck_fem_case(case)["status"] == "independent_numerical_agreement"


def test_disagreement_in_stress_fails_closed(monkeypatch):
    from hardware_splicer import mechanical_fem_crosscheck as crosscheck
    pytest.importorskip("skfem")
    original = crosscheck._independent_scikit_fem

    def corrupt(case):
        ref = original(case)
        ref["max_von_mises_pa"] *= 1.2
        ref["element_von_mises_pa"] = [
            value * 1.2 for value in ref["element_von_mises_pa"]
        ]
        return ref

    monkeypatch.setattr(crosscheck, "_independent_scikit_fem", corrupt)
    report = crosscheck_fem_case(_tetra())
    assert report["status"] == "independent_numerical_disagreement"
    assert "max_stress_relative_error" in report["disagreement_blockers"]
    assert report["fabrication_authorized"] is False


def test_disagreement_in_displacement_and_energy_fails_closed(monkeypatch):
    from hardware_splicer import mechanical_fem_crosscheck as crosscheck
    pytest.importorskip("skfem")
    original = crosscheck._independent_scikit_fem

    def corrupt(case):
        ref = original(case)
        ref["nodal_displacements_m"][1][0] *= .75
        ref["total_strain_energy_j"] *= .75
        return ref

    monkeypatch.setattr(crosscheck, "_independent_scikit_fem", corrupt)
    report = crosscheck_fem_case(_tetra())
    assert "nodal_displacement_l2_relative_error" in report["disagreement_blockers"]
    assert "strain_energy_relative_error" in report["disagreement_blockers"]
    assert report["yield_margin_usable_for_engineering_release"] is False


def test_invalid_tolerance_rejected():
    for tolerance in (0, 0.5, math.nan):
        with pytest.raises(ValueError, match="relative_tolerance"):
            crosscheck_fem_case(_tetra(), relative_tolerance=tolerance)


@pytest.fixture(scope="module")
def reference_cad(tmp_path_factory):
    gmsh = pytest.importorskip("gmsh")
    pytest.importorskip("skfem")
    parent = tmp_path_factory.mktemp("independent_fem_cad")
    bar = parent / "bar.step"
    drilled = parent / "drilled.step"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("bar")
        gmsh.model.occ.addBox(0, 0, 0, 100, 10, 10)
        gmsh.model.occ.synchronize()
        gmsh.write(str(bar))
        gmsh.clear()
        gmsh.model.add("drilled")
        box = gmsh.model.occ.addBox(0, 0, 0, 100, 20, 10)
        drill = gmsh.model.occ.addCylinder(50, 10, 0, 0, 0, 10, 3)
        gmsh.model.occ.cut(
            [(3, box)], [(3, drill)],
            removeObject=True, removeTool=True,
        )
        gmsh.model.occ.synchronize()
        gmsh.write(str(drilled))
    finally:
        gmsh.finalize()
    return bar, drilled


def _cad_report(source, *, mesh_size=8, force=None, mode=None, tolerance=.10):
    return validate_cad_with_independent_solver(
        source,
        mesh_target_mm=mesh_size,
        stl_units=None,
        fixed_plane="x_min",
        loaded_plane="x_max",
        total_force_n=force or [100, 0, 0],
        youngs_modulus_pa=2e9,
        poisson_ratio=.25,
        yield_strength_pa=1e8,
        analytic_bar_benchmark=mode,
        benchmark_relative_tolerance=tolerance,
    )


def test_reference_bar_axial_passes_independent_and_analytic(reference_cad):
    r = _cad_report(reference_cad[0], mode="axial")
    assert r["status"] == "independent_numerical_agreement"
    assert r["comparison_metrics"]["max_displacement_relative_error"] < 1e-6
    assert r["comparison_metrics"]["max_stress_relative_error"] < 1e-8
    assert r["analytic_reference"]["within_declared_tolerance"] is True
    assert r["analytic_reference"]["relative_error"] < .01
    assert r["source_cad_sha256"].startswith("sha256:")
    assert r["independent_physical_model_verified"] is False


def test_reference_bar_bending_detects_coarse_mesh_error(reference_cad):
    r = _cad_report(
        reference_cad[0],
        force=[0, 0, -1],
        mode="cantilever",
        mesh_size=4,
    )
    assert not r["disagreement_blockers"]
    assert r["status"] == "analytic_benchmark_disagreement"
    assert r["analytic_reference"]["relative_error"] > .20
    assert not r["analytic_reference"]["within_declared_tolerance"]
    assert r["fabrication_authorized"] is False


def test_hole_rejected_by_unperforated_bar_formula(reference_cad):
    with pytest.raises(ValueError, match="unperforated STEP bar"):
        _cad_report(reference_cad[1], mode="axial")


def test_independent_cad_drilled_mesh_comparison_passes_implementation_only(reference_cad):
    r = _cad_report(reference_cad[1])
    assert r["status"] == "independent_numerical_agreement"
    assert r["tetrahedron_count"] > 100
    assert r["comparison_metrics"]["element_von_mises_l2_relative_error"] < 1e-8
    assert r["mesh_convergence_verified"] is False


def test_crosscheck_cli_writes_non_authorizing_report(reference_cad, tmp_path):
    from hardware_splicer.mechanical_fem_crosscheck import main

    output = tmp_path / "external-crosscheck.json"
    assert main([
        str(reference_cad[0]),
        "--mesh-size-mm", "8",
        "--fixed-plane", "x_min",
        "--loaded-plane", "x_max",
        "--force-n", "100", "0", "0",
        "--youngs-pa", "2000000000",
        "--poisson", ".25",
        "--analytic-bar-benchmark", "axial",
        "--out", str(output),
    ]) == 0
    data = json.loads(output.read_text())
    assert data["status"] == "independent_numerical_agreement"
    assert data["analytic_reference"]["within_declared_tolerance"] is True
    assert data["fabrication_authorized"] is False


def test_crosscheck_cli_returns_nonzero_for_analytic_failure(reference_cad, tmp_path):
    from hardware_splicer.mechanical_fem_crosscheck import main

    output = tmp_path / "analytic-failure.json"
    assert main([
        str(reference_cad[0]),
        "--mesh-size-mm", "4",
        "--fixed-plane", "x_min",
        "--loaded-plane", "x_max",
        "--force-n", "0", "0", "-1",
        "--youngs-pa", "2000000000",
        "--poisson", ".25",
        "--analytic-bar-benchmark", "cantilever",
        "--out", str(output),
    ]) == 2
    data = json.loads(output.read_text())
    assert data["status"] == "analytic_benchmark_disagreement"
    assert data["analytic_reference"]["within_declared_tolerance"] is False
    assert data["structural_safety_verified"] is False

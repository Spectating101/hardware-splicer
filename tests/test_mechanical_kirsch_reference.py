"""Analytical stress benchmark and Mecha bracket transfer are different gates."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

# Structural/FEM extras are opt-in. Generic HS CI deliberately installs
# only the core dependencies; the dedicated CAD/FEM job exercises this suite.
np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from hardware_splicer.mechanical_kirsch_reference import (
    kirsch_stress,
    run_kirsch_annulus_reference,
    run_kirsch_reference_series,
)
from hardware_splicer.mechanical_bracket_screening import (
    _check_bracket_spec,
    generate_bracket_reference_step,
    run_bracket_transfer_screening,
)


def test_kirsch_rim_neumann_and_hoop_stress_three_sigma():
    a = .003
    remote = 1e6
    theta = np.linspace(0, 2 * math.pi, 32, endpoint=False)
    stress = kirsch_stress(
        a * np.cos(theta), a * np.sin(theta),
        hole_radius_m=a, remote_tension_pa=remote,
    )
    assert np.max(np.abs(stress["sigma_rr_pa"])) < 1e-8
    assert np.max(np.abs(stress["tau_rt_pa"])) < 1e-8
    assert stress["sigma_tt_pa"][8] == pytest.approx(3 * remote)
    assert stress["sigma_tt_pa"][0] == pytest.approx(-remote)
    assert stress["sigma_tt_pa"][24] == pytest.approx(3 * remote)


def test_kirsch_far_field_correct_uniaxial_components():
    stress = kirsch_stress(
        np.array([300., 0]), np.array([0., 300.]),
        hole_radius_m=.003, remote_tension_pa=2e6,
    )
    assert stress["sigma_xx_pa"] == pytest.approx([2e6, 2e6], rel=1e-8)
    assert np.abs(stress["sigma_yy_pa"]).max() < 1
    assert np.abs(stress["tau_xy_pa"]).max() < 1


@pytest.mark.parametrize("bad", [
    {"hole_radius_m": -.001, "remote_tension_pa": 1e6},
    {"hole_radius_m": .003, "remote_tension_pa": math.nan},
])
def test_invalid_analytic_arguments_rejected(bad):
    with pytest.raises(ValueError):
        kirsch_stress(.005, 0., **bad)


def test_kirsch_inside_hole_fails_closed():
    with pytest.raises(ValueError, match="inside circular hole"):
        kirsch_stress(.002, 0., hole_radius_m=.003, remote_tension_pa=1e6)


@pytest.fixture(scope="module")
def kirsch_series():
    pytest.importorskip("gmsh")
    pytest.importorskip("skfem")
    return run_kirsch_reference_series()


def test_kirsch_analytic_reference_converges(kirsch_series):
    series = kirsch_series
    assert series["status"] == "analytical_plane_stress_series_pass"
    assert series["blockers"] == []
    assert len(series["levels"]) == 3
    errors = [
        row["near_hole_weighted_stress_l2_relative_error"]
        for row in series["levels"]
    ]
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < .06
    assert errors[0] < .12
    assert all(row["hole_boundary_facets"] >= 6 for row in series["levels"])
    assert all(row["outer_boundary_facets"] > row["hole_boundary_facets"]
               for row in series["levels"])
    assert all(row["min_abs_sampled_curved_jacobian_m2"] > 0
               for row in series["levels"])
    assert all(row["work_energy_relative_difference"] < 1e-7
               for row in series["levels"])
    assert series["finite_3d_geometry_strength_verified"] is False
    assert series["fabrication_authorized"] is False


def test_kirsch_tiny_tolerance_rejects_benchmark():
    r = run_kirsch_annulus_reference(
        mesh_target_mm=2.3, relative_error_tolerance=.001
    )
    assert r["status"] == "analytical_plane_stress_reference_inconclusive"
    assert not r["benchmark_validated_for_this_ideal_2d_case"]
    assert r["applies_directly_to_finite_3d_bracket"] is False
    assert r["structural_safety_verified"] is False


@pytest.mark.parametrize("sizes", [
    [2.3, 1.7], [2.3, 2.3, 1.3], [1.3, 1.7, 2.3],
    [2.3, 1.7, math.nan],
])
def test_bad_study_params_fail_before_gmsh(sizes):
    with pytest.raises(ValueError, match="3 or 4 finite decreasing"):
        run_kirsch_reference_series(mesh_targets_mm=sizes)


def test_analytic_cli_creates_audit_json(tmp_path):
    from hardware_splicer.mechanical_kirsch_reference import main
    out = tmp_path / "kirsch-evidence.json"
    assert main(["--out", str(out)]) == 0
    data = json.loads(out.read_text("utf-8"))
    assert data["status"] == "analytical_plane_stress_series_pass"
    assert data["levels"][0]["theoretical_infinite_plate_peak_hoop_over_remote"] == 3.
    assert data["structural_safety_verified"] is False


@pytest.fixture(scope="module")
def real_mecha_template():
    # Read the actual project's Mecha-Splicer model, not an invented CAD spec.
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "apps" / "mecha-splicer" / "src"))
    from mecha_splicer.templates.mint_templates import spec_for_template
    from mecha_splicer.spec import BracketSpec

    actual = spec_for_template("simple_plate_bracket")
    assert actual["process"] == "fdm"
    params = BracketSpec.model_validate(actual["bracket"])
    return params.model_dump(mode="json")


def test_real_mecha_bracket_template_registry_recovers(real_mecha_template):
    # Regression for previously present JSON-style lowercase true in
    # Python source, which broke the whole template registry at call time.
    assert real_mecha_template["w_mm"] == 60.
    assert real_mecha_template["d_mm"] == 20.
    assert real_mecha_template["hole_d_mm"] == 3.2
    assert real_mecha_template["hole_spacing_mm"] == 40.


@pytest.mark.parametrize("mutation", [
    {"hole_spacing_mm": 60.},
    {"hole_d_mm": 25.},
    {"t_mm": 0.},
    {"hole_spacing_mm": math.nan},
])
def test_invalid_mecha_bracket_dimensions_rejected(real_mecha_template, mutation):
    with pytest.raises(ValueError):
        _check_bracket_spec({**real_mecha_template, **mutation})


def test_mecha_bracket_geometry_rejects_overwrite(real_mecha_template, tmp_path):
    dest = tmp_path / "already.step"
    dest.write_text("existing design is protected")
    with pytest.raises(ValueError, match="refuses to overwrite"):
        generate_bracket_reference_step(real_mecha_template, dest)
    assert dest.read_text() == "existing design is protected"


@pytest.fixture(scope="module")
def real_mecha_transfer(real_mecha_template, tmp_path_factory):
    root = tmp_path_factory.mktemp("mecha_template_screen")
    study = run_bracket_transfer_screening(
        spec=real_mecha_template,
        step_path=root / "simple_plate_bracket.step",
        mesh_targets_mm=[8, 6, 5],
        applied_edge_force_n=30,
        assumed_youngs_pa=2e9,
        assumed_poisson=.25,
    )
    return study, root


def test_actual_mecha_bracket_report_flags_hotspot_switch(real_mecha_transfer):
    report, root = real_mecha_transfer
    assert (root / "simple_plate_bracket.step").exists()
    assert report["mecha_spec_sha256"].startswith("sha256:")
    assert report["geometry"]["step_sha256"].startswith("sha256:")
    assert report["status"] == "inconclusive_bracket_transfer"
    study = report["curved_fem_study"]
    assert len(study["levels"]) == 3
    assert all(
        x["peak_sampled_von_mises_pa"] > 0 for x in study["levels"]
    )
    assert "p2_peak_hotspot_moves_with_curved_mesh_refinement" in study["blockers"]
    assert study["adjacent_mesh_comparisons"][0]["peak_hotspot_shift_mm"] > 30
    assert all(
        x["peak_stress_relative_change"] < .03
        for x in study["adjacent_mesh_comparisons"]
    )
    assert report["load_case"]["fastener_bearing_contact_modeled"] is False
    assert report["load_case"]["load_case_matches_an_actual_assembled_product"] is False
    assert report["kirsch_reference_applies_directly"] is False
    assert report["structural_safety_verified"] is False
    assert report["fabrication_authorized"] is False


def test_bracket_transfer_cli_preserves_study_and_step(real_mecha_template, tmp_path):
    # A second end-to-end CLI run also verifies failure exit code semantics.
    from hardware_splicer.mechanical_bracket_screening import main
    config = tmp_path / "from_mecha.json"
    config.write_text(
        json.dumps({"bracket": real_mecha_template}), encoding="utf-8"
    )
    step = tmp_path / "generated.step"
    report = tmp_path / "bracket-study.json"
    assert main([
        "--spec-json", str(config), "--step-out", str(step),
        "--report-out", str(report), "--mesh-study-mm", "8", "6", "5",
        "--edge-force-n", "30",
    ]) == 2
    assert step.exists()
    result = json.loads(report.read_text())
    assert result["status"] == "inconclusive_bracket_transfer"
    assert result["geometry"]["step_sha256"].startswith("sha256:")
    assert result["load_case"]["printed_polymer_anisotropy_calibrated"] is False

"""Numerical proof and guarded limits for reduced-order bolt-bore loads."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

from hardware_splicer.mechanical_bracket_screening import (
    generate_bracket_reference_step,
)
from hardware_splicer.mechanical_fastener_bearing import (
    _validate_inputs,
    solve_bore_bearing_case,
    run_fastener_bearing_mesh_series,
    screen_mecha_bracket_bearing,
)


@pytest.fixture(scope="module")
def bracket_spec():
    pytest.importorskip("gmsh")
    pytest.importorskip("skfem")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "apps" / "mecha-splicer" / "src"))
    from mecha_splicer.templates.mint_templates import spec_for_template
    from mecha_splicer.spec import BracketSpec

    values = spec_for_template("simple_plate_bracket")["bracket"]
    result = BracketSpec.model_validate(values).model_dump(mode="json")
    assert result["w_mm"] == 60
    assert result["hole_d_mm"] == 3.2
    return result


@pytest.fixture(scope="module")
def bracket_step(bracket_spec, tmp_path_factory):
    path = tmp_path_factory.mktemp("bearing_cases") / "two_hole.step"
    result = generate_bracket_reference_step(bracket_spec, path)
    assert result["step_sha256"].startswith("sha256:")
    return path


def _case(path, **kw):
    defaults = dict(
        mesh_target_mm=8.,
        centers_xy_mm=((10., 10.), (50., 10.)),
        hole_d_mm=3.2,
        thickness_mm=4.,
        force_n=30.,
        youngs_pa=2e9,
        poisson=.25,
    )
    defaults.update(kw)
    return solve_bore_bearing_case(path, **defaults)


def _study(path, **kw):
    defaults = dict(
        mesh_targets_mm=[8., 6., 5.],
        centers_xy_mm=((10., 10.), (50., 10.)),
        hole_d_mm=3.2, thickness_mm=4.,
        force_n=30., youngs_pa=2e9, poisson=.25,
    )
    defaults.update(kw)
    return run_fastener_bearing_mesh_series(path, **defaults)


def test_real_bracket_bore_facets_and_force_pressure(bracket_step):
    r = _case(bracket_step)
    assert r["status"] == "reduced_order_bore_bearing_screen_only"
    assert 400 < r["tetrahedron_count"] < 5000
    assert 0 < r["quadratic_dof_count"] < 8000
    expected_cylinder_area_m2 = math.pi * .0032 * .004
    for observed in r["hole_wall_full_area_m2"]:
        assert observed == pytest.approx(expected_cylinder_area_m2, rel=.015)
    assert r["anchor_half_wall_facet_count"] >= 6
    assert r["load_half_wall_facet_count"] >= 6
    assert r["integrated_bearing_resultant_n"][0] == pytest.approx(30., abs=1e-6)
    assert abs(r["integrated_bearing_resultant_n"][1]) < .75
    assert abs(r["integrated_bearing_resultant_n"][2]) < .75
    assert r["support_reaction_n"] == pytest.approx(
        [-value for value in r["integrated_bearing_resultant_n"]],
        abs=1e-6,
    )
    assert r["force_balance_error_n"] < 1e-7
    assert r["unconstrained_dof_residual_n"] < 1e-7
    assert r["strain_energy_j"] == pytest.approx(
        r["external_half_work_j"], rel=1e-8,
    )
    assert r["curved_vs_step_volume_error"] < .01
    assert r["min_curved_jacobian"] > 0
    assert r["bearing_pressure_scale_pa"] > 0


def test_hole_stress_is_recorded_independently(bracket_step):
    r = _case(bracket_step)
    assert len(r["per_hole_stress"]) == 2
    assert r["per_hole_stress"][0]["center_xy_mm"] == [10., 10.]
    assert r["per_hole_stress"][1]["center_xy_mm"] == [50., 10.]
    assert all(x["quadrature_sample_count"] > 100 for x in r["per_hole_stress"])
    assert all(x["peak_sampled_von_mises_pa"] > 2e6 for x in r["per_hole_stress"])
    assert all(x["weighted_rms_von_mises_pa"] > 0 for x in r["per_hole_stress"])
    assert r["peak_sampled_von_mises_pa"] >= max(
        item["peak_sampled_von_mises_pa"] for item in r["per_hole_stress"]
    )
    assert r["boundary_assumptions"]["contact_is_unilateral_nonlinear"] is False
    assert r["material_properties_measured"] is False
    assert r["joint_strength_verified"] is False
    assert r["structural_safety_verified"] is False
    assert r["fabrication_authorized"] is False


@pytest.fixture(scope="module")
def bearing_series(bracket_step):
    return _study(bracket_step)


def test_actual_3mesh_bearing_series_fails_closed_on_hole_local_changes(bearing_series):
    r = bearing_series
    assert r["status"] == "inconclusive_bore_bearing_refinement"
    assert len(r["levels"]) == 3
    assert len(r["adjacent_comparisons"]) == 2
    assert r["levels"][0]["quadratic_dof_count"] < r["levels"][1]["quadratic_dof_count"]
    assert r["levels"][1]["quadratic_dof_count"] < r["levels"][2]["quadratic_dof_count"]
    assert all(len(x["per_hole_stress"]) == 2 for x in r["levels"])
    assert len(r["blockers"]) >= 1
    assert "hole_0_peak_stress_unstable" in r["blockers"]
    assert "hole_1_peak_stress_unstable" in r["blockers"]
    assert "hole_0_hotspot_angle_unstable" in r["blockers"]
    assert r["stress_convergence_verified"] is False
    assert r["true_joint_bearing_strength_verified"] is False
    assert r["fabrication_authorized"] is False
    assert r["release_authorized"] is False


def test_real_mecha_bracket_integration_provenance(bracket_spec, tmp_path):
    report = screen_mecha_bracket_bearing(
        spec=bracket_spec,
        step_path=tmp_path / "generated_bearing.step",
        mesh_targets_mm=[8, 6, 5],
    )
    assert (tmp_path / "generated_bearing.step").exists()
    assert report["status"] == "inconclusive_mecha_fastener_bearing"
    assert report["mecha_source_spec_sha256"].startswith("sha256:")
    assert report["geometry"]["step_sha256"].startswith("sha256:")
    assert report["bearing_study"]["status"] == "inconclusive_bore_bearing_refinement"
    assert report["true_bolt_contact_validated"] is False
    assert report["screw_hole_bearing_strength_verified"] is False
    assert report["fabrication_authorized"] is False


def test_mecha_cli_keeps_nonzero_report(bracket_spec, tmp_path):
    from hardware_splicer.mechanical_fastener_bearing import main
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps({"bracket": bracket_spec}))
    step = tmp_path / "plate.step"
    report = tmp_path / "study.json"
    assert main([
        "--spec-json", str(spec_file), "--step-out", str(step),
        "--mesh-study-mm", "8", "6", "5",
        "--force-n", "30", "--out", str(report),
    ]) == 2
    assert step.exists()
    result = json.loads(report.read_text())
    assert result["status"] == "inconclusive_mecha_fastener_bearing"
    assert result["bearing_study"]["fabrication_authorized"] is False


@pytest.mark.parametrize("centers,diameter,thickness,force", [
    (((10., 10.),), 3.2, 4., 30.),
    (((50., 10.), (10., 10.)), 3.2, 4., 30.),
    (((10., 10.), (11., 10.)), 3.2, 4., 30.),
    (((10., 10.), (50., 10.)), -1., 4., 30.),
    (((10., 10.), (50., 10.)), 3.2, 4., 0.),
    (((10., 10.), (50., 10.)), 3.2, math.nan, 30.),
])
def test_invalid_bearing_spec_rejected(centers, diameter, thickness, force):
    with pytest.raises(ValueError):
        _validate_inputs(
            centers, diameter, thickness, force,
            youngs_pa=2e9, poisson=.25, neighborhood_mm=3.,
        )


@pytest.mark.parametrize("sizes", [
    [8, 6], [8, 6, 6], [6, 8, 5], [8, math.nan, 5]
])
def test_invalid_bearing_series_stops_before_mesh(sizes):
    with pytest.raises(ValueError, match="3–4 decreasing mesh"):
        _study("/tmp/nonexistent.step", mesh_targets_mm=sizes)


def test_restrictive_per_hole_tolerance_never_authorizes_bad_case(bearing_series):
    r = bearing_series
    assert any(
        not hole["peak_tolerance_met"]
        for comp in r["adjacent_comparisons"]
        for hole in comp["holes"]
    )
    assert r["structural_safety_verified"] is False
    assert r["release_authorized"] is False

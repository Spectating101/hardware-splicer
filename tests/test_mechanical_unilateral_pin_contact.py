"""Unilateral bore-pin contact: Signorini-like penalty law, activation and gates."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

from hardware_splicer.mechanical_unilateral_pin_contact import (
    _input_checks,
    analytic_unilateral_spring,
    solve_pin_to_bore_contact,
    run_pin_contact_mesh_series,
    run_penalty_stiffness_sensitivity,
)


@pytest.fixture(scope="module")
def mecha_pin_spec():
    pytest.importorskip("gmsh")
    pytest.importorskip("skfem")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "apps" / "mecha-splicer" / "src"))
    from mecha_splicer.templates.mint_templates import spec_for_template
    return spec_for_template("simple_plate_bracket")["bracket"]


@pytest.fixture(scope="module")
def pin_step(mecha_pin_spec, tmp_path_factory):
    from hardware_splicer.mechanical_bracket_screening import (
        generate_bracket_reference_step,
    )
    root = tmp_path_factory.mktemp("unilateral-pin")
    dest = root / "actual-mecha-two-hole-plate.step"
    export = generate_bracket_reference_step(mecha_pin_spec, dest)
    assert export["step_sha256"].startswith("sha256:")
    return dest


def case(path, **kwargs):
    values = {
        "mesh_target_mm": 8,
        "centers_xy_mm": ((10., 10.), (50., 10.)),
        "hole_d_mm": 3.2,
        "thickness_mm": 4.,
        "drive_mm": .02,
        "clearance_mm": .005,
        "penalty_pa_per_m": 5e11,
        "youngs_pa": 2e9,
        "poisson": .25,
    }
    values.update(kwargs)
    return solve_pin_to_bore_contact(path, **values)


def series(path, **kwargs):
    values = {
        "mesh_sizes_mm": (8, 6, 5),
        "centers_xy_mm": ((10., 10.), (50., 10.)),
        "hole_d_mm": 3.2,
        "thickness_mm": 4.,
        "drive_mm": .02,
        "clearance_mm": .005,
        "penalty_pa_per_m": 5e11,
        "youngs_pa": 2e9,
        "poisson": .25,
    }
    values.update(kwargs)
    return run_pin_contact_mesh_series(path, **values)


def test_exact_one_dimensional_unilateral_spring_reference():
    a = analytic_unilateral_spring(
        stiffness_n_per_m=1e6,
        contact_penalty_n_per_m=3e6,
        pin_drive_m=0,
        clearance_m=.0001,
    )
    assert a["reaction_force_n"] == 0
    assert a["displacement_m"] == 0
    assert a["contact_active"] is False

    b = analytic_unilateral_spring(
        stiffness_n_per_m=1e6,
        contact_penalty_n_per_m=3e6,
        pin_drive_m=.0005,
        clearance_m=.0001,
    )
    assert b["displacement_m"] == pytest.approx(.0003)
    assert b["reaction_force_n"] == pytest.approx(300.)
    assert b["penetration_m"] == pytest.approx(.0001)
    assert b["contact_active"] is True


def test_unilateral_zero_drive_cannot_pull_on_pin(pin_step):
    report = case(pin_step, drive_mm=0)
    assert report["status"] == "unilateral_penalty_contact_screen_only"
    assert report["active_contact_qp_count"] == 0
    assert report["active_contact_area_m2"] == 0
    assert report["peak_compressive_contact_pressure_pa"] == 0
    assert report["max_regularized_penetration_mm"] == 0
    assert report["pin_to_bore_resultant_n"] == pytest.approx([0, 0, 0], abs=1e-9)
    assert all(item["peak_von_mises_pa"] == pytest.approx(0., abs=1e-7)
               for item in report["per_hole_stress"])
    assert report["fabrication_authorized"] is False


def test_less_drive_than_clearance_cannot_activate_contact(pin_step):
    report = case(pin_step, drive_mm=.004, clearance_mm=.005)
    assert report["active_contact_qp_count"] == 0
    assert report["peak_compressive_contact_pressure_pa"] == 0
    assert report["pin_to_bore_resultant_n"] == pytest.approx([0, 0, 0], abs=1e-9)


def test_active_set_pressure_response_increases_with_drive(pin_step):
    small = case(pin_step, drive_mm=.02)
    large = case(pin_step, drive_mm=.05)
    assert small["active_contact_qp_count"] > 0
    assert large["active_contact_qp_count"] >= small["active_contact_qp_count"]
    assert large["active_contact_area_m2"] >= small["active_contact_area_m2"]
    assert large["pin_to_bore_resultant_n"][0] > small["pin_to_bore_resultant_n"][0]
    assert 19 < small["pin_to_bore_resultant_n"][0] < 25
    assert 60 < large["pin_to_bore_resultant_n"][0] < 80
    assert 0 < small["max_regularized_penetration_mm"] < .02
    assert small["contact_iteration_count"] >= 2
    assert small["global_reaction_balance_error_n"] < 1e-5
    assert small["free_dof_force_residual_n"] < 1e-5
    assert small["simplified_anchor_reaction_n"] == pytest.approx(
        [-x for x in small["pin_to_bore_resultant_n"]],
        abs=1e-5,
    )
    assert abs(small["pin_to_bore_resultant_n"][1]) < .05 * (
        small["pin_to_bore_resultant_n"][0]
    )
    assert small["full_nonlinear_contact_verified"] is False
    assert small["true_anchor_bolt_contact_validated"] is False
    assert small["fabrication_authorized"] is False


@pytest.fixture(scope="module")
def pin_series(pin_step):
    return series(pin_step)


def test_pin_pressure_series_evidence_is_numerically_stable_not_physical(pin_series):
    assert pin_series["status"] == "numerically_stable_unilateral_contact_screen"
    assert pin_series["blockers"] == []
    levels = pin_series["levels"]
    assert len(levels) == 3
    forces = [x["pin_to_bore_resultant_n"][0] for x in levels]
    assert max(forces) / min(forces) < 1.03
    assert levels[0]["quadratic_dof_count"] < levels[1]["quadratic_dof_count"]
    assert levels[1]["quadratic_dof_count"] < levels[2]["quadratic_dof_count"]
    assert all(2 <= x["contact_iteration_count"] <= 20 for x in levels)
    assert all(x["active_contact_qp_count"] > 0 for x in levels)
    assert all(len(x["per_hole_stress"]) == 2 for x in levels)
    assert all(x["global_reaction_balance_error_n"] < 1e-5 for x in levels)
    assert pin_series["full_assembly_contact_verified"] is False
    assert pin_series["structural_safety_verified"] is False
    assert pin_series["fabrication_authorized"] is False
    assert pin_series["release_authorized"] is False


def test_stricter_stress_tolerance_flags_hole_hotspots(pin_step):
    report = series(
        pin_step,
        peak_stress_relative_tolerance=.02,
        rms_stress_relative_tolerance=.01,
    )
    assert report["status"] == "inconclusive_unilateral_contact_refinement"
    assert report["blockers"]
    assert any("peak_contact_stress_unstable" in x for x in report["blockers"])
    assert report["fabrication_authorized"] is False


def test_active_set_iteration_budget_blocks_nonconvergence(pin_step):
    with pytest.raises(ValueError, match="active set did not converge"):
        case(pin_step, max_iterations=2)


@pytest.mark.parametrize("override", [
    {"drive_mm": -.001},
    {"drive_mm": math.nan},
    {"clearance_mm": -.01},
    {"clearance_mm": .5},
    {"penalty_pa_per_m": 0.},
    {"penalty_pa_per_m": math.inf},
    {"mesh_target_mm": 0.},
    {"hole_d_mm": 0.},
])
def test_bounded_invalid_pin_inputs_rejected_before_meshing(override):
    kwargs = dict(
        centers_xy_mm=((10., 10.), (50., 10.)),
        hole_d_mm=3.2, thickness_mm=4.,
        drive_mm=.02, clearance_mm=.005,
        penalty_pa_per_m=5e11, youngs_pa=2e9, poisson=.25,
        mesh_target_mm=8,
    )
    kwargs.update(override)
    with pytest.raises(ValueError):
        _input_checks(**kwargs)


@pytest.mark.parametrize("sizes", [
    (8, 6), (8, 6, 6), (8, 9, 5), (8, math.nan, 5),
])
def test_invalid_pin_mesh_series_rejected_early(sizes):
    with pytest.raises(ValueError, match="3–4 finite strictly decreasing"):
        series("/tmp/should-not-exist.step", mesh_sizes_mm=sizes)


def test_mecha_spec_cli_emits_provenanced_json(mecha_pin_spec, tmp_path):
    from hardware_splicer.mechanical_unilateral_pin_contact import main
    spec = tmp_path / "mecha_bracket.json"
    spec.write_text(json.dumps({"bracket": mecha_pin_spec}), encoding="utf-8")
    step = tmp_path / "plate.step"
    report = tmp_path / "pin-contact.json"
    rc = main([
        "--spec-json", str(spec), "--step-out", str(step),
        "--mesh-study-mm", "8", "6", "5",
        "--drive-mm", ".02", "--clearance-mm", ".005",
        "--out", str(report),
    ])
    assert rc == 2
    assert step.exists()
    data = json.loads(report.read_text())
    assert data["status"] == "inconclusive_joint_contact_screening"
    assert data["mesh_sensitivity"]["status"] == "numerically_stable_unilateral_contact_screen"
    assert data["penalty_sensitivity"]["status"] == "inconclusive_penalty_parameter_dependence"
    assert "contact_force_sensitive_to_penalty_stiffness" in data["blockers"]
    assert data["source_spec_sha256"].startswith("sha256:")
    assert data["generated_step_provenance"]["step_sha256"].startswith("sha256:")
    assert data["true_pin_joint_strength_verified"] is False
    assert data["release_authorized"] is False


def test_contact_penalty_dependence_is_detected(pin_step):
    report = run_penalty_stiffness_sensitivity(
        pin_step, mesh_target_mm=8,
        centers_xy_mm=((10., 10.), (50., 10.)),
        hole_d_mm=3.2, thickness_mm=4.,
        drive_mm=.02, clearance_mm=.005,
        baseline_penalty_pa_per_m=5e11,
    )
    assert report["status"] == "inconclusive_penalty_parameter_dependence"
    assert "contact_force_sensitive_to_penalty_stiffness" in report["blockers"]
    values = [x["contact_force_x_n"] for x in report["levels"]]
    assert values[0] < values[1] < values[2]
    assert values[0] == pytest.approx(9.54, rel=.03)
    assert values[1] == pytest.approx(21.44, rel=.03)
    assert values[2] == pytest.approx(25.40, rel=.03)
    assert report["penalty_independence_mathematically_proven"] is False
    assert report["fabrication_authorized"] is False


@pytest.mark.parametrize("bad_tolerance", [0, math.nan, .5])
def test_sensitivity_threshold_input_fails_closed(bad_tolerance):
    with pytest.raises(ValueError, match="peak_stress_relative_tolerance"):
        series(
            "/tmp/should-not-exist.step",
            peak_stress_relative_tolerance=bad_tolerance,
        )

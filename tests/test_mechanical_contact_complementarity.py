"""Contact complementarity numerical benchmark and real two-bore screening."""

from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import pytest
from hardware_splicer.mechanical_contact_complementarity import (
    benchmark_contact_spring,
    solve_contact_quadratic_program,
)
from hardware_splicer.mechanical_two_pin_contact import solve_two_pin_contact
from hardware_splicer.mechanical_contact_validation import audit_two_pin_contact


@pytest.mark.parametrize("drive,expected_n", [
    (0., 0.), (.05, 0.), (.1, 0.), (.5, 400.),
])
def test_spring_analytical_nonadhesive_contact(drive, expected_n):
    r=benchmark_contact_spring(pin_drive_mm=drive)
    assert r["status"]=="analytical_unilateral_spring_pass"
    assert r["actual_compressive_force_n"]==pytest.approx(expected_n,abs=1e-9)
    assert r["nodal_gap_m"] >= -1e-10
    assert r["fabrication_authorized"] is False


def test_active_selector_does_not_affect_exact_spring_reaction():
    reactions=[
        benchmark_contact_spring(
            pin_drive_mm=.5,
            activation_stiffness_n_m=k,
        )["actual_compressive_force_n"]
        for k in [1e6,1e7,1e9]
    ]
    assert reactions==pytest.approx([400.,400.,400.],abs=1e-10)


def test_two_dimensional_independent_complementarity():
    import numpy as np
    from scipy import sparse
    K=sparse.csr_matrix([[4e6,0.],[0.,2e6]])
    C=sparse.eye(2,format="csr")
    q=np.array([.0001,-.0001])
    r=solve_contact_quadratic_program(K,C,q)
    assert r["nodal_displacement_m"]==pytest.approx([.0001,0.],abs=1e-12)
    assert r["contact_lambda_n"]==pytest.approx([400.,0.],abs=1e-7)
    assert r["max_negative_gap_m"]<1e-10
    assert r["min_contact_lambda_n"]>=-1e-9
    assert r["max_complementarity_n_m"]<1e-8
    assert r["penalty_stiffness_used_in_physics"] is False


@pytest.mark.parametrize("bad", [math.nan,-1])
def test_unsafe_active_selection_rejected(bad):
    import numpy as np
    from scipy import sparse
    with pytest.raises(ValueError,match="selection parameter"):
        solve_contact_quadratic_program(
            sparse.eye(1),sparse.eye(1),np.array([1e-3]),
            activation_stiffness_n_m=bad,
        )


def test_contact_rank_deficiency_explicitly_rejected():
    import numpy as np
    from scipy import sparse
    with pytest.raises(ValueError,match="rank deficient"):
        solve_contact_quadratic_program(
            sparse.csc_matrix((2,2)),
            sparse.csr_matrix([[1.,0.]]),
            np.array([.01]),
        )


@pytest.fixture(scope="module")
def mecha_spec():
    pytest.importorskip("gmsh")
    pytest.importorskip("skfem")
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/"apps"/"mecha-splicer"/"src"))
    from mecha_splicer.templates.mint_templates import spec_for_template
    return spec_for_template("simple_plate_bracket")["bracket"]


@pytest.fixture(scope="module")
def bracket_step(mecha_spec,tmp_path_factory):
    from hardware_splicer.mechanical_bracket_screening import (
        generate_bracket_reference_step,
    )
    root=tmp_path_factory.mktemp("kkt-two-pin")
    path=root/"actual-mecha-bracket.step"
    evidence=generate_bracket_reference_step(mecha_spec,path)
    assert evidence["step_sha256"].startswith("sha256:")
    return path


def solve_bracket(step,**kw):
    params=dict(
        mesh_target_mm=8,
        centers_xy_mm=((10.,10.),(50.,10.)),
        hole_d_mm=3.2,
        thickness_mm=4.,
        right_pin_drive_mm=.02,
        radial_clearance_mm=.005,
        numerical_gauge_n_per_m=.01,
    )
    params.update(kw)
    return solve_two_pin_contact(step,**params)


def test_genuinely_two_unilateral_pin_surfaces_equilibrate(bracket_step):
    r=solve_bracket(bracket_step)
    assert r["status"]=="nodal_two_pin_complementarity_screen_only"
    assert r["both_pin_surfaces_use_unilateral_constraints"] is True
    assert r["penalty_stiffness_used_in_physics"] is False
    assert r["quadratic_dof_count"]>1000
    assert all(x["active_contact_node_count"]>=8 for x in r["per_pin"])
    fa=r["per_pin"][0]["integrated_nodal_contact_resultant_n"]
    fb=r["per_pin"][1]["integrated_nodal_contact_resultant_n"]
    assert fa[0]==pytest.approx(-fb[0],rel=.0001)
    assert fb[0]==pytest.approx(16.22,rel=.04)
    assert r["nodal_max_gap_violation_m"]<5e-10
    assert r["min_contact_multiplier_n"]>=-1e-7
    assert r["max_complementarity_n_m"]<1e-8
    assert r["relative_gauge_reaction"]<1e-4
    assert r["physical_validation_required"] is True
    assert r["fabrication_authorized"] is False
    assert r["release_authorized"] is False


def test_two_pin_zero_motion_does_not_generate_contact(bracket_step):
    r=solve_bracket(bracket_step,right_pin_drive_mm=0)
    assert all(
        x["active_contact_node_count"]==0 for x in r["per_pin"]
    )
    assert r["transmitted_force_scale_n"]==pytest.approx(0,abs=1e-8)
    assert r["global_peak_sampled_von_mises_pa"]==pytest.approx(0,abs=1e-6)


def test_two_pin_active_set_selection_independence(bracket_step):
    forces=[
        solve_bracket(
            bracket_step,active_selection_n_per_m=k
        )["transmitted_force_scale_n"]
        for k in [1e6,1e7,1e8]
    ]
    assert max(forces)-min(forces)<1e-5


@pytest.fixture(scope="module")
def refined_study(bracket_step):
    return audit_two_pin_contact(
        bracket_step,
        mesh_sizes_mm=(8,6,5),
        centers_xy_mm=((10.,10.),(50.,10.)),
        hole_d_mm=3.2,thickness_mm=4,
        right_pin_drive_mm=.02,radial_clearance_mm=.005,
    )


def test_two_pin_audit_detects_stress_instability(refined_study):
    r=refined_study
    assert r["status"]=="inconclusive_two_pin_contact_stress"
    assert r["blockers"]==[
        "hole_0_peak_stress_not_converged",
        "hole_1_peak_stress_not_converged",
    ]
    assert len(r["mesh_levels"])==3
    assert all(
        x["transmitted_force_scale_n"]>15 for x in r["mesh_levels"]
    )
    assert max(x["transmitted_force_scale_n"] for x in r["mesh_levels"]) / min(
        x["transmitted_force_scale_n"] for x in r["mesh_levels"]
    ) < 1.03
    assert all(
        item["nodal_max_gap_violation_m"]<5e-10
        for item in r["mesh_levels"]
    )
    assert r["nodal_contact_penalty_parameter_needed"] is False
    assert r["continuous_contact_surface_verified"] is False
    assert r["structural_safety_verified"] is False
    assert r["fabrication_authorized"] is False


def test_rigid_gauge_small_and_parameter_insensitive(refined_study):
    r=refined_study
    assert max(x["relative_gauge_reaction"] for x in r[
        "numerical_gauge_sensitivity"
    ])<.001
    vals=[x["transmitted_force_n"] for x in r[
        "numerical_gauge_sensitivity"
    ]]
    assert max(vals)/min(vals) < 1.005
    vals=[x["transmitted_force_n"] for x in r[
        "active_set_selection_sensitivity"
    ]]
    assert max(vals)-min(vals)<.0001
    assert r["release_authorized"] is False


@pytest.mark.parametrize("bad_sizes",[
    (8,6),(8,8,5),(6,8,5),(8,6,math.nan)
])
def test_invalid_mesh_schedule_rejected_without_loading_cad(bad_sizes):
    with pytest.raises(ValueError,match="strictly decreasing"):
        audit_two_pin_contact(
            "/tmp/nonexistent.step",mesh_sizes_mm=bad_sizes
        )


def test_cli_preserves_inconclusive_evidence(mecha_spec,tmp_path):
    from hardware_splicer.mechanical_contact_validation import main
    spec=tmp_path/"spec.json"
    spec.write_text(json.dumps({"bracket":mecha_spec}),encoding="utf-8")
    step=tmp_path/"bracket.step"
    report=tmp_path/"contact_report.json"
    rc=main([
        "--spec-json",str(spec),
        "--step-out",str(step),
        "--mesh-study-mm","8","6","5",
        "--drive-mm",".02",
        "--clearance-mm",".005",
        "--out",str(report),
    ])
    assert rc==2
    assert step.exists()
    data=json.loads(report.read_text())
    assert data["status"]=="inconclusive_two_pin_contact_stress"
    assert "hole_0_peak_stress_not_converged" in data["blockers"]
    assert data["source_spec_sha256"].startswith("sha256:")
    assert data["generated_step_provenance"]["step_sha256"].startswith("sha256:")
    assert data["fabrication_authorized"] is False

"""HS structural screening is routed into actual Mecha, planning and authority."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.mechanical_workflow_integration import (
    screen_mecha_project,
    structural_capability_for_design,
)
from hardware_splicer.mechanical_authority import build_mechanical_authority


BRACKET = {
    "name": "plate", "w_mm": 60, "d_mm": 20, "t_mm": 4,
    "hole_d_mm": 3.2, "hole_spacing_mm": 40,
}


def test_bracket_advisory_has_real_capability_and_no_fictitious_screen():
    candidate = structural_capability_for_design({"bracket": BRACKET})
    assert candidate["status"] == "available_not_run"
    assert candidate["supported_for_contact"] is True
    assert candidate["dimensions_mm"]["hole_d_mm"] == 3.2
    assert candidate["bracket_spec_sha256"].startswith("sha256:")
    assert "contact_fem_not_executed_for_this_design" in candidate["blockers"]
    assert candidate["fabrication_authorized"] is False
    assert candidate["release_authorized"] is False


def test_unsupported_geometry_does_not_sneak_into_contact_solver():
    bad = {**BRACKET, "hole_spacing_mm": 100}
    report = structural_capability_for_design({"bracket": bad})
    assert report["status"] == "unsupported_bracket_geometry"
    assert report["supported_for_contact"] is False
    assert report["release_authorized"] is False


def test_other_mechanics_remain_explicitly_unsupported():
    report = structural_capability_for_design({
        "enclosure": {"inner_w_mm": 40, "inner_d_mm": 20},
        "pan_tilt": {"pan_servo": "sg90"},
    })
    assert report["status"] == "unsupported_mechanical_topology"
    assert report["fabrication_authorized"] is False
    empty = structural_capability_for_design({})
    assert empty["status"] == "not_applicable"


def test_off_is_not_a_fake_positive_gate(tmp_path):
    report = screen_mecha_project({"bracket": BRACKET}, out_dir=tmp_path, mode="off")
    assert report["status"] == "disabled_by_request"
    assert report["release_authorized"] is False
    assert list(tmp_path.iterdir()) == []


def test_run_requires_explicit_destination():
    with pytest.raises(ValueError, match="explicit run requires"):
        screen_mecha_project({"bracket": BRACKET}, out_dir=None, mode="run")
    with pytest.raises(ValueError, match="mode"):
        screen_mecha_project({"bracket": BRACKET}, out_dir=".", mode="certified")


def test_failed_solver_fails_closed_and_keeps_source(tmp_path, monkeypatch):
    import hardware_splicer.mechanical_contact_workbench as workbench

    def cannot_solve(**_kw):
        raise ValueError("curved Jacobian not positive")
    monkeypatch.setattr(workbench, "run_contact_workbench", cannot_solve)
    report = screen_mecha_project({"bracket": BRACKET}, out_dir=tmp_path, mode="run")
    assert report["status"] == "solver_blocked"
    assert report["fabrication_authorized"] is False
    assert report["release_authorized"] is False
    assert "structural_contact_solver_failed_or_unavailable" in report["blockers"]
    assert json.loads((tmp_path / "STRUCTURAL_SPEC.json").read_text())["bracket"]["name"] == "plate"


def test_mecha_build_publishes_structural_advisory_in_normal_files(tmp_path):
    from mecha_splicer.runner import run
    spec = {
        "project_name": "hs-mechanical-end-to-end",
        "mode": "prototype",
        "process": "fdm",
        "bracket": BRACKET,
    }
    bundle = run(spec, out_dir=tmp_path)
    structural = bundle["structural_screening"]
    assert structural["status"] == "available_not_run"
    assert bundle["structural_release_blocked"] is True
    assert "structural_screening" in json.loads(
        (tmp_path / "mecha_splicer.bundle.json").read_text()
    )
    sim = json.loads((tmp_path / "SIM_RESULTS.json").read_text())
    assert sim["structural_screening"]["status"] == "available_not_run"
    assert sim["structural_release_blocked"] is True
    assert "contact_fem_not_executed_for_this_design" in (
        tmp_path / "RISK_REGISTER.md"
    ).read_text()
    assert "Structural FEM" in (tmp_path / "MECH_CHECK.md").read_text()
    assert "Structural contact analysis" in (tmp_path / "BUILD_RECIPE.md").read_text()
    assert not (tmp_path / "STRUCTURAL_SCREENING").exists()


def test_mecha_enclosure_does_not_claim_bracket_contact_support(tmp_path):
    from mecha_splicer.runner import run
    spec = {
        "project_name": "enclosure-only",
        "enclosure": {
            "name": "box", "inner_w_mm": 60,
            "inner_d_mm": 40, "inner_h_mm": 20,
        },
    }
    bundle = run(spec, out_dir=tmp_path)
    assert bundle["structural_screening"]["status"] == "unsupported_mechanical_topology"
    assert bundle["structural_release_blocked"] is True
    assert "no_validated_contact_case" in (tmp_path / "RISK_REGISTER.md").read_text()


def test_mecha_runner_run_mode_requires_real_output_directory():
    from mecha_splicer.runner import run
    with pytest.raises(ValueError, match="requires out_dir"):
        run({"project_name": "invalid", "bracket": BRACKET},
            structural_screening="run")


def _closed_authority_inputs():
    spec = {
        "mechanism": {"pan_tilt": {"name": "pt"}},
        "mechanical_measurement_capture": {
            "geometry_verified": True,
        },
        "mechanical_bench_capture": {
            "bench_verified": True,
        },
        "mechanical_release": {
            "scope_statement": "Reviewed fixture only",
            "acceptance_reviewed": True,
            "artifact_uris": ["test://fixture"],
        },
    }
    eng = {
        "analysis": {
            "mechanism": {
                "outputs": ["pt_base.scad"],
                "simulation": [{"status": "pass", "severity": "info",
                                "message": "Nominal torque estimate"}],
            }
        }
    }
    return spec, eng


def test_structural_review_caps_production_mechanical_authority():
    spec, eng = _closed_authority_inputs()
    original = build_mechanical_authority(spec, engineering=eng)
    assert original["production_authorized"] is True
    eng["analysis"]["mechanism"]["structural_screening"] = {
        "schema_version": "hardware_splicer.mechanical_workflow_bridge.v1",
        "status": "screened_inconclusive",
        "blockers": ["hole_0_peak_stress_not_converged"],
        "fabrication_authorized": False,
        "release_authorized": False,
    }
    guarded = build_mechanical_authority(spec, engineering=eng)
    assert guarded["structural_release_blocked"] is True
    assert guarded["production_authorized"] is False
    assert guarded["current_authority_level"] != "production_mechanical_release"
    release_stage = guarded["stages"][-1]
    assert release_stage["stage_id"] == "production_mechanical_release"
    assert release_stage["status"] == "open"
    assert "hole_0_peak_stress_not_converged" in release_stage["blockers"]


def test_mechanism_bridge_returns_structural_scope(tmp_path):
    from hardware_splicer.mechanism_bridge import (
        run_mechanism_pack, write_mechanism_pack_artifacts,
    )
    pack = run_mechanism_pack(
        project_name="board enclosure", build_id="sensor_logger",
        out_dir=tmp_path,
    )
    assert pack["status"] == "ok"
    assert "structural_screening" in pack
    assert pack["structural_screening"]["status"] == "unsupported_mechanical_topology"
    write_mechanism_pack_artifacts(pack, tmp_path)
    summary = json.loads((tmp_path / "MECHATRONICS_PACK.json").read_text())
    assert summary["structural_screening"]["status"] == "unsupported_mechanical_topology"
    assert summary["structural_release_blocked"] is True


def test_capability_discovery_lists_opt_in_mechanical_stack():
    from hardware_splicer.capability_runtime import capability_report
    report = capability_report()
    rows = [x for x in report["capabilities"]
            if x["id"] == "curved-mechanical-contact-fem"]
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "opt_in"
    assert row["required"] is False
    assert row["python_modules"] == ["gmsh", "skfem", "numpy", "scipy"]
    assert row["claim"].lower().find("certification") >= 0


def test_console_entrypoint_is_provided():
    from pathlib import Path
    import tomllib
    repo = Path(__file__).resolve().parents[1]
    config = tomllib.loads((repo / "pyproject.toml").read_text())
    assert config["project"]["scripts"]["hs-mechanical"] == (
        "hardware_splicer.cli_entry:main_mechanical"
    )



def test_disabling_structural_analysis_cannot_promote_mechanical_release():
    spec, eng = _closed_authority_inputs()
    eng["analysis"]["mechanism"]["structural_screening"] = {
        "schema_version": "hardware_splicer.mechanical_workflow_bridge.v1",
        "status": "disabled_by_request",
        "release_authorized": False,
    }
    result = build_mechanical_authority(spec, engineering=eng)
    assert result["structural_release_blocked"] is True
    assert result["production_authorized"] is False


def test_real_mecha_runner_with_opt_in_solver_packages_review(tmp_path):
    pytest.importorskip("gmsh")
    pytest.importorskip("skfem")
    from mecha_splicer.runner import run
    bundle = run(
        {"project_name": "actual-bracket", "bracket": BRACKET},
        out_dir=tmp_path, structural_screening="run",
        structural_mesh_sizes_mm=(8.,6.,5.),
        structural_pin_drive_mm=.02,
        structural_radial_clearance_mm=.005,
    )
    structural = bundle["structural_screening"]
    assert structural["status"] == "screened_inconclusive"
    assert structural["numerical_complementarity_checked"] is True
    assert structural["computed_force_n"][0] > 15
    assert "hole_0_contact_surface_resolution_not_refined" in structural["blockers"]
    paths = structural["artifacts"]
    assert Path(paths["review_html"]).exists()
    assert Path(paths["evidence_json"]).exists()
    assert Path(paths["predicted_load_curve_csv"]).exists()
    assert "hole_0_peak_stress_not_converged" in (
        tmp_path / "RISK_REGISTER.md"
    ).read_text()
    assert json.loads((tmp_path / "SIM_RESULTS.json").read_text())[
        "structural_screening"
    ]["status"] == "screened_inconclusive"
    assert json.loads((tmp_path / "mecha_splicer.bundle.json").read_text())[
        "structural_release_blocked"
    ] is True
    assert structural["fabrication_authorized"] is False

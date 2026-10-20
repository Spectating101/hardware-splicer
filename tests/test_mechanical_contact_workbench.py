"""Operator workflow and physical evidence inventory — never authorizes release."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from hardware_splicer.mechanical_contact_workbench import (
    TRIAL_FIELDS,
    read_physical_trials,
    make_operator_review,
    render_html_report,
    run_contact_workbench,
)


def write_trials(path, specimens):
    with path.open("w", newline="", encoding="utf-8") as handle:
        w = csv.DictWriter(handle, fieldnames=TRIAL_FIELDS)
        w.writeheader()
        w.writerows(specimens)


def specimens_example():
    result = []
    for name in ("flat", "on_edge"):
        for i in range(3):
            result.append({
                "specimen_id": f"{name}-{i}",
                "print_orientation": name,
                "material_batch": "PETG-fake-for-test",
                "fixture_protocol_id": "TEST-PROTOCOL",
                "measured_bore_d_mm": 3.21,
                "measured_pin_d_mm": 3.20,
                "maximum_force_n": 17+i,
                "displacement_at_maximum_mm": 0.15+i*.02,
                "failure_mode": "hole_bearing",
            })
    return result


def test_specimen_data_schema_and_statistics(tmp_path):
    p = tmp_path / "synthetic_traces.csv"
    write_trials(p, specimens_example())
    r = read_physical_trials(p)
    assert r["specimen_count"] == 6
    assert r["minimum_trial_evidence_gate_met"] is True
    assert r["evidence_completeness_blockers"] == []
    assert len(r["orientations"]) == 2
    assert all(x["specimen_count"] == 3 for x in r["orientations"])
    assert all(x["radial_clearance_mm_median"] == pytest.approx(.005)
               for x in r["orientations"])
    assert r["engineering_strength_signoff_present"] is False
    assert r["model_vs_physical_predictions_validated"] is False
    assert r["fabrication_authorized"] is False


def test_insufficient_physical_sample_is_not_signed_off(tmp_path):
    p = tmp_path / "incomplete.csv"
    write_trials(p, specimens_example()[:2])
    r = read_physical_trials(p)
    assert not r["minimum_trial_evidence_gate_met"]
    assert "less_than_two_print_orientations" in r[
        "evidence_completeness_blockers"
    ]
    assert "fewer_than_three_specimens_per_orientation" in r[
        "evidence_completeness_blockers"
    ]


@pytest.mark.parametrize("bad_change", [
    {"specimen_id": "flat-1"},
    {"measured_bore_d_mm": "NaN"},
    {"measured_pin_d_mm": "3.4"},
    {"maximum_force_n": -1},
    {"failure_mode": "no confirmed testing"},
    {"print_orientation": ""},
])
def test_invalid_physical_rows_refused(tmp_path, bad_change):
    p = tmp_path / "invalid.csv"
    rows = specimens_example()
    rows[0] = {**rows[0], **bad_change}
    write_trials(p, rows)
    with pytest.raises(ValueError):
        read_physical_trials(p)


def test_malicious_trial_metadata_escaped_in_html(tmp_path):
    p = tmp_path / "trials.csv"
    rows = specimens_example()
    for row in rows:
        row["material_batch"] = "<script>alert('bad')</script>"
    write_trials(p, rows)
    physical = read_physical_trials(p)
    audit = {
        "status": "inconclusive_two_pin_contact_stress",
        "blockers": ["hole_0_peak_stress_not_converged"],
        "mesh_levels": [{
            "mesh_target_mm": 8,
            "transmitted_force_scale_n": 16.2,
            "global_peak_sampled_von_mises_pa": 4e6,
            "clearance_mm": .005,
            "nodal_max_gap_violation_m": 0.,
            "relative_gauge_reaction": 1e-5,
            "per_hole_stress": [{
                "hole_index": 0,
                "weighted_rms_von_mises_pa": 5e5,
            }],
        }],
        "generated_step_provenance": {},
        "source_step_sha256": "sha256:<img onerror=alert(1)>",
    }
    report = {
        "contact_audit": audit,
        "physical_trials": physical,
        "source_spec_sha256": "sha256:<script>alert(1)</script>",
        "operator_review": make_operator_review(audit, physical),
    }
    html = render_html_report(report)
    assert "<script>alert(1)</script>" not in html
    assert "<img onerror=alert(1)>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img" in html
    assert "default-src 'none'" in html


def test_operator_review_does_not_certify_complete_trial_csv(tmp_path):
    p = tmp_path / "complete_synthetic.csv"
    write_trials(p, specimens_example())
    data = read_physical_trials(p)
    audit = {
        "status": "inconclusive_two_pin_contact_stress",
        "blockers": ["hole_0_peak_stress_not_converged"],
        "generated_step_provenance": {},
        "mesh_levels": [{
            "clearance_mm": .005,
            "nodal_max_gap_violation_m": 0.,
            "relative_gauge_reaction": 1e-6,
        }],
    }
    r = make_operator_review(audit, data)
    assert r["physical_record_inventory_complete"] is True
    assert r["ready_to_issue_strength_rating"] is False
    assert r["ready_for_load_bearing_fabrication"] is False
    assert "measured_clearance_differs_from_fem_assumption" not in r["primary_blockers"]
    assert r["release_authorized"] is False


def test_measured_clearance_mismatch_is_blocked(tmp_path):
    p = tmp_path / "wide_fit.csv"
    rows = specimens_example()
    for row in rows:
        row["measured_bore_d_mm"] = 3.28
    write_trials(p, rows)
    physical = read_physical_trials(p)
    audit = {
        "status": "inconclusive_two_pin_contact_stress",
        "blockers": [],
        "generated_step_provenance": {},
        "mesh_levels": [{
            "clearance_mm": .005,
            "nodal_max_gap_violation_m": 0.,
            "relative_gauge_reaction": 1e-6,
        }],
    }
    review = make_operator_review(audit, physical)
    assert "measured_clearance_differs_from_fem_assumption" in review[
        "primary_blockers"
    ]


@pytest.fixture(scope="module")
def mecha_spec_file(tmp_path_factory):
    gmsh = pytest.importorskip("gmsh")
    pytest.importorskip("skfem")
    root = tmp_path_factory.mktemp("workbench-spec")
    path = root / "spec.json"
    path.write_text(json.dumps({
        "bracket": {
            "name":"plate","w_mm":60,"d_mm":20,"t_mm":4,
            "hole_d_mm":3.2,"hole_spacing_mm":40,
        }
    }))
    return path


def test_one_command_produces_auditable_bundle(mecha_spec_file, tmp_path):
    output = tmp_path / "bracket-evidence"
    r = run_contact_workbench(
        spec_file=mecha_spec_file,
        outdir=output,
        mesh_sizes_mm=(8,6,5),
    )
    assert r["schema_version"] == "hardware_splicer.contact_workbench_v1"
    assert r["contact_audit"]["status"] == "inconclusive_two_pin_contact_stress"
    assert len(r["contact_audit"]["mesh_levels"]) == 3
    assert "hole_0_contact_surface_resolution_not_refined" in r[
        "contact_audit"]["blockers"]
    assert "hole_1_contact_surface_resolution_not_refined" in r[
        "contact_audit"]["blockers"]
    assert all(
        len(x["between_node_surface_gap_probes"]) == 2
        for x in r["contact_audit"]["mesh_levels"]
    )
    assert all(
        max(p["largest_sampled_between_node_penetration_m"]
            for p in x["between_node_surface_gap_probes"]) < 1e-7
        for x in r["contact_audit"]["mesh_levels"]
    )
    assert r["operator_review"]["ready_for_load_bearing_fabrication"] is False
    curve = r["simulated_pin_sweep"]
    assert curve["status"] == "bounded_numerical_contact_sweep_only"
    assert len(curve["levels"]) == 4
    assert curve["levels"][0]["force_transferred_n"] == pytest.approx(0)
    assert 15 <= curve["levels"][2]["force_transferred_n"] <= 17
    assert curve["levels"][3]["force_transferred_n"] > 50
    assert curve["physical_force_displacement_curve_measured"] is False
    assert r["fabrication_authorized"] is False
    assert set(p.name for p in output.iterdir()) == {
        "bracket.step", "evidence.json", "review.html", "remaining_actions.txt",
        "predicted_load_curve.csv",
    }
    assert "LOAD-BEARING RELEASE BLOCKED" in (
        output/"review.html").read_text()
    assert json.loads((output/"evidence.json").read_text())[
        "contact_audit"]["status"] == "inconclusive_two_pin_contact_stress"
    with pytest.raises(ValueError, match="must be empty"):
        run_contact_workbench(spec_file=mecha_spec_file, outdir=output)


def test_bad_mesh_inputs_refused_before_writing_artifacts(mecha_spec_file,tmp_path):
    output = tmp_path / "should-not-exist"
    with pytest.raises(ValueError, match="strictly decrease"):
        run_contact_workbench(
            spec_file=mecha_spec_file,outdir=output,mesh_sizes_mm=(8,8,6)
        )
    assert not output.exists()

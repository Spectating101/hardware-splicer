"""The CAD-to-FEM CLI must not exit successfully when its mesh-convergence gate fails."""

from __future__ import annotations

import json

import pytest

from hardware_splicer import mechanical_cad_convergence, mechanical_cad_fem

ARGS = ["part.step", "--fixed-plane", "x_min", "--loaded-plane", "x_max", "--force-n", "0", "0", "-10",
        "--youngs-pa", "2e9", "--poisson", "0.35", "--mesh-study-mm", "12", "8", "6"]


@pytest.mark.parametrize("blockers, code", [(["stress_changed_beyond_tolerance"], 2), ([], 0)])
def test_mesh_study_exit_code_follows_the_convergence_gate(tmp_path, monkeypatch, blockers, code):
    status = "inconclusive_refinement" if blockers else "numerically_stable_screening"
    monkeypatch.setattr(mechanical_cad_convergence, "run_cad_mesh_sensitivity",
                        lambda *a, **k: {"status": status, "sensitivity_blockers": blockers})
    out = tmp_path / "report.json"
    assert mechanical_cad_fem.main(ARGS + ["--out", str(out)]) == code
    assert json.loads(out.read_text())["status"] == status  # the report is saved either way

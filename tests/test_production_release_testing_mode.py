from __future__ import annotations

from hardware_splicer.production_release_metrics import build_production_release_metrics


def test_production_gates_relaxed_in_testing_mode(monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_TESTING_MODE", "1")
    metrics = build_production_release_metrics(
        result={"ok": True, "project_name": "bench"},
        project_authority={
            "project_authority_level": "control_safety_planning",
            "claimable": False,
            "authority_score": 0.5,
        },
    )
    assert metrics["gates_passed"] == metrics["gates_total"]
    assert all(row.get("testing_mode_relaxed") for row in metrics["weighted_gates"] if row["id"] != "compile_artifacts")

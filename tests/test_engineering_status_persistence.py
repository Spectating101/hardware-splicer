from __future__ import annotations

from hardware_splicer.engineering_plan_store import engineering_snapshot


def test_guided_snapshot_retains_status_manufacturing_and_execution_payloads() -> None:
    plan = {
        "schema_version": "hardware_splicer.guided_engineering_plan.v1",
        "machine_project": {
            "project_id": "persistent-status",
            "name": "Persistent status",
        },
        "engineering_context": {"normalized_mode": "modify"},
        "manufacturing_projection": {"projected_component_ids": ["mfg-connector-j1"]},
        "manufacturing_closure": {"status": "blocked", "checks": [{"check_id": "pin-conflict"}]},
        "engineering_execution_plan": {"checks": [{"execution_id": "exec-pytest"}]},
        "engineering_status": {
            "overall_status": "blocked",
            "current_phase": "manufacturing",
            "next_action_id": "next-manufacturing",
        },
        "operator_guide": {"steps": [{"step_id": "scope"}]},
        "ordered_steps": [{"step_id": "scope"}],
        "engineering_readiness": {
            "status": "blocked",
            "next_action_id": "next-manufacturing",
        },
    }

    snapshot = engineering_snapshot(plan)

    assert snapshot["manufacturingProjection"]["projected_component_ids"] == ["mfg-connector-j1"]
    assert snapshot["manufacturingClosure"]["status"] == "blocked"
    assert snapshot["engineeringExecutionPlan"]["checks"][0]["execution_id"] == "exec-pytest"
    assert snapshot["engineeringStatus"]["next_action_id"] == "next-manufacturing"
    assert snapshot["orderedSteps"][0]["step_id"] == "scope"

from __future__ import annotations

from hardware_splicer.engineering_plan_store import (
    engineering_snapshot,
    resolve_engineering_project_id,
)


def test_resolve_engineering_project_id_prefers_explicit_request_identity() -> None:
    plan = {"machine_project": {"project_id": "embedded-project"}}

    assert resolve_engineering_project_id(plan, project_id="requested-project") == "requested-project"
    assert resolve_engineering_project_id(plan) == "embedded-project"


def test_resolve_engineering_project_id_uses_stable_plan_fallbacks() -> None:
    assert resolve_engineering_project_id({"project_id": "plan-project"}) == "plan-project"
    assert resolve_engineering_project_id({"project_name": "named-project"}) == "named-project"
    assert resolve_engineering_project_id({}) == "engineering-project"


def test_engineering_snapshot_uses_the_same_canonical_identity() -> None:
    plan = {
        "project_id": "plan-project",
        "project_name": "Plan Project",
        "machine_project": {"name": "Machine Project"},
    }

    snapshot = engineering_snapshot(plan)

    assert snapshot["projectId"] == "plan-project"
    assert snapshot["projectName"] == "Machine Project"

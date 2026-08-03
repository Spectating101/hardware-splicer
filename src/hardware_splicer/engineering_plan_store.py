"""Persistence helpers for enriched engineering plans."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .project_store import ProjectStore


def engineering_snapshot(plan: Mapping[str, Any]) -> Dict[str, Any]:
    machine_project = plan.get("machine_project") if isinstance(plan.get("machine_project"), Mapping) else {}
    project_id = str(machine_project.get("project_id") or plan.get("project_name") or "engineering-project")
    return {
        "snapshot_schema_version": "hardware_splicer.engineering_project_snapshot.v1",
        "projectId": project_id,
        "projectName": str(machine_project.get("name") or plan.get("project_name") or project_id),
        "mode": str((plan.get("engineering_context") or {}).get("normalized_mode") or "greenfield"),
        "currentStage": "engineering_plan",
        "engineeringPlan": dict(plan),
        "machineProject": dict(machine_project),
        "engineeringSourceGraph": dict(plan.get("engineering_source_graph") or {}),
        "robotTopology": dict(plan.get("robot_topology") or {}),
        "engineeringAnalysis": dict(plan.get("engineering_analysis") or {}),
        "changeImpact": dict(plan.get("change_impact") or {}),
        "engineeringIdentityMap": dict(plan.get("engineering_identity_map") or {}),
        "engineeringReadiness": dict(plan.get("engineering_readiness") or {}),
        "missingInfo": list(plan.get("missing_info") or []),
    }


def save_engineering_plan(
    store: ProjectStore,
    plan: Mapping[str, Any],
    *,
    project_id: str | None = None,
    expected_revision: int | None = None,
) -> Dict[str, Any]:
    snapshot = engineering_snapshot(plan)
    resolved_project_id = str(project_id or snapshot["projectId"])
    snapshot["projectId"] = resolved_project_id
    machine_project = snapshot.get("machineProject")
    if isinstance(machine_project, dict):
        machine_project["project_id"] = resolved_project_id
    return store.save(
        resolved_project_id,
        snapshot,
        expected_revision=expected_revision,
        metadata={
            "source": "engineering_planner",
            "engineering_plan_schema": plan.get("schema_version"),
            "native_robot_genre": plan.get("native_robot_genre"),
            "blocking_source_conflict_count": (plan.get("engineering_readiness") or {}).get("blocking_source_conflict_count"),
            "blocking_analysis_finding_count": (plan.get("engineering_readiness") or {}).get("blocking_analysis_finding_count"),
            "blocking_change_impact_count": (plan.get("engineering_readiness") or {}).get("blocking_change_impact_count"),
            "physical_authority_unchanged": True,
        },
    )

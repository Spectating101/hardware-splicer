"""Persistence helpers for enriched guided engineering plans."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .project_store import ProjectStore


def resolve_engineering_project_id(
    plan: Mapping[str, Any],
    *,
    project_id: str | None = None,
) -> str:
    """Resolve the stable project identity used by engineering-plan persistence.

    An explicit route/request identity wins so callers can target a known project,
    while callers that omit it inherit the identity embedded in the plan.  The
    physical-evidence persistence layer compares both forms before writing, which
    prevents an explicit project ID from silently rebinding a plan from another
    project.
    """

    explicit = str(project_id or "").strip()
    if explicit:
        return explicit

    machine_project = (
        plan.get("machine_project")
        if isinstance(plan.get("machine_project"), Mapping)
        else {}
    )
    for candidate in (
        machine_project.get("project_id"),
        plan.get("project_id"),
        plan.get("project_name"),
    ):
        resolved = str(candidate or "").strip()
        if resolved:
            return resolved
    return "engineering-project"


def engineering_snapshot(plan: Mapping[str, Any]) -> Dict[str, Any]:
    machine_project = plan.get("machine_project") if isinstance(plan.get("machine_project"), Mapping) else {}
    project_id = resolve_engineering_project_id(plan)
    return {
        "snapshot_schema_version": "hardware_splicer.engineering_project_snapshot.v1",
        "projectId": project_id,
        "projectName": str(machine_project.get("name") or plan.get("project_name") or project_id),
        "mode": str((plan.get("engineering_context") or {}).get("normalized_mode") or "greenfield"),
        "currentStage": "guided_engineering_plan",
        "engineeringPlan": dict(plan),
        "machineProject": dict(machine_project),
        "engineeringSourceGraph": dict(plan.get("engineering_source_graph") or {}),
        "robotTopology": dict(plan.get("robot_topology") or {}),
        "engineeringAnalysis": dict(plan.get("engineering_analysis") or {}),
        "changeImpact": dict(plan.get("change_impact") or {}),
        "engineeringIdentityMap": dict(plan.get("engineering_identity_map") or {}),
        "verificationBridge": dict(plan.get("verification_bridge") or {}),
        "engineeringArtifactProjection": dict(plan.get("engineering_artifact_projection") or {}),
        "manufacturingProjection": dict(plan.get("manufacturing_projection") or {}),
        "manufacturingClosure": dict(plan.get("manufacturing_closure") or {}),
        "engineeringExecutionPlan": dict(plan.get("engineering_execution_plan") or {}),
        "operatorGuide": dict(plan.get("operator_guide") or {}),
        "orderedSteps": list(plan.get("ordered_steps") or []),
        "sourceAdapter": dict(plan.get("source_adapter") or {}),
        "engineeringReadiness": dict(plan.get("engineering_readiness") or {}),
        "engineeringStatus": dict(plan.get("engineering_status") or {}),
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
    resolved_project_id = resolve_engineering_project_id(plan, project_id=project_id)
    snapshot["projectId"] = resolved_project_id
    machine_project = snapshot.get("machineProject")
    if isinstance(machine_project, dict):
        machine_project["project_id"] = resolved_project_id
    readiness = plan.get("engineering_readiness") if isinstance(plan.get("engineering_readiness"), Mapping) else {}
    return store.save(
        resolved_project_id,
        snapshot,
        expected_revision=expected_revision,
        metadata={
            "source": "guided_engineering_planner",
            "engineering_plan_schema": plan.get("schema_version"),
            "native_robot_genre": plan.get("native_robot_genre"),
            "blocking_source_conflict_count": readiness.get("blocking_source_conflict_count"),
            "blocking_analysis_finding_count": readiness.get("blocking_analysis_finding_count"),
            "blocking_change_impact_count": readiness.get("blocking_change_impact_count"),
            "manufacturing_closure_status": readiness.get("manufacturing_closure_status"),
            "manufacturing_closure_blocker_count": readiness.get("manufacturing_closure_blocker_count"),
            "bounded_execution_check_count": readiness.get("bounded_execution_check_count"),
            "bounded_execution_unresolved_count": readiness.get("bounded_execution_unresolved_count"),
            "operator_guide_step_count": readiness.get("operator_guide_step_count"),
            "verification_method_count": readiness.get("verification_method_count"),
            "physical_authority_unchanged": True,
            "manufacturing_authority_unchanged": True,
            "automatic_execution": False,
        },
    )

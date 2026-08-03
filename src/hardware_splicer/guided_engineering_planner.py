"""Final planning composition for guided, evidence-governed robot engineering."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .change_impact import ChangeImpactGraph
from .complete_engineering_planner import plan_complete_engineering_project
from .engineering_analysis import EngineeringAnalysisReport
from .engineering_artifact_projection import project_engineering_artifacts
from .engineering_execution_plan import EngineeringExecutionPlan, build_engineering_execution_plan
from .engineering_source_graph import EngineeringSourceGraph
from .engineering_verification_bridge import bridge_engineering_verification
from .machine_project import MachineProject
from .manufacturing_closure import ManufacturingClosureReport, build_manufacturing_closure
from .manufacturing_projection import project_manufacturing_identities
from .robot_operator_guide import RobotOperatorGuide, build_robot_operator_guide
from .robot_topology import RobotTopology


GUIDED_ENGINEERING_PLAN_SCHEMA = "hardware_splicer.guided_engineering_plan.v1"


def _closure_blockers(report: ManufacturingClosureReport) -> list[str]:
    return [f"Manufacturing closure {row.check_id}: {row.message}" for row in report.blocking_checks]


def _execution_missing(report: EngineeringExecutionPlan) -> list[str]:
    rows: list[str] = []
    for item in report.unresolved:
        subject = item.get("source_id") or item.get("artifact_id") or report.project_id
        rows.append(f"Prepare bounded execution input for {subject}: {item.get('reason', 'unresolved execution input')}")
    return rows


def plan_guided_engineering_project(
    intake: Mapping[str, Any],
    *,
    engineering_sources: Iterable[Mapping[str, Any] | str] | None = None,
    declared_conflicts: Iterable[Mapping[str, Any]] | None = None,
    baseline_project: Mapping[str, Any] | MachineProject | None = None,
    skip_vision: bool = False,
) -> Dict[str, Any]:
    """Create the complete plan, source projection, closure, verification, and guide."""

    plan = plan_complete_engineering_project(
        intake,
        engineering_sources=engineering_sources,
        declared_conflicts=declared_conflicts,
        baseline_project=baseline_project,
        skip_vision=skip_vision,
    )
    project = MachineProject.model_validate(plan["machine_project"])
    topology = RobotTopology.model_validate(plan["robot_topology"])
    source_graph = EngineeringSourceGraph.model_validate(plan["engineering_source_graph"])
    analysis = EngineeringAnalysisReport.model_validate(plan["engineering_analysis"])
    change_impact = ChangeImpactGraph.model_validate(plan["change_impact"])
    identity_map = dict(plan.get("engineering_identity_map") or {})

    project = project_engineering_artifacts(
        project,
        source_graph=source_graph,
        identity_map=identity_map,
    )
    project = bridge_engineering_verification(
        project,
        analysis=analysis,
        change_impact=change_impact,
        identity_map=identity_map,
    )
    project = project_manufacturing_identities(project, plan=plan, intake=intake)
    manufacturing_projection = project.discipline_payloads.get("manufacturing_projection")

    closure = build_manufacturing_closure(plan, intake=intake, project=project)
    closure_payload = closure.model_dump(mode="json")
    execution_plan = build_engineering_execution_plan(plan, source_graph=source_graph)
    execution_payload = execution_plan.model_dump(mode="json")
    payloads = dict(project.discipline_payloads)
    payloads["manufacturing_closure"] = closure_payload
    payloads["engineering_execution_plan"] = execution_payload
    metadata = dict(project.metadata)
    metadata.update(
        {
            "manufacturing_closure_schema": closure.schema_version,
            "manufacturing_closure_status": closure.status,
            "manufacturing_closure_blocker_count": len(closure.blocking_checks),
            "engineering_execution_plan_schema": execution_plan.schema_version,
            "engineering_execution_check_count": len(execution_plan.checks),
            "engineering_execution_unresolved_count": len(execution_plan.unresolved),
            "automatic_execution": False,
            "manufacturing_authority_unchanged": True,
        }
    )
    project = project.model_copy(update={"discipline_payloads": payloads, "metadata": metadata}, deep=True)
    plan["manufacturing_projection"] = manufacturing_projection
    plan["manufacturing_closure"] = closure_payload
    plan["engineering_execution_plan"] = execution_payload

    guide: RobotOperatorGuide = build_robot_operator_guide(
        plan,
        project=project,
        topology=topology,
        source_graph=source_graph,
        analysis=analysis,
        change_impact=change_impact,
    )
    combined_blockers = list(dict.fromkeys([*guide.current_blockers, *_closure_blockers(closure)]))
    guide = guide.model_copy(update={"current_blockers": combined_blockers}, deep=True)

    payloads = dict(project.discipline_payloads)
    payloads["robot_operator_guide"] = guide.model_dump(mode="json")
    metadata = dict(project.metadata)
    metadata.update(
        {
            "guided_engineering_plan": GUIDED_ENGINEERING_PLAN_SCHEMA,
            "operator_guide_step_count": len(guide.steps),
            "operator_guide_blocker_count": len(guide.current_blockers),
            "operational_authority_unchanged": True,
        }
    )
    project = project.model_copy(update={"discipline_payloads": payloads, "metadata": metadata}, deep=True)

    plan["schema_version"] = GUIDED_ENGINEERING_PLAN_SCHEMA
    plan["complete_engineering_plan_schema"] = "hardware_splicer.complete_engineering_plan.v1"
    plan["machine_project"] = project.model_dump(mode="json")
    plan["operator_guide"] = guide.model_dump(mode="json")
    plan["ordered_steps"] = [row.model_dump(mode="json") for row in guide.steps]
    plan["verification_bridge"] = project.discipline_payloads.get("engineering_verification_bridge")
    plan["engineering_artifact_projection"] = project.discipline_payloads.get("engineering_artifact_projection")

    missing = list(plan.get("missing_info") or [])
    missing.extend(_closure_blockers(closure))
    missing.extend(_execution_missing(execution_plan))
    plan["missing_info"] = list(dict.fromkeys(missing))

    scenario = dict(plan.get("scenario") or {})
    compile_spec = dict(scenario.get("compile_spec") or {})
    compile_spec["machine_project"] = project.model_dump(mode="json")
    compile_spec["operator_guide"] = guide.model_dump(mode="json")
    compile_spec["ordered_steps"] = plan["ordered_steps"]
    compile_spec["engineering_verification_bridge"] = plan["verification_bridge"]
    compile_spec["engineering_artifact_projection"] = plan["engineering_artifact_projection"]
    compile_spec["manufacturing_projection"] = manufacturing_projection
    compile_spec["manufacturing_closure"] = closure_payload
    compile_spec["engineering_execution_plan"] = execution_payload
    scenario["compile_spec"] = compile_spec
    scenario["manufacturing_acceptance"] = {
        "status": closure.status,
        "blocking_check_count": len(closure.blocking_checks),
        "warning_check_count": len(closure.warning_checks),
        "projected_component_count": len((manufacturing_projection or {}).get("projected_component_ids", [])),
        "projected_interface_count": len((manufacturing_projection or {}).get("projected_interface_ids", [])),
        "projected_artifact_count": len((manufacturing_projection or {}).get("projected_artifact_ids", [])),
        "fabrication_authorized": False,
        "release_authorized": False,
    }
    scenario["execution_acceptance"] = {
        "preview_check_count": len(execution_plan.checks),
        "unresolved_input_count": len(execution_plan.unresolved),
        "automatic_execution": False,
        "device_access_authorized": False,
        "flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
    }
    plan["scenario"] = scenario

    readiness = dict(plan.get("engineering_readiness") or {})
    prior_blocked = readiness.get("status") == "blocked"
    readiness.update(
        {
            "status": "blocked" if prior_blocked or closure.blocking_checks else readiness.get("status", "candidate"),
            "operator_guide_generated": True,
            "operator_guide_step_count": len(guide.steps),
            "operator_guide_blocker_count": len(guide.current_blockers),
            "verification_method_count": len(project.verifications),
            "analysis_evidence_count": len(
                [row for row in project.evidence if row.kind == "bounded_engineering_calculation"]
            ),
            "projected_source_evidence_count": len(
                (plan["engineering_artifact_projection"] or {}).get("projected_evidence_ids", [])
            ),
            "firmware_lineage_component_count": len(
                (plan["engineering_artifact_projection"] or {}).get("firmware_component_ids", [])
            ),
            "middleware_contract_component_count": len(
                (plan["engineering_artifact_projection"] or {}).get("middleware_component_ids", [])
            ),
            "manufacturing_projected_component_count": len((manufacturing_projection or {}).get("projected_component_ids", [])),
            "manufacturing_projected_interface_count": len((manufacturing_projection or {}).get("projected_interface_ids", [])),
            "manufacturing_projected_artifact_count": len((manufacturing_projection or {}).get("projected_artifact_ids", [])),
            "manufacturing_closure_status": closure.status,
            "manufacturing_closure_blocker_count": len(closure.blocking_checks),
            "manufacturing_closure_warning_count": len(closure.warning_checks),
            "manufacturing_inputs_reconciled": not bool(closure.blocking_checks),
            "bounded_execution_plan_generated": True,
            "bounded_execution_check_count": len(execution_plan.checks),
            "bounded_execution_unresolved_count": len(execution_plan.unresolved),
            "automatic_execution": False,
            "physical_validation_required": True,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }
    )
    plan["engineering_readiness"] = readiness
    return plan

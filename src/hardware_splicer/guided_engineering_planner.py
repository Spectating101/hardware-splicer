"""Final planning composition for guided, evidence-governed robot engineering."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .change_impact import ChangeImpactGraph
from .complete_engineering_planner import plan_complete_engineering_project
from .engineering_analysis import EngineeringAnalysisReport
from .engineering_source_graph import EngineeringSourceGraph
from .engineering_verification_bridge import bridge_engineering_verification
from .machine_project import MachineProject
from .robot_operator_guide import RobotOperatorGuide, build_robot_operator_guide
from .robot_topology import RobotTopology


GUIDED_ENGINEERING_PLAN_SCHEMA = "hardware_splicer.guided_engineering_plan.v1"


def plan_guided_engineering_project(
    intake: Mapping[str, Any],
    *,
    engineering_sources: Iterable[Mapping[str, Any] | str] | None = None,
    declared_conflicts: Iterable[Mapping[str, Any]] | None = None,
    baseline_project: Mapping[str, Any] | MachineProject | None = None,
    skip_vision: bool = False,
) -> Dict[str, Any]:
    """Create the complete plan, verification bridge, and ordered operator guide."""

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

    project = bridge_engineering_verification(
        project,
        analysis=analysis,
        change_impact=change_impact,
        identity_map=identity_map,
    )
    guide: RobotOperatorGuide = build_robot_operator_guide(
        plan,
        project=project,
        topology=topology,
        source_graph=source_graph,
        analysis=analysis,
        change_impact=change_impact,
    )
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
    plan["verification_bridge"] = project.discipline_payloads.get("engineering_verification_bridge")

    scenario = dict(plan.get("scenario") or {})
    compile_spec = dict(scenario.get("compile_spec") or {})
    compile_spec["machine_project"] = project.model_dump(mode="json")
    compile_spec["operator_guide"] = guide.model_dump(mode="json")
    compile_spec["engineering_verification_bridge"] = plan["verification_bridge"]
    scenario["compile_spec"] = compile_spec
    plan["scenario"] = scenario

    readiness = dict(plan.get("engineering_readiness") or {})
    readiness.update(
        {
            "operator_guide_generated": True,
            "operator_guide_step_count": len(guide.steps),
            "operator_guide_blocker_count": len(guide.current_blockers),
            "verification_method_count": len(project.verifications),
            "analysis_evidence_count": len(
                [row for row in project.evidence if row.kind == "bounded_engineering_calculation"]
            ),
            "physical_validation_required": True,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }
    )
    plan["engineering_readiness"] = readiness
    return plan

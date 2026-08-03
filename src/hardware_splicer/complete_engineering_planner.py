"""Complete engineering-plan composition including first-class robot projection."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .engineering_planner import plan_engineering_project
from .machine_project import MachineProject
from .robot_machine_projection import project_robot_topology
from .robot_topology import RobotTopology


COMPLETE_ENGINEERING_PLAN_SCHEMA = "hardware_splicer.complete_engineering_plan.v1"


def _topology_to_machine_map(project: MachineProject) -> Dict[str, str]:
    projection = project.discipline_payloads.get("robot_machine_projection")
    if not isinstance(projection, Mapping):
        return {}
    mapping: Dict[str, str] = {}
    for key in ("link_component_ids", "joint_component_ids", "actuator_component_ids"):
        values = projection.get(key)
        if isinstance(values, Mapping):
            mapping.update({str(source): str(target) for source, target in values.items()})
    for component in project.components:
        topology_id = component.metadata.get("topology_object_id") if isinstance(component.metadata, Mapping) else None
        if topology_id:
            mapping[str(topology_id)] = component.component_id
    return mapping


def plan_complete_engineering_project(
    intake: Mapping[str, Any],
    *,
    engineering_sources: Iterable[Mapping[str, Any] | str] | None = None,
    declared_conflicts: Iterable[Mapping[str, Any]] | None = None,
    baseline_project: Mapping[str, Any] | MachineProject | None = None,
    skip_vision: bool = False,
) -> Dict[str, Any]:
    """Create the enriched plan and project robot topology into MachineProject."""

    plan = plan_engineering_project(
        intake,
        engineering_sources=engineering_sources,
        declared_conflicts=declared_conflicts,
        baseline_project=baseline_project,
        skip_vision=skip_vision,
    )
    project = MachineProject.model_validate(plan["machine_project"])
    topology = RobotTopology.model_validate(plan["robot_topology"])
    projected = project_robot_topology(project, topology)
    topology_to_machine = _topology_to_machine_map(projected)

    identity_map = dict(plan.get("engineering_identity_map") or {})
    identity_map["topology_to_machine_component"] = topology_to_machine
    for topology_id, row in dict(identity_map.get("topology_objects") or {}).items():
        if isinstance(row, dict) and topology_id in topology_to_machine:
            row["machine_component_id"] = topology_to_machine[topology_id]

    plan["schema_version"] = COMPLETE_ENGINEERING_PLAN_SCHEMA
    plan["engineering_base_plan_schema"] = "hardware_splicer.engineering_plan.v1"
    plan["machine_project"] = projected.model_dump(mode="json")
    plan["engineering_identity_map"] = identity_map
    plan["identity_map"] = identity_map
    plan["robot_machine_projection"] = projected.discipline_payloads.get("robot_machine_projection")

    scenario = dict(plan.get("scenario") or {})
    compile_spec = dict(scenario.get("compile_spec") or {})
    compile_spec["machine_project"] = projected.model_dump(mode="json")
    compile_spec["engineering_identity_map"] = identity_map
    compile_spec["robot_machine_projection"] = plan["robot_machine_projection"]
    scenario["compile_spec"] = compile_spec
    plan["scenario"] = scenario

    readiness = dict(plan.get("engineering_readiness") or {})
    readiness.update(
        {
            "machine_project_traceability_issue_count": len(projected.traceability_issues()),
            "machine_project_robot_projection_complete": True,
            "projected_component_count": (plan["robot_machine_projection"] or {}).get("projected_component_count", 0),
            "projected_interface_count": (plan["robot_machine_projection"] or {}).get("projected_interface_count", 0),
            "power_on_authorized": False,
            "release_authorized": False,
        }
    )
    plan["engineering_readiness"] = readiness
    return plan

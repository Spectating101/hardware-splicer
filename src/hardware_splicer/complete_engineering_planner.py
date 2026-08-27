"""Complete engineering-plan composition including structured-source import."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .change_impact import build_change_impact_graph
from .engineering_analysis import analyze_engineering_candidate
from .engineering_planner import plan_engineering_project
from .engineering_source_adapters import AdaptedSourceBundle, adapt_engineering_sources
from .engineering_source_graph import EngineeringSourceGraph
from .machine_project import AuthorityState, MachineProject
from .robot_machine_projection import project_robot_topology
from .robot_model_import import topology_from_robot_model
from .robot_topology import RobotGenre, RobotTopology


COMPLETE_ENGINEERING_PLAN_SCHEMA = "hardware_splicer.complete_engineering_plan.v1"


def _source_values(
    intake: Mapping[str, Any],
    engineering_sources: Iterable[Mapping[str, Any] | str] | None,
) -> list[Mapping[str, Any] | str]:
    if engineering_sources is not None:
        return list(engineering_sources)
    raw = intake.get("engineering_sources")
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, Mapping):
        values: list[Mapping[str, Any] | str] = []
        for key, item in raw.items():
            if isinstance(item, list):
                values.extend(item)
            elif isinstance(item, Mapping):
                values.append(item)
            elif item is not None:
                values.append({"source_id": str(key), "uri": str(item), "source_type": str(key)})
        return values
    return []


def _selected_model_source_id(intake: Mapping[str, Any], bundle: AdaptedSourceBundle) -> str | None:
    explicit = str(
        intake.get("selected_robot_model_source_id")
        or intake.get("robot_model_source_id")
        or ""
    ).strip()
    if explicit:
        return explicit
    if len(bundle.robot_models) == 1:
        return next(iter(bundle.robot_models))
    return None


def _identity_map(
    project: MachineProject,
    topology: RobotTopology,
    source_graph: EngineeringSourceGraph,
) -> Dict[str, Any]:
    component_aliases: dict[str, list[str]] = {}
    for component in project.components:
        aliases = [component.component_id, component.name]
        intake_part = component.metadata.get("intake_part") if isinstance(component.metadata, Mapping) else None
        if isinstance(intake_part, Mapping):
            aliases.extend(
                str(intake_part.get(key))
                for key in ("component_id", "module_id", "name")
                if intake_part.get(key)
            )
        component_aliases[component.component_id] = sorted(set(aliases))
    topology_objects: dict[str, Dict[str, Any]] = {}
    for link in topology.links:
        topology_objects[link.link_id] = {
            "kind": "link",
            "frame_id": link.frame_id,
            "mechanical_component_id": link.mechanical_component_id,
        }
    for joint in topology.joints:
        topology_objects[joint.joint_id] = {
            "kind": "joint",
            "parent_link_id": joint.parent_link_id,
            "child_link_id": joint.child_link_id,
            "actuator_id": joint.actuator_id,
            "firmware_joint_id": joint.firmware_joint_id,
            "middleware_joint_name": joint.middleware_joint_name,
        }
    for actuator in topology.actuators:
        topology_objects[actuator.actuator_id] = {
            "kind": "actuator",
            "joint_ids": actuator.joint_ids,
            "source_part_id": actuator.source_part_id,
            "electrical_component_id": actuator.electrical_component_id,
            "firmware_channel_id": actuator.firmware_channel_id,
        }
    for sensor in topology.sensors:
        topology_objects[sensor.sensor_id] = {
            "kind": "sensor",
            "frame_id": sensor.frame_id,
            "source_part_id": sensor.source_part_id,
            "electrical_component_id": sensor.electrical_component_id,
            "firmware_sensor_id": sensor.firmware_sensor_id,
            "middleware_interfaces": sensor.middleware_interfaces,
        }
    known_ids = set(topology_objects) | set(component_aliases) | {project.project_id}
    return {
        "schema_version": "hardware_splicer.engineering_identity_map.v1",
        "project_id": project.project_id,
        "component_aliases": component_aliases,
        "topology_objects": topology_objects,
        "source_claim_targets": {
            claim.claim_id: claim.subject_id if claim.subject_id in known_ids else project.project_id
            for claim in source_graph.claims
        },
        "unresolved_source_ids": source_graph.unresolved_source_ids,
        "authority": AuthorityState.PROPOSED.value,
    }


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
            # Robot projection deliberately creates physical, firmware, and middleware
            # components for one topology sensor/actuator. The first projected component is
            # the physical topology object; later channel/interface components must not
            # overwrite that canonical identity mapping.
            mapping.setdefault(str(topology_id), component.component_id)
    return mapping


def _replace_model_dependent_payloads(
    plan: Dict[str, Any],
    topology: RobotTopology,
    *,
    baseline_project: Mapping[str, Any] | MachineProject | None,
) -> tuple[MachineProject, EngineeringSourceGraph, Dict[str, Any]]:
    project = MachineProject.model_validate(plan["machine_project"])
    source_graph = EngineeringSourceGraph.model_validate(plan["engineering_source_graph"])
    normalized_intake = dict(plan.get("normalized_intake") or {})
    analysis = analyze_engineering_candidate(normalized_intake, topology=topology)
    change_impact = build_change_impact_graph(
        normalized_intake,
        machine_project=project,
        topology=topology,
        source_graph=source_graph,
        baseline_project=baseline_project,
    )
    identity_map = _identity_map(project, topology, source_graph)
    payloads = dict(project.discipline_payloads)
    payloads.update(
        {
            "robot_topology": topology.model_dump(mode="json"),
            "engineering_analysis": analysis.model_dump(mode="json"),
            "change_impact": change_impact.model_dump(mode="json"),
            "engineering_identity_map": identity_map,
        }
    )
    metadata = dict(project.metadata)
    metadata.update(
        {
            "robot_genre": topology.robot_genre.value,
            "robot_topology_id": topology.topology_id,
            "structured_robot_model_imported": True,
            "blocking_analysis_finding_count": len(analysis.blocking_findings),
            "change_mode": change_impact.mode.value,
        }
    )
    project = project.model_copy(update={"discipline_payloads": payloads, "metadata": metadata}, deep=True)
    plan.update(
        {
            "archetype": topology.robot_genre.value if topology.robot_genre != RobotGenre.GENERIC else plan.get("archetype"),
            "native_robot_genre": topology.robot_genre.value,
            "robot_topology": topology.model_dump(mode="json"),
            "engineering_analysis": analysis.model_dump(mode="json"),
            "change_impact": change_impact.model_dump(mode="json"),
            "engineering_identity_map": identity_map,
            "identity_map": identity_map,
            "baseline_revision": change_impact.baseline_revision,
            "candidate_revision": change_impact.candidate_revision,
            "affected_subsystems": change_impact.affected_target_ids,
            "compatibility_impact": [row.model_dump(mode="json") for row in change_impact.impacts],
            "regression_scope": [row.model_dump(mode="json") for row in change_impact.regression_checks],
            "machine_project": project.model_dump(mode="json"),
        }
    )
    plan["modification_delta"] = {
        "mode": change_impact.mode.value,
        "baseline_project_id": change_impact.baseline_project_id,
        "baseline_revision": change_impact.baseline_revision,
        "affected_domains": change_impact.affected_domains,
        "affected_target_ids": change_impact.affected_target_ids,
    }
    readiness = dict(plan.get("engineering_readiness") or {})
    readiness.update(
        {
            "blocking_analysis_finding_count": len(analysis.blocking_findings),
            "blocking_change_impact_count": len(change_impact.blocking_impacts),
            "native_robot_topology": topology.robot_genre != RobotGenre.GENERIC,
        }
    )
    if analysis.blocking_findings or change_impact.blocking_impacts:
        readiness["status"] = "blocked"
    plan["engineering_readiness"] = readiness
    return project, source_graph, identity_map


def plan_complete_engineering_project(
    intake: Mapping[str, Any],
    *,
    engineering_sources: Iterable[Mapping[str, Any] | str] | None = None,
    declared_conflicts: Iterable[Mapping[str, Any]] | None = None,
    baseline_project: Mapping[str, Any] | MachineProject | None = None,
    skip_vision: bool = False,
) -> Dict[str, Any]:
    """Create the enriched, structured-source-aware, fully projected plan."""

    raw_sources = _source_values(intake, engineering_sources)
    bundle = adapt_engineering_sources(raw_sources)
    source_rows: list[Mapping[str, Any] | str]
    if bundle.sources:
        source_rows = list(bundle.sources)
    else:
        source_rows = raw_sources
    plan = plan_engineering_project(
        intake,
        engineering_sources=source_rows,
        declared_conflicts=declared_conflicts,
        baseline_project=baseline_project,
        skip_vision=skip_vision,
    )
    project = MachineProject.model_validate(plan["machine_project"])
    source_graph = EngineeringSourceGraph.model_validate(plan["engineering_source_graph"])
    topology = RobotTopology.model_validate(plan["robot_topology"])
    selected_model_source_id = _selected_model_source_id(intake, bundle)
    if selected_model_source_id:
        if selected_model_source_id not in bundle.robot_models:
            plan.setdefault("missing_info", []).append(
                f"Selected robot model source {selected_model_source_id!r} was not available after adaptation."
            )
            plan.setdefault("engineering_readiness", {})["status"] = "blocked"
        else:
            topology = topology_from_robot_model(bundle.robot_models[selected_model_source_id])
            project, source_graph, _ = _replace_model_dependent_payloads(
                plan,
                topology,
                baseline_project=baseline_project,
            )
    elif len(bundle.robot_models) > 1:
        plan.setdefault("missing_info", []).append(
            "Select one robot model source before projecting structured geometry: "
            + ", ".join(sorted(bundle.robot_models))
        )
        plan.setdefault("engineering_readiness", {})["status"] = "blocked"

    if bundle.unresolved:
        plan.setdefault("missing_info", []).extend(
            f"Resolve source adapter input at index {row.get('index')}: {row.get('reason')}"
            for row in bundle.unresolved
        )
        plan.setdefault("engineering_readiness", {})["status"] = "blocked"

    identity_map = _identity_map(project, topology, source_graph)
    projected = project_robot_topology(project, topology)
    topology_to_machine = _topology_to_machine_map(projected)
    identity_map["topology_to_machine_component"] = topology_to_machine
    for topology_id, row in dict(identity_map.get("topology_objects") or {}).items():
        if isinstance(row, dict) and topology_id in topology_to_machine:
            row["machine_component_id"] = topology_to_machine[topology_id]

    plan["schema_version"] = COMPLETE_ENGINEERING_PLAN_SCHEMA
    plan["engineering_base_plan_schema"] = "hardware_splicer.engineering_plan.v1"
    plan["machine_project"] = projected.model_dump(mode="json")
    plan["robot_topology"] = topology.model_dump(mode="json")
    plan["engineering_identity_map"] = identity_map
    plan["identity_map"] = identity_map
    plan["robot_machine_projection"] = projected.discipline_payloads.get("robot_machine_projection")
    plan["source_adapter"] = {
        "schema_version": bundle.schema_version,
        "adapted_source_count": len(bundle.sources),
        "robot_model_source_ids": sorted(bundle.robot_models),
        "selected_robot_model_source_id": selected_model_source_id,
        "unresolved": bundle.unresolved,
    }

    scenario = dict(plan.get("scenario") or {})
    compile_spec = dict(scenario.get("compile_spec") or {})
    compile_spec.update(
        {
            "machine_project": projected.model_dump(mode="json"),
            "robot_topology": topology.model_dump(mode="json"),
            "engineering_identity_map": identity_map,
            "robot_machine_projection": plan["robot_machine_projection"],
            "source_adapter": plan["source_adapter"],
        }
    )
    robotics_project = dict(compile_spec.get("robotics_project") or {})
    platform = dict(robotics_project.get("platform") or {})
    platform.update(
        {
            "type": topology.robot_genre.value,
            "topology_id": topology.topology_id,
            "degree_of_freedom_count": topology.degree_of_freedom_count,
            "link_ids": [row.link_id for row in topology.links],
            "joint_ids": [row.joint_id for row in topology.joints],
            "actuator_ids": [row.actuator_id for row in topology.actuators],
            "sensor_ids": [row.sensor_id for row in topology.sensors],
        }
    )
    robotics_project["platform"] = platform
    compile_spec["robotics_project"] = robotics_project
    scenario["compile_spec"] = compile_spec
    plan["scenario"] = scenario

    readiness = dict(plan.get("engineering_readiness") or {})
    readiness.update(
        {
            "machine_project_traceability_issue_count": len(projected.traceability_issues()),
            "machine_project_robot_projection_complete": True,
            "projected_component_count": (plan["robot_machine_projection"] or {}).get("projected_component_count", 0),
            "projected_interface_count": (plan["robot_machine_projection"] or {}).get("projected_interface_count", 0),
            "structured_source_adapter_complete": not bool(bundle.unresolved),
            "structured_robot_model_selected": selected_model_source_id is not None,
            "power_on_authorized": False,
            "release_authorized": False,
        }
    )
    plan["engineering_readiness"] = readiness
    plan["missing_info"] = list(dict.fromkeys(plan.get("missing_info") or []))
    return plan

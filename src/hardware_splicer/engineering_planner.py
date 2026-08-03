"""Source-agnostic engineering planning built on the existing Hardware Splicer intake.

This module does not replace the mature intake/compiler path.  It enriches that path
with canonical source provenance, robot topology, change propagation, and a
MachineProject projection so richer engineering reasoning remains compatible with
existing build, evidence, bench, and package workflows.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence

from .change_impact import ChangeImpactGraph, ChangeMode, build_change_impact_graph
from .engineering_source_graph import EngineeringSourceGraph, build_engineering_source_graph
from .machine_project import AuthorityState, MachineProject
from .machine_project_seed import machine_project_from_intake
from .project_intake import plan_project_from_intake
from .robot_topology import RobotGenre, RobotTopology, build_robot_topology


ENGINEERING_PLAN_SCHEMA = "hardware_splicer.engineering_plan.v1"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _source_id(value: Mapping[str, Any]) -> str:
    return str(value.get("source_id") or value.get("id") or value.get("name") or "").strip()


def _resolve_sources(
    intake: Mapping[str, Any],
    source_catalog: Iterable[Mapping[str, Any] | str] | None,
) -> tuple[list[Mapping[str, Any] | str], list[str]]:
    catalog = list(source_catalog or [])
    catalog_by_id = {
        _source_id(row): row
        for row in catalog
        if isinstance(row, Mapping) and _source_id(row)
    }
    raw = intake.get("engineering_sources")
    if raw is None:
        raw = intake.get("reference_sources")
    values: list[Any]
    if isinstance(raw, Mapping):
        values = []
        for key, item in raw.items():
            if isinstance(item, list):
                values.extend(item)
            elif item is not None:
                values.append(item if isinstance(item, Mapping) else {"source_id": str(key), "uri": item, "source_type": str(key)})
    else:
        values = _sequence(raw)
    if not values and catalog:
        values = catalog

    resolved: list[Mapping[str, Any] | str] = []
    unresolved: list[str] = []
    for value in values:
        if isinstance(value, Mapping):
            resolved.append(value)
            continue
        token = str(value)
        if token in catalog_by_id:
            resolved.append(catalog_by_id[token])
        else:
            resolved.append(token)
            unresolved.append(token)
    return resolved, unresolved


def _native_archetype(topology: RobotTopology, fallback: str) -> str:
    if topology.robot_genre == RobotGenre.GENERIC:
        return fallback
    return topology.robot_genre.value


def _identity_map(
    machine_project: MachineProject,
    topology: RobotTopology,
    source_graph: EngineeringSourceGraph,
) -> Dict[str, Any]:
    component_aliases: dict[str, list[str]] = {}
    for component in machine_project.components:
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

    claim_targets: dict[str, str] = {}
    known_ids = set(topology_objects) | set(component_aliases) | {machine_project.project_id}
    for claim in source_graph.claims:
        if claim.subject_id in known_ids:
            claim_targets[claim.claim_id] = claim.subject_id
        else:
            claim_targets[claim.claim_id] = machine_project.project_id

    return {
        "schema_version": "hardware_splicer.engineering_identity_map.v1",
        "project_id": machine_project.project_id,
        "component_aliases": component_aliases,
        "topology_objects": topology_objects,
        "source_claim_targets": claim_targets,
        "unresolved_source_ids": source_graph.unresolved_source_ids,
        "authority": AuthorityState.PROPOSED.value,
    }


def _machine_project_with_engineering_payloads(
    machine_project: MachineProject,
    source_graph: EngineeringSourceGraph,
    topology: RobotTopology,
    change_impact: ChangeImpactGraph,
    identity_map: Mapping[str, Any],
) -> MachineProject:
    payloads = dict(machine_project.discipline_payloads)
    payloads.update(
        {
            "engineering_source_graph": source_graph.model_dump(mode="json"),
            "robot_topology": topology.model_dump(mode="json"),
            "change_impact": change_impact.model_dump(mode="json"),
            "engineering_identity_map": dict(identity_map),
        }
    )
    metadata = dict(machine_project.metadata)
    metadata.update(
        {
            "engineering_planner": ENGINEERING_PLAN_SCHEMA,
            "source_provenance_complete": source_graph.source_provenance_complete,
            "blocking_source_conflict_count": len(source_graph.blocking_conflicts),
            "robot_genre": topology.robot_genre.value,
            "change_mode": change_impact.mode.value,
            "physical_authority_unchanged": True,
        }
    )
    return machine_project.model_copy(
        update={"discipline_payloads": payloads, "metadata": metadata},
        deep=True,
    )


def _engineering_missing_info(
    source_graph: EngineeringSourceGraph,
    topology: RobotTopology,
    change_impact: ChangeImpactGraph,
) -> list[str]:
    rows: list[str] = []
    rows.extend(
        f"Resolve engineering source reference {source_id!r}."
        for source_id in source_graph.unresolved_source_ids
    )
    rows.extend(
        f"Disposition source conflict {conflict.conflict_id!r}: {conflict.reason}"
        for conflict in source_graph.blocking_conflicts
    )
    rows.extend(
        f"Resolve robot topology field {item.get('object_id', topology.topology_id)}.{item.get('field', 'unknown')}: {item.get('reason', '')}"
        for item in topology.unresolved
    )
    rows.extend(
        f"Resolve change-impact field {item.get('field', 'unknown')}: {item.get('reason', '')}"
        for item in change_impact.unresolved
    )
    return rows


def plan_engineering_project(
    intake: Mapping[str, Any],
    *,
    engineering_sources: Iterable[Mapping[str, Any] | str] | None = None,
    declared_conflicts: Iterable[Mapping[str, Any]] | None = None,
    baseline_project: Mapping[str, Any] | MachineProject | None = None,
    skip_vision: bool = False,
) -> Dict[str, Any]:
    """Produce an enriched source-agnostic engineering plan.

    Existing intake planning remains the build and artifact baseline.  The added graphs
    are canonical planning artifacts with proposed/declared/observed authority only.
    """

    body = dict(intake or {})
    plan = dict(plan_project_from_intake(body, skip_vision=skip_vision))
    machine_project = machine_project_from_intake(body)
    resolved_sources, unresolved_source_ids = _resolve_sources(body, engineering_sources)
    conflict_rows = list(declared_conflicts or _sequence(body.get("declared_conflicts")))
    source_graph = build_engineering_source_graph(
        resolved_sources,
        declared_conflicts=[row for row in conflict_rows if isinstance(row, Mapping)],
        unresolved_source_ids=unresolved_source_ids,
    )
    topology = build_robot_topology(
        body,
        hinted_genre=str(body.get("robot_genre") or plan.get("archetype") or ""),
        machine_project=machine_project,
    )
    change_impact = build_change_impact_graph(
        body,
        machine_project=machine_project,
        topology=topology,
        source_graph=source_graph,
        baseline_project=baseline_project,
    )
    identity_map = _identity_map(machine_project, topology, source_graph)
    machine_project = _machine_project_with_engineering_payloads(
        machine_project,
        source_graph,
        topology,
        change_impact,
        identity_map,
    )

    native_archetype = _native_archetype(topology, str(plan.get("archetype") or "generic_mechatronics"))
    plan["schema_version"] = ENGINEERING_PLAN_SCHEMA
    plan["legacy_intake_schema_version"] = "hardware_splicer.project_intake.v1"
    plan["archetype"] = native_archetype
    plan["native_robot_genre"] = topology.robot_genre.value
    plan["engineering_source_graph"] = source_graph.model_dump(mode="json")
    plan["reference_sources"] = source_graph.model_dump(mode="json")
    plan["source_conflicts"] = [row.model_dump(mode="json") for row in source_graph.conflicts]
    plan["robot_topology"] = topology.model_dump(mode="json")
    plan["change_impact"] = change_impact.model_dump(mode="json")
    plan["engineering_identity_map"] = identity_map
    plan["identity_map"] = identity_map
    plan["machine_project"] = machine_project.model_dump(mode="json")
    plan["baseline_revision"] = change_impact.baseline_revision
    plan["candidate_revision"] = change_impact.candidate_revision
    plan["affected_subsystems"] = change_impact.affected_target_ids
    plan["compatibility_impact"] = [row.model_dump(mode="json") for row in change_impact.impacts]
    plan["regression_scope"] = [row.model_dump(mode="json") for row in change_impact.regression_checks]
    plan["modification_delta"] = {
        "mode": change_impact.mode.value,
        "baseline_project_id": change_impact.baseline_project_id,
        "baseline_revision": change_impact.baseline_revision,
        "affected_domains": change_impact.affected_domains,
        "affected_target_ids": change_impact.affected_target_ids,
    }
    plan["source_provenance"] = {
        "source_count": len(source_graph.sources),
        "claim_count": len(source_graph.claims),
        "conflict_count": len(source_graph.conflicts),
        "blocking_conflict_count": len(source_graph.blocking_conflicts),
        "complete": source_graph.source_provenance_complete,
        "authority_ceiling_preserved": True,
    }

    scenario = _mapping(plan.get("scenario"))
    compile_spec = _mapping(scenario.get("compile_spec"))
    compile_spec.update(
        {
            "engineering_source_graph": source_graph.model_dump(mode="json"),
            "robot_topology": topology.model_dump(mode="json"),
            "change_impact": change_impact.model_dump(mode="json"),
            "engineering_identity_map": identity_map,
            "machine_project": machine_project.model_dump(mode="json"),
        }
    )
    robotics_project = _mapping(compile_spec.get("robotics_project"))
    platform = _mapping(robotics_project.get("platform"))
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
    scenario["engineering_acceptance"] = {
        "blocking_source_conflicts": len(source_graph.blocking_conflicts),
        "unresolved_topology_fields": len(topology.unresolved),
        "blocking_change_impacts": len(change_impact.blocking_impacts),
        "power_on_authorized": False,
        "release_authorized": False,
    }
    plan["scenario"] = scenario

    missing = list(plan.get("missing_info") or [])
    missing.extend(_engineering_missing_info(source_graph, topology, change_impact))
    plan["missing_info"] = list(dict.fromkeys(missing))
    confidence = float(plan.get("planning_confidence") or 0.0)
    confidence -= min(len(source_graph.blocking_conflicts) * 0.05, 0.25)
    confidence -= min(len(source_graph.unresolved_source_ids) * 0.03, 0.15)
    plan["planning_confidence"] = round(max(0.0, min(confidence, 1.0)), 3)
    plan["engineering_readiness"] = {
        "status": "blocked" if source_graph.blocking_conflicts or change_impact.blocking_impacts else "candidate",
        "candidate_machine_synthesized": True,
        "native_robot_topology": topology.robot_genre != RobotGenre.GENERIC,
        "source_provenance_complete": source_graph.source_provenance_complete,
        "blocking_source_conflict_count": len(source_graph.blocking_conflicts),
        "blocking_change_impact_count": len(change_impact.blocking_impacts),
        "physical_validation_required": True,
        "power_on_authorized": False,
        "release_authorized": False,
    }
    return plan

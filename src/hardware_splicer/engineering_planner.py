"""Source-agnostic engineering planning built on Hardware Splicer's truth-bound intake.

The canonical engineering path uses ``plan_project_from_intake_truthful`` so historical
demo scaffolds cannot enter model-first project truth. The mature legacy intake planner is
retained only as an injected offline-compatibility callback for existing regression/demo
paths. Canonical source provenance, robot topology, bounded quantitative analysis, change
propagation, and MachineProject projection are layered on top of that fail-closed intake.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .change_impact import ChangeImpactGraph, build_change_impact_graph
from .engineering_analysis import EngineeringAnalysisReport, analyze_engineering_candidate
from .engineering_source_graph import EngineeringSourceGraph, build_engineering_source_graph
from .machine_project import AuthorityState, MachineProject
from .machine_project_seed import machine_project_from_intake
from .project_intake import plan_project_from_intake
from .project_intake_truth import plan_project_from_intake_truthful
from .robot_topology import RobotGenre, RobotTopology, build_robot_topology, detect_robot_genre
from .semantic_project_mode import (
    SemanticProjectModeError,
    interpret_project_mode,
    parse_project_mode_proposal,
    unresolved_project_mode_proposal,
)
from .semantic_robot_genre import (
    SemanticRobotGenreError,
    interpret_robot_genre,
    parse_robot_genre_proposal,
    unresolved_robot_genre_proposal,
)


ENGINEERING_PLAN_SCHEMA = "hardware_splicer.engineering_plan.v1"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def normalize_engineering_intake(intake: Mapping[str, Any]) -> Dict[str, Any]:
    """Lift explicit nested change/failure fields without interpreting project prose."""

    body = dict(intake or {})
    constraints = _mapping(body.get("constraints"))
    change_request = _mapping(body.get("change_request"))
    repair_request = _mapping(body.get("repair"))

    if body.get("baseline_revision") is None:
        nested_baseline = change_request.get("baseline_revision")
        if nested_baseline is None:
            nested_baseline = constraints.get("baseline_revision")
        if nested_baseline is not None:
            body["baseline_revision"] = nested_baseline
    if body.get("candidate_revision") is None and change_request.get("candidate_revision") is not None:
        body["candidate_revision"] = change_request["candidate_revision"]
    if body.get("field_failure") is None and change_request.get("failure_event"):
        body["field_failure"] = {
            "event": change_request.get("failure_event"),
            "requested_outcome": change_request.get("requested_outcome"),
            "must_preserve": change_request.get("must_preserve") or [],
        }

    context = _mapping(body.get("engineering_context"))
    context.update(
        {
            "baseline_revision": body.get("baseline_revision"),
            "candidate_revision": body.get("candidate_revision"),
            "change_request_present": bool(change_request),
            "field_failure_present": bool(body.get("field_failure")),
            "repair_request_present": bool(repair_request or body.get("salvage_mode")),
        }
    )
    body["engineering_context"] = context
    return body


def _legacy_mode_from_goal(goal: str) -> str:
    """Historical prose classifier retained only for explicit offline compatibility."""
    lowered = str(goal or "").lower()
    failure_tokens = (
        "field failure",
        "tipping",
        "tipped",
        "brownout",
        "reboot",
        "failed in field",
        "return to field",
        "returning to field",
        "regression before field",
    )
    repair_tokens = ("repair", "recover", "salvage", "donor", "splice", "burned")
    modification_tokens = ("modify", "upgrade", "revise", "replace", "add a", "add an")
    if any(token in lowered for token in failure_tokens):
        return "evolve"
    if any(token in lowered for token in repair_tokens):
        return "repair"
    if any(token in lowered for token in modification_tokens):
        return "modify"
    return "greenfield"


def _project_mode_proposal(body: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve workflow mode from declared/structured state before semantic prose."""
    explicit = str(body.get("mode") or body.get("project_mode") or "").strip()
    if explicit:
        try:
            proposal = parse_project_mode_proposal(
                {
                    "status": "declared",
                    "mode": explicit,
                    "reasoning": "Structured project mode supplied by the project intake.",
                    "confidence": 1.0,
                    "unresolved_questions": [],
                    "source": "declared",
                    "authority_effect": "none",
                    "automatic_execution": False,
                }
            )
            return proposal.model_dump(mode="json")
        except SemanticProjectModeError as exc:
            return unresolved_project_mode_proposal(
                f"Declared project mode is invalid: {exc}"
            ).model_dump(mode="json")

    if body.get("field_failure"):
        return parse_project_mode_proposal(
            {
                "status": "structured_state",
                "mode": "evolve",
                "reasoning": "Persisted field_failure state requires a field-evolution workflow.",
                "confidence": 1.0,
                "unresolved_questions": [],
                "source": "structured_state",
                "authority_effect": "none",
                "automatic_execution": False,
            }
        ).model_dump(mode="json")
    if body.get("repair") or body.get("salvage_mode"):
        return parse_project_mode_proposal(
            {
                "status": "structured_state",
                "mode": "repair",
                "reasoning": "Persisted repair/salvage state requires a repair workflow.",
                "confidence": 1.0,
                "unresolved_questions": [],
                "source": "structured_state",
                "authority_effect": "none",
                "automatic_execution": False,
            }
        ).model_dump(mode="json")
    if body.get("change_request") or body.get("baseline_revision") is not None or body.get("baseline_project"):
        return parse_project_mode_proposal(
            {
                "status": "structured_state",
                "mode": "modify",
                "reasoning": "A persisted change request or baseline establishes a modification workflow.",
                "confidence": 1.0,
                "unresolved_questions": [],
                "source": "structured_state",
                "authority_effect": "none",
                "automatic_execution": False,
            }
        ).model_dump(mode="json")

    goal = str(body.get("goal") or body.get("intent") or body.get("brief") or "").strip()
    from .integrations.llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        return {
            "schema_version": "hardware_splicer.semantic_project_mode.v1",
            "status": "legacy_heuristic",
            "mode": _legacy_mode_from_goal(goal),
            "reasoning": "Explicit offline compatibility classifier; not canonical project truth.",
            "confidence": 0.0,
            "unresolved_questions": [],
            "source": "legacy_keyword",
            "authority_effect": "none",
            "automatic_execution": False,
        }

    if not goal:
        return unresolved_project_mode_proposal(
            "No explicit project mode, structured change state, or project goal was supplied."
        ).model_dump(mode="json")
    try:
        return interpret_project_mode(goal).model_dump(mode="json")
    except SemanticProjectModeError as exc:
        return unresolved_project_mode_proposal(str(exc)).model_dump(mode="json")


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
    return fallback if topology.robot_genre == RobotGenre.GENERIC else topology.robot_genre.value


def _robot_genre_proposal(body: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve topology genre with explicit provenance and fail-closed model behavior."""
    explicit = str(body.get("robot_genre") or "").strip()
    if explicit:
        try:
            proposal = parse_robot_genre_proposal(
                {
                    "status": "declared",
                    "genre": explicit,
                    "reasoning": "Structured robot_genre supplied by the project intake.",
                    "confidence": 1.0,
                    "unresolved_questions": [],
                    "source": "declared",
                    "authority_effect": "none",
                    "automatic_execution": False,
                }
            )
            return proposal.model_dump(mode="json")
        except SemanticRobotGenreError as exc:
            return unresolved_robot_genre_proposal(
                f"Declared robot_genre is invalid: {exc}"
            ).model_dump(mode="json")

    goal = str(body.get("goal") or body.get("intent") or body.get("brief") or "").strip()
    parts = [
        dict(row)
        for row in _sequence(
            body.get("available_parts") or body.get("parts") or body.get("resources") or []
        )
        if isinstance(row, Mapping)
    ]
    constraints = _mapping(body.get("constraints"))

    from .integrations.llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        legacy = detect_robot_genre(goal, parts)
        return {
            "schema_version": "hardware_splicer.semantic_robot_genre.v1",
            "status": "legacy_heuristic",
            "genre": legacy.value,
            "reasoning": "Explicit offline compatibility classifier; not canonical engineering truth.",
            "confidence": 0.0,
            "unresolved_questions": [],
            "source": "legacy_keyword",
            "authority_effect": "none",
            "automatic_execution": False,
        }

    try:
        return interpret_robot_genre(
            goal or "Resolve the machine topology genre from supplied evidence.",
            parts=parts,
            constraints=constraints,
        ).model_dump(mode="json")
    except SemanticRobotGenreError as exc:
        return unresolved_robot_genre_proposal(str(exc)).model_dump(mode="json")


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

    known_ids = set(topology_objects) | set(component_aliases) | {machine_project.project_id}
    claim_targets = {
        claim.claim_id: claim.subject_id if claim.subject_id in known_ids else machine_project.project_id
        for claim in source_graph.claims
    }
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
    analysis: EngineeringAnalysisReport,
    change_impact: ChangeImpactGraph,
    identity_map: Mapping[str, Any],
) -> MachineProject:
    payloads = dict(machine_project.discipline_payloads)
    payloads.update(
        {
            "engineering_source_graph": source_graph.model_dump(mode="json"),
            "robot_topology": topology.model_dump(mode="json"),
            "engineering_analysis": analysis.model_dump(mode="json"),
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
            "blocking_analysis_finding_count": len(analysis.blocking_findings),
            "robot_genre": topology.robot_genre.value,
            "change_mode": change_impact.mode.value,
            "physical_authority_unchanged": True,
        }
    )
    return machine_project.model_copy(update={"discipline_payloads": payloads, "metadata": metadata}, deep=True)


def _engineering_missing_info(
    source_graph: EngineeringSourceGraph,
    topology: RobotTopology,
    analysis: EngineeringAnalysisReport,
    change_impact: ChangeImpactGraph,
) -> list[str]:
    rows: list[str] = []
    rows.extend(f"Resolve engineering source reference {source_id!r}." for source_id in source_graph.unresolved_source_ids)
    rows.extend(
        f"Disposition source conflict {conflict.conflict_id!r}: {conflict.reason}"
        for conflict in source_graph.blocking_conflicts
    )
    rows.extend(
        f"Resolve robot topology field {item.get('object_id', topology.topology_id)}.{item.get('field', 'unknown')}: {item.get('reason', '')}"
        for item in topology.unresolved
    )
    rows.extend(
        f"Provide analysis input for {finding.finding_id}: {', '.join(finding.missing_inputs)}"
        for finding in analysis.findings
        if finding.missing_inputs
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
    """Produce an enriched source-agnostic engineering plan."""

    body = normalize_engineering_intake(intake)
    mode_proposal = _project_mode_proposal(body)
    body["mode"] = str(mode_proposal.get("mode") or "greenfield")
    context = _mapping(body.get("engineering_context"))
    context.update(
        {
            "normalized_mode": body["mode"],
            "project_mode_status": mode_proposal.get("status"),
            "project_mode_source": mode_proposal.get("source"),
        }
    )
    body["engineering_context"] = context

    plan = dict(
        plan_project_from_intake_truthful(
            body,
            skip_vision=skip_vision,
            legacy_planner=plan_project_from_intake,
        )
    )
    architecture_truth = _mapping(plan.get("architecture_truth"))
    machine_project = machine_project_from_intake(body)
    resolved_sources, unresolved_source_ids = _resolve_sources(body, engineering_sources)
    conflict_rows = list(declared_conflicts or _sequence(body.get("declared_conflicts")))
    source_graph = build_engineering_source_graph(
        resolved_sources,
        declared_conflicts=[row for row in conflict_rows if isinstance(row, Mapping)],
        unresolved_source_ids=unresolved_source_ids,
    )

    genre_proposal = _robot_genre_proposal(body)
    topology = build_robot_topology(
        body,
        hinted_genre=str(genre_proposal.get("genre") or "generic_mechatronics"),
        machine_project=machine_project,
    )
    topology = topology.model_copy(
        update={
            "metadata": {
                **dict(topology.metadata),
                "robot_genre_proposal": genre_proposal,
                "robot_genre_source": genre_proposal.get("source"),
                "robot_genre_status": genre_proposal.get("status"),
            }
        },
        deep=True,
    )
    analysis = analyze_engineering_candidate(body, topology=topology)
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
        analysis,
        change_impact,
        identity_map,
    )

    native_archetype = _native_archetype(topology, str(plan.get("archetype") or "generic_mechatronics"))
    plan.update(
        {
            "schema_version": ENGINEERING_PLAN_SCHEMA,
            "legacy_intake_schema_version": "hardware_splicer.project_intake.v1",
            "project_intake_truth_schema": "hardware_splicer.project_intake_truth.v1",
            "normalized_intake": body,
            "engineering_context": body.get("engineering_context"),
            "project_mode_proposal": mode_proposal,
            "architecture_truth": architecture_truth,
            "architecture_status": architecture_truth.get("status"),
            "architecture_source": architecture_truth.get("source"),
            "archetype": native_archetype,
            "native_robot_genre": topology.robot_genre.value,
            "robot_genre_proposal": genre_proposal,
            "engineering_source_graph": source_graph.model_dump(mode="json"),
            "reference_sources": source_graph.model_dump(mode="json"),
            "source_conflicts": [row.model_dump(mode="json") for row in source_graph.conflicts],
            "robot_topology": topology.model_dump(mode="json"),
            "engineering_analysis": analysis.model_dump(mode="json"),
            "change_impact": change_impact.model_dump(mode="json"),
            "engineering_identity_map": identity_map,
            "identity_map": identity_map,
            "machine_project": machine_project.model_dump(mode="json"),
            "baseline_revision": change_impact.baseline_revision,
            "candidate_revision": change_impact.candidate_revision,
            "affected_subsystems": change_impact.affected_target_ids,
            "compatibility_impact": [row.model_dump(mode="json") for row in change_impact.impacts],
            "regression_scope": [row.model_dump(mode="json") for row in change_impact.regression_checks],
        }
    )
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
            "engineering_analysis": analysis.model_dump(mode="json"),
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
        "blocking_analysis_findings": len(analysis.blocking_findings),
        "blocking_change_impacts": len(change_impact.blocking_impacts),
        "project_mode_status": mode_proposal.get("status"),
        "architecture_status": architecture_truth.get("status"),
        "architecture_source": architecture_truth.get("source"),
        "power_on_authorized": False,
        "release_authorized": False,
    }
    plan["scenario"] = scenario

    missing = list(plan.get("missing_info") or [])
    missing.extend(_engineering_missing_info(source_graph, topology, analysis, change_impact))
    for question in list(mode_proposal.get("unresolved_questions") or []):
        text = str(question).strip()
        if text:
            missing.append(f"Resolve project mode: {text}")
    for question in list(genre_proposal.get("unresolved_questions") or []):
        text = str(question).strip()
        if text:
            missing.append(f"Resolve robot genre evidence: {text}")
    for question in list(architecture_truth.get("unresolved_questions") or []):
        text = str(question).strip()
        if text:
            missing.append(f"Resolve architecture truth: {text}")
    plan["missing_info"] = list(dict.fromkeys(missing))
    confidence = float(plan.get("planning_confidence") or 0.0)
    confidence -= min(len(source_graph.blocking_conflicts) * 0.05, 0.25)
    confidence -= min(len(source_graph.unresolved_source_ids) * 0.03, 0.15)
    confidence -= min(len(analysis.blocking_findings) * 0.02, 0.2)
    if str(mode_proposal.get("status") or "") == "unresolved":
        confidence -= 0.05
    if str(genre_proposal.get("status") or "") == "unresolved":
        confidence -= 0.05
    if str(architecture_truth.get("status") or "") == "unresolved":
        confidence = min(confidence, 0.25)
    plan["planning_confidence"] = round(max(0.0, min(confidence, 1.0)), 3)
    blocked = bool(
        source_graph.blocking_conflicts
        or analysis.blocking_findings
        or change_impact.blocking_impacts
        or str(mode_proposal.get("status") or "") == "unresolved"
        or str(architecture_truth.get("status") or "") == "unresolved"
    )
    plan["engineering_readiness"] = {
        "status": "blocked" if blocked else "candidate",
        "candidate_machine_synthesized": True,
        "project_mode": body["mode"],
        "project_mode_status": mode_proposal.get("status"),
        "project_mode_source": mode_proposal.get("source"),
        "architecture_status": architecture_truth.get("status"),
        "architecture_source": architecture_truth.get("source"),
        "architecture_build_id": architecture_truth.get("build_id"),
        "native_robot_topology": topology.robot_genre != RobotGenre.GENERIC,
        "robot_genre_status": genre_proposal.get("status"),
        "robot_genre_source": genre_proposal.get("source"),
        "source_provenance_complete": source_graph.source_provenance_complete,
        "blocking_source_conflict_count": len(source_graph.blocking_conflicts),
        "blocking_analysis_finding_count": len(analysis.blocking_findings),
        "blocking_change_impact_count": len(change_impact.blocking_impacts),
        "physical_validation_required": True,
        "power_on_authorized": False,
        "release_authorized": False,
    }
    return plan
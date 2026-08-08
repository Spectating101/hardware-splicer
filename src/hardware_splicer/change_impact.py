"""Cross-domain change and failure impact graph.

The graph connects a requirement change, donor replacement, or field failure to
proposed subsystem effects and regression scope.  Inferences remain proposed until
supported by analysis, measurement, simulation, bench, or field evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .engineering_source_graph import EngineeringSourceGraph
from .machine_project import AuthorityState, MachineProject
from .robot_topology import RobotTopology


CHANGE_IMPACT_SCHEMA = "hardware_splicer.change_impact_graph.v1"


class ChangeMode(str, Enum):
    GREENFIELD = "greenfield"
    MODIFY = "modify"
    REPAIR = "repair"
    FIELD_EVOLUTION = "field_evolution"


class ImpactDomain(str, Enum):
    SYSTEM = "system"
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    FIRMWARE = "firmware"
    SOFTWARE = "software"
    CONTROL = "control"
    SAFETY = "safety"
    SOURCING = "sourcing"
    ASSEMBLY = "assembly"
    VERIFICATION = "verification"


class ImpactSeverity(str, Enum):
    INFO = "info"
    REVIEW = "review"
    BLOCKING = "blocking"
    SAFETY_CRITICAL = "safety_critical"


class ImpactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ChangeTrigger(ImpactModel):
    trigger_id: str = Field(min_length=1)
    trigger_type: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImpactNode(ImpactModel):
    impact_id: str = Field(min_length=1)
    domain: ImpactDomain
    target_id: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    severity: ImpactSeverity = ImpactSeverity.REVIEW
    status: str = "proposed"
    source_trigger_ids: list[str] = Field(default_factory=list)
    verification_target_ids: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImpactEdge(ImpactModel):
    edge_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relationship: str = Field(min_length=1)
    rationale: str = ""
    authority: AuthorityState = AuthorityState.PROPOSED


class RegressionCheck(ImpactModel):
    check_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    target_ids: list[str] = Field(min_length=1)
    method: str = Field(min_length=1)
    acceptance_criteria: Dict[str, Any] = Field(default_factory=dict)
    blocking: bool = True
    status: str = "planned"
    authority: AuthorityState = AuthorityState.PROPOSED


class ChangeImpactGraph(ImpactModel):
    schema_version: str = CHANGE_IMPACT_SCHEMA
    change_id: str = Field(min_length=1)
    mode: ChangeMode
    baseline_project_id: str | None = None
    baseline_revision: str | int | None = None
    candidate_revision: str | int | None = None
    triggers: list[ChangeTrigger] = Field(default_factory=list)
    impacts: list[ImpactNode] = Field(default_factory=list)
    edges: list[ImpactEdge] = Field(default_factory=list)
    regression_checks: list[RegressionCheck] = Field(default_factory=list)
    unresolved: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_references(self) -> "ChangeImpactGraph":
        trigger_ids = [row.trigger_id for row in self.triggers]
        impact_ids = [row.impact_id for row in self.impacts]
        check_ids = [row.check_id for row in self.regression_checks]
        edge_ids = [row.edge_id for row in self.edges]
        for label, values in (
            ("trigger", trigger_ids),
            ("impact", impact_ids),
            ("regression", check_ids),
            ("edge", edge_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} identifier")
        graph_ids = set(trigger_ids) | set(impact_ids) | set(check_ids)
        for impact in self.impacts:
            missing = sorted(set(impact.source_trigger_ids) - set(trigger_ids))
            if missing:
                raise ValueError(f"impact {impact.impact_id!r} references unknown triggers: {missing}")
        for edge in self.edges:
            if edge.source_id not in graph_ids or edge.target_id not in graph_ids:
                raise ValueError(f"impact edge {edge.edge_id!r} references unknown graph object")
        return self

    @property
    def affected_domains(self) -> list[str]:
        return sorted({row.domain.value for row in self.impacts})

    @property
    def affected_target_ids(self) -> list[str]:
        return sorted({row.target_id for row in self.impacts})

    @property
    def blocking_impacts(self) -> list[ImpactNode]:
        return [
            row
            for row in self.impacts
            if row.severity in {ImpactSeverity.BLOCKING, ImpactSeverity.SAFETY_CRITICAL}
        ]


_DOMAIN_TARGETS: dict[ImpactDomain, str] = {
    ImpactDomain.SYSTEM: "system",
    ImpactDomain.MECHANICAL: "mechanical-structure",
    ImpactDomain.ELECTRICAL: "power-system",
    ImpactDomain.FIRMWARE: "firmware-control",
    ImpactDomain.SOFTWARE: "software-control",
    ImpactDomain.CONTROL: "control-stack",
    ImpactDomain.SAFETY: "safety-case",
    ImpactDomain.SOURCING: "sourcing",
    ImpactDomain.ASSEMBLY: "assembly",
    ImpactDomain.VERIFICATION: "verification",
}


def _stable_id(prefix: str, *values: Any) -> str:
    rendered = json.dumps(values, sort_keys=True, default=str, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(rendered.encode('utf-8')).hexdigest()[:12]}"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _text(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{key} {item}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_text(item) for item in value)
    return str(value or "")


def _mode(intake: Mapping[str, Any]) -> ChangeMode:
    """Resolve change mode with explicit structured mode taking precedence over prose.

    Engineering Planner now persists a provenance-aware project mode before change-impact
    analysis. Once that explicit mode exists, this layer must not silently reinterpret it
    because the goal happens to contain words such as "repair", "brownout", or "upgrade".
    The historical prose fallback remains only for direct legacy callers that provide no
    explicit mode.
    """
    explicit = str(intake.get("mode") or intake.get("project_mode") or "").strip().lower()
    explicit_modes = {
        "greenfield": ChangeMode.GREENFIELD,
        "modify": ChangeMode.MODIFY,
        "modification": ChangeMode.MODIFY,
        "repair": ChangeMode.REPAIR,
        "evolve": ChangeMode.FIELD_EVOLUTION,
        "field_evolution": ChangeMode.FIELD_EVOLUTION,
    }
    if explicit in explicit_modes:
        return explicit_modes[explicit]

    # Structured project facts remain stronger than free-form prose for direct callers.
    if intake.get("field_failure"):
        return ChangeMode.FIELD_EVOLUTION
    if intake.get("repair") or intake.get("salvage_mode"):
        return ChangeMode.REPAIR
    if intake.get("baseline_project") or intake.get("baseline_revision") is not None:
        return ChangeMode.MODIFY

    # Legacy compatibility only: callers without an explicit/structured mode may still
    # be classified from prose. This result remains a proposed impact-analysis input.
    goal = _text(intake.get("goal") or intake.get("intent")).lower()
    if "field failure" in goal:
        return ChangeMode.FIELD_EVOLUTION
    if any(token in goal for token in ("repair", "recover", "donor", "splice")):
        return ChangeMode.REPAIR
    if any(token in goal for token in ("modify", "upgrade", "add a", "replace")):
        return ChangeMode.MODIFY
    return ChangeMode.GREENFIELD


def _source_ids(source_graph: EngineeringSourceGraph | None, tokens: Sequence[str]) -> list[str]:
    if source_graph is None:
        return []
    wanted = [token.lower() for token in tokens]
    matches: list[str] = []
    for source in source_graph.sources:
        haystack = " ".join(
            [source.source_id, source.source_type.value, source.uri or "", source.revision or ""]
        ).lower()
        if not wanted or any(token in haystack for token in wanted):
            matches.append(source.source_id)
    return matches


def _trigger_rows(intake: Mapping[str, Any], source_graph: EngineeringSourceGraph | None) -> list[ChangeTrigger]:
    rows: list[ChangeTrigger] = []
    candidates = [
        ("change_request", intake.get("change_request")),
        ("field_failure", intake.get("field_failure")),
        ("repair_request", intake.get("repair")),
        ("goal", intake.get("goal") or intake.get("intent")),
    ]
    observations = intake.get("observations") or intake.get("field_observations") or []
    if isinstance(observations, Mapping):
        candidates.extend((f"observation_{key}", value) for key, value in observations.items())
    elif isinstance(observations, list):
        candidates.extend((f"observation_{index + 1}", value) for index, value in enumerate(observations))
    telemetry = intake.get("telemetry") or intake.get("measurements") or []
    if isinstance(telemetry, Mapping):
        candidates.extend((f"measurement_{key}", value) for key, value in telemetry.items())
    elif isinstance(telemetry, list):
        candidates.extend((f"measurement_{index + 1}", value) for index, value in enumerate(telemetry))

    seen: set[str] = set()
    for trigger_type, value in candidates:
        statement = _text(value).strip()
        if not statement or statement.lower() in seen:
            continue
        seen.add(statement.lower())
        measured = trigger_type.startswith("measurement")
        observed = trigger_type.startswith("observation") or trigger_type == "field_failure"
        authority = AuthorityState.MEASURED if measured else AuthorityState.OBSERVED if observed else AuthorityState.DECLARED
        tokens = re.findall(r"[a-zA-Z0-9_.-]+", statement.lower())[:8]
        rows.append(
            ChangeTrigger(
                trigger_id=_stable_id("trigger", trigger_type, statement),
                trigger_type=trigger_type,
                statement=statement,
                source_ids=_source_ids(source_graph, tokens),
                authority=authority,
            )
        )
    return rows


def _inferred_domains(text: str, mode: ChangeMode) -> set[ImpactDomain]:
    lowered = text.lower()
    domains: set[ImpactDomain] = {ImpactDomain.SYSTEM, ImpactDomain.VERIFICATION}
    keyword_map = {
        ImpactDomain.MECHANICAL: (
            "payload", "mass", "weight", "mast", "mount", "bracket", "tip", "tipping",
            "center of mass", "clearance", "collision", "frame", "wheel", "motor mismatch",
            "vibration", "gear", "joint", "arm", "leg",
        ),
        ImpactDomain.ELECTRICAL: (
            "brownout", "voltage", "current", "power", "battery", "rail", "regulator",
            "driver", "burned", "connector", "wire", "motor", "sensor deck",
        ),
        ImpactDomain.FIRMWARE: (
            "firmware", "binary", "flash", "pin", "driver", "reset", "calibration", "mcu",
            "controller", "sensor deck",
        ),
        ImpactDomain.SOFTWARE: (
            "ros", "nav2", "moveit", "urdf", "topic", "service", "dataset", "perception",
            "camera", "lidar", "navigation",
        ),
        ImpactDomain.CONTROL: (
            "stability", "gait", "pid", "control", "tipping", "payload", "motor mismatch",
            "odometry", "flight", "trajectory", "inverse kinematics",
        ),
        ImpactDomain.SAFETY: (
            "tip", "tipping", "brownout", "burned", "first motion", "emergency", "flight",
            "collision", "overcurrent", "unknown", "field failure",
        ),
        ImpactDomain.SOURCING: (
            "replace", "replacement", "procure", "unavailable", "donor", "mismatch", "burned",
        ),
        ImpactDomain.ASSEMBLY: (
            "mount", "wiring", "connector", "replace", "repair", "assembly", "cable", "routing",
        ),
    }
    for domain, tokens in keyword_map.items():
        if any(token in lowered for token in tokens):
            domains.add(domain)
    if mode in {ChangeMode.MODIFY, ChangeMode.REPAIR, ChangeMode.FIELD_EVOLUTION}:
        domains.update({ImpactDomain.SAFETY, ImpactDomain.ASSEMBLY})
    return domains


def _target_for_domain(
    domain: ImpactDomain,
    machine_project: MachineProject | None,
    topology: RobotTopology | None,
    text: str,
) -> str:
    lowered = text.lower()
    if topology is not None:
        if domain == ImpactDomain.MECHANICAL:
            if "payload" in lowered or "mast" in lowered or "mount" in lowered:
                return topology.root_link_id
            if "joint" in lowered or "arm" in lowered or "leg" in lowered:
                return topology.joints[0].joint_id if topology.joints else topology.root_link_id
        if domain == ImpactDomain.CONTROL:
            return topology.topology_id
        if domain == ImpactDomain.ELECTRICAL and topology.actuators:
            return topology.actuators[0].electrical_component_id or topology.actuators[0].actuator_id
        if domain == ImpactDomain.SOFTWARE and topology.sensors:
            return topology.sensors[0].sensor_id
    if machine_project is not None:
        preferred = _DOMAIN_TARGETS[domain]
        if any(row.subsystem_id == preferred for row in machine_project.subsystems):
            return preferred
        domain_alias = {
            ImpactDomain.MECHANICAL: "mechanical",
            ImpactDomain.ELECTRICAL: "electrical",
            ImpactDomain.FIRMWARE: "firmware",
            ImpactDomain.SOFTWARE: "software",
        }.get(domain)
        if domain_alias:
            for subsystem in machine_project.subsystems:
                if subsystem.domain.value == domain_alias:
                    return subsystem.subsystem_id
        return machine_project.project_id
    return _DOMAIN_TARGETS[domain]


def _effect(domain: ImpactDomain, trigger_text: str, mode: ChangeMode) -> str:
    subject = trigger_text[:180]
    templates = {
        ImpactDomain.SYSTEM: f"Re-evaluate system requirements and release envelope after: {subject}",
        ImpactDomain.MECHANICAL: f"Recalculate fit, load path, mass properties, clearances, and structural margins after: {subject}",
        ImpactDomain.ELECTRICAL: f"Recalculate rail voltage, peak/continuous current, protection, wiring, and connector margins after: {subject}",
        ImpactDomain.FIRMWARE: f"Review pin map, configuration, calibration, fault handling, build, flash, and binary lineage after: {subject}",
        ImpactDomain.SOFTWARE: f"Review model, middleware, transforms, topics, services, and application behavior after: {subject}",
        ImpactDomain.CONTROL: f"Re-tune and revalidate control, stability, kinematics, odometry, or trajectory assumptions after: {subject}",
        ImpactDomain.SAFETY: f"Block unrestricted operation until hazards and safe-stop behavior are revalidated after: {subject}",
        ImpactDomain.SOURCING: f"Verify replacement identity, package, rating, availability, and revision compatibility after: {subject}",
        ImpactDomain.ASSEMBLY: f"Revise assembly, cable routing, fastening, access, and repair instructions after: {subject}",
        ImpactDomain.VERIFICATION: f"Define regression evidence and acceptance criteria for every affected domain after: {subject}",
    }
    return templates[domain]


def _severity(domain: ImpactDomain, text: str, mode: ChangeMode) -> ImpactSeverity:
    lowered = text.lower()
    if domain == ImpactDomain.SAFETY or any(token in lowered for token in ("tipping", "brownout", "burned", "flight", "overcurrent")):
        return ImpactSeverity.SAFETY_CRITICAL if domain == ImpactDomain.SAFETY else ImpactSeverity.BLOCKING
    if mode == ChangeMode.FIELD_EVOLUTION:
        return ImpactSeverity.BLOCKING
    return ImpactSeverity.REVIEW


def _regression_check(domain: ImpactDomain, target_id: str, change_id: str) -> RegressionCheck:
    methods = {
        ImpactDomain.SYSTEM: ("Requirements and release review", "review"),
        ImpactDomain.MECHANICAL: ("Measured fit, load, clearance, mass-property, and stability check", "measurement_and_test"),
        ImpactDomain.ELECTRICAL: ("Current-limited rail, startup, transient, and protection test", "bench_test"),
        ImpactDomain.FIRMWARE: ("Reproducible build, binary hash, flash, configuration, and fault test", "build_flash_test"),
        ImpactDomain.SOFTWARE: ("Interface, transform, simulation, and application regression", "simulation_and_integration_test"),
        ImpactDomain.CONTROL: ("Tethered or bounded motion/control regression", "bounded_motion_test"),
        ImpactDomain.SAFETY: ("Emergency stop, fault containment, and safe-state demonstration", "safety_demonstration"),
        ImpactDomain.SOURCING: ("Part identity and rating reconciliation", "inspection"),
        ImpactDomain.ASSEMBLY: ("Assembly, fastening, cable, and serviceability inspection", "inspection"),
        ImpactDomain.VERIFICATION: ("Evidence completeness and scoped release review", "review"),
    }
    name, method = methods[domain]
    return RegressionCheck(
        check_id=_stable_id("regression", change_id, domain.value, target_id),
        name=name,
        target_ids=[target_id],
        method=method,
        acceptance_criteria={"status": "pass", "evidence_required": True, "scope": domain.value},
        blocking=True,
    )


def build_change_impact_graph(
    intake: Mapping[str, Any],
    *,
    machine_project: MachineProject | None = None,
    topology: RobotTopology | None = None,
    source_graph: EngineeringSourceGraph | None = None,
    baseline_project: Mapping[str, Any] | MachineProject | None = None,
) -> ChangeImpactGraph:
    body = dict(intake or {})
    mode = _mode(body)
    baseline_body: Mapping[str, Any]
    if isinstance(baseline_project, MachineProject):
        baseline_body = baseline_project.model_dump(mode="json")
    else:
        baseline_body = baseline_project if isinstance(baseline_project, Mapping) else _mapping(body.get("baseline_project"))
    baseline_project_id = str(
        baseline_body.get("project_id")
        or body.get("baseline_project_id")
        or (machine_project.project_id if machine_project and mode != ChangeMode.GREENFIELD else "")
    ).strip() or None
    baseline_revision = (
        body.get("baseline_revision")
        if body.get("baseline_revision") is not None
        else baseline_body.get("revision", baseline_body.get("revision_id"))
    )
    candidate_revision = body.get("candidate_revision")
    change_id = _stable_id(
        "change",
        baseline_project_id,
        baseline_revision,
        body.get("goal"),
        body.get("change_request"),
        body.get("field_failure"),
    )
    triggers = _trigger_rows(body, source_graph)
    combined_text = " ".join(row.statement for row in triggers)
    domains = _inferred_domains(combined_text, mode)
    if mode != ChangeMode.GREENFIELD and baseline_revision is None:
        # Without a pinned baseline the existing wiring, pin contracts, and power
        # distribution are unknown. Conservatively require electrical review rather
        # than inferring that a visually mechanical or software-facing change is
        # electrically isolated.
        domains.add(ImpactDomain.ELECTRICAL)

    impacts: list[ImpactNode] = []
    checks: list[RegressionCheck] = []
    edges: list[ImpactEdge] = []
    for domain in sorted(domains, key=lambda value: value.value):
        target_id = _target_for_domain(domain, machine_project, topology, combined_text)
        impact_id = _stable_id("impact", change_id, domain.value, target_id, combined_text)
        impact = ImpactNode(
            impact_id=impact_id,
            domain=domain,
            target_id=target_id,
            effect=_effect(domain, combined_text, mode),
            severity=_severity(domain, combined_text, mode),
            source_trigger_ids=[row.trigger_id for row in triggers],
            verification_target_ids=[],
            metadata={"inference_basis": "keyword_and_topology_projection", "requires_engineering_review": True},
        )
        check = _regression_check(domain, target_id, change_id)
        impact.verification_target_ids = [check.check_id]
        impacts.append(impact)
        checks.append(check)
        for trigger in triggers:
            edges.append(
                ImpactEdge(
                    edge_id=_stable_id("edge", trigger.trigger_id, impact_id),
                    source_id=trigger.trigger_id,
                    target_id=impact_id,
                    relationship="may_affect",
                    rationale=f"{trigger.trigger_type} indicates a possible {domain.value} consequence.",
                )
            )
        edges.append(
            ImpactEdge(
                edge_id=_stable_id("edge", impact_id, check.check_id),
                source_id=impact_id,
                target_id=check.check_id,
                relationship="requires_regression",
                rationale="Proposed impacts require scoped verification before authority can be restored.",
            )
        )

    unresolved: list[Dict[str, Any]] = []
    if mode != ChangeMode.GREENFIELD and baseline_revision is None:
        unresolved.append({"field": "baseline_revision", "reason": "A modification, repair, or field evolution requires a pinned baseline revision."})
    if not triggers:
        unresolved.append({"field": "change_trigger", "reason": "No explicit change request, repair description, or failure evidence was supplied."})
    if mode == ChangeMode.FIELD_EVOLUTION and source_graph and not any(
        source.source_type.value in {"measurement", "telemetry", "test_log", "operator_observation"}
        for source in source_graph.sources
    ):
        unresolved.append({"field": "field_evidence", "reason": "Field evolution should attach measurements, telemetry, logs, or observations."})

    return ChangeImpactGraph(
        change_id=change_id,
        mode=mode,
        baseline_project_id=baseline_project_id,
        baseline_revision=baseline_revision,
        candidate_revision=candidate_revision,
        triggers=triggers,
        impacts=impacts,
        edges=edges,
        regression_checks=checks,
        unresolved=unresolved,
        metadata={
            "candidate_only": True,
            "impact_analysis_authority": AuthorityState.PROPOSED.value,
            "affected_domains": sorted(domain.value for domain in domains),
            "blocking_impact_count": sum(
                row.severity in {ImpactSeverity.BLOCKING, ImpactSeverity.SAFETY_CRITICAL}
                for row in impacts
            ),
            "release_authority_preserved": mode == ChangeMode.GREENFIELD,
        },
    )
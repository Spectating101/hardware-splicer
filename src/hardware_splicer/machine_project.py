"""Canonical cross-discipline machine project model.

This module is the semantic spine for Hardware Splicer as a machinery-engineering
platform.  PCB, mechanical, firmware, sourcing, assembly, splice, and bench data
remain discipline payloads attached to one traceable machine project rather than
becoming competing project formats.

The model is deliberately conservative about authority: importing or composing
state never upgrades a claim.  Release assessment reports blockers; it does not
silently promote a project to build-ready or operationally authorized.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


MACHINE_PROJECT_SCHEMA = "hardware_splicer.machine_project.v1"


class Domain(str, Enum):
    SYSTEM = "system"
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    FIRMWARE = "firmware"
    SOFTWARE = "software"
    SOURCING = "sourcing"
    ASSEMBLY = "assembly"
    VERIFICATION = "verification"


class AuthorityState(str, Enum):
    UNKNOWN = "unknown"
    PROPOSED = "proposed"
    DECLARED = "declared"
    OBSERVED = "observed"
    MEASURED = "measured"
    VERIFIED = "verified"
    AUTHORIZED = "authorized"


class LifecycleState(str, Enum):
    INTAKE = "intake"
    ARCHITECTURE = "architecture"
    DESIGN = "design"
    VERIFY = "verify"
    BENCH = "bench"
    PACKAGE = "package"


class ReleaseState(str, Enum):
    CONCEPT = "concept"
    DESIGN_READY = "design_ready"
    BUILD_READY = "build_ready"
    BENCH_READY = "bench_ready"
    OPERATIONALLY_AUTHORIZED = "operationally_authorized"


class RequirementKind(str, Enum):
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    SAFETY = "safety"
    INTERFACE = "interface"
    CONSTRAINT = "constraint"


class VerificationStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class VerificationType(str, Enum):
    ANALYSIS = "analysis"
    INSPECTION = "inspection"
    TEST = "test"
    DEMONSTRATION = "demonstration"


class ComponentSource(str, Enum):
    NEW = "new"
    DONOR = "donor"
    GENERATED = "generated"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class MachineBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ArtifactRef(MachineBaseModel):
    artifact_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    authority: AuthorityState = AuthorityState.UNKNOWN
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Requirement(MachineBaseModel):
    requirement_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    kind: RequirementKind = RequirementKind.FUNCTIONAL
    priority: str = "should"
    source: str = "user"
    parent_requirement_id: str | None = None
    allocated_to: list[str] = Field(default_factory=list)
    verification_method_ids: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Function(MachineBaseModel):
    function_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    parent_function_id: str | None = None
    allocated_subsystem_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Subsystem(MachineBaseModel):
    subsystem_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domain: Domain
    purpose: str = ""
    parent_subsystem_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    function_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    interface_ids: list[str] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PartIdentity(MachineBaseModel):
    manufacturer: str | None = None
    manufacturer_part_number: str | None = None
    supplier: str | None = None
    supplier_part_number: str | None = None
    package: str | None = None
    symbol_ref: str | None = None
    footprint_ref: str | None = None
    datasheet_ref: str | None = None
    provenance: str | None = None


class Component(MachineBaseModel):
    component_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domain: Domain
    subsystem_id: str
    role: str = ""
    source: ComponentSource = ComponentSource.UNKNOWN
    part: PartIdentity | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    function_ids: list[str] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InterfaceEndpoint(MachineBaseModel):
    object_id: str = Field(min_length=1)
    port: str = Field(min_length=1)
    role: str = ""


class InterfaceContract(MachineBaseModel):
    contract_type: str = Field(min_length=1)
    values: Dict[str, Any] = Field(default_factory=dict)
    unresolved_fields: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.UNKNOWN

    @model_validator(mode="after")
    def unresolved_contract_cannot_be_authorized(self) -> "InterfaceContract":
        if self.unresolved_fields and self.authority in {
            AuthorityState.VERIFIED,
            AuthorityState.AUTHORIZED,
        }:
            raise ValueError("an interface contract with unresolved fields cannot be verified or authorized")
        return self


class Interface(MachineBaseModel):
    interface_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    endpoints: list[InterfaceEndpoint] = Field(min_length=2)
    contracts: list[InterfaceContract] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    verification_method_ids: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.UNKNOWN
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unresolved_interface_cannot_be_authorized(self) -> "Interface":
        unresolved = any(contract.unresolved_fields for contract in self.contracts)
        if unresolved and self.authority in {AuthorityState.VERIFIED, AuthorityState.AUTHORIZED}:
            raise ValueError("an interface with unresolved contracts cannot be verified or authorized")
        return self


class Constraint(MachineBaseModel):
    constraint_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domain: Domain
    statement: str = Field(min_length=1)
    severity: str = "required"
    applies_to: list[str] = Field(default_factory=list)
    source_requirement_ids: list[str] = Field(default_factory=list)
    verification_method_ids: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvidenceRef(MachineBaseModel):
    evidence_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    ref: str | None = None
    supports: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.UNKNOWN
    simulated: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def simulated_evidence_cannot_authorize_physical_state(self) -> "EvidenceRef":
        if self.simulated and self.authority in {AuthorityState.MEASURED, AuthorityState.AUTHORIZED}:
            raise ValueError("simulated evidence cannot be measured physical evidence or operational authorization")
        return self


class VerificationMethod(MachineBaseModel):
    verification_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    method_type: VerificationType
    status: VerificationStatus = VerificationStatus.PLANNED
    requirement_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    procedure: str = ""
    acceptance_criteria: Dict[str, Any] = Field(default_factory=dict)
    authority: AuthorityState = AuthorityState.PROPOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def passed_verification_requires_evidence(self) -> "VerificationMethod":
        if self.status == VerificationStatus.PASSED and not self.evidence_ids:
            raise ValueError("a passed verification method must reference evidence")
        return self


class TraceabilityIssue(MachineBaseModel):
    code: str
    message: str
    object_id: str | None = None
    severity: str = "error"


class ReleaseAssessment(MachineBaseModel):
    requested_state: ReleaseState
    achieved_state: ReleaseState
    blockers: list[TraceabilityIssue] = Field(default_factory=list)
    warnings: list[TraceabilityIssue] = Field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return not self.blockers and self.achieved_state == self.requested_state


class MachineProject(MachineBaseModel):
    schema_version: str = MACHINE_PROJECT_SCHEMA
    project_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    lifecycle_state: LifecycleState = LifecycleState.INTAKE
    requested_release_state: ReleaseState = ReleaseState.CONCEPT
    requirements: list[Requirement] = Field(default_factory=list)
    functions: list[Function] = Field(default_factory=list)
    subsystems: list[Subsystem] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    interfaces: list[Interface] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    verifications: list[VerificationMethod] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    discipline_payloads: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_references(self) -> "MachineProject":
        issues = traceability_issues(self)
        reference_errors = [issue for issue in issues if issue.code.startswith("invalid_ref") or issue.code == "duplicate_id"]
        if reference_errors:
            rendered = "; ".join(issue.message for issue in reference_errors)
            raise ValueError(rendered)
        return self

    def traceability_issues(self) -> list[TraceabilityIssue]:
        return traceability_issues(self)

    def assess_release(self, requested: ReleaseState | None = None) -> ReleaseAssessment:
        return assess_release(self, requested=requested)


_COLLECTION_ID_FIELDS: tuple[tuple[str, str], ...] = (
    ("requirements", "requirement_id"),
    ("functions", "function_id"),
    ("subsystems", "subsystem_id"),
    ("components", "component_id"),
    ("interfaces", "interface_id"),
    ("constraints", "constraint_id"),
    ("verifications", "verification_id"),
    ("evidence", "evidence_id"),
    ("artifacts", "artifact_id"),
)


def _ids(rows: Sequence[Any], field: str) -> set[str]:
    return {str(getattr(row, field)) for row in rows}


def _all_object_ids(project: MachineProject) -> set[str]:
    values = {project.project_id}
    for collection_name, field_name in _COLLECTION_ID_FIELDS:
        values.update(_ids(getattr(project, collection_name), field_name))
    for subsystem in project.subsystems:
        values.update(ref.artifact_id for ref in subsystem.artifact_refs)
    for component in project.components:
        values.update(ref.artifact_id for ref in component.artifact_refs)
    return values


def _append_invalid_refs(
    issues: list[TraceabilityIssue],
    *,
    object_id: str,
    field: str,
    values: Iterable[str],
    valid: set[str],
) -> None:
    for value in values:
        if value not in valid:
            issues.append(
                TraceabilityIssue(
                    code="invalid_ref",
                    object_id=object_id,
                    message=f"{object_id}.{field} references unknown object {value!r}",
                )
            )


def traceability_issues(project: MachineProject) -> list[TraceabilityIssue]:
    issues: list[TraceabilityIssue] = []
    seen: dict[str, str] = {project.project_id: "project"}

    for collection_name, field_name in _COLLECTION_ID_FIELDS:
        for row in getattr(project, collection_name):
            value = str(getattr(row, field_name))
            if value in seen:
                issues.append(
                    TraceabilityIssue(
                        code="duplicate_id",
                        object_id=value,
                        message=f"identifier {value!r} is used by both {seen[value]} and {collection_name}",
                    )
                )
            else:
                seen[value] = collection_name

    requirement_ids = _ids(project.requirements, "requirement_id")
    function_ids = _ids(project.functions, "function_id")
    subsystem_ids = _ids(project.subsystems, "subsystem_id")
    component_ids = _ids(project.components, "component_id")
    interface_ids = _ids(project.interfaces, "interface_id")
    verification_ids = _ids(project.verifications, "verification_id")
    evidence_ids = _ids(project.evidence, "evidence_id")
    all_ids = _all_object_ids(project)
    endpoint_ids = {project.project_id, *subsystem_ids, *component_ids}

    for requirement in project.requirements:
        if requirement.parent_requirement_id:
            _append_invalid_refs(
                issues,
                object_id=requirement.requirement_id,
                field="parent_requirement_id",
                values=[requirement.parent_requirement_id],
                valid=requirement_ids,
            )
        _append_invalid_refs(
            issues,
            object_id=requirement.requirement_id,
            field="allocated_to",
            values=requirement.allocated_to,
            valid=all_ids,
        )
        _append_invalid_refs(
            issues,
            object_id=requirement.requirement_id,
            field="verification_method_ids",
            values=requirement.verification_method_ids,
            valid=verification_ids,
        )

    for function in project.functions:
        if function.parent_function_id:
            _append_invalid_refs(
                issues,
                object_id=function.function_id,
                field="parent_function_id",
                values=[function.parent_function_id],
                valid=function_ids,
            )
        _append_invalid_refs(
            issues,
            object_id=function.function_id,
            field="allocated_subsystem_ids",
            values=function.allocated_subsystem_ids,
            valid=subsystem_ids,
        )
        _append_invalid_refs(
            issues,
            object_id=function.function_id,
            field="requirement_ids",
            values=function.requirement_ids,
            valid=requirement_ids,
        )

    for subsystem in project.subsystems:
        if subsystem.parent_subsystem_id:
            _append_invalid_refs(
                issues,
                object_id=subsystem.subsystem_id,
                field="parent_subsystem_id",
                values=[subsystem.parent_subsystem_id],
                valid=subsystem_ids,
            )
        _append_invalid_refs(issues, object_id=subsystem.subsystem_id, field="requirement_ids", values=subsystem.requirement_ids, valid=requirement_ids)
        _append_invalid_refs(issues, object_id=subsystem.subsystem_id, field="function_ids", values=subsystem.function_ids, valid=function_ids)
        _append_invalid_refs(issues, object_id=subsystem.subsystem_id, field="component_ids", values=subsystem.component_ids, valid=component_ids)
        _append_invalid_refs(issues, object_id=subsystem.subsystem_id, field="interface_ids", values=subsystem.interface_ids, valid=interface_ids)

    for component in project.components:
        _append_invalid_refs(issues, object_id=component.component_id, field="subsystem_id", values=[component.subsystem_id], valid=subsystem_ids)
        _append_invalid_refs(issues, object_id=component.component_id, field="requirement_ids", values=component.requirement_ids, valid=requirement_ids)
        _append_invalid_refs(issues, object_id=component.component_id, field="function_ids", values=component.function_ids, valid=function_ids)

    for interface in project.interfaces:
        _append_invalid_refs(
            issues,
            object_id=interface.interface_id,
            field="endpoints",
            values=[endpoint.object_id for endpoint in interface.endpoints],
            valid=endpoint_ids,
        )
        _append_invalid_refs(issues, object_id=interface.interface_id, field="requirement_ids", values=interface.requirement_ids, valid=requirement_ids)
        _append_invalid_refs(issues, object_id=interface.interface_id, field="verification_method_ids", values=interface.verification_method_ids, valid=verification_ids)

    for constraint in project.constraints:
        _append_invalid_refs(issues, object_id=constraint.constraint_id, field="applies_to", values=constraint.applies_to, valid=all_ids)
        _append_invalid_refs(issues, object_id=constraint.constraint_id, field="source_requirement_ids", values=constraint.source_requirement_ids, valid=requirement_ids)
        _append_invalid_refs(issues, object_id=constraint.constraint_id, field="verification_method_ids", values=constraint.verification_method_ids, valid=verification_ids)

    for verification in project.verifications:
        _append_invalid_refs(issues, object_id=verification.verification_id, field="requirement_ids", values=verification.requirement_ids, valid=requirement_ids)
        _append_invalid_refs(issues, object_id=verification.verification_id, field="target_ids", values=verification.target_ids, valid=all_ids)
        _append_invalid_refs(issues, object_id=verification.verification_id, field="evidence_ids", values=verification.evidence_ids, valid=evidence_ids)

    for evidence in project.evidence:
        _append_invalid_refs(issues, object_id=evidence.evidence_id, field="supports", values=evidence.supports, valid=all_ids)

    for requirement in project.requirements:
        if not requirement.verification_method_ids:
            issues.append(
                TraceabilityIssue(
                    code="unverified_requirement",
                    object_id=requirement.requirement_id,
                    message=f"requirement {requirement.requirement_id!r} has no verification method",
                    severity="warning" if requirement.kind != RequirementKind.SAFETY else "error",
                )
            )

    for interface in project.interfaces:
        unresolved = sorted({field for contract in interface.contracts for field in contract.unresolved_fields})
        if unresolved:
            issues.append(
                TraceabilityIssue(
                    code="unresolved_interface",
                    object_id=interface.interface_id,
                    message=f"interface {interface.interface_id!r} has unresolved fields: {', '.join(unresolved)}",
                )
            )

    return issues


def assess_release(project: MachineProject, requested: ReleaseState | None = None) -> ReleaseAssessment:
    target = requested or project.requested_release_state
    issues = traceability_issues(project)
    blockers = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity != "error"]

    verification_by_id = {row.verification_id: row for row in project.verifications}
    safety_requirements = [row for row in project.requirements if row.kind == RequirementKind.SAFETY]
    for requirement in safety_requirements:
        methods = [verification_by_id[value] for value in requirement.verification_method_ids if value in verification_by_id]
        if not methods or any(method.status != VerificationStatus.PASSED for method in methods):
            blockers.append(
                TraceabilityIssue(
                    code="safety_not_closed",
                    object_id=requirement.requirement_id,
                    message=f"safety requirement {requirement.requirement_id!r} is not closed by passing verification",
                )
            )

    failed = [row for row in project.verifications if row.status in {VerificationStatus.FAILED, VerificationStatus.BLOCKED}]
    blockers.extend(
        TraceabilityIssue(
            code="verification_not_passed",
            object_id=row.verification_id,
            message=f"verification {row.verification_id!r} is {row.status.value}",
        )
        for row in failed
    )

    physical_evidence = [row for row in project.evidence if not row.simulated and row.authority in {AuthorityState.MEASURED, AuthorityState.VERIFIED, AuthorityState.AUTHORIZED}]
    all_required_passed = bool(project.verifications) and all(row.status == VerificationStatus.PASSED for row in project.verifications)

    achieved = ReleaseState.CONCEPT
    if not any(issue.code.startswith("invalid_ref") or issue.code == "duplicate_id" for issue in blockers):
        achieved = ReleaseState.DESIGN_READY
    if achieved == ReleaseState.DESIGN_READY and not any(issue.code in {"unresolved_interface", "unverified_requirement"} for issue in blockers):
        achieved = ReleaseState.BUILD_READY
    if achieved == ReleaseState.BUILD_READY and all_required_passed:
        achieved = ReleaseState.BENCH_READY
    if achieved == ReleaseState.BENCH_READY and physical_evidence and not blockers:
        achieved = ReleaseState.OPERATIONALLY_AUTHORIZED

    order = list(ReleaseState)
    if order.index(achieved) < order.index(target):
        blockers.append(
            TraceabilityIssue(
                code="release_state_not_reached",
                object_id=project.project_id,
                message=f"requested {target.value}, but evidence supports only {achieved.value}",
            )
        )

    return ReleaseAssessment(
        requested_state=target,
        achieved_state=achieved,
        blockers=blockers,
        warnings=warnings,
    )


def _legacy_stage(value: Any) -> LifecycleState:
    raw = str(value or "intake").lower()
    try:
        return LifecycleState(raw)
    except ValueError:
        return LifecycleState.DESIGN


def _node_id(node: Mapping[str, Any], index: int) -> str:
    value = str(node.get("id") or node.get("module_id") or node.get("name") or f"node-{index + 1}")
    return value.replace(" ", "-")


def machine_project_from_session(session: Mapping[str, Any]) -> MachineProject:
    """Lift the current circuit-centric session into a machine project without authority promotion.

    The complete legacy session is retained under ``discipline_payloads.splice_session``.
    Graph nodes become proposed electrical components, and graph edges become unknown
    electrical interfaces.  Donor or bench data is preserved but never converted into
    authorization merely because the project was migrated.
    """

    project_id = str(session.get("projectId") or session.get("project_id") or "machine-project")
    name = str(session.get("projectName") or session.get("project_name") or "Untitled machine")
    purpose = str(session.get("goal") or (session.get("graph") or {}).get("phrase") or name)
    graph = session.get("graph") if isinstance(session.get("graph"), Mapping) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []

    root_subsystem = Subsystem(
        subsystem_id="electrical-system",
        name="Electrical system",
        domain=Domain.ELECTRICAL,
        purpose="Migrated circuit and carrier design workspace",
        authority=AuthorityState.PROPOSED,
    )

    components: list[Component] = []
    component_ids: list[str] = []
    for index, raw_node in enumerate(nodes):
        node = raw_node if isinstance(raw_node, Mapping) else {"name": str(raw_node)}
        component_id = _node_id(node, index)
        component_ids.append(component_id)
        data = node.get("data") if isinstance(node.get("data"), Mapping) else {}
        label = str(data.get("label") or node.get("label") or node.get("name") or component_id)
        components.append(
            Component(
                component_id=component_id,
                name=label,
                domain=Domain.ELECTRICAL,
                subsystem_id=root_subsystem.subsystem_id,
                role=str(data.get("role") or node.get("type") or "migrated circuit node"),
                source=ComponentSource.UNKNOWN,
                authority=AuthorityState.PROPOSED,
                metadata={"legacy_node": dict(node)},
            )
        )

    interfaces: list[Interface] = []
    interface_ids: list[str] = []
    known_components = set(component_ids)
    for index, raw_edge in enumerate(edges):
        edge = raw_edge if isinstance(raw_edge, Mapping) else {}
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in known_components or target not in known_components:
            continue
        interface_id = str(edge.get("id") or f"interface-{index + 1}")
        interface_ids.append(interface_id)
        interfaces.append(
            Interface(
                interface_id=interface_id,
                name=str(edge.get("label") or f"{source} to {target}"),
                kind="electrical",
                endpoints=[
                    InterfaceEndpoint(object_id=source, port=str(edge.get("sourceHandle") or "unresolved")),
                    InterfaceEndpoint(object_id=target, port=str(edge.get("targetHandle") or "unresolved")),
                ],
                contracts=[
                    InterfaceContract(
                        contract_type="electrical",
                        unresolved_fields=["pin_mapping", "voltage_domain", "direction"],
                        authority=AuthorityState.UNKNOWN,
                    )
                ],
                authority=AuthorityState.UNKNOWN,
                metadata={"legacy_edge": dict(edge)},
            )
        )

    root_subsystem.component_ids = component_ids
    root_subsystem.interface_ids = interface_ids

    artifacts: list[ArtifactRef] = []
    build_dir = session.get("buildDir") or session.get("build_dir")
    if build_dir:
        artifacts.append(
            ArtifactRef(
                artifact_id="legacy-build-dir",
                kind="build_directory",
                ref=str(build_dir),
                authority=AuthorityState.UNKNOWN,
            )
        )

    return MachineProject(
        project_id=project_id,
        name=name,
        purpose=purpose,
        lifecycle_state=_legacy_stage(session.get("currentStage") or session.get("current_stage")),
        requested_release_state=ReleaseState.CONCEPT,
        subsystems=[root_subsystem],
        components=components,
        interfaces=interfaces,
        artifacts=artifacts,
        discipline_payloads={"splice_session": dict(session)},
        metadata={
            "migration": "project_session_to_machine_project.v1",
            "legacy_mode": session.get("mode"),
            "authority_preserved_without_upgrade": True,
        },
    )

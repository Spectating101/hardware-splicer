"""Project structured engineering sources into canonical MachineProject artifacts."""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping

from .engineering_source_graph import EngineeringSourceGraph, SourceType
from .machine_project import (
    ArtifactRef,
    AuthorityState,
    Component,
    ComponentSource,
    Domain,
    EvidenceRef,
    Interface,
    InterfaceContract,
    InterfaceEndpoint,
    MachineProject,
    Subsystem,
    VerificationMethod,
    VerificationStatus,
    VerificationType,
)


ARTIFACT_PROJECTION_SCHEMA = "hardware_splicer.engineering_artifact_projection.v1"


def _slug(value: str, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._").lower()
    return token[:120] or fallback


def _ensure_subsystem(
    subsystems: dict[str, Subsystem],
    subsystem_id: str,
    *,
    name: str,
    domain: Domain,
    purpose: str,
) -> None:
    if subsystem_id in subsystems:
        return
    subsystems[subsystem_id] = Subsystem(
        subsystem_id=subsystem_id,
        name=name,
        domain=domain,
        purpose=purpose,
        parent_subsystem_id="system" if "system" in subsystems else None,
        authority=AuthorityState.PROPOSED,
        metadata={"projection": ARTIFACT_PROJECTION_SCHEMA},
    )


def _append_component(
    components: dict[str, Component],
    subsystems: dict[str, Subsystem],
    component: Component,
) -> None:
    if component.component_id not in components:
        components[component.component_id] = component
    subsystem = subsystems[component.subsystem_id]
    if component.component_id not in subsystem.component_ids:
        subsystems[component.subsystem_id] = subsystem.model_copy(
            update={"component_ids": [*subsystem.component_ids, component.component_id]},
            deep=True,
        )


def _append_interface(
    interfaces: dict[str, Interface],
    subsystems: dict[str, Subsystem],
    interface: Interface,
    subsystem_ids: list[str],
) -> None:
    if interface.interface_id not in interfaces:
        interfaces[interface.interface_id] = interface
    for subsystem_id in subsystem_ids:
        subsystem = subsystems[subsystem_id]
        if interface.interface_id not in subsystem.interface_ids:
            subsystems[subsystem_id] = subsystem.model_copy(
                update={"interface_ids": [*subsystem.interface_ids, interface.interface_id]},
                deep=True,
            )


def _claims_for_source(graph: EngineeringSourceGraph, source_id: str) -> dict[str, list[Any]]:
    values: dict[str, list[Any]] = {}
    for claim in graph.claims:
        if claim.source_id == source_id:
            values.setdefault(claim.predicate, []).append(claim.value)
    return values


def _first(values: Mapping[str, list[Any]], key: str) -> Any:
    rows = values.get(key) or []
    return rows[0] if rows else None


def _mapped_target(subject_id: str, identity_map: Mapping[str, Any], project: MachineProject) -> str:
    topology_map = identity_map.get("topology_to_machine_component")
    if isinstance(topology_map, Mapping) and subject_id in topology_map:
        return str(topology_map[subject_id])
    aliases = identity_map.get("component_aliases")
    if isinstance(aliases, Mapping):
        for component_id, names in aliases.items():
            if subject_id == component_id or (isinstance(names, list) and subject_id in names):
                return str(component_id)
    valid = {
        project.project_id,
        *(row.subsystem_id for row in project.subsystems),
        *(row.component_id for row in project.components),
        *(row.interface_id for row in project.interfaces),
    }
    return subject_id if subject_id in valid else project.project_id


def _artifact_ref(
    *,
    artifact_id: str,
    kind: str,
    ref: str | None,
    authority: AuthorityState,
    source_id: str,
    revision: Any = None,
    content_hash: Any = None,
    metadata: Mapping[str, Any] | None = None,
) -> ArtifactRef:
    """Build the current canonical ArtifactRef without reviving retired schema fields."""
    resolved_ref = str(ref or content_hash or f"source://{source_id}").strip()
    details = {
        "projection": ARTIFACT_PROJECTION_SCHEMA,
        "source_id": source_id,
        **dict(metadata or {}),
    }
    if revision not in (None, ""):
        details["revision"] = str(revision)
    if content_hash not in (None, ""):
        details["content_hash"] = str(content_hash)
    return ArtifactRef(
        artifact_id=artifact_id,
        kind=kind,
        ref=resolved_ref,
        authority=authority,
        metadata=details,
    )


def project_engineering_artifacts(
    project: MachineProject,
    *,
    source_graph: EngineeringSourceGraph,
    identity_map: Mapping[str, Any],
) -> MachineProject:
    """Project adapted source metadata without upgrading its authority."""

    subsystems = {row.subsystem_id: row.model_copy(deep=True) for row in project.subsystems}
    components = {row.component_id: row.model_copy(deep=True) for row in project.components}
    interfaces = {row.interface_id: row.model_copy(deep=True) for row in project.interfaces}
    artifacts = {row.artifact_id: row.model_copy(deep=True) for row in project.artifacts}
    evidence = {row.evidence_id: row.model_copy(deep=True) for row in project.evidence}
    verifications = {row.verification_id: row.model_copy(deep=True) for row in project.verifications}

    _ensure_subsystem(
        subsystems,
        "robot-firmware",
        name="Robot firmware",
        domain=Domain.FIRMWARE,
        purpose="Versioned firmware source, build, flash, configuration, and hardware lineage.",
    )
    _ensure_subsystem(
        subsystems,
        "robot-middleware",
        name="Robot middleware",
        domain=Domain.SOFTWARE,
        purpose="Versioned robot models, topics, services, frames, actions, and application contracts.",
    )
    _ensure_subsystem(
        subsystems,
        "verification-system",
        name="Verification and evidence",
        domain=Domain.VERIFICATION,
        purpose="Measurements, telemetry, test logs, analysis, regression, and release evidence.",
    )

    firmware_component_ids: list[str] = []
    middleware_component_ids: list[str] = []
    projected_evidence_ids: list[str] = []

    for source in source_graph.sources:
        metadata = dict(source.metadata)
        artifact_kind = str(metadata.get("artifact_kind") or "")
        claims = _claims_for_source(source_graph, source.source_id)
        source_token = _slug(source.source_id, "source")

        if artifact_kind == "firmware_manifest":
            manifest = metadata.get("firmware_manifest") if isinstance(metadata.get("firmware_manifest"), Mapping) else {}
            subject_id = str(manifest.get("firmware_component_id") or manifest.get("component_id") or "firmware")
            component_id = f"source-firmware-{_slug(subject_id, source_token)}"
            firmware_component_ids.append(component_id)
            _append_component(
                components,
                subsystems,
                Component(
                    component_id=component_id,
                    name=f"Firmware lineage for {subject_id}",
                    domain=Domain.FIRMWARE,
                    subsystem_id="robot-firmware",
                    role="versioned firmware build and flash target",
                    source=ComponentSource.EXTERNAL,
                    authority=source.authority_ceiling,
                    metadata={
                        "projection": ARTIFACT_PROJECTION_SCHEMA,
                        "source_id": source.source_id,
                        "manifest": dict(manifest),
                    },
                ),
            )
            source_artifact_id = f"artifact-firmware-source-{source_token}"
            artifacts[source_artifact_id] = _artifact_ref(
                artifact_id=source_artifact_id,
                kind="firmware_source_manifest",
                ref=source.uri,
                revision=_first(claims, "source_revision") or source.revision,
                content_hash=source.content_hash,
                authority=source.authority_ceiling,
                source_id=source.source_id,
            )
            binary_hash = _first(claims, "binary_hash")
            binary_artifact_id: str | None = None
            if binary_hash:
                binary_artifact_id = f"artifact-firmware-binary-{source_token}"
                artifacts[binary_artifact_id] = _artifact_ref(
                    artifact_id=binary_artifact_id,
                    kind="firmware_binary",
                    ref=str(binary_hash),
                    revision=_first(claims, "source_revision") or source.revision,
                    content_hash=str(binary_hash),
                    authority=source.authority_ceiling,
                    source_id=source.source_id,
                    metadata={
                        "hardware_revision": _first(claims, "hardware_revision"),
                        "board_profile": _first(claims, "board_profile"),
                    },
                )
            manifest_evidence_id = f"evidence-firmware-manifest-{source_token}"
            evidence[manifest_evidence_id] = EvidenceRef(
                evidence_id=manifest_evidence_id,
                kind="firmware_manifest",
                basis="Pinned firmware source/build/flash declaration.",
                ref=source.uri or f"source://{source.source_id}",
                supports=[component_id],
                authority=source.authority_ceiling,
                metadata={
                    "projection": ARTIFACT_PROJECTION_SCHEMA,
                    "source_id": source.source_id,
                    "source_revision": _first(claims, "source_revision"),
                    "toolchain": _first(claims, "toolchain"),
                    "build_command": _first(claims, "build_command"),
                    "binary_hash": binary_hash,
                    "flash_result": _first(claims, "flash_result"),
                    "pin_map_hash": _first(claims, "pin_map_hash"),
                },
            )
            projected_evidence_ids.append(manifest_evidence_id)
            complete_build = all(
                _first(claims, key)
                for key in ("source_revision", "toolchain", "build_command", "binary_hash")
            )
            flash_result = str(_first(claims, "flash_result") or "").lower()
            flashed = flash_result in {"pass", "passed", "success", "successful", "verified"}
            verifications[f"verification-firmware-lineage-{source_token}"] = VerificationMethod(
                verification_id=f"verification-firmware-lineage-{source_token}",
                name=f"Firmware lineage: {subject_id}",
                method_type=VerificationType.INSPECTION,
                status=(
                    VerificationStatus.PASSED
                    if complete_build and flashed
                    else VerificationStatus.PLANNED
                    if complete_build
                    else VerificationStatus.BLOCKED
                ),
                target_ids=[component_id],
                evidence_ids=[manifest_evidence_id],
                procedure="Verify source revision, toolchain, dependencies, build command, binary hash, hardware revision, pin-map hash, flash result, and safe-start behavior.",
                acceptance_criteria={
                    "source_revision_pinned": True,
                    "toolchain_pinned": True,
                    "binary_hash_recorded": True,
                    "hardware_revision_recorded": True,
                    "flash_result_pass": True,
                    "physical_safe_start_required": True,
                },
                authority=source.authority_ceiling,
                metadata={
                    "projection": ARTIFACT_PROJECTION_SCHEMA,
                    "source_artifact_id": source_artifact_id,
                    "binary_artifact_id": binary_artifact_id,
                    "declared_manifest_does_not_authorize_flash": True,
                },
            )

        if artifact_kind == "ros_interface_manifest":
            manifest = metadata.get("ros_interface_manifest") if isinstance(metadata.get("ros_interface_manifest"), Mapping) else {}
            node_id = str(manifest.get("node_id") or manifest.get("package") or "robot-middleware")
            component_id = f"source-middleware-{_slug(node_id, source_token)}"
            middleware_component_ids.append(component_id)
            _append_component(
                components,
                subsystems,
                Component(
                    component_id=component_id,
                    name=f"Middleware contract for {node_id}",
                    domain=Domain.SOFTWARE,
                    subsystem_id="robot-middleware",
                    role="versioned middleware and robot-model contract",
                    source=ComponentSource.EXTERNAL,
                    authority=source.authority_ceiling,
                    metadata={
                        "projection": ARTIFACT_PROJECTION_SCHEMA,
                        "source_id": source.source_id,
                        "manifest": dict(manifest),
                    },
                ),
            )
            artifact_id = f"artifact-middleware-manifest-{source_token}"
            artifacts[artifact_id] = _artifact_ref(
                artifact_id=artifact_id,
                kind="middleware_interface_manifest",
                ref=source.uri,
                revision=source.revision,
                content_hash=source.content_hash,
                authority=source.authority_ceiling,
                source_id=source.source_id,
            )
            topics = _first(claims, "ros_topics") or []
            services = _first(claims, "ros_services") or []
            frames = _first(claims, "coordinate_frames") or []
            unresolved = []
            if not topics and not services:
                unresolved.append("topics_or_services")
            if not frames:
                unresolved.append("coordinate_frames")
            interface = Interface(
                interface_id=f"interface-middleware-contract-{source_token}",
                name=f"Middleware contract for {node_id}",
                kind="middleware_contract",
                endpoints=[
                    InterfaceEndpoint(object_id=component_id, port="manifest", role="declared_interface"),
                    InterfaceEndpoint(object_id=project.project_id, port="robot_application", role="project_consumer"),
                ],
                contracts=[
                    InterfaceContract(
                        contract_type="middleware_manifest",
                        values={
                            "topics": topics,
                            "services": services,
                            "actions": _first(claims, "ros_actions") or [],
                            "frames": frames,
                            "parameters": _first(claims, "ros_parameters") or {},
                            "distribution": _first(claims, "ros_distribution"),
                            "urdf_revision": _first(claims, "urdf_revision"),
                        },
                        unresolved_fields=unresolved,
                        authority=source.authority_ceiling,
                    )
                ],
                authority=source.authority_ceiling,
                metadata={"projection": ARTIFACT_PROJECTION_SCHEMA, "source_id": source.source_id},
            )
            _append_interface(interfaces, subsystems, interface, ["robot-middleware"])

        if source.source_type in {SourceType.MEASUREMENT, SourceType.TELEMETRY, SourceType.TEST_LOG, SourceType.OPERATOR_OBSERVATION}:
            for claim in source_graph.claims:
                if claim.source_id != source.source_id:
                    continue
                evidence_id = f"evidence-source-claim-{_slug(claim.claim_id, 'claim')}"
                target_id = _mapped_target(claim.subject_id, identity_map, project)
                evidence[evidence_id] = EvidenceRef(
                    evidence_id=evidence_id,
                    kind=source.source_type.value,
                    basis=f"{claim.predicate}: {claim.value}",
                    ref=source.uri or f"source://{source.source_id}/{claim.claim_id}",
                    supports=[target_id],
                    authority=claim.authority,
                    metadata={
                        "projection": ARTIFACT_PROJECTION_SCHEMA,
                        "source_id": source.source_id,
                        "claim_id": claim.claim_id,
                        "predicate": claim.predicate,
                        "value": claim.value,
                        "units": claim.units,
                        "confidence": claim.confidence,
                        "evidence_locator": claim.evidence_locator,
                        "claim_metadata": claim.metadata,
                    },
                )
                projected_evidence_ids.append(evidence_id)

    payloads = dict(project.discipline_payloads)
    payloads["engineering_artifact_projection"] = {
        "schema_version": ARTIFACT_PROJECTION_SCHEMA,
        "firmware_component_ids": sorted(set(firmware_component_ids)),
        "middleware_component_ids": sorted(set(middleware_component_ids)),
        "projected_evidence_ids": sorted(set(projected_evidence_ids)),
        "authority_preserved": True,
    }
    metadata = dict(project.metadata)
    metadata.update(
        {
            "engineering_artifacts_projected": True,
            "engineering_artifact_projection": ARTIFACT_PROJECTION_SCHEMA,
            "source_authority_preserved": True,
        }
    )
    return MachineProject(
        **{
            **project.model_dump(mode="python"),
            "subsystems": list(subsystems.values()),
            "components": list(components.values()),
            "interfaces": list(interfaces.values()),
            "artifacts": list(artifacts.values()),
            "evidence": list(evidence.values()),
            "verifications": list(verifications.values()),
            "discipline_payloads": payloads,
            "metadata": metadata,
        }
    )

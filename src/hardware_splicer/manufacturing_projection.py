"""Project manufacturing identities into the canonical MachineProject graph."""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping

from .machine_project import (
    ArtifactRef,
    AuthorityState,
    Component,
    ComponentSource,
    Domain,
    Interface,
    InterfaceContract,
    InterfaceEndpoint,
    MachineProject,
    Subsystem,
)


MANUFACTURING_PROJECTION_SCHEMA = "hardware_splicer.manufacturing_projection.v1"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        rows: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("id", str(key))
                rows.append(row)
            elif isinstance(item, list):
                rows.extend(dict(row) for row in item if isinstance(row, Mapping))
        return rows
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _slug(value: Any, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip("-._").lower()
    return token[:120] or fallback


def _first(row: Mapping[str, Any], *fields: str, fallback: str = "") -> str:
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            return str(value)
    return fallback


def _sources(plan: Mapping[str, Any], intake: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    normalized = _mapping(plan.get("normalized_intake"))
    scenario = _mapping(plan.get("scenario"))
    compile_spec = _mapping(scenario.get("compile_spec"))
    machine = _mapping(plan.get("machine_project"))
    discipline = _mapping(machine.get("discipline_payloads"))
    return [intake, normalized, plan, compile_spec, discipline]


def _gather(plan: Mapping[str, Any], intake: Mapping[str, Any], *keys: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source in _sources(plan, intake):
        for key in keys:
            result.extend(_rows(source.get(key)))
    return result


def _ensure_subsystem(
    subsystems: list[Subsystem],
    *,
    subsystem_id: str,
    name: str,
    domain: Domain,
    purpose: str,
) -> Subsystem:
    existing = next((row for row in subsystems if row.subsystem_id == subsystem_id), None)
    if existing is not None:
        return existing
    row = Subsystem(
        subsystem_id=subsystem_id,
        name=name,
        domain=domain,
        purpose=purpose,
        authority=AuthorityState.PROPOSED,
    )
    subsystems.append(row)
    return row


def project_manufacturing_identities(
    project: MachineProject,
    *,
    plan: Mapping[str, Any],
    intake: Mapping[str, Any] | None = None,
) -> MachineProject:
    """Add manufacturing objects without upgrading design or physical authority."""

    body = dict(intake or {})
    subsystems = list(project.subsystems)
    components = list(project.components)
    interfaces = list(project.interfaces)
    artifacts = list(project.artifacts)
    component_ids = {row.component_id for row in components}
    interface_ids = {row.interface_id for row in interfaces}
    artifact_ids = {row.artifact_id for row in artifacts}

    electrical_system = _ensure_subsystem(
        subsystems,
        subsystem_id="manufacturing-electrical",
        name="Manufacturing electrical and harness system",
        domain=Domain.ELECTRICAL,
        purpose="Physical connectors, cables, harnesses, and pin-level manufacturing identity",
    )
    mechanical_system = _ensure_subsystem(
        subsystems,
        subsystem_id="manufacturing-mechanical",
        name="Manufacturing mechanical system",
        domain=Domain.MECHANICAL,
        purpose="Physical instances, mounts, fasteners, and CAD identity",
    )
    assembly_system = _ensure_subsystem(
        subsystems,
        subsystem_id="manufacturing-assembly",
        name="Manufacturing assembly system",
        domain=Domain.ASSEMBLY,
        purpose="Assembly and release candidate artifact identity",
    )

    connector_map: dict[str, str] = {}
    projected_components: list[str] = []
    projected_interfaces: list[str] = []
    projected_artifacts: list[str] = []

    connectors = _gather(plan, body, "connectors", "connector_instances")
    for index, row in enumerate(connectors):
        raw_id = _first(row, "connector_id", "instance_id", "id", "name", fallback=f"connector-{index + 1}")
        connector_id = _slug(raw_id, f"connector-{index + 1}")
        component_id = f"mfg-connector-{connector_id}"
        connector_map[connector_id] = component_id
        if component_id not in component_ids:
            components.append(
                Component(
                    component_id=component_id,
                    name=_first(row, "name", fallback=raw_id),
                    domain=Domain.ELECTRICAL,
                    subsystem_id=electrical_system.subsystem_id,
                    role="physical connector instance",
                    source=ComponentSource.EXTERNAL,
                    authority=AuthorityState.DECLARED,
                    metadata={
                        "manufacturing_object_type": "connector",
                        "connector_id": connector_id,
                        "mating_connector_id": _slug(_first(row, "mates_with", "mate_id", "mating_connector_id"), "") or None,
                        "pin_count": row.get("pin_count"),
                        "part_number": row.get("part_number") or row.get("mpn"),
                        "source_row": row,
                    },
                )
            )
            component_ids.add(component_id)
            projected_components.append(component_id)

    instances = _gather(plan, body, "physical_instances", "part_instances", "assembly_instances")
    for index, row in enumerate(instances):
        raw_id = _first(row, "instance_id", "id", "serial", fallback=f"instance-{index + 1}")
        part_id = _first(row, "part_id", "component_id", "mpn", "sku", "name", fallback="unknown-part")
        component_id = f"mfg-instance-{_slug(raw_id, f'instance-{index + 1}')}"
        if component_id in component_ids:
            continue
        components.append(
            Component(
                component_id=component_id,
                name=_first(row, "name", fallback=raw_id),
                domain=Domain.ASSEMBLY,
                subsystem_id=assembly_system.subsystem_id,
                role="physical part instance",
                source=ComponentSource.DONOR if row.get("donor") or row.get("salvaged") else ComponentSource.EXTERNAL,
                authority=AuthorityState.OBSERVED if row.get("serial") or row.get("measured") else AuthorityState.DECLARED,
                metadata={
                    "manufacturing_object_type": "physical_instance",
                    "part_id": part_id,
                    "quantity": row.get("quantity") or row.get("qty") or 1,
                    "serial": row.get("serial"),
                    "condition": row.get("condition"),
                    "source_row": row,
                },
            )
        )
        component_ids.add(component_id)
        projected_components.append(component_id)

    fasteners = _gather(plan, body, "fasteners", "fastener_schedule")
    for index, row in enumerate(fasteners):
        raw_id = _first(row, "fastener_id", "part_id", "id", "name", fallback=f"fastener-{index + 1}")
        component_id = f"mfg-fastener-{_slug(raw_id, f'fastener-{index + 1}')}"
        if component_id in component_ids:
            continue
        components.append(
            Component(
                component_id=component_id,
                name=_first(row, "name", fallback=raw_id),
                domain=Domain.MECHANICAL,
                subsystem_id=mechanical_system.subsystem_id,
                role="fastener schedule item",
                source=ComponentSource.EXTERNAL,
                authority=AuthorityState.DECLARED,
                metadata={
                    "manufacturing_object_type": "fastener",
                    "size": row.get("size"),
                    "thread": row.get("thread"),
                    "length": row.get("length") or row.get("length_mm"),
                    "torque": row.get("torque") or row.get("torque_nm"),
                    "quantity": row.get("quantity") or row.get("qty"),
                    "source_row": row,
                },
            )
        )
        component_ids.add(component_id)
        projected_components.append(component_id)

    cad_rows = _gather(plan, body, "cad_models", "step_models", "mechanical_models")
    cad_artifact_map: dict[str, str] = {}
    for index, row in enumerate(cad_rows):
        raw_id = _first(row, "cad_id", "model_id", "part_id", "id", "name", fallback=f"cad-{index + 1}")
        cad_id = _slug(raw_id, f"cad-{index + 1}")
        artifact_id = f"mfg-cad-{cad_id}"
        cad_artifact_map[cad_id] = artifact_id
        if artifact_id not in artifact_ids:
            artifacts.append(
                ArtifactRef(
                    artifact_id=artifact_id,
                    kind=str(row.get("format") or row.get("kind") or "cad_model"),
                    ref=str(row.get("ref") or row.get("path") or row.get("uri") or raw_id),
                    authority=AuthorityState.DECLARED,
                    metadata={
                        "manufacturing_object_type": "cad_model",
                        "content_hash": row.get("content_hash") or row.get("sha256"),
                        "revision": row.get("revision") or row.get("version"),
                        "source_row": row,
                    },
                )
            )
            artifact_ids.add(artifact_id)
            projected_artifacts.append(artifact_id)

    fabrication = _gather(plan, body, "fabrication_artifacts", "manufacturing_artifacts", "release_artifacts")
    for index, row in enumerate(fabrication):
        raw_id = _first(row, "artifact_id", "id", "name", "path", fallback=f"artifact-{index + 1}")
        artifact_id = f"mfg-release-{_slug(raw_id, f'artifact-{index + 1}')}"
        if artifact_id in artifact_ids:
            continue
        artifacts.append(
            ArtifactRef(
                artifact_id=artifact_id,
                kind=str(row.get("kind") or row.get("format") or "fabrication_artifact"),
                ref=str(row.get("ref") or row.get("path") or row.get("uri") or raw_id),
                authority=AuthorityState.DECLARED,
                metadata={
                    "manufacturing_object_type": "fabrication_artifact",
                    "revision": row.get("revision") or row.get("source_revision") or row.get("commit"),
                    "content_hash": row.get("content_hash") or row.get("sha256") or row.get("hash"),
                    "source_row": row,
                },
            )
        )
        artifact_ids.add(artifact_id)
        projected_artifacts.append(artifact_id)

    harnesses = _gather(plan, body, "harnesses", "cables", "wire_harnesses")
    for index, row in enumerate(harnesses):
        raw_id = _first(row, "harness_id", "cable_id", "id", "name", fallback=f"harness-{index + 1}")
        harness_id = _slug(raw_id, f"harness-{index + 1}")
        component_id = f"mfg-harness-{harness_id}"
        if component_id not in component_ids:
            components.append(
                Component(
                    component_id=component_id,
                    name=_first(row, "name", fallback=raw_id),
                    domain=Domain.ELECTRICAL,
                    subsystem_id=electrical_system.subsystem_id,
                    role="wire harness or cable assembly",
                    source=ComponentSource.EXTERNAL,
                    authority=AuthorityState.DECLARED,
                    metadata={
                        "manufacturing_object_type": "harness",
                        "conductors": row.get("conductors") or [],
                        "length": row.get("length") or row.get("length_mm"),
                        "source_row": row,
                    },
                )
            )
            component_ids.add(component_id)
            projected_components.append(component_id)
        endpoints = row.get("endpoints") if isinstance(row.get("endpoints"), (list, tuple)) else [row.get("from"), row.get("to")]
        endpoint_component_ids: list[str] = []
        for endpoint in endpoints:
            value = endpoint.get("connector_id") if isinstance(endpoint, Mapping) else endpoint
            resolved = connector_map.get(_slug(value, ""))
            if resolved:
                endpoint_component_ids.append(resolved)
        if len(endpoint_component_ids) >= 2:
            interface_id = f"mfg-harness-interface-{harness_id}"
            if interface_id not in interface_ids:
                unresolved = [] if row.get("conductors") else ["conductor_schedule"]
                interfaces.append(
                    Interface(
                        interface_id=interface_id,
                        name=f"Harness interface {raw_id}",
                        kind="electrical_harness",
                        endpoints=[
                            InterfaceEndpoint(object_id=value, port="connector", role="harness endpoint")
                            for value in endpoint_component_ids
                        ],
                        contracts=[
                            InterfaceContract(
                                contract_type="harness_pinout",
                                values={
                                    "harness_component_id": component_id,
                                    "conductors": row.get("conductors") or [],
                                    "length": row.get("length") or row.get("length_mm"),
                                },
                                unresolved_fields=unresolved,
                                authority=AuthorityState.DECLARED,
                            )
                        ],
                        authority=AuthorityState.DECLARED,
                        metadata={"manufacturing_object_type": "harness_interface"},
                    )
                )
                interface_ids.add(interface_id)
                projected_interfaces.append(interface_id)

    mounts = _gather(plan, body, "mounts", "mechanical_mounts", "mounting_interfaces")
    for index, row in enumerate(mounts):
        raw_id = _first(row, "mount_id", "interface_id", "id", "name", fallback=f"mount-{index + 1}")
        mount_id = _slug(raw_id, f"mount-{index + 1}")
        component_id = f"mfg-mount-{mount_id}"
        cad_id = _slug(_first(row, "cad_id", "model_id", "step_model_id", "geometry_ref"), "")
        artifact_ref = cad_artifact_map.get(cad_id)
        if component_id not in component_ids:
            components.append(
                Component(
                    component_id=component_id,
                    name=_first(row, "name", fallback=raw_id),
                    domain=Domain.MECHANICAL,
                    subsystem_id=mechanical_system.subsystem_id,
                    role="mechanical mount or assembly interface",
                    source=ComponentSource.GENERATED,
                    artifact_refs=[next(row for row in artifacts if row.artifact_id == artifact_ref)] if artifact_ref else [],
                    authority=AuthorityState.DECLARED,
                    metadata={
                        "manufacturing_object_type": "mount",
                        "cad_artifact_id": artifact_ref,
                        "fastener_ids": row.get("fastener_ids") or [],
                        "source_row": row,
                    },
                )
            )
            component_ids.add(component_id)
            projected_components.append(component_id)

    subsystem_updates: dict[str, Subsystem] = {}
    for subsystem in subsystems:
        owned_components = [row.component_id for row in components if row.subsystem_id == subsystem.subsystem_id]
        owned_interfaces = [
            row.interface_id
            for row in interfaces
            if any(endpoint.object_id in set(owned_components) for endpoint in row.endpoints)
        ]
        subsystem_updates[subsystem.subsystem_id] = subsystem.model_copy(
            update={
                "component_ids": sorted(set(subsystem.component_ids) | set(owned_components)),
                "interface_ids": sorted(set(subsystem.interface_ids) | set(owned_interfaces)),
            },
            deep=True,
        )
    subsystems = [subsystem_updates[row.subsystem_id] for row in subsystems]

    payloads = dict(project.discipline_payloads)
    payloads["manufacturing_projection"] = {
        "schema_version": MANUFACTURING_PROJECTION_SCHEMA,
        "projected_component_ids": projected_components,
        "projected_interface_ids": projected_interfaces,
        "projected_artifact_ids": projected_artifacts,
        "connector_component_map": connector_map,
        "cad_artifact_map": cad_artifact_map,
        "authority": AuthorityState.PROPOSED.value,
        "manufacturing_authorized": False,
    }
    metadata = dict(project.metadata)
    metadata.update(
        {
            "manufacturing_projection_schema": MANUFACTURING_PROJECTION_SCHEMA,
            "manufacturing_projected_component_count": len(projected_components),
            "manufacturing_projected_interface_count": len(projected_interfaces),
            "manufacturing_projected_artifact_count": len(projected_artifacts),
            "manufacturing_authority_unchanged": True,
        }
    )
    return MachineProject.model_validate(
        project.model_copy(
            update={
                "subsystems": subsystems,
                "components": components,
                "interfaces": interfaces,
                "artifacts": artifacts,
                "discipline_payloads": payloads,
                "metadata": metadata,
            },
            deep=True,
        ).model_dump(mode="json")
    )

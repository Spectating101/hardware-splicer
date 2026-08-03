"""Project canonical robot topology into first-class MachineProject objects.

Topology payloads remain available for discipline-specific tools, while this projection
creates stable components and interfaces that participate in MachineProject diffs,
traceability, evidence, and release assessment. All projected state is proposed and
unresolved interface fields remain explicit.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .machine_project import (
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
from .robot_topology import RobotTopology


PROJECTION_SCHEMA = "hardware_splicer.robot_machine_projection.v1"


def _component_id(kind: str, topology_id: str) -> str:
    return f"robot-{kind}-{topology_id}"


def _interface_id(kind: str, topology_id: str) -> str:
    return f"robot-interface-{kind}-{topology_id}"


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
    parent = "system" if "system" in subsystems and subsystem_id != "system" else None
    subsystems[subsystem_id] = Subsystem(
        subsystem_id=subsystem_id,
        name=name,
        domain=domain,
        purpose=purpose,
        parent_subsystem_id=parent,
        authority=AuthorityState.PROPOSED,
        metadata={"projection": PROJECTION_SCHEMA},
    )


def _upsert_component(
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


def _upsert_interface(
    interfaces: dict[str, Interface],
    subsystems: dict[str, Subsystem],
    interface: Interface,
    subsystem_ids: Iterable[str],
) -> None:
    if interface.interface_id not in interfaces:
        interfaces[interface.interface_id] = interface
    for subsystem_id in dict.fromkeys(subsystem_ids):
        if subsystem_id not in subsystems:
            continue
        subsystem = subsystems[subsystem_id]
        if interface.interface_id not in subsystem.interface_ids:
            subsystems[subsystem_id] = subsystem.model_copy(
                update={"interface_ids": [*subsystem.interface_ids, interface.interface_id]},
                deep=True,
            )


def _component(
    component_id: str,
    name: str,
    domain: Domain,
    subsystem_id: str,
    role: str,
    *,
    metadata: Mapping[str, Any],
) -> Component:
    return Component(
        component_id=component_id,
        name=name,
        domain=domain,
        subsystem_id=subsystem_id,
        role=role,
        source=ComponentSource.GENERATED,
        authority=AuthorityState.PROPOSED,
        metadata={"projection": PROJECTION_SCHEMA, **dict(metadata)},
    )


def project_robot_topology(
    project: MachineProject,
    topology: RobotTopology,
) -> MachineProject:
    """Return an idempotently enriched MachineProject for ``topology``."""

    subsystems = {row.subsystem_id: row.model_copy(deep=True) for row in project.subsystems}
    components = {row.component_id: row.model_copy(deep=True) for row in project.components}
    interfaces = {row.interface_id: row.model_copy(deep=True) for row in project.interfaces}

    _ensure_subsystem(
        subsystems,
        "system",
        name="Machine system",
        domain=Domain.SYSTEM,
        purpose=project.purpose,
    )
    _ensure_subsystem(
        subsystems,
        "robot-structure",
        name="Robot structure and kinematics",
        domain=Domain.MECHANICAL,
        purpose="Links, joints, frames, load paths, mounts, and kinematic relationships.",
    )
    _ensure_subsystem(
        subsystems,
        "robot-actuation",
        name="Robot actuation",
        domain=Domain.MECHANICAL,
        purpose="Actuators, transmissions, command paths, and physical feedback.",
    )
    _ensure_subsystem(
        subsystems,
        "robot-perception",
        name="Robot perception",
        domain=Domain.ELECTRICAL,
        purpose="Sensors, mounting frames, electrical channels, and observations.",
    )
    _ensure_subsystem(
        subsystems,
        "robot-firmware",
        name="Robot firmware",
        domain=Domain.FIRMWARE,
        purpose="Hardware abstraction, actuator/sensor channels, calibration, and safety behavior.",
    )
    _ensure_subsystem(
        subsystems,
        "robot-middleware",
        name="Robot middleware and application interfaces",
        domain=Domain.SOFTWARE,
        purpose="Robot models, frames, topics, services, messages, and application contracts.",
    )
    _ensure_subsystem(
        subsystems,
        "power-system",
        name="Power system",
        domain=Domain.ELECTRICAL,
        purpose="Energy storage, conversion, distribution, protection, and current delivery.",
    )

    link_component_ids: dict[str, str] = {}
    for link in topology.links:
        component_id = _component_id("link", link.link_id)
        link_component_ids[link.link_id] = component_id
        _upsert_component(
            components,
            subsystems,
            _component(
                component_id,
                link.name,
                Domain.MECHANICAL,
                "robot-structure",
                "robot link",
                metadata={
                    "topology_object_id": link.link_id,
                    "frame_id": link.frame_id,
                    "parent_link_id": link.parent_link_id,
                    "mechanical_component_id": link.mechanical_component_id,
                    "mass_kg": link.mass_kg,
                    "center_of_mass": link.center_of_mass,
                    "collision_geometry_refs": link.collision_geometry_refs,
                },
            ),
        )

    joint_component_ids: dict[str, str] = {}
    for joint in topology.joints:
        component_id = _component_id("joint", joint.joint_id)
        joint_component_ids[joint.joint_id] = component_id
        _upsert_component(
            components,
            subsystems,
            _component(
                component_id,
                joint.name,
                Domain.MECHANICAL,
                "robot-structure",
                "robot joint",
                metadata={
                    "topology_object_id": joint.joint_id,
                    "joint_type": joint.joint_type.value,
                    "axis": joint.axis,
                    "limits": joint.limits,
                    "firmware_joint_id": joint.firmware_joint_id,
                    "middleware_joint_name": joint.middleware_joint_name,
                    "calibration_ref": joint.calibration_ref,
                },
            ),
        )
        unresolved = []
        if not joint.limits:
            unresolved.extend(["lower_limit", "upper_limit", "velocity_limit", "effort_limit"])
        if joint.joint_type.value != "fixed" and not joint.calibration_ref:
            unresolved.append("calibration_ref")
        interface = Interface(
            interface_id=_interface_id("joint", joint.joint_id),
            name=f"{joint.name} mechanical contract",
            kind="mechanical_joint",
            endpoints=[
                InterfaceEndpoint(
                    object_id=link_component_ids[joint.parent_link_id],
                    port=joint.joint_id,
                    role="parent_link",
                ),
                InterfaceEndpoint(
                    object_id=link_component_ids[joint.child_link_id],
                    port=joint.joint_id,
                    role="child_link",
                ),
            ],
            contracts=[
                InterfaceContract(
                    contract_type="kinematic_joint",
                    values={
                        "joint_component_id": component_id,
                        "joint_type": joint.joint_type.value,
                        "axis": joint.axis,
                        "limits": joint.limits,
                        "calibration_ref": joint.calibration_ref,
                    },
                    unresolved_fields=unresolved,
                    authority=AuthorityState.PROPOSED,
                )
            ],
            authority=AuthorityState.PROPOSED,
            metadata={"projection": PROJECTION_SCHEMA, "topology_joint_id": joint.joint_id},
        )
        _upsert_interface(interfaces, subsystems, interface, ["robot-structure"])

    actuator_component_ids: dict[str, str] = {}
    for actuator in topology.actuators:
        actuator_component_id = _component_id("actuator", actuator.actuator_id)
        actuator_component_ids[actuator.actuator_id] = actuator_component_id
        firmware_component_id = _component_id("firmware-channel", actuator.actuator_id)
        _upsert_component(
            components,
            subsystems,
            _component(
                actuator_component_id,
                actuator.name,
                Domain.MECHANICAL,
                "robot-actuation",
                "robot actuator",
                metadata={
                    "topology_object_id": actuator.actuator_id,
                    "actuator_type": actuator.actuator_type,
                    "joint_ids": actuator.joint_ids,
                    "source_part_id": actuator.source_part_id,
                    "electrical_component_id": actuator.electrical_component_id,
                    "driver_channel_id": actuator.driver_channel_id,
                },
            ),
        )
        _upsert_component(
            components,
            subsystems,
            _component(
                firmware_component_id,
                f"Firmware channel for {actuator.name}",
                Domain.FIRMWARE,
                "robot-firmware",
                "actuator firmware channel",
                metadata={
                    "topology_object_id": actuator.actuator_id,
                    "firmware_channel_id": actuator.firmware_channel_id,
                    "command_interface": actuator.command_interface,
                    "feedback_interface": actuator.feedback_interface,
                },
            ),
        )
        command_interface = Interface(
            interface_id=_interface_id("actuator-command", actuator.actuator_id),
            name=f"{actuator.name} command and feedback",
            kind="firmware_actuator_channel",
            endpoints=[
                InterfaceEndpoint(object_id=actuator_component_id, port="command_feedback", role="physical_actuator"),
                InterfaceEndpoint(object_id=firmware_component_id, port="driver_channel", role="firmware_channel"),
            ],
            contracts=[
                InterfaceContract(
                    contract_type="actuator_command_feedback",
                    values={
                        "command_interface": actuator.command_interface,
                        "feedback_interface": actuator.feedback_interface,
                        "driver_channel_id": actuator.driver_channel_id,
                        "firmware_channel_id": actuator.firmware_channel_id,
                    },
                    unresolved_fields=["protocol", "update_rate_hz", "safety_timeout_ms", "fault_state"],
                    authority=AuthorityState.PROPOSED,
                )
            ],
            authority=AuthorityState.PROPOSED,
            metadata={"projection": PROJECTION_SCHEMA, "topology_actuator_id": actuator.actuator_id},
        )
        _upsert_interface(
            interfaces,
            subsystems,
            command_interface,
            ["robot-actuation", "robot-firmware"],
        )
        power_interface = Interface(
            interface_id=_interface_id("actuator-power", actuator.actuator_id),
            name=f"{actuator.name} power contract",
            kind="electrical_power",
            endpoints=[
                InterfaceEndpoint(object_id=actuator_component_id, port="power", role="load"),
                InterfaceEndpoint(object_id="power-system", port="actuator_rail", role="supply"),
            ],
            contracts=[
                InterfaceContract(
                    contract_type="actuator_power",
                    values={"electrical_component_id": actuator.electrical_component_id},
                    unresolved_fields=[
                        "nominal_voltage_v",
                        "peak_current_a",
                        "continuous_current_a",
                        "connector",
                        "protection",
                    ],
                    authority=AuthorityState.PROPOSED,
                )
            ],
            authority=AuthorityState.PROPOSED,
            metadata={"projection": PROJECTION_SCHEMA, "topology_actuator_id": actuator.actuator_id},
        )
        _upsert_interface(
            interfaces,
            subsystems,
            power_interface,
            ["robot-actuation", "power-system"],
        )

    root_link_component_id = link_component_ids[topology.root_link_id]
    for sensor in topology.sensors:
        sensor_component_id = _component_id("sensor", sensor.sensor_id)
        firmware_component_id = _component_id("firmware-sensor", sensor.sensor_id)
        middleware_component_id = _component_id("middleware-sensor", sensor.sensor_id)
        _upsert_component(
            components,
            subsystems,
            _component(
                sensor_component_id,
                sensor.name,
                Domain.ELECTRICAL,
                "robot-perception",
                "robot sensor",
                metadata={
                    "topology_object_id": sensor.sensor_id,
                    "sensor_type": sensor.sensor_type,
                    "frame_id": sensor.frame_id,
                    "source_part_id": sensor.source_part_id,
                    "electrical_component_id": sensor.electrical_component_id,
                },
            ),
        )
        _upsert_component(
            components,
            subsystems,
            _component(
                firmware_component_id,
                f"Firmware channel for {sensor.name}",
                Domain.FIRMWARE,
                "robot-firmware",
                "sensor firmware channel",
                metadata={
                    "topology_object_id": sensor.sensor_id,
                    "firmware_sensor_id": sensor.firmware_sensor_id,
                },
            ),
        )
        _upsert_component(
            components,
            subsystems,
            _component(
                middleware_component_id,
                f"Middleware interface for {sensor.name}",
                Domain.SOFTWARE,
                "robot-middleware",
                "sensor middleware interface",
                metadata={
                    "topology_object_id": sensor.sensor_id,
                    "middleware_interfaces": sensor.middleware_interfaces,
                    "frame_id": sensor.frame_id,
                },
            ),
        )
        mount_interface = Interface(
            interface_id=_interface_id("sensor-mount", sensor.sensor_id),
            name=f"{sensor.name} mount",
            kind="mechanical_mount",
            endpoints=[
                InterfaceEndpoint(object_id=sensor_component_id, port="mount", role="mounted_sensor"),
                InterfaceEndpoint(object_id=root_link_component_id, port=sensor.frame_id, role="host_structure"),
            ],
            contracts=[
                InterfaceContract(
                    contract_type="sensor_mount",
                    values={"frame_id": sensor.frame_id},
                    unresolved_fields=["pose", "fastener", "clearance", "vibration_limit"],
                    authority=AuthorityState.PROPOSED,
                )
            ],
            authority=AuthorityState.PROPOSED,
            metadata={"projection": PROJECTION_SCHEMA, "topology_sensor_id": sensor.sensor_id},
        )
        _upsert_interface(
            interfaces,
            subsystems,
            mount_interface,
            ["robot-perception", "robot-structure"],
        )
        firmware_interface = Interface(
            interface_id=_interface_id("sensor-firmware", sensor.sensor_id),
            name=f"{sensor.name} electrical and firmware channel",
            kind="sensor_data_channel",
            endpoints=[
                InterfaceEndpoint(object_id=sensor_component_id, port="electrical_data", role="physical_sensor"),
                InterfaceEndpoint(object_id=firmware_component_id, port="driver", role="firmware_driver"),
            ],
            contracts=[
                InterfaceContract(
                    contract_type="sensor_electrical_firmware",
                    values={
                        "electrical_component_id": sensor.electrical_component_id,
                        "firmware_sensor_id": sensor.firmware_sensor_id,
                    },
                    unresolved_fields=["protocol", "pin_map", "sample_rate_hz", "supply_voltage_v"],
                    authority=AuthorityState.PROPOSED,
                )
            ],
            authority=AuthorityState.PROPOSED,
            metadata={"projection": PROJECTION_SCHEMA, "topology_sensor_id": sensor.sensor_id},
        )
        _upsert_interface(
            interfaces,
            subsystems,
            firmware_interface,
            ["robot-perception", "robot-firmware"],
        )
        middleware_interface = Interface(
            interface_id=_interface_id("sensor-middleware", sensor.sensor_id),
            name=f"{sensor.name} middleware contract",
            kind="middleware_interface",
            endpoints=[
                InterfaceEndpoint(object_id=firmware_component_id, port="published_data", role="producer"),
                InterfaceEndpoint(object_id=middleware_component_id, port="application_interface", role="consumer"),
            ],
            contracts=[
                InterfaceContract(
                    contract_type="sensor_middleware",
                    values={
                        "interfaces": sensor.middleware_interfaces,
                        "frame_id": sensor.frame_id,
                    },
                    unresolved_fields=["message_type", "topic_or_service_name", "qos", "frame_transform"],
                    authority=AuthorityState.PROPOSED,
                )
            ],
            authority=AuthorityState.PROPOSED,
            metadata={"projection": PROJECTION_SCHEMA, "topology_sensor_id": sensor.sensor_id},
        )
        _upsert_interface(
            interfaces,
            subsystems,
            middleware_interface,
            ["robot-firmware", "robot-middleware"],
        )

    payloads = dict(project.discipline_payloads)
    payloads["robot_topology"] = topology.model_dump(mode="json")
    payloads["robot_machine_projection"] = {
        "schema_version": PROJECTION_SCHEMA,
        "topology_id": topology.topology_id,
        "link_component_ids": link_component_ids,
        "joint_component_ids": joint_component_ids,
        "actuator_component_ids": actuator_component_ids,
        "projected_component_count": len(components) - len(project.components),
        "projected_interface_count": len(interfaces) - len(project.interfaces),
        "authority": AuthorityState.PROPOSED.value,
    }
    metadata = dict(project.metadata)
    metadata.update(
        {
            "robot_topology_projected": True,
            "robot_topology_id": topology.topology_id,
            "robot_genre": topology.robot_genre.value,
            "projection_authority": AuthorityState.PROPOSED.value,
        }
    )
    return MachineProject(
        **{
            **project.model_dump(mode="python"),
            "subsystems": list(subsystems.values()),
            "components": list(components.values()),
            "interfaces": list(interfaces.values()),
            "discipline_payloads": payloads,
            "metadata": metadata,
        }
    )

"""Deterministic seeding of a canonical machine project from project intake.

The seed is intentionally conservative. It creates purpose, requirements,
subsystems, components, and declared constraints, but it does not invent pin
mappings, mechanical fits, firmware behavior, or verification evidence.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .machine_project import (
    AuthorityState,
    Component,
    ComponentSource,
    Constraint,
    Domain,
    Function,
    LifecycleState,
    MachineProject,
    Requirement,
    RequirementKind,
    Subsystem,
)


def _slug(value: str, fallback: str = "machine-project") -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    return slug[:80] or fallback


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _parts(intake: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = intake.get("available_parts") or intake.get("parts") or intake.get("resources") or []
    return [dict(row) for row in raw if isinstance(row, Mapping)] if isinstance(raw, list) else []


def _part_source(row: Mapping[str, Any]) -> ComponentSource:
    condition = str(row.get("condition") or row.get("status") or "").lower()
    source = str(row.get("source") or "").lower()
    if any(token in condition or token in source for token in ("salvage", "salvaged", "donor", "reused", "owned")):
        return ComponentSource.DONOR
    if any(token in condition or token in source for token in ("new", "purchase", "procure")):
        return ComponentSource.NEW
    return ComponentSource.UNKNOWN


def _part_bucket(row: Mapping[str, Any]) -> tuple[str, Domain]:
    kind = " ".join(
        str(row.get(key) or "").lower()
        for key in ("type", "category", "role", "name", "module_id")
    )
    if any(token in kind for token in ("motor", "servo", "actuator", "wheel", "gear", "pump", "fan")):
        return "actuation-system", Domain.MECHANICAL
    if any(token in kind for token in ("chassis", "frame", "bracket", "mount", "enclosure", "housing", "bearing")):
        return "mechanical-structure", Domain.MECHANICAL
    if any(token in kind for token in ("battery", "power", "regulator", "converter", "supply", "bms")):
        return "power-system", Domain.ELECTRICAL
    if any(token in kind for token in ("microcontroller", "controller", "esp32", "arduino", "mcu", "processor")):
        return "control-electronics", Domain.ELECTRICAL
    if any(token in kind for token in ("sensor", "camera", "encoder", "display", "imu", "lidar")):
        return "perception-system", Domain.ELECTRICAL
    return "electrical-system", Domain.ELECTRICAL


def _constraint_domain(key: str) -> Domain:
    lowered = key.lower()
    if any(token in lowered for token in ("voltage", "current", "power", "battery", "rail", "logic")):
        return Domain.ELECTRICAL
    if any(token in lowered for token in ("size", "dimension", "mass", "weight", "mount", "clearance", "travel", "torque")):
        return Domain.MECHANICAL
    if any(token in lowered for token in ("firmware", "latency", "loop_hz", "sample_rate", "protocol")):
        return Domain.FIRMWARE
    if any(token in lowered for token in ("budget", "cost", "supplier", "availability")):
        return Domain.SOURCING
    return Domain.SYSTEM


def _constraint_statement(key: str, value: Any) -> str:
    label = key.replace("_", " ").strip()
    if isinstance(value, bool):
        return f"{label} shall be {'enabled' if value else 'disabled'}."
    return f"{label} shall be {value}."


def machine_project_from_intake(intake: Mapping[str, Any]) -> MachineProject:
    """Create a traceable architecture seed from a raw Hardware Splicer intake."""

    body = dict(intake or {})
    raw_name = str(body.get("project_name") or body.get("name") or body.get("goal") or "machine-project")
    project_id = _slug(raw_name)
    name = str(body.get("project_name") or body.get("name") or project_id).replace("_", " ").strip()
    purpose = str(body.get("goal") or body.get("intent") or body.get("brief") or name).strip()
    constraints_body = _dict(body.get("constraints"))
    parts = _parts(body)

    requirement_ids: list[str] = ["req-primary-purpose"]
    requirements = [
        Requirement(
            requirement_id="req-primary-purpose",
            statement=purpose,
            kind=RequirementKind.FUNCTIONAL,
            allocated_to=["system"],
            authority=AuthorityState.DECLARED,
            metadata={"source_field": "goal"},
        )
    ]

    if constraints_body.get("runtime_min") is not None:
        requirement_ids.append("req-runtime")
        requirements.append(
            Requirement(
                requirement_id="req-runtime",
                statement=f"The machine shall operate for at least {constraints_body['runtime_min']} minutes.",
                kind=RequirementKind.PERFORMANCE,
                allocated_to=["power-system"],
                authority=AuthorityState.DECLARED,
                metadata={"source_field": "constraints.runtime_min"},
            )
        )

    subsystem_specs: dict[str, tuple[str, Domain, str]] = {
        "system": ("Machine system", Domain.SYSTEM, purpose),
    }
    if "req-runtime" in requirement_ids:
        subsystem_specs["power-system"] = (
            "Power system",
            Domain.ELECTRICAL,
            "Energy storage, conversion, distribution, and runtime delivery.",
        )

    components: list[Component] = []
    component_ids_by_subsystem: dict[str, list[str]] = {}

    for index, row in enumerate(parts):
        subsystem_id, domain = _part_bucket(row)
        subsystem_specs.setdefault(
            subsystem_id,
            (
                subsystem_id.replace("-", " ").title(),
                domain,
                "Seeded from declared intake parts.",
            ),
        )
        component_id = _slug(
            str(row.get("component_id") or row.get("module_id") or row.get("name") or f"component-{index + 1}"),
            fallback=f"component-{index + 1}",
        )
        if any(component.component_id == component_id for component in components):
            component_id = f"{component_id}-{index + 1}"
        components.append(
            Component(
                component_id=component_id,
                name=str(row.get("name") or row.get("module_id") or component_id),
                domain=domain,
                subsystem_id=subsystem_id,
                role=str(row.get("type") or row.get("role") or "declared intake component"),
                source=_part_source(row),
                authority=AuthorityState.DECLARED,
                metadata={"intake_part": row},
            )
        )
        component_ids_by_subsystem.setdefault(subsystem_id, []).append(component_id)

    if any(row.domain == Domain.ELECTRICAL for row in components):
        subsystem_specs.setdefault(
            "firmware-control",
            ("Firmware and control", Domain.FIRMWARE, "Control behavior and embedded software."),
        )
    if body.get("mechanism") or any(row.domain == Domain.MECHANICAL for row in components):
        subsystem_specs.setdefault(
            "mechanical-structure",
            ("Mechanical structure", Domain.MECHANICAL, "Structure, mounts, enclosure, and physical relationships."),
        )

    subsystems: list[Subsystem] = []
    child_subsystems = [key for key in subsystem_specs if key != "system"]
    for subsystem_id, (subsystem_name, domain, subsystem_purpose) in subsystem_specs.items():
        subsystems.append(
            Subsystem(
                subsystem_id=subsystem_id,
                name=subsystem_name,
                domain=domain,
                purpose=subsystem_purpose,
                parent_subsystem_id=None if subsystem_id == "system" else "system",
                requirement_ids=requirement_ids if subsystem_id == "system" else (
                    ["req-runtime"] if subsystem_id == "power-system" and "req-runtime" in requirement_ids else []
                ),
                function_ids=["function-primary"] if subsystem_id == "system" else [],
                component_ids=component_ids_by_subsystem.get(subsystem_id, []),
                authority=AuthorityState.PROPOSED,
            )
        )

    functions = [
        Function(
            function_id="function-primary",
            name="Deliver primary machine purpose",
            description=purpose,
            allocated_subsystem_ids=child_subsystems or ["system"],
            requirement_ids=["req-primary-purpose"],
            authority=AuthorityState.PROPOSED,
        )
    ]

    constraints: list[Constraint] = []
    for index, (key, value) in enumerate(sorted(constraints_body.items())):
        constraints.append(
            Constraint(
                constraint_id=f"constraint-{_slug(str(key), fallback=str(index + 1))}",
                name=str(key).replace("_", " ").title(),
                domain=_constraint_domain(str(key)),
                statement=_constraint_statement(str(key), value),
                applies_to=["system"],
                source_requirement_ids=["req-runtime"] if key == "runtime_min" and "req-runtime" in requirement_ids else [],
                authority=AuthorityState.DECLARED,
                metadata={"raw_value": value},
            )
        )

    return MachineProject(
        project_id=project_id,
        name=name,
        purpose=purpose,
        lifecycle_state=LifecycleState.ARCHITECTURE,
        requirements=requirements,
        functions=functions,
        subsystems=subsystems,
        components=components,
        constraints=constraints,
        discipline_payloads={"project_intake": body},
        metadata={
            "seed": "machine_project_from_intake.v1",
            "interfaces_inferred": False,
            "verification_inferred": False,
            "authority_preserved_without_upgrade": True,
        },
    )

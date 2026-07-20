"""Authority-limited authoring operations for canonical machine projects."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .machine_project import (
    AuthorityState,
    Component,
    Constraint,
    Interface,
    InterfaceContract,
    MachineProject,
    Requirement,
    RequirementKind,
    Subsystem,
)

_ALLOWED_AUTHORING_AUTHORITY = {
    AuthorityState.UNKNOWN,
    AuthorityState.PROPOSED,
    AuthorityState.DECLARED,
}


class MachineEditError(ValueError):
    pass


def _authority(value: Any, *, label: str) -> None:
    if value is None:
        return
    try:
        authority = AuthorityState(str(value))
    except ValueError as exc:
        raise MachineEditError(f"invalid {label} authority: {value!r}") from exc
    if authority not in _ALLOWED_AUTHORING_AUTHORITY:
        raise MachineEditError(
            f"ordinary authoring cannot assign {authority.value} authority to {label}; "
            "measured and stronger states require evidence workflows"
        )


def _upsert(rows: list[Dict[str, Any]], id_field: str, payload: Mapping[str, Any]) -> None:
    object_id = str(payload.get(id_field) or "").strip()
    if not object_id:
        raise MachineEditError(f"{id_field} is required")
    for index, row in enumerate(rows):
        if str(row.get(id_field)) == object_id:
            rows[index] = {**row, **dict(payload)}
            return
    rows.append(dict(payload))


def _append_unique(row: Dict[str, Any], field: str, value: str) -> None:
    values = list(row.get(field) or [])
    if value not in values:
        values.append(value)
    row[field] = values


def _remove_value(row: Dict[str, Any], field: str, value: str) -> None:
    row[field] = [item for item in row.get(field) or [] if item != value]


def _object_index(project: Mapping[str, Any]) -> Dict[str, tuple[str, Dict[str, Any]]]:
    result: Dict[str, tuple[str, Dict[str, Any]]] = {}
    for collection, id_field in (
        ("functions", "function_id"),
        ("subsystems", "subsystem_id"),
        ("components", "component_id"),
        ("interfaces", "interface_id"),
    ):
        for row in project.get(collection, []):
            result[str(row.get(id_field))] = (collection, row)
    return result


def _sync_requirement_allocation(
    project: Dict[str, Any],
    requirement_id: str,
    allocated_to: list[str],
) -> None:
    index = _object_index(project)
    unknown = [object_id for object_id in allocated_to if object_id not in index]
    if unknown:
        raise MachineEditError(
            f"requirement {requirement_id!r} allocation references unknown objects: {', '.join(unknown)}"
        )
    for collection in ("functions", "subsystems", "components", "interfaces"):
        for row in project.get(collection, []):
            _remove_value(row, "requirement_ids", requirement_id)
    for object_id in allocated_to:
        _, row = index[object_id]
        _append_unique(row, "requirement_ids", requirement_id)


def _endpoint_subsystem_ids(project: Mapping[str, Any], interface: Mapping[str, Any]) -> set[str]:
    component_subsystems = {
        str(row.get("component_id")): str(row.get("subsystem_id"))
        for row in project.get("components", [])
    }
    subsystem_ids = {str(row.get("subsystem_id")) for row in project.get("subsystems", [])}
    result: set[str] = set()
    for endpoint in interface.get("endpoints") or []:
        object_id = str(endpoint.get("object_id") or "")
        if object_id in subsystem_ids:
            result.add(object_id)
        elif object_id in component_subsystems:
            result.add(component_subsystems[object_id])
    return result


def _sync_interface_membership(project: Dict[str, Any], interface_id: str) -> None:
    interface = next(
        (row for row in project.get("interfaces", []) if row.get("interface_id") == interface_id),
        None,
    )
    if interface is None:
        return
    participating = _endpoint_subsystem_ids(project, interface)
    for subsystem in project.get("subsystems", []):
        _remove_value(subsystem, "interface_ids", interface_id)
        if subsystem.get("subsystem_id") in participating:
            _append_unique(subsystem, "interface_ids", interface_id)


def _sync_component_membership(
    project: Dict[str, Any],
    component_id: str,
    subsystem_id: str,
) -> None:
    target = None
    for subsystem in project.get("subsystems", []):
        _remove_value(subsystem, "component_ids", component_id)
        if subsystem.get("subsystem_id") == subsystem_id:
            target = subsystem
    if target is None:
        raise MachineEditError(f"unknown component subsystem {subsystem_id!r}")
    _append_unique(target, "component_ids", component_id)


def _referencers(project: Mapping[str, Any], requirement_id: str) -> list[str]:
    references: list[str] = []
    for row in project.get("requirements", []):
        if row.get("requirement_id") != requirement_id and row.get("parent_requirement_id") == requirement_id:
            references.append(f"requirements/{row.get('requirement_id')}.parent_requirement_id")
        if row.get("requirement_id") == requirement_id and row.get("verification_method_ids"):
            references.extend(
                f"verifications/{verification_id}"
                for verification_id in row.get("verification_method_ids") or []
            )
    for collection, id_field, fields in (
        ("functions", "function_id", ("requirement_ids",)),
        ("subsystems", "subsystem_id", ("requirement_ids",)),
        ("components", "component_id", ("requirement_ids",)),
        ("interfaces", "interface_id", ("requirement_ids",)),
        ("constraints", "constraint_id", ("source_requirement_ids",)),
        ("verifications", "verification_id", ("requirement_ids",)),
    ):
        for row in project.get(collection, []):
            if any(requirement_id in (row.get(field) or []) for field in fields):
                references.append(f"{collection}/{row.get(id_field)}")
    return sorted(set(references))


def apply_machine_edits(
    project: MachineProject,
    operations: Iterable[Mapping[str, Any]],
) -> MachineProject:
    """Apply deterministic authoring operations and return a fully revalidated candidate."""

    body = project.model_dump(mode="json")
    for raw in operations:
        operation = str(raw.get("type") or "").strip()
        payload = raw.get("payload")
        if not isinstance(payload, Mapping):
            raise MachineEditError(f"operation {operation!r} requires an object payload")
        data = dict(payload)

        if operation == "upsert_requirement":
            _authority(data.get("authority"), label="requirement")
            existing = next(
                (row for row in body["requirements"] if row["requirement_id"] == data.get("requirement_id")),
                None,
            )
            validated = Requirement.model_validate({**(existing or {}), **data}).model_dump(mode="json")
            _upsert(body["requirements"], "requirement_id", validated)
            _sync_requirement_allocation(
                body,
                validated["requirement_id"],
                list(validated.get("allocated_to") or []),
            )

        elif operation == "allocate_requirement":
            requirement_id = str(data.get("requirement_id") or "")
            row = next((item for item in body["requirements"] if item["requirement_id"] == requirement_id), None)
            if row is None:
                raise MachineEditError(f"unknown requirement {requirement_id!r}")
            allocated_to = list(data.get("allocated_to") or [])
            row["allocated_to"] = allocated_to
            _sync_requirement_allocation(body, requirement_id, allocated_to)

        elif operation == "remove_requirement":
            requirement_id = str(data.get("requirement_id") or "")
            row = next((item for item in body["requirements"] if item["requirement_id"] == requirement_id), None)
            if row is None:
                raise MachineEditError(f"unknown requirement {requirement_id!r}")
            if row.get("kind") == RequirementKind.SAFETY.value and not bool(data.get("confirm_safety_removal")):
                raise MachineEditError("removing a safety requirement requires confirm_safety_removal=true")
            references = _referencers(body, requirement_id)
            if references:
                raise MachineEditError(
                    f"requirement {requirement_id!r} is still referenced by: {', '.join(references)}"
                )
            body["requirements"] = [
                item for item in body["requirements"] if item["requirement_id"] != requirement_id
            ]

        elif operation == "upsert_subsystem":
            _authority(data.get("authority"), label="subsystem")
            existing = next(
                (row for row in body["subsystems"] if row["subsystem_id"] == data.get("subsystem_id")),
                None,
            )
            validated = Subsystem.model_validate({**(existing or {}), **data}).model_dump(mode="json")
            _upsert(body["subsystems"], "subsystem_id", validated)

        elif operation == "upsert_component":
            _authority(data.get("authority"), label="component")
            existing = next(
                (row for row in body["components"] if row["component_id"] == data.get("component_id")),
                None,
            )
            validated = Component.model_validate({**(existing or {}), **data}).model_dump(mode="json")
            _upsert(body["components"], "component_id", validated)
            _sync_component_membership(
                body,
                validated["component_id"],
                validated["subsystem_id"],
            )

        elif operation == "upsert_constraint":
            _authority(data.get("authority"), label="constraint")
            existing = next(
                (row for row in body["constraints"] if row["constraint_id"] == data.get("constraint_id")),
                None,
            )
            validated = Constraint.model_validate({**(existing or {}), **data}).model_dump(mode="json")
            _upsert(body["constraints"], "constraint_id", validated)

        elif operation == "upsert_interface":
            _authority(data.get("authority"), label="interface")
            for contract in data.get("contracts") or []:
                _authority(contract.get("authority"), label="interface contract")
            existing = next(
                (row for row in body["interfaces"] if row["interface_id"] == data.get("interface_id")),
                None,
            )
            validated = Interface.model_validate({**(existing or {}), **data}).model_dump(mode="json")
            _upsert(body["interfaces"], "interface_id", validated)
            _sync_interface_membership(body, validated["interface_id"])

        elif operation == "update_interface_contract":
            interface_id = str(data.get("interface_id") or "")
            contract_type = str(data.get("contract_type") or "")
            interface = next(
                (row for row in body["interfaces"] if row["interface_id"] == interface_id),
                None,
            )
            if interface is None:
                raise MachineEditError(f"unknown interface {interface_id!r}")
            if not contract_type:
                raise MachineEditError("contract_type is required")
            _authority(data.get("authority"), label="interface contract")
            existing = next(
                (row for row in interface.get("contracts", []) if row["contract_type"] == contract_type),
                None,
            )
            contract_payload = {
                **(existing or {}),
                **{key: value for key, value in data.items() if key not in {"interface_id"}},
            }
            validated = InterfaceContract.model_validate(contract_payload).model_dump(mode="json")
            contracts = interface.setdefault("contracts", [])
            _upsert(contracts, "contract_type", validated)

        elif operation == "set_requested_release_state":
            state = str(data.get("requested_release_state") or "")
            if not state:
                raise MachineEditError("requested_release_state is required")
            body["requested_release_state"] = state

        else:
            raise MachineEditError(f"unsupported machine edit operation: {operation!r}")

        try:
            body = MachineProject.model_validate(body).model_dump(mode="json")
        except Exception as exc:
            raise MachineEditError(f"operation {operation!r} violates machine-project invariants: {exc}") from exc

    return MachineProject.model_validate(body)

"""Conservative projection from MachineProject into ElectricalDesign.

Only explicit component pin metadata and exact endpoint-port matches become electrical
connectivity. Unmatched endpoints remain visible as unresolved net fields.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .electrical_design import (
    ElectricalComponent,
    ElectricalDesign,
    ElectricalNet,
    ElectricalPin,
    NetKind,
    PinElectricalType,
    PowerDomain,
)
from .machine_project import AuthorityState, Domain, MachineProject


def _physical_electrical_component(row: Mapping[str, Any]) -> bool:
    if row.get("domain") == Domain.ELECTRICAL.value:
        return True
    part = row.get("part") if isinstance(row.get("part"), Mapping) else {}
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    return bool(
        part.get("symbol_ref")
        or part.get("footprint_ref")
        or metadata.get("electrical_pins")
    )


def _reference(row: Mapping[str, Any], index: int) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    value = metadata.get("reference") or metadata.get("designator")
    if value:
        return str(value)
    domain = str(row.get("domain") or "")
    prefix = "J" if "connector" in str(row.get("role") or "").lower() else "U"
    if domain == Domain.ELECTRICAL.value and "battery" in str(row.get("name") or "").lower():
        prefix = "BT"
    return f"{prefix}{index + 1}"


def _pin_type(value: Any) -> PinElectricalType:
    raw = str(value or PinElectricalType.PASSIVE.value).strip().lower()
    aliases = {
        "in": PinElectricalType.INPUT,
        "out": PinElectricalType.OUTPUT,
        "io": PinElectricalType.BIDIRECTIONAL,
        "bidir": PinElectricalType.BIDIRECTIONAL,
        "power": PinElectricalType.POWER_IN,
        "pwr_in": PinElectricalType.POWER_IN,
        "pwr_out": PinElectricalType.POWER_OUT,
        "nc": PinElectricalType.NO_CONNECT,
    }
    if raw in aliases:
        return aliases[raw]
    try:
        return PinElectricalType(raw)
    except ValueError:
        return PinElectricalType.PASSIVE


def _net_kind(value: Any) -> NetKind:
    raw = str(value or "signal").strip().lower()
    if raw in {"power", "supply"}:
        return NetKind.POWER
    if raw in {"ground", "gnd", "return"}:
        return NetKind.GROUND
    if raw in {"analog", "sensor_analog"}:
        return NetKind.ANALOG
    if raw in {"differential", "diff"}:
        return NetKind.DIFFERENTIAL
    return NetKind.SIGNAL


def _pin_payload(component: Mapping[str, Any], raw: Mapping[str, Any], index: int) -> Dict[str, Any]:
    component_id = str(component["component_id"])
    number = str(raw.get("number") or raw.get("pin") or index + 1)
    pin_id = str(raw.get("pin_id") or f"{component_id}:{number}")
    unresolved = list(raw.get("unresolved_fields") or [])
    authority = str(raw.get("authority") or component.get("authority") or AuthorityState.DECLARED.value)
    if unresolved and authority in {AuthorityState.VERIFIED.value, AuthorityState.AUTHORIZED.value}:
        authority = AuthorityState.DECLARED.value
    return {
        "pin_id": pin_id,
        "component_id": component_id,
        "number": number,
        "name": str(raw.get("name") or number),
        "electrical_type": _pin_type(raw.get("electrical_type") or raw.get("type")).value,
        "required": bool(raw.get("required", False)),
        "net_id": None,
        "voltage_min_v": raw.get("voltage_min_v"),
        "voltage_max_v": raw.get("voltage_max_v"),
        "max_current_a": raw.get("max_current_a"),
        "unresolved_fields": unresolved,
        "authority": authority,
        "metadata": {
            **(dict(raw.get("metadata")) if isinstance(raw.get("metadata"), Mapping) else {}),
            "machine_component_id": component_id,
        },
    }


def _contract_values(interface: Mapping[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    values: Dict[str, Any] = {}
    unresolved: list[str] = []
    for contract in interface.get("contracts") or []:
        if not isinstance(contract, Mapping):
            continue
        values.update(dict(contract.get("values") or {}))
        unresolved.extend(str(value) for value in contract.get("unresolved_fields") or [])
    return values, sorted(set(unresolved))


def _voltage_range(values: Mapping[str, Any]) -> tuple[float | None, float | None]:
    lower = values.get("voltage_min_v")
    upper = values.get("voltage_max_v")
    nominal = values.get("nominal_voltage_v")
    logic = values.get("logic_voltage_v")
    if nominal is not None:
        lower = nominal if lower is None else lower
        upper = nominal if upper is None else upper
    if logic is not None:
        lower = 0.0 if lower is None else lower
        upper = logic if upper is None else upper
    return lower, upper


def electrical_design_from_machine_project(project: MachineProject) -> ElectricalDesign:
    body = project.model_dump(mode="json")
    source_components = [row for row in body["components"] if _physical_electrical_component(row)]
    components: list[Dict[str, Any]] = []
    pins: list[Dict[str, Any]] = []
    pin_lookup: Dict[tuple[str, str], str] = {}

    for index, row in enumerate(source_components):
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        raw_pins = metadata.get("electrical_pins") if isinstance(metadata.get("electrical_pins"), list) else []
        component_pins: list[str] = []
        for pin_index, raw in enumerate(raw_pins):
            if not isinstance(raw, Mapping):
                continue
            pin = _pin_payload(row, raw, pin_index)
            pins.append(pin)
            component_pins.append(pin["pin_id"])
            pin_lookup[(row["component_id"], pin["number"])] = pin["pin_id"]
            pin_lookup[(row["component_id"], pin["name"])] = pin["pin_id"]
            pin_lookup[(row["component_id"], pin["pin_id"])] = pin["pin_id"]
        part = row.get("part") if isinstance(row.get("part"), Mapping) else {}
        components.append(
            ElectricalComponent(
                component_id=row["component_id"],
                reference=_reference(row, index),
                name=row["name"],
                symbol_ref=part.get("symbol_ref"),
                footprint_ref=part.get("footprint_ref"),
                pin_ids=component_pins,
                authority=row.get("authority") or AuthorityState.DECLARED.value,
                metadata={
                    "machine_domain": row.get("domain"),
                    "machine_role": row.get("role"),
                    "pin_model_missing": not bool(component_pins),
                },
            ).model_dump(mode="json")
        )

    pin_by_id = {row["pin_id"]: row for row in pins}
    component_ids = {row["component_id"] for row in components}
    nets: list[Dict[str, Any]] = []

    for interface in body["interfaces"]:
        values, unresolved = _contract_values(interface)
        connected: list[str] = []
        for endpoint in interface.get("endpoints") or []:
            object_id = str(endpoint.get("object_id") or "")
            port = str(endpoint.get("port") or "")
            if object_id not in component_ids:
                unresolved.append(f"endpoint_binding:{object_id}:{port}")
                continue
            pin_id = pin_lookup.get((object_id, port))
            if pin_id is None:
                unresolved.append(f"pin_mapping:{object_id}:{port}")
                continue
            pin = pin_by_id[pin_id]
            if pin["net_id"] is not None and pin["net_id"] != interface["interface_id"]:
                unresolved.append(f"pin_already_bound:{pin_id}")
                continue
            pin["net_id"] = interface["interface_id"]
            connected.append(pin_id)

        lower, upper = _voltage_range(values)
        authority = str(interface.get("authority") or AuthorityState.UNKNOWN.value)
        unresolved = sorted(set(unresolved))
        source_authority = authority
        if unresolved and authority in {AuthorityState.VERIFIED.value, AuthorityState.AUTHORIZED.value}:
            authority = AuthorityState.DECLARED.value
        net = ElectricalNet(
            net_id=interface["interface_id"],
            name=interface["name"],
            kind=_net_kind(interface.get("kind")),
            pin_ids=connected,
            voltage_min_v=lower,
            voltage_max_v=upper,
            peak_current_a=values.get("peak_current_a") or values.get("max_current_a"),
            pair_net_id=values.get("pair_net_id"),
            unresolved_fields=unresolved,
            authority=authority,
            metadata={
                "machine_interface_id": interface["interface_id"],
                "source_authority": source_authority,
                "authority_downgraded_for_unresolved": authority != source_authority,
            },
        )
        nets.append(net.model_dump(mode="json"))

    power_domains: list[Dict[str, Any]] = []
    declared_domains = body.get("discipline_payloads", {}).get("power_domains")
    if isinstance(declared_domains, list):
        for raw in declared_domains:
            if not isinstance(raw, Mapping):
                continue
            power_domains.append(PowerDomain.model_validate(raw).model_dump(mode="json"))

    return ElectricalDesign(
        design_id=f"{project.project_id}-electrical",
        project_id=project.project_id,
        components=[ElectricalComponent.model_validate(row) for row in components],
        pins=[ElectricalPin.model_validate(row) for row in pins],
        nets=[ElectricalNet.model_validate(row) for row in nets],
        power_domains=[PowerDomain.model_validate(row) for row in power_domains],
        metadata={
            "source_schema": project.schema_version,
            "projection": "machine_project_to_electrical_design.v1",
            "connectivity_requires_exact_pin_matches": True,
        },
    )

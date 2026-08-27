"""Deterministic identity projection from interchange netlists to electrical truth.

Circuit JSON import produces source-graph/netlist truth. This module projects that
truth into the canonical :mod:`electrical_design` model without using display names
as authority-bearing identities. Imported data remains proposed until reviewed and
evidenced through the normal Hardware Splicer workflows.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping, Sequence

from .electrical_design import (
    ElectricalComponent,
    ElectricalDesign,
    ElectricalNet,
    ElectricalPin,
    NetKind,
    PinElectricalType,
)
from .machine_project import AuthorityState
from .netlist.ir import CircuitNetlist


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _pin_number(doc: Mapping[str, Any]) -> str:
    value = doc.get("pin_number")
    if value is None:
        value = (
            doc.get("most_frequently_referenced_by_name")
            or doc.get("name")
            or next(iter(doc.get("port_hints") or []), None)
            or doc.get("source_port_id")
        )
    return _text(value)


def _pin_type(value: Any) -> PinElectricalType:
    raw = _text(value).lower()
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
        return PinElectricalType(raw) if raw else PinElectricalType.PASSIVE
    except ValueError:
        return PinElectricalType.PASSIVE


def _net_kind(name: str, source_net: Mapping[str, Any]) -> NetKind:
    upper = name.upper()
    if source_net.get("is_ground") or upper in {"GND", "AGND", "DGND", "PGND"}:
        return NetKind.GROUND
    if (
        source_net.get("is_power")
        or upper.startswith(("VCC", "VDD", "VBUS", "+"))
        or upper.endswith(("V", "_POWER"))
    ):
        return NetKind.POWER
    if source_net.get("is_analog"):
        return NetKind.ANALOG
    if source_net.get("is_differential"):
        return NetKind.DIFFERENTIAL
    return NetKind.SIGNAL


def _component_identity(source_component_id: str, reference: str) -> str:
    if source_component_id:
        return f"electrical:source-component:{source_component_id}"
    return f"electrical:reference:{reference}"


def _pin_identity(source_port_id: str, pin_key: str) -> str:
    if source_port_id:
        return f"electrical:source-port:{source_port_id}"
    return f"electrical:pin:{_digest(pin_key)}"


def _net_identity(name: str, source_net_ids: Sequence[str]) -> str:
    values = sorted({_text(value) for value in source_net_ids if _text(value)})
    if len(values) == 1:
        return f"electrical:source-net:{values[0]}"
    if values:
        return f"electrical:source-net-group:{_digest('|'.join(values))}"
    return f"electrical:net:{_digest(name)}"


def electrical_design_from_interchange(
    netlist: CircuitNetlist,
    documents: Sequence[Mapping[str, Any]],
    *,
    project_id: str,
    design_id: str | None = None,
) -> ElectricalDesign:
    """Project imported connectivity into stable canonical electrical identities.

    Source component/port/net identifiers are preferred. KiCad-style references,
    pins, and net names remain explicit aliases for artifact matching. Any ambiguous
    or unresolved identity is retained in design metadata and never upgrades the
    imported authority ceiling above ``proposed``.
    """

    source_components = {
        _text(doc.get("source_component_id")): doc
        for doc in documents
        if doc.get("type") == "source_component" and doc.get("source_component_id")
    }
    source_ports = [doc for doc in documents if doc.get("type") == "source_port"]

    component_id_by_ref: Dict[str, str] = {}
    reference_by_source_id: Dict[str, str] = {}
    component_rows: Dict[str, Dict[str, Any]] = {}
    unresolved: list[Dict[str, Any]] = []

    for component in netlist.components:
        source_component_id = _text(component.metadata.get("source_component_id"))
        component_id = _component_identity(source_component_id, component.ref)
        if component.ref in component_id_by_ref:
            unresolved.append(
                {
                    "kind": "duplicate_component_reference",
                    "reference": component.ref,
                    "component_id": component_id,
                }
            )
            continue
        component_id_by_ref[component.ref] = component_id
        if source_component_id:
            reference_by_source_id[source_component_id] = component.ref
        source_doc = source_components.get(source_component_id, {})
        component_rows[component.ref] = {
            "component_id": component_id,
            "reference": component.ref,
            "name": _text(source_doc.get("name")) or component.value or component.ref,
            "symbol_ref": source_doc.get("symbol_ref") or source_doc.get("kicad_symbol"),
            "footprint_ref": component.footprint or None,
            "pin_ids": [],
            "authority": AuthorityState.PROPOSED,
            "metadata": {
                **dict(component.metadata),
                "identity": {
                    "canonical_component_id": component_id,
                    "source_component_id": source_component_id or None,
                    "kicad_reference": component.ref,
                    "module_id": component.module_id,
                },
                "value": component.value,
                "authority_ceiling": AuthorityState.PROPOSED.value,
            },
        }

    port_by_pin_key: Dict[str, Mapping[str, Any]] = {}
    for port in source_ports:
        source_component_id = _text(port.get("source_component_id"))
        reference = reference_by_source_id.get(source_component_id)
        pin_number = _pin_number(port)
        if not reference or not pin_number:
            unresolved.append(
                {
                    "kind": "source_port_component_mapping",
                    "source_port_id": port.get("source_port_id"),
                    "source_component_id": source_component_id or None,
                }
            )
            continue
        pin_key = f"{reference}.{pin_number}"
        if pin_key in port_by_pin_key:
            unresolved.append(
                {
                    "kind": "ambiguous_source_port",
                    "pin_key": pin_key,
                    "source_port_ids": [
                        port_by_pin_key[pin_key].get("source_port_id"),
                        port.get("source_port_id"),
                    ],
                }
            )
            continue
        port_by_pin_key[pin_key] = port

    all_pin_keys = set(port_by_pin_key)
    for net in netlist.nets:
        all_pin_keys.update(pin.key() for pin in net.pins)

    pin_rows: Dict[str, Dict[str, Any]] = {}
    for pin_key in sorted(all_pin_keys):
        reference, separator, number = pin_key.partition(".")
        if not separator or reference not in component_rows:
            unresolved.append({"kind": "pin_component_mapping", "pin_key": pin_key})
            continue
        port = port_by_pin_key.get(pin_key, {})
        source_port_id = _text(port.get("source_port_id"))
        pin_id = _pin_identity(source_port_id, pin_key)
        component_id = component_id_by_ref[reference]
        pin_rows[pin_key] = {
            "pin_id": pin_id,
            "component_id": component_id,
            "number": number,
            "name": _text(port.get("name")) or number,
            "electrical_type": _pin_type(
                port.get("electrical_type") or port.get("pin_type") or port.get("type_hint")
            ),
            "required": bool(port.get("required", False)),
            "net_id": None,
            "unresolved_fields": [],
            "authority": AuthorityState.PROPOSED,
            "metadata": {
                "identity": {
                    "canonical_pin_id": pin_id,
                    "source_port_id": source_port_id or None,
                    "source_component_id": _text(port.get("source_component_id")) or None,
                    "kicad_reference": reference,
                    "kicad_pin": number,
                    "pin_key": pin_key,
                },
                "port_hints": list(port.get("port_hints") or []),
                "authority_ceiling": AuthorityState.PROPOSED.value,
            },
        }
        component_rows[reference]["pin_ids"].append(pin_id)

    source_net_metadata = dict(
        (netlist.metadata.get("circuit_json") or {}).get("source_nets") or {}
    )
    net_rows: list[ElectricalNet] = []
    net_identity_by_name: Dict[str, str] = {}

    for net in netlist.nets:
        source_info = dict(source_net_metadata.get(net.name) or {})
        source_net_ids = list(source_info.get("source_net_ids") or [])
        net_id = _net_identity(net.name, source_net_ids)
        net_identity_by_name[net.name] = net_id
        accepted_pin_ids: list[str] = []
        unresolved_fields: list[str] = []

        for pin_ref in net.pins:
            pin_key = pin_ref.key()
            pin = pin_rows.get(pin_key)
            if pin is None:
                unresolved_fields.append(f"pin_identity:{pin_key}")
                unresolved.append(
                    {
                        "kind": "net_pin_identity",
                        "net_name": net.name,
                        "pin_key": pin_key,
                    }
                )
                continue
            if pin["net_id"] is not None and pin["net_id"] != net_id:
                unresolved_fields.append(f"multiple_net_membership:{pin_key}")
                unresolved.append(
                    {
                        "kind": "multiple_net_membership",
                        "pin_key": pin_key,
                        "first_net_id": pin["net_id"],
                        "other_net_id": net_id,
                    }
                )
                continue
            pin["net_id"] = net_id
            accepted_pin_ids.append(pin["pin_id"])

        source_net = dict(source_info.get("source_net") or {})
        net_rows.append(
            ElectricalNet(
                net_id=net_id,
                name=net.name,
                kind=_net_kind(net.name, source_net),
                pin_ids=accepted_pin_ids,
                unresolved_fields=sorted(set(unresolved_fields)),
                authority=AuthorityState.PROPOSED,
                metadata={
                    "identity": {
                        "canonical_net_id": net_id,
                        "source_net_ids": source_net_ids,
                        "source_trace_ids": list(source_info.get("source_trace_ids") or []),
                        "kicad_net_name": net.name,
                    },
                    "authority_ceiling": AuthorityState.PROPOSED.value,
                },
            )
        )

    components = [
        ElectricalComponent.model_validate(component_rows[reference])
        for reference in sorted(component_rows)
    ]
    pins = [ElectricalPin.model_validate(pin_rows[key]) for key in sorted(pin_rows)]
    diagnostics = dict(netlist.metadata.get("circuit_json") or {})

    return ElectricalDesign(
        design_id=design_id or f"{project_id}-electrical-import",
        project_id=project_id,
        components=components,
        pins=pins,
        nets=net_rows,
        metadata={
            "source_schema": netlist.schema_version,
            "source": netlist.source,
            "projection": "interchange_netlist_to_electrical_design.v1",
            "interchange": netlist.metadata.get("interchange") or "circuit-json",
            "authority_ceiling": AuthorityState.PROPOSED.value,
            "identity_map": {
                "components_by_reference": component_id_by_ref,
                "pins_by_key": {key: row["pin_id"] for key, row in pin_rows.items()},
                "nets_by_name": net_identity_by_name,
            },
            "unresolved_identity": unresolved,
            "import_diagnostics": diagnostics,
        },
    )

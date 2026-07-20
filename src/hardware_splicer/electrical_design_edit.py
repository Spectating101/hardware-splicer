"""Deterministic authoring operations for canonical electrical designs."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .electrical_design import (
    ElectricalComponent,
    ElectricalDesign,
    ElectricalNet,
    ElectricalPin,
    PowerDomain,
)
from .machine_project import AuthorityState


class ElectricalEditError(ValueError):
    pass


_ALLOWED_AUTHORITY = {
    AuthorityState.UNKNOWN,
    AuthorityState.PROPOSED,
    AuthorityState.DECLARED,
}


def _authority(value: Any, *, label: str) -> None:
    if value is None:
        return
    try:
        authority = AuthorityState(str(value))
    except ValueError as exc:
        raise ElectricalEditError(f"invalid {label} authority: {value!r}") from exc
    if authority not in _ALLOWED_AUTHORITY:
        raise ElectricalEditError(
            f"ordinary electrical authoring cannot assign {authority.value} authority to {label}"
        )


def _find(rows: list[Dict[str, Any]], id_field: str, object_id: str) -> Dict[str, Any] | None:
    return next((row for row in rows if str(row.get(id_field)) == object_id), None)


def _upsert(rows: list[Dict[str, Any]], id_field: str, payload: Mapping[str, Any]) -> None:
    object_id = str(payload.get(id_field) or "").strip()
    if not object_id:
        raise ElectricalEditError(f"{id_field} is required")
    for index, row in enumerate(rows):
        if str(row.get(id_field)) == object_id:
            rows[index] = dict(payload)
            return
    rows.append(dict(payload))


def _append_unique(row: Dict[str, Any], field: str, value: str) -> None:
    values = list(row.get(field) or [])
    if value not in values:
        values.append(value)
    row[field] = values


def _remove_value(row: Dict[str, Any], field: str, value: str) -> None:
    row[field] = [item for item in row.get(field) or [] if item != value]


def _sync_pin_component(body: Dict[str, Any], pin_id: str, component_id: str) -> None:
    target = None
    for component in body["components"]:
        _remove_value(component, "pin_ids", pin_id)
        if component["component_id"] == component_id:
            target = component
    if target is None:
        raise ElectricalEditError(f"unknown pin component {component_id!r}")
    _append_unique(target, "pin_ids", pin_id)


def _sync_pin_net(body: Dict[str, Any], pin_id: str, net_id: str | None) -> None:
    target = None
    for net in body["nets"]:
        _remove_value(net, "pin_ids", pin_id)
        if net_id is not None and net["net_id"] == net_id:
            target = net
    if net_id is not None and target is None:
        raise ElectricalEditError(f"unknown target net {net_id!r}")
    if target is not None:
        _append_unique(target, "pin_ids", pin_id)
    pin = _find(body["pins"], "pin_id", pin_id)
    if pin is None:
        raise ElectricalEditError(f"unknown pin {pin_id!r}")
    pin["net_id"] = net_id


def _sync_net_membership(body: Dict[str, Any], net_id: str, pin_ids: list[str]) -> None:
    unknown = [pin_id for pin_id in pin_ids if _find(body["pins"], "pin_id", pin_id) is None]
    if unknown:
        raise ElectricalEditError(f"net {net_id!r} references unknown pins: {', '.join(unknown)}")
    existing = _find(body["nets"], "net_id", net_id)
    old_pin_ids = list(existing.get("pin_ids") or []) if existing else []
    for pin_id in old_pin_ids:
        if pin_id not in pin_ids:
            pin = _find(body["pins"], "pin_id", pin_id)
            if pin is not None and pin.get("net_id") == net_id:
                pin["net_id"] = None
    for pin_id in pin_ids:
        _sync_pin_net(body, pin_id, net_id)


def apply_electrical_edits(
    design: ElectricalDesign,
    operations: Iterable[Mapping[str, Any]],
) -> ElectricalDesign:
    body = design.model_dump(mode="json")

    for raw in operations:
        operation = str(raw.get("type") or "").strip()
        payload = raw.get("payload")
        if not isinstance(payload, Mapping):
            raise ElectricalEditError(f"operation {operation!r} requires an object payload")
        data = dict(payload)

        if operation == "upsert_component":
            _authority(data.get("authority"), label="component")
            component_id = str(data.get("component_id") or "")
            existing = _find(body["components"], "component_id", component_id)
            validated = ElectricalComponent.model_validate({**(existing or {}), **data}).model_dump(mode="json")
            for pin_id in validated.get("pin_ids") or []:
                pin = _find(body["pins"], "pin_id", pin_id)
                if pin is None:
                    raise ElectricalEditError(f"component {component_id!r} references unknown pin {pin_id!r}")
                if pin["component_id"] != component_id:
                    raise ElectricalEditError(f"pin {pin_id!r} belongs to {pin['component_id']!r}")
            _upsert(body["components"], "component_id", validated)

        elif operation == "upsert_pin":
            _authority(data.get("authority"), label="pin")
            pin_id = str(data.get("pin_id") or "")
            existing = _find(body["pins"], "pin_id", pin_id)
            validated = ElectricalPin.model_validate({**(existing or {}), **data}).model_dump(mode="json")
            requested_net = validated.get("net_id")
            validated["net_id"] = existing.get("net_id") if existing else None
            _upsert(body["pins"], "pin_id", validated)
            _sync_pin_component(body, pin_id, validated["component_id"])
            _sync_pin_net(body, pin_id, requested_net)

        elif operation == "remove_pin":
            pin_id = str(data.get("pin_id") or "")
            pin = _find(body["pins"], "pin_id", pin_id)
            if pin is None:
                raise ElectricalEditError(f"unknown pin {pin_id!r}")
            if pin.get("net_id") and not bool(data.get("force_disconnect")):
                raise ElectricalEditError("connected pin removal requires force_disconnect=true")
            _sync_pin_net(body, pin_id, None)
            for component in body["components"]:
                _remove_value(component, "pin_ids", pin_id)
            body["pins"] = [row for row in body["pins"] if row["pin_id"] != pin_id]

        elif operation == "upsert_net":
            _authority(data.get("authority"), label="net")
            net_id = str(data.get("net_id") or "")
            existing = _find(body["nets"], "net_id", net_id)
            requested_pins = list(data.get("pin_ids") if "pin_ids" in data else (existing or {}).get("pin_ids") or [])
            validated = ElectricalNet.model_validate(
                {**(existing or {}), **data, "pin_ids": requested_pins}
            ).model_dump(mode="json")
            _sync_net_membership(body, net_id, requested_pins)
            _upsert(body["nets"], "net_id", validated)
            for pin_id in requested_pins:
                _sync_pin_net(body, pin_id, net_id)

        elif operation == "remove_net":
            net_id = str(data.get("net_id") or "")
            net = _find(body["nets"], "net_id", net_id)
            if net is None:
                raise ElectricalEditError(f"unknown net {net_id!r}")
            if net.get("pin_ids") and not bool(data.get("force_disconnect")):
                raise ElectricalEditError("connected net removal requires force_disconnect=true")
            for pin_id in list(net.get("pin_ids") or []):
                _sync_pin_net(body, pin_id, None)
            for other in body["nets"]:
                if other.get("pair_net_id") == net_id:
                    other["pair_net_id"] = None
            for domain in body["power_domains"]:
                _remove_value(domain, "source_net_ids", net_id)
                if domain.get("return_net_id") == net_id:
                    domain["return_net_id"] = None
            body["nets"] = [row for row in body["nets"] if row["net_id"] != net_id]

        elif operation == "connect_pin":
            pin_id = str(data.get("pin_id") or "")
            net_id = str(data.get("net_id") or "")
            if not pin_id or not net_id:
                raise ElectricalEditError("connect_pin requires pin_id and net_id")
            _sync_pin_net(body, pin_id, net_id)

        elif operation == "disconnect_pin":
            pin_id = str(data.get("pin_id") or "")
            if not pin_id:
                raise ElectricalEditError("disconnect_pin requires pin_id")
            _sync_pin_net(body, pin_id, None)

        elif operation == "upsert_power_domain":
            _authority(data.get("authority"), label="power domain")
            domain_id = str(data.get("domain_id") or "")
            existing = _find(body["power_domains"], "domain_id", domain_id)
            validated = PowerDomain.model_validate({**(existing or {}), **data}).model_dump(mode="json")
            _upsert(body["power_domains"], "domain_id", validated)

        else:
            raise ElectricalEditError(f"unsupported electrical edit operation: {operation!r}")

        try:
            body = ElectricalDesign.model_validate(body).model_dump(mode="json")
        except Exception as exc:
            raise ElectricalEditError(f"operation {operation!r} violates electrical-design invariants: {exc}") from exc

    return ElectricalDesign.model_validate(body)

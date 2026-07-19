"""Persistent, evidence-bearing updates for donor interface contracts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from .donor.interface_contract import (
    Contact,
    InterfaceContract,
    InterfaceStatus,
    SignalContract,
    SignalDirection,
    accepted_measurement,
)
from .evidence import EpistemicStatus, EvidenceValue, ReviewStatus

SCHEMA_VERSION = "hardware_splicer.evidence_contract_store.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"evidence package not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(value), indent=2), encoding="utf-8")
    tmp.replace(path)


def _evidence_value(raw: Any) -> EvidenceValue:
    if not isinstance(raw, Mapping):
        return EvidenceValue()
    try:
        status = EpistemicStatus(str(raw.get("status") or "unknown"))
    except ValueError:
        status = EpistemicStatus.UNKNOWN
    try:
        review = ReviewStatus(str(raw.get("review_status") or "unreviewed"))
    except ValueError:
        review = ReviewStatus.UNREVIEWED
    return EvidenceValue(
        value=raw.get("value"),
        unit=raw.get("unit"),
        status=status,
        confidence=float(raw.get("confidence") or 0.0),
        evidence_ids=tuple(str(v) for v in (raw.get("evidence_ids") or []) if str(v)),
        producer=str(raw.get("producer") or "unknown"),
        method=str(raw.get("method") or ""),
        review_status=review,
        supersedes=tuple(str(v) for v in (raw.get("supersedes") or []) if str(v)),
    )


def _contract_from_dict(raw: Mapping[str, Any]) -> InterfaceContract:
    contacts = [
        Contact(
            contact_id=str(row.get("contact_id") or ""),
            label=str(row.get("label") or ""),
            connector_ref=str(row.get("connector_ref") or ""),
            pin_number=str(row.get("pin_number") or ""),
            side=str(row.get("side") or "unknown"),
            x_mm=row.get("x_mm"),
            y_mm=row.get("y_mm"),
            evidence_ids=tuple(str(v) for v in (row.get("evidence_ids") or []) if str(v)),
        )
        for row in (raw.get("contacts") or [])
        if isinstance(row, Mapping) and row.get("contact_id")
    ]
    signals = []
    for row in raw.get("signals") or []:
        if not isinstance(row, Mapping) or not row.get("signal_id"):
            continue
        try:
            direction = SignalDirection(str(row.get("direction") or "unknown"))
        except ValueError:
            direction = SignalDirection.UNKNOWN
        signals.append(
            SignalContract(
                signal_id=str(row.get("signal_id")),
                contact_id=str(row.get("contact_id") or ""),
                direction=direction,
                voltage_min_v=_evidence_value(row.get("voltage_min_v")),
                voltage_max_v=_evidence_value(row.get("voltage_max_v")),
                active_level=_evidence_value(row.get("active_level")),
                idle_level=_evidence_value(row.get("idle_level")),
                protocol=_evidence_value(row.get("protocol")),
                controller_pin=_evidence_value(row.get("controller_pin")),
                notes=str(row.get("notes") or ""),
            )
        )
    try:
        status = InterfaceStatus(str(raw.get("status") or "unknown"))
    except ValueError:
        status = InterfaceStatus.UNKNOWN
    return InterfaceContract(
        interface_id=str(raw.get("interface_id") or ""),
        board_id=str(raw.get("board_id") or "donor-board"),
        block_id=str(raw.get("block_id") or "functional-block"),
        functional_role=str(raw.get("functional_role") or "unknown"),
        contacts=contacts,
        signals=signals,
        power_domains=[dict(v) for v in (raw.get("power_domains") or []) if isinstance(v, Mapping)],
        reference_equivalents=[dict(v) for v in (raw.get("reference_equivalents") or []) if isinstance(v, Mapping)],
        status=status,
        blockers=[str(v) for v in (raw.get("blockers") or []) if str(v)],
    )


def _accepted(value: Any, *, unit: str | None, evidence_id: str, method: str, producer: str) -> EvidenceValue:
    return accepted_measurement(
        value,
        unit=unit,
        evidence_id=evidence_id,
        method=method,
        producer=producer,
        confidence=1.0,
    )


def _upsert_contact(contract: InterfaceContract, update: Mapping[str, Any], evidence_id: str) -> str:
    contact_id = str(update.get("contact_id") or "").strip()
    if not contact_id:
        raise ValueError("contact_id is required")
    existing = next((row for row in contract.contacts if row.contact_id == contact_id), None)
    if existing:
        replacement = Contact(
            contact_id=contact_id,
            label=str(update.get("contact_label") or existing.label),
            connector_ref=str(update.get("connector_ref") or existing.connector_ref),
            pin_number=str(update.get("pin_number") or existing.pin_number),
            side=str(update.get("side") or existing.side),
            x_mm=update.get("x_mm", existing.x_mm),
            y_mm=update.get("y_mm", existing.y_mm),
            evidence_ids=tuple(dict.fromkeys((*existing.evidence_ids, evidence_id))),
        )
        contract.contacts = [replacement if row.contact_id == contact_id else row for row in contract.contacts]
    else:
        contract.contacts.append(
            Contact(
                contact_id=contact_id,
                label=str(update.get("contact_label") or contact_id),
                connector_ref=str(update.get("connector_ref") or ""),
                pin_number=str(update.get("pin_number") or ""),
                side=str(update.get("side") or "unknown"),
                x_mm=update.get("x_mm"),
                y_mm=update.get("y_mm"),
                evidence_ids=(evidence_id,),
            )
        )
    return contact_id


def _upsert_signal(contract: InterfaceContract, update: Mapping[str, Any], evidence_id: str) -> SignalContract:
    signal_id = str(update.get("signal_id") or "").strip()
    if not signal_id:
        raise ValueError("signal_id is required")
    contact_id = _upsert_contact(contract, update, evidence_id)
    current = next((row for row in contract.signals if row.signal_id == signal_id), None)
    try:
        direction = SignalDirection(str(update.get("direction") or (current.direction.value if current else "unknown")))
    except ValueError as exc:
        raise ValueError("direction must be input, output, bidirectional, power_input, power_output, passive, or unknown") from exc
    method = str(update.get("method") or "operator-reviewed interface contract")
    producer = str(update.get("producer") or "human+instrument")

    def measured(key: str, unit: str | None, fallback: EvidenceValue) -> EvidenceValue:
        if key not in update or update.get(key) in {None, ""}:
            return fallback
        return _accepted(update.get(key), unit=unit, evidence_id=evidence_id, method=method, producer=producer)

    signal = SignalContract(
        signal_id=signal_id,
        contact_id=contact_id,
        direction=direction,
        voltage_min_v=measured("voltage_min_v", "V", current.voltage_min_v if current else EvidenceValue()),
        voltage_max_v=measured("voltage_max_v", "V", current.voltage_max_v if current else EvidenceValue()),
        active_level=measured("active_level", None, current.active_level if current else EvidenceValue()),
        idle_level=measured("idle_level", None, current.idle_level if current else EvidenceValue()),
        protocol=measured("protocol", None, current.protocol if current else EvidenceValue()),
        controller_pin=measured("controller_pin", None, current.controller_pin if current else EvidenceValue()),
        notes=str(update.get("notes") or (current.notes if current else "")),
    )
    contract.signals = [signal if row.signal_id == signal_id else row for row in contract.signals]
    if not current:
        contract.signals.append(signal)
    return signal


def apply_interface_contract_update(
    build_dir: str | Path,
    *,
    interface_id: str,
    update: Mapping[str, Any],
) -> Dict[str, Any]:
    """Apply a typed, provenance-bearing interface update to SPLICE_PLAN.json."""
    root = Path(build_dir).resolve()
    plan_path = root / "SPLICE_PLAN.json"
    package = _read_json(plan_path)
    integrations = package.get("evidence_integrations")
    if not isinstance(integrations, dict):
        raise ValueError("build has no canonical evidence integrations")
    interfaces = integrations.get("interfaces")
    if not isinstance(interfaces, list):
        raise ValueError("evidence interfaces missing")
    target = next(
        (
            row
            for row in interfaces
            if isinstance(row, dict)
            and str((row.get("interface_contract") or {}).get("interface_id") or "") == interface_id
        ),
        None,
    )
    if target is None:
        raise ValueError(f"unknown interface_id: {interface_id}")
    operation = str(update.get("operation") or "upsert_signal")
    if operation != "upsert_signal":
        raise ValueError("only upsert_signal is currently supported")
    evidence_id = str(update.get("evidence_id") or f"interface-update:{interface_id}:{int(datetime.now(timezone.utc).timestamp())}")
    contract = _contract_from_dict(target.get("interface_contract") or {})
    signal = _upsert_signal(contract, update, evidence_id)
    contract.blockers = []
    contract.recompute_status()

    target["interface_contract"] = contract.to_dict()
    target["resolved_module"] = contract.to_resolved_module()
    target["blockers"] = contract.unresolved_fields()
    target["compile_status"] = "ready" if contract.can_generate_firmware() else "blocked"

    unresolved_driver_interfaces = []
    for row in interfaces:
        if not isinstance(row, Mapping):
            continue
        raw_contract = row.get("interface_contract") if isinstance(row.get("interface_contract"), Mapping) else {}
        role = str(raw_contract.get("functional_role") or "").lower()
        references = raw_contract.get("reference_equivalents") or []
        driver = "driver" in role or any(
            isinstance(ref, Mapping) and str(ref.get("module_id") or "") in {"l298n", "a4988-stepper"}
            for ref in references
        )
        if driver and raw_contract.get("firmware_authorized") is not True:
            unresolved_driver_interfaces.append(str(raw_contract.get("interface_id") or ""))
    authority = integrations.setdefault("authority", {})
    authority["firmware_authorized"] = not unresolved_driver_interfaces
    authority["unresolved_driver_interfaces"] = unresolved_driver_interfaces
    authority["updated_at"] = _now()

    evidence_graph = integrations.setdefault("evidence_graph", {})
    evidence_rows = evidence_graph.setdefault("evidence", [])
    evidence_rows.append(
        {
            "evidence_id": evidence_id,
            "kind": "interface_contract_update",
            "method": str(update.get("method") or "operator-reviewed interface contract"),
            "producer": str(update.get("producer") or "human+instrument"),
            "payload": {
                "interface_id": interface_id,
                "signal_id": signal.signal_id,
                "contact_id": signal.contact_id,
                "update": dict(update),
            },
            "created_at": _now(),
            "source_uri": update.get("source_uri"),
            "notes": str(update.get("notes") or ""),
        }
    )

    authority_modules = [
        dict(row)
        for row in (package.get("authority_resolved_modules") or integrations.get("authority_resolved_modules") or [])
        if isinstance(row, Mapping)
        and not (
            str(row.get("source") or "") == "donor_interface_contract"
            and str(row.get("donor_block_id") or "") == contract.block_id
            and str(row.get("board_id") or "") == contract.board_id
        )
    ]
    authority_modules.append(contract.to_resolved_module())
    package["authority_resolved_modules"] = authority_modules
    integrations["authority_resolved_modules"] = authority_modules

    firmware = package.get("firmware_scaffold")
    if isinstance(firmware, dict):
        firmware["evidence_authorized"] = bool(authority["firmware_authorized"])
        if authority["firmware_authorized"]:
            if firmware.get("status") == "blocked_needs_donor_control_interface":
                firmware["status"] = "candidate_authorized_for_compile"
            firmware.pop("authority_blockers", None)
        else:
            firmware["status"] = "blocked_needs_donor_control_interface"
            firmware["authority_blockers"] = unresolved_driver_interfaces

    package["evidence_integrations"] = integrations
    _write_json_atomic(plan_path, package)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "interface_id": interface_id,
        "interface_contract": contract.to_dict(),
        "interface_package": target,
        "authority": authority,
        "evidence_integrations": integrations,
        "resolved_fields": [
            field for field in ("signals", f"signals.{signal.signal_id}.direction", f"signals.{signal.signal_id}.voltage_max_v", f"signals.{signal.signal_id}.active_level", f"signals.{signal.signal_id}.controller_pin")
            if field not in contract.unresolved_fields()
        ],
        "unresolved_fields": contract.unresolved_fields(),
        "plan_path": str(plan_path),
    }

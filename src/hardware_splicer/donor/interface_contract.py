from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Mapping, Optional

from hardware_splicer.evidence import EvidenceValue, EpistemicStatus, ReviewStatus


SCHEMA_VERSION = "hardware_splicer.interface_contract.v1"


class SignalDirection(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    POWER_INPUT = "power_input"
    POWER_OUTPUT = "power_output"
    PASSIVE = "passive"
    UNKNOWN = "unknown"


class InterfaceStatus(str, Enum):
    UNKNOWN = "unknown"
    PARTIAL = "partial"
    VERIFIED = "verified"
    REJECTED = "rejected"


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "unknown"


def virtual_donor_module_id(board_id: str, block_id: str) -> str:
    return f"donor:{_slug(board_id)}:{_slug(block_id)}"


@dataclass(frozen=True)
class Contact:
    contact_id: str
    label: str = ""
    connector_ref: str = ""
    pin_number: str = ""
    side: str = "unknown"
    x_mm: Optional[float] = None
    y_mm: Optional[float] = None
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        body = asdict(self)
        body["evidence_ids"] = list(self.evidence_ids)
        return body


@dataclass(frozen=True)
class SignalContract:
    signal_id: str
    contact_id: str
    direction: SignalDirection = SignalDirection.UNKNOWN
    voltage_min_v: EvidenceValue = field(default_factory=EvidenceValue)
    voltage_max_v: EvidenceValue = field(default_factory=EvidenceValue)
    active_level: EvidenceValue = field(default_factory=EvidenceValue)
    idle_level: EvidenceValue = field(default_factory=EvidenceValue)
    protocol: EvidenceValue = field(default_factory=EvidenceValue)
    controller_pin: EvidenceValue = field(default_factory=EvidenceValue)
    notes: str = ""

    def authoritative_for_firmware(self) -> bool:
        if self.direction not in {
            SignalDirection.INPUT,
            SignalDirection.OUTPUT,
            SignalDirection.BIDIRECTIONAL,
        }:
            return False
        required = [self.voltage_max_v, self.active_level, self.controller_pin]
        return all(v.authoritative for v in required)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "contact_id": self.contact_id,
            "direction": self.direction.value,
            "voltage_min_v": self.voltage_min_v.to_dict(),
            "voltage_max_v": self.voltage_max_v.to_dict(),
            "active_level": self.active_level.to_dict(),
            "idle_level": self.idle_level.to_dict(),
            "protocol": self.protocol.to_dict(),
            "controller_pin": self.controller_pin.to_dict(),
            "notes": self.notes,
        }


@dataclass
class InterfaceContract:
    interface_id: str
    board_id: str
    block_id: str
    functional_role: str
    contacts: List[Contact] = field(default_factory=list)
    signals: List[SignalContract] = field(default_factory=list)
    power_domains: List[Dict[str, Any]] = field(default_factory=list)
    reference_equivalents: List[Dict[str, Any]] = field(default_factory=list)
    interface_complete: EvidenceValue = field(default_factory=EvidenceValue)
    status: InterfaceStatus = InterfaceStatus.UNKNOWN
    blockers: List[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @property
    def virtual_module_id(self) -> str:
        return virtual_donor_module_id(self.board_id, self.block_id)

    def _interface_complete_authoritative(self) -> bool:
        return self.interface_complete.authoritative and self.interface_complete.value is True

    def unresolved_fields(self) -> List[str]:
        unresolved: List[str] = []
        if not self.contacts:
            unresolved.append("contacts")
        if not self.signals:
            unresolved.append("signals")
        for signal in self.signals:
            prefix = f"signals.{signal.signal_id}"
            if signal.direction == SignalDirection.UNKNOWN:
                unresolved.append(f"{prefix}.direction")
            if not signal.voltage_max_v.authoritative:
                unresolved.append(f"{prefix}.voltage_max_v")
            if signal.direction in {
                SignalDirection.INPUT,
                SignalDirection.OUTPUT,
                SignalDirection.BIDIRECTIONAL,
            } and not signal.active_level.authoritative:
                unresolved.append(f"{prefix}.active_level")
            if signal.direction in {
                SignalDirection.INPUT,
                SignalDirection.OUTPUT,
                SignalDirection.BIDIRECTIONAL,
            } and not signal.controller_pin.authoritative:
                unresolved.append(f"{prefix}.controller_pin")
        if not self._interface_complete_authoritative():
            unresolved.append("interface_complete")
        return unresolved

    def _active_signals_authoritative(self) -> bool:
        active_signals = [
            s
            for s in self.signals
            if s.direction in {
                SignalDirection.INPUT,
                SignalDirection.OUTPUT,
                SignalDirection.BIDIRECTIONAL,
            }
        ]
        return bool(active_signals) and all(s.authoritative_for_firmware() for s in active_signals)

    def can_generate_firmware(self) -> bool:
        return (
            self.status == InterfaceStatus.VERIFIED
            and not self.blockers
            and self._active_signals_authoritative()
            and self._interface_complete_authoritative()
        )

    def recompute_status(self) -> InterfaceStatus:
        if self.blockers:
            self.status = InterfaceStatus.REJECTED
        elif self._active_signals_authoritative() and self._interface_complete_authoritative():
            self.status = InterfaceStatus.VERIFIED
        elif self.contacts or self.signals:
            self.status = InterfaceStatus.PARTIAL
        else:
            self.status = InterfaceStatus.UNKNOWN
        return self.status

    def to_resolved_module(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "part_name": self.functional_role or self.block_id,
            "module_id": self.virtual_module_id,
            "role": "drv" if "driver" in self.functional_role else "misc",
            "source": "donor_interface_contract",
            "confidence": 1.0 if self.status == InterfaceStatus.VERIFIED else 0.5,
            "matched_on": "interface_contract",
            "donor_block_id": self.block_id,
            "board_id": self.board_id,
            "interface_status": self.status.value,
            "interface_complete": self._interface_complete_authoritative(),
            "firmware_authorized": self.can_generate_firmware(),
            "reference_equivalents": list(self.reference_equivalents),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "interface_id": self.interface_id,
            "board_id": self.board_id,
            "block_id": self.block_id,
            "virtual_module_id": self.virtual_module_id,
            "functional_role": self.functional_role,
            "contacts": [c.to_dict() for c in self.contacts],
            "signals": [s.to_dict() for s in self.signals],
            "power_domains": list(self.power_domains),
            "reference_equivalents": list(self.reference_equivalents),
            "interface_complete": self.interface_complete.to_dict(),
            "status": self.status.value,
            "blockers": list(self.blockers),
            "unresolved_fields": self.unresolved_fields(),
            "firmware_authorized": self.can_generate_firmware(),
        }


def interface_from_functional_salvage(block: Mapping[str, Any]) -> InterfaceContract:
    board_id = str(block.get("board_id") or "donor-board")
    block_id = str(block.get("block_id") or block.get("name") or "functional-block")
    functional_role = str(block.get("function_type") or block.get("name") or "unknown")
    refs = [str(v) for v in (block.get("connector_refs") or []) if str(v).strip()]
    contacts = [
        Contact(
            contact_id=f"{ref}.unknown",
            label=ref,
            connector_ref=ref,
        )
        for ref in refs
    ]

    text = " ".join(
        [
            functional_role,
            str(block.get("name") or ""),
            " ".join(str(v) for v in (block.get("capabilities") or [])),
        ]
    ).lower()
    reference_equivalents: List[Dict[str, Any]] = []
    if "h-bridge" in text or "hbridge" in text or "motor driver" in text:
        reference_equivalents.append(
            {
                "module_id": "l298n",
                "relationship": "functional_analogy_only",
                "electrical_contract_inherited": False,
            }
        )
    elif "stepper" in text:
        reference_equivalents.append(
            {
                "module_id": "a4988-stepper",
                "relationship": "functional_analogy_only",
                "electrical_contract_inherited": False,
            }
        )

    contract = InterfaceContract(
        interface_id=f"if:{_slug(board_id)}:{_slug(block_id)}",
        board_id=board_id,
        block_id=block_id,
        functional_role=functional_role,
        contacts=contacts,
        reference_equivalents=reference_equivalents,
        status=InterfaceStatus.PARTIAL if contacts else InterfaceStatus.UNKNOWN,
    )
    return contract


def accepted_measurement(
    value: Any,
    *,
    unit: Optional[str],
    evidence_id: str,
    method: str,
    producer: str = "human+instrument",
    confidence: float = 1.0,
) -> EvidenceValue:
    return EvidenceValue(
        value=value,
        unit=unit,
        status=EpistemicStatus.MEASURED,
        confidence=confidence,
        evidence_ids=(evidence_id,),
        producer=producer,
        method=method,
        review_status=ReviewStatus.ACCEPTED,
    )

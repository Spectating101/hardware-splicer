"""Canonical pin/net/power-domain electrical design model and ERC.

The electrical model is intentionally separate from the visual graph. A canvas edge is
not an electrical connection until component pins, net membership, voltage/current
limits, and unresolved fields are represented here.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .machine_project import AuthorityState


ELECTRICAL_DESIGN_SCHEMA = "hardware_splicer.electrical_design.v1"


class PinElectricalType(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    PASSIVE = "passive"
    POWER_IN = "power_in"
    POWER_OUT = "power_out"
    OPEN_COLLECTOR = "open_collector"
    OPEN_EMITTER = "open_emitter"
    NO_CONNECT = "no_connect"


class NetKind(str, Enum):
    SIGNAL = "signal"
    POWER = "power"
    GROUND = "ground"
    ANALOG = "analog"
    DIFFERENTIAL = "differential"


class ElectricalBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ElectricalComponent(ElectricalBaseModel):
    component_id: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    name: str = Field(min_length=1)
    symbol_ref: str | None = None
    footprint_ref: str | None = None
    pin_ids: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ElectricalPin(ElectricalBaseModel):
    pin_id: str = Field(min_length=1)
    component_id: str = Field(min_length=1)
    number: str = Field(min_length=1)
    name: str = Field(min_length=1)
    electrical_type: PinElectricalType = PinElectricalType.PASSIVE
    required: bool = False
    net_id: str | None = None
    voltage_min_v: float | None = None
    voltage_max_v: float | None = None
    max_current_a: float | None = Field(default=None, ge=0)
    unresolved_fields: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_voltage_and_authority(self) -> "ElectricalPin":
        if (
            self.voltage_min_v is not None
            and self.voltage_max_v is not None
            and self.voltage_min_v > self.voltage_max_v
        ):
            raise ValueError("pin voltage_min_v cannot exceed voltage_max_v")
        if self.unresolved_fields and self.authority in {
            AuthorityState.VERIFIED,
            AuthorityState.AUTHORIZED,
        }:
            raise ValueError("a pin with unresolved fields cannot be verified or authorized")
        return self


class ElectricalNet(ElectricalBaseModel):
    net_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: NetKind = NetKind.SIGNAL
    pin_ids: list[str] = Field(default_factory=list)
    voltage_min_v: float | None = None
    voltage_max_v: float | None = None
    peak_current_a: float | None = Field(default=None, ge=0)
    pair_net_id: str | None = None
    unresolved_fields: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_voltage_and_authority(self) -> "ElectricalNet":
        if (
            self.voltage_min_v is not None
            and self.voltage_max_v is not None
            and self.voltage_min_v > self.voltage_max_v
        ):
            raise ValueError("net voltage_min_v cannot exceed voltage_max_v")
        if self.unresolved_fields and self.authority in {
            AuthorityState.VERIFIED,
            AuthorityState.AUTHORIZED,
        }:
            raise ValueError("a net with unresolved fields cannot be verified or authorized")
        return self


class PowerDomain(ElectricalBaseModel):
    domain_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    nominal_voltage_v: float
    voltage_min_v: float | None = None
    voltage_max_v: float | None = None
    source_net_ids: list[str] = Field(default_factory=list)
    return_net_id: str | None = None
    component_ids: list[str] = Field(default_factory=list)
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_range(self) -> "PowerDomain":
        lower = self.voltage_min_v if self.voltage_min_v is not None else self.nominal_voltage_v
        upper = self.voltage_max_v if self.voltage_max_v is not None else self.nominal_voltage_v
        if lower > upper:
            raise ValueError("power-domain voltage_min_v cannot exceed voltage_max_v")
        if not lower <= self.nominal_voltage_v <= upper:
            raise ValueError("power-domain nominal voltage must lie within its range")
        return self


class ElectricalIssue(ElectricalBaseModel):
    code: str
    message: str
    severity: str = "error"
    object_id: str | None = None
    related_ids: list[str] = Field(default_factory=list)


class ElectricalDesign(ElectricalBaseModel):
    schema_version: str = ELECTRICAL_DESIGN_SCHEMA
    design_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    components: list[ElectricalComponent] = Field(default_factory=list)
    pins: list[ElectricalPin] = Field(default_factory=list)
    nets: list[ElectricalNet] = Field(default_factory=list)
    power_domains: list[PowerDomain] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "ElectricalDesign":
        errors = electrical_reference_issues(self)
        if errors:
            raise ValueError("; ".join(issue.message for issue in errors))
        return self

    def erc_issues(self) -> list[ElectricalIssue]:
        return electrical_rule_check(self)


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def electrical_reference_issues(design: ElectricalDesign) -> list[ElectricalIssue]:
    issues: list[ElectricalIssue] = []
    component_ids = {row.component_id for row in design.components}
    pin_ids = {row.pin_id for row in design.pins}
    net_ids = {row.net_id for row in design.nets}

    for collection, values in (
        ("component", [row.component_id for row in design.components]),
        ("pin", [row.pin_id for row in design.pins]),
        ("net", [row.net_id for row in design.nets]),
        ("power domain", [row.domain_id for row in design.power_domains]),
    ):
        for duplicate in sorted(_duplicates(values)):
            issues.append(
                ElectricalIssue(
                    code="duplicate_id",
                    object_id=duplicate,
                    message=f"duplicate {collection} identifier {duplicate!r}",
                )
            )

    for duplicate in sorted(_duplicates([row.reference for row in design.components])):
        issues.append(
            ElectricalIssue(
                code="duplicate_reference",
                object_id=duplicate,
                message=f"duplicate component reference {duplicate!r}",
            )
        )

    pin_by_id = {row.pin_id: row for row in design.pins}
    net_by_id = {row.net_id: row for row in design.nets}

    for component in design.components:
        for pin_id in component.pin_ids:
            pin = pin_by_id.get(pin_id)
            if pin is None:
                issues.append(
                    ElectricalIssue(
                        code="invalid_pin_ref",
                        object_id=component.component_id,
                        related_ids=[pin_id],
                        message=f"component {component.component_id!r} references unknown pin {pin_id!r}",
                    )
                )
            elif pin.component_id != component.component_id:
                issues.append(
                    ElectricalIssue(
                        code="pin_owner_mismatch",
                        object_id=pin_id,
                        related_ids=[component.component_id, pin.component_id],
                        message=f"pin {pin_id!r} is listed by {component.component_id!r} but owned by {pin.component_id!r}",
                    )
                )

    for pin in design.pins:
        if pin.component_id not in component_ids:
            issues.append(
                ElectricalIssue(
                    code="invalid_component_ref",
                    object_id=pin.pin_id,
                    related_ids=[pin.component_id],
                    message=f"pin {pin.pin_id!r} references unknown component {pin.component_id!r}",
                )
            )
        if pin.net_id is not None:
            net = net_by_id.get(pin.net_id)
            if net is None:
                issues.append(
                    ElectricalIssue(
                        code="invalid_net_ref",
                        object_id=pin.pin_id,
                        related_ids=[pin.net_id],
                        message=f"pin {pin.pin_id!r} references unknown net {pin.net_id!r}",
                    )
                )
            elif pin.pin_id not in net.pin_ids:
                issues.append(
                    ElectricalIssue(
                        code="net_membership_mismatch",
                        object_id=pin.pin_id,
                        related_ids=[pin.net_id],
                        message=f"pin {pin.pin_id!r} names net {pin.net_id!r} but is absent from its membership",
                    )
                )

    for net in design.nets:
        for pin_id in net.pin_ids:
            pin = pin_by_id.get(pin_id)
            if pin is None:
                issues.append(
                    ElectricalIssue(
                        code="invalid_pin_ref",
                        object_id=net.net_id,
                        related_ids=[pin_id],
                        message=f"net {net.net_id!r} references unknown pin {pin_id!r}",
                    )
                )
            elif pin.net_id != net.net_id:
                issues.append(
                    ElectricalIssue(
                        code="net_membership_mismatch",
                        object_id=pin_id,
                        related_ids=[net.net_id, str(pin.net_id)],
                        message=f"net {net.net_id!r} contains pin {pin_id!r}, but the pin names net {pin.net_id!r}",
                    )
                )
        if net.pair_net_id is not None and net.pair_net_id not in net_ids:
            issues.append(
                ElectricalIssue(
                    code="invalid_pair_ref",
                    object_id=net.net_id,
                    related_ids=[net.pair_net_id],
                    message=f"net {net.net_id!r} references unknown differential pair {net.pair_net_id!r}",
                )
            )

    for domain in design.power_domains:
        for net_id in domain.source_net_ids:
            if net_id not in net_ids:
                issues.append(
                    ElectricalIssue(
                        code="invalid_net_ref",
                        object_id=domain.domain_id,
                        related_ids=[net_id],
                        message=f"power domain {domain.domain_id!r} references unknown source net {net_id!r}",
                    )
                )
        if domain.return_net_id is not None and domain.return_net_id not in net_ids:
            issues.append(
                ElectricalIssue(
                    code="invalid_net_ref",
                    object_id=domain.domain_id,
                    related_ids=[domain.return_net_id],
                    message=f"power domain {domain.domain_id!r} references unknown return net {domain.return_net_id!r}",
                )
            )
        for component_id in domain.component_ids:
            if component_id not in component_ids:
                issues.append(
                    ElectricalIssue(
                        code="invalid_component_ref",
                        object_id=domain.domain_id,
                        related_ids=[component_id],
                        message=f"power domain {domain.domain_id!r} references unknown component {component_id!r}",
                    )
                )

    return issues


def _range_overlap(
    left_min: float | None,
    left_max: float | None,
    right_min: float | None,
    right_max: float | None,
) -> bool:
    if None in {left_min, left_max, right_min, right_max}:
        return True
    return max(float(left_min), float(right_min)) <= min(float(left_max), float(right_max))


def electrical_rule_check(design: ElectricalDesign) -> list[ElectricalIssue]:
    issues: list[ElectricalIssue] = []
    pin_by_id = {row.pin_id: row for row in design.pins}
    net_by_id = {row.net_id: row for row in design.nets}

    for pin in design.pins:
        if pin.required and pin.net_id is None:
            issues.append(
                ElectricalIssue(
                    code="required_pin_unconnected",
                    object_id=pin.pin_id,
                    message=f"required pin {pin.pin_id!r} is unconnected",
                )
            )
        if pin.unresolved_fields:
            issues.append(
                ElectricalIssue(
                    code="unresolved_pin",
                    severity="warning",
                    object_id=pin.pin_id,
                    message=f"pin {pin.pin_id!r} has unresolved fields: {', '.join(sorted(pin.unresolved_fields))}",
                )
            )

    for net in design.nets:
        pins = [pin_by_id[pin_id] for pin_id in net.pin_ids if pin_id in pin_by_id]
        if len(pins) == 1:
            issues.append(
                ElectricalIssue(
                    code="single_pin_net",
                    severity="warning",
                    object_id=net.net_id,
                    related_ids=[pins[0].pin_id],
                    message=f"net {net.net_id!r} connects only one pin",
                )
            )
        if net.unresolved_fields:
            issues.append(
                ElectricalIssue(
                    code="unresolved_net",
                    severity="warning",
                    object_id=net.net_id,
                    message=f"net {net.net_id!r} has unresolved fields: {', '.join(sorted(net.unresolved_fields))}",
                )
            )

        hard_drivers = [
            pin
            for pin in pins
            if pin.electrical_type in {PinElectricalType.OUTPUT, PinElectricalType.POWER_OUT}
        ]
        input_like = [
            pin
            for pin in pins
            if pin.electrical_type in {PinElectricalType.INPUT, PinElectricalType.POWER_IN}
        ]
        if len(hard_drivers) > 1:
            issues.append(
                ElectricalIssue(
                    code="multiple_drivers",
                    object_id=net.net_id,
                    related_ids=[pin.pin_id for pin in hard_drivers],
                    message=f"net {net.net_id!r} has multiple hard drivers",
                )
            )
        if input_like and not hard_drivers and not any(
            pin.electrical_type in {
                PinElectricalType.BIDIRECTIONAL,
                PinElectricalType.OPEN_COLLECTOR,
                PinElectricalType.OPEN_EMITTER,
            }
            for pin in pins
        ):
            issues.append(
                ElectricalIssue(
                    code="undriven_input_net",
                    object_id=net.net_id,
                    related_ids=[pin.pin_id for pin in input_like],
                    message=f"net {net.net_id!r} contains inputs but no driver",
                )
            )
        if net.kind == NetKind.POWER and not any(
            pin.electrical_type == PinElectricalType.POWER_OUT for pin in pins
        ):
            issues.append(
                ElectricalIssue(
                    code="power_without_source",
                    object_id=net.net_id,
                    related_ids=[pin.pin_id for pin in pins],
                    message=f"power net {net.net_id!r} has no power-output source",
                )
            )

        for pin in pins:
            if pin.electrical_type == PinElectricalType.NO_CONNECT:
                issues.append(
                    ElectricalIssue(
                        code="no_connect_pin_connected",
                        object_id=pin.pin_id,
                        related_ids=[net.net_id],
                        message=f"no-connect pin {pin.pin_id!r} is connected to net {net.net_id!r}",
                    )
                )
            if not _range_overlap(
                pin.voltage_min_v,
                pin.voltage_max_v,
                net.voltage_min_v,
                net.voltage_max_v,
            ):
                issues.append(
                    ElectricalIssue(
                        code="voltage_domain_mismatch",
                        object_id=pin.pin_id,
                        related_ids=[net.net_id],
                        message=f"pin {pin.pin_id!r} voltage range does not overlap net {net.net_id!r}",
                    )
                )

        if net.kind == NetKind.POWER and net.peak_current_a is not None:
            available = sum(
                float(pin.max_current_a)
                for pin in pins
                if pin.electrical_type == PinElectricalType.POWER_OUT and pin.max_current_a is not None
            )
            if available > 0 and float(net.peak_current_a) > available:
                issues.append(
                    ElectricalIssue(
                        code="source_current_exceeded",
                        object_id=net.net_id,
                        related_ids=[pin.pin_id for pin in pins if pin.electrical_type == PinElectricalType.POWER_OUT],
                        message=f"power net {net.net_id!r} requires {net.peak_current_a:g} A but sources declare {available:g} A",
                    )
                )

        if net.kind == NetKind.DIFFERENTIAL:
            if net.pair_net_id is None:
                issues.append(
                    ElectricalIssue(
                        code="differential_pair_missing",
                        object_id=net.net_id,
                        message=f"differential net {net.net_id!r} has no pair_net_id",
                    )
                )
            else:
                pair = net_by_id.get(net.pair_net_id)
                if pair is not None and pair.pair_net_id != net.net_id:
                    issues.append(
                        ElectricalIssue(
                            code="differential_pair_not_reciprocal",
                            object_id=net.net_id,
                            related_ids=[net.pair_net_id],
                            message=f"differential pair {net.net_id!r}/{net.pair_net_id!r} is not reciprocal",
                        )
                    )

    return issues

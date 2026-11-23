"""Bounded DC and single-driver signal checks for an explicitly specified harness.

Contracts describe declared design limits, not measured hardware. This does not
infer donor pinouts, conductor ampacity, connector mating or protocol behavior.
"""
from __future__ import annotations

from collections import defaultdict
import csv
from decimal import Decimal
from html import escape
import io
import json
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
Text = Annotated[str, Field(max_length=512)]
Number = Annotated[Decimal, Field(ge=0, le=1_000_000, allow_inf_nan=False, max_digits=16, decimal_places=6)]
Voltage = Annotated[Decimal, Field(ge=0, le=60, allow_inf_nan=False, max_digits=10, decimal_places=6)]


class WiringModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def no_boolean_numbers(cls, value):
        if isinstance(value, bool):
            raise ValueError("boolean values are not wiring specifications")
        return value


class VoltageRange(WiringModel):
    minimum: Voltage
    maximum: Voltage

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum > self.maximum:
            raise ValueError("voltage range is reversed")
        return self


class PinContract(WiringModel):
    pin_id: Identifier
    label: Text = ""
    role: Literal["power_out", "power_in", "ground", "signal_out", "signal_in", "unknown"] = "unknown"
    # Supply operating range for power pins. Digital input/output limits below
    # describe high/low levels separately; rail names are never logic thresholds.
    voltage: VoltageRange | None = None
    current_a: Number | None = None  # output capacity / input worst-case demand
    signal: Text = ""  # e.g. UART-data, not an inferred protocol implementation
    high: VoltageRange | None = None
    low: VoltageRange | None = None
    reference_pin: Identifier | None = None
    required: Literal["yes", "no"] = "no"


class EndpointContract(WiringModel):
    manufacturer: Text = ""
    mpn: Text = ""
    specification: Text = ""
    description: Text = ""
    pin_view: Text = ""  # mating face, board top, etc.; never guessed
    pins: list[PinContract] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def pin_identity(self):
        pins = {pin.pin_id: pin for pin in self.pins}
        if len(pins) != len(self.pins):
            raise ValueError("duplicate pin IDs")
        for pin in self.pins:
            if pin.reference_pin is not None and (pin.reference_pin not in pins or pins[pin.reference_pin].role != "ground"):
                raise ValueError("reference_pin must identify a ground pin on this endpoint")
        return self


class WireContract(WiringModel):
    manufacturer: Text = ""
    mpn: Text = ""
    specification: Text = ""
    gauge_awg: int | None = Field(default=None, ge=0, le=40, strict=True)
    ampacity_a: Number | None = None
    insulation_voltage_v: Number | None = None


class SourceBinding(WiringModel):
    source_id: str = Field(min_length=1, max_length=256)
    content_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    pointer: str = Field(default="", max_length=512)  # RFC 6901 into retained JSON


class Endpoint(WiringModel):
    endpoint_id: Identifier
    material_id: Identifier
    contract: EndpointContract
    source: SourceBinding | None = None


class Terminal(WiringModel):
    endpoint_id: Identifier
    pin_id: Identifier


class Wire(WiringModel):
    wire_id: Identifier
    material_id: Identifier
    start: Terminal
    end: Terminal
    length_m: Number = Field(gt=0, le=100)
    color: Literal["BK", "BN", "RD", "OR", "YE", "GN", "BU", "VT", "GY", "WT", "PK", "TQ"] | None = None
    contract: WireContract
    source: SourceBinding | None = None


class HarnessSpecification(WiringModel):
    description: Text = ""
    endpoints: list[Endpoint] = Field(min_length=2, max_length=50)
    wires: list[Wire] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def topology(self):
        endpoints = {row.endpoint_id: row for row in self.endpoints}
        if len(endpoints) != len(self.endpoints):
            raise ValueError("duplicate endpoint IDs")
        if len({row.wire_id for row in self.wires}) != len(self.wires):
            raise ValueError("duplicate wire IDs")
        pairs = set()
        for wire in self.wires:
            pair = []
            for terminal in (wire.start, wire.end):
                endpoint = endpoints.get(terminal.endpoint_id)
                if endpoint is None or terminal.pin_id not in {pin.pin_id for pin in endpoint.contract.pins}:
                    raise ValueError("wire references an unknown endpoint or pin")
                pair.append((terminal.endpoint_id, terminal.pin_id))
            if pair[0] == pair[1] or tuple(sorted(pair)) in pairs:
                raise ValueError("duplicate or self-connected wire")
            pairs.add(tuple(sorted(pair)))
        return self


def assess_harness(specification: HarnessSpecification, material_lines: list[dict], source_checks: list[dict]) -> dict:
    """Evaluate declared limits on the complete connected nets, not wire pairs."""
    spec = specification
    issues = []

    def issue(severity, code, target, **details):
        issues.append({"severity": severity, "code": code, "target": target, **details})

    material_map = {row["material_id"]: row for row in material_lines}
    quantities = defaultdict(Decimal)
    units = {}
    for row, quantity, unit, target in [
        *((ep, Decimal(1), "ea", ep.endpoint_id) for ep in spec.endpoints),
        *((wire, wire.length_m, "m", wire.wire_id) for wire in spec.wires),
    ]:
        material = material_map.get(row.material_id)
        if material is None:
            raise ValueError("harness material is absent from its material assessment: " + row.material_id)
        if material["unit"] != unit or (row.material_id in units and units[row.material_id] != unit):
            raise ValueError("endpoint materials require ea and wire materials require m")
        units[row.material_id] = unit
        quantities[row.material_id] += quantity
        contract = row.contract
        identity = (material["manufacturer"].strip().casefold(), material["mpn"].strip())
        if all(identity):
            matches = identity == (contract.manufacturer.strip().casefold(), contract.mpn.strip())
        else:
            matches = bool(contract.specification.strip() and contract.specification.strip() == material["specification"].strip())
        if material["specification"].strip() and material["specification"].strip() != contract.specification.strip():
            matches = False
        if not matches:
            issue("blocked", "contract_material_identity_mismatch", target, material_id=row.material_id)
        if material.get("issues"):
            issue("unresolved", "material_assessment_has_open_issues", target, material_id=row.material_id,
                  material_issues=material["issues"])
    for material_id, quantity in quantities.items():
        if quantity > Decimal(material_map[material_id]["quantity"]):
            issue("blocked", "harness_exceeds_material_requirement", material_id,
                  required=str(quantity), assessed=material_map[material_id]["quantity"], unit=units[material_id])
    for row in source_checks:
        if row["status"] != "registered_contract_bytes_match":
            issue("unresolved", "contract_source_unbound", row["target"])

    pins = {(ep.endpoint_id, pin.pin_id): pin for ep in spec.endpoints for pin in ep.contract.pins}
    parent = {key: key for key in pins}

    def find(key):
        while parent[key] != key:
            key = parent[key]
        return key

    def terminal(value):
        return (value.endpoint_id, value.pin_id)

    connected = set()
    for wire in spec.wires:
        a, b = terminal(wire.start), terminal(wire.end)
        parent[find(a)] = find(b)
        connected.update((a, b))
    groups = defaultdict(list)
    for key in sorted(connected):
        groups[find(key)].append(key)
    net_names = {root: "net-" + str(index + 1) for index, root in enumerate(sorted(groups))}
    nets = []
    return_demands = defaultdict(Decimal)
    for key, pin in pins.items():
        if pin.role == "power_in" and pin.current_a is not None and key in connected and pin.reference_pin:
            return_demands[find((key[0], pin.reference_pin))] += pin.current_a
    for endpoint in spec.endpoints:
        if not endpoint.contract.pin_view.strip():
            issue("unresolved", "pin_view_missing", endpoint.endpoint_id)
        for pin in endpoint.contract.pins:
            if pin.required == "yes" and (endpoint.endpoint_id, pin.pin_id) not in connected:
                issue("unresolved", "required_pin_unconnected", endpoint.endpoint_id + "." + pin.pin_id)
    for root in sorted(groups):
        keys = groups[root]
        net_id = net_names[root]
        roles = {pins[key].role for key in keys}
        wires = [wire for wire in spec.wires if find(terminal(wire.start)) == root]
        before = len(issues)
        max_voltage = None
        demand = None
        if roles == {"ground"}:
            demand = return_demands[root]
            # Every connected supply load needs a declared demand; otherwise
            # the return conductor cannot acquire a zero-current pass.
            for key, pin in pins.items():
                if key in connected and pin.role == "power_in" and pin.reference_pin and find((key[0], pin.reference_pin)) == root and pin.current_a is None:
                    issue("unresolved", "return_current_unknown", net_id)
                    demand = None
        elif roles <= {"power_in", "power_out"} and "power_out" in roles:
            drivers = [key for key in keys if pins[key].role == "power_out"]
            loads = [key for key in keys if pins[key].role == "power_in"]
            if len(drivers) != 1:
                issue("blocked", "multiple_power_sources", net_id)
            elif not loads:
                issue("unresolved", "power_load_missing", net_id)
            else:
                driver = pins[drivers[0]]
                demand = sum((pins[key].current_a or Decimal(0) for key in loads), Decimal(0))
                if driver.current_a is None or any(pins[key].current_a is None for key in loads):
                    issue("unresolved", "power_current_limit_missing", net_id)
                    if any(pins[key].current_a is None for key in loads):
                        demand = None
                elif demand > driver.current_a:
                    issue("blocked", "supply_current_exceeded", net_id, demand_a=str(demand), capacity_a=str(driver.current_a))
                if driver.voltage is None:
                    issue("unresolved", "supply_voltage_missing", net_id)
                else:
                    max_voltage = driver.voltage.maximum
                    for key in loads:
                        allowed = pins[key].voltage
                        if allowed is None:
                            issue("unresolved", "load_voltage_missing", net_id, pin=".".join(key))
                        elif driver.voltage.minimum < allowed.minimum or driver.voltage.maximum > allowed.maximum:
                            issue("blocked", "supply_voltage_outside_load_range", net_id, pin=".".join(key))
        elif roles <= {"signal_in", "signal_out"} and "signal_out" in roles:
            drivers = [key for key in keys if pins[key].role == "signal_out"]
            loads = [key for key in keys if pins[key].role == "signal_in"]
            if len(drivers) != 1:
                issue("blocked", "multiple_signal_drivers", net_id)
            elif not loads:
                issue("unresolved", "signal_receiver_missing", net_id)
            else:
                driver = pins[drivers[0]]
                for key in loads:
                    receiver = pins[key]
                    if not driver.signal.strip() or not receiver.signal.strip():
                        issue("unresolved", "signal_identity_missing", net_id)
                    elif driver.signal != receiver.signal:
                        issue("blocked", "signal_identity_mismatch", net_id, pin=".".join(key))
                    for level in ("high", "low"):
                        output, allowed = getattr(driver, level), getattr(receiver, level)
                        if output is None or allowed is None:
                            issue("unresolved", "logic_" + level + "_limits_missing", net_id)
                        elif output.minimum < allowed.minimum or output.maximum > allowed.maximum:
                            issue("blocked", "logic_" + level + "_outside_input_range", net_id, pin=".".join(key))
                if driver.high is not None and driver.low is not None:
                    max_voltage = max(driver.high.maximum, driver.low.maximum)
                # Signal sink/source drive capacity is not specified by the
                # initial contract and must not become a complete signal pass.
                issue("unresolved", "signal_loading_and_timing_not_assessed", net_id)
        elif "unknown" in roles:
            issue("unresolved", "pin_role_unknown", net_id)
        else:
            issue("blocked", "incompatible_pin_roles", net_id, roles=sorted(roles))

        if roles != {"ground"}:
            references = []
            for key in keys:
                pin = pins[key]
                ref = (key[0], pin.reference_pin) if pin.reference_pin else None
                if ref is None or ref not in connected:
                    issue("unresolved", "ground_reference_unconnected", net_id, pin=".".join(key))
                else:
                    references.append(find(ref))
            if len(set(references)) > 1:
                issue("blocked", "ground_reference_mismatch", net_id)
        for wire in wires:
            if wire.contract.gauge_awg is None:
                issue("unresolved", "wire_gauge_missing", wire.wire_id)
            if demand is not None:
                if wire.contract.ampacity_a is None:
                    issue("unresolved", "wire_ampacity_missing", wire.wire_id)
                elif demand > wire.contract.ampacity_a:
                    issue("blocked", "wire_current_exceeded", wire.wire_id, demand_a=str(demand))
            if max_voltage is not None:
                if wire.contract.insulation_voltage_v is None:
                    issue("unresolved", "wire_insulation_rating_missing", wire.wire_id)
                elif max_voltage > wire.contract.insulation_voltage_v:
                    issue("blocked", "wire_insulation_voltage_exceeded", wire.wire_id)
        local = issues[before:]
        nets.append({"net_id": net_id, "pins": [".".join(key) for key in keys],
                     "wire_ids": [wire.wire_id for wire in wires], "roles": sorted(roles),
                     "declared_current_a": str(demand) if demand is not None else None,
                     "status": _status(local)})
    return {
        "schema_version": "hardware_splicer.harness_check.v1",
        "status": _status(issues), "issues": issues, "nets": nets,
        "summary": {"endpoint_count": len(spec.endpoints), "wire_count": len(spec.wires),
                    "net_count": len(nets), "blocked_count": sum(row["severity"] == "blocked" for row in issues),
                    "unresolved_count": sum(row["severity"] == "unresolved" for row in issues)},
        "harness_materials": [{"material_id": key, "quantity": str(value), "unit": units[key],
                               "assessed_material_shortage": material_map[key]["shortage"]}
                              for key, value in sorted(quantities.items())],
        "authority": "declared_contract_checks_only", "physical_authority_granted": False,
        "complete_device_compatibility_verified": False, "construction_ready": False,
        "limitations": [
            "Retained source bytes bind declarations; they do not establish manufacturer authenticity or physical measurements.",
            "Lengths, pin viewing orientation, terminations and ratings require their own source review; routing, fit and voltage drop are not verified.",
            "Ampacity is supplied explicitly, never inferred from AWG. Each conductor is conservatively checked against the entire net demand.",
            "Signal loading, timing, protocol behavior, shared regulator budgets, transients, fuses and complete device coverage are not assessed.",
        ],
    }


def _status(issues):
    return "blocked" if any(row["severity"] == "blocked" for row in issues) else "unresolved" if issues else "passes_declared_checks"


def wireviz_document(spec: HarnessSpecification, report: dict) -> str:
    """JSON is valid YAML; expose only our fixed data schema to WireViz."""
    names = {ep.endpoint_id: "X" + str(index + 1) for index, ep in enumerate(spec.endpoints)}
    connectors, cables, connections, pin_maps = {}, {}, [], {}

    def display(value):
        # Native TSV is line based; product text must not introduce new rows or
        # columns, and Graphviz must receive text rather than user HTML.
        return escape(re.sub(r"[\x00-\x1f\x7f]", " ", value))

    # WireViz expands connection strings such as 01 and 1-2 into numbers/ranges,
    # but does not normalize connector pins. Assign unambiguous aliases only
    # where needed and retain the physical identifier in the visible pin label.
    for endpoint in spec.endpoints:
        reserved = {pin.pin_id for pin in endpoint.contract.pins}
        mapping = {}
        for index, pin in enumerate(endpoint.contract.pins):
            value = pin.pin_id
            if re.fullmatch(r"0|[1-9][0-9]*", value):
                mapped = int(value)
            elif value.isdigit() or re.fullmatch(r"[0-9]+-[0-9]+", value):
                mapped = "HS_PIN_" + str(index + 1)
                while mapped in reserved:
                    mapped += "_"
                reserved.add(mapped)
            else:
                mapped = value
            mapping[value] = mapped
        pin_maps[endpoint.endpoint_id] = mapping

    for endpoint in spec.endpoints:
        contract = endpoint.contract
        connectors[names[endpoint.endpoint_id]] = {
            "type": display(contract.description or endpoint.endpoint_id),
            "manufacturer": display(contract.manufacturer), "mpn": display(contract.mpn),
            "pn": display(endpoint.material_id),
            "pins": [pin_maps[endpoint.endpoint_id][pin.pin_id] for pin in contract.pins],
            "pinlabels": [display((pin.pin_id + ": " if str(pin_maps[endpoint.endpoint_id][pin.pin_id]) != pin.pin_id else "") + (pin.label or pin.pin_id)) for pin in contract.pins],
            "notes": display("DIGITAL REVIEW: " + report["status"] + "; " + endpoint.endpoint_id + "; pin view: " + (contract.pin_view or "UNRESOLVED")),
        }
    for index, wire in enumerate(spec.wires):
        name = "W" + str(index + 1)
        cable = {"wirecount": 1, "length": float(wire.length_m), "pn": display(wire.material_id),
                 "manufacturer": display(wire.contract.manufacturer), "mpn": display(wire.contract.mpn),
                 "notes": display(wire.wire_id + "; declared cut length")}
        if wire.contract.gauge_awg is not None:
            cable["gauge"] = str(wire.contract.gauge_awg) + " AWG"
        if wire.color:
            cable["colors"] = [wire.color]
        cables[name] = cable
        connections.append([{names[wire.start.endpoint_id]: [pin_maps[wire.start.endpoint_id][wire.start.pin_id]]}, {name: [1]},
                            {names[wire.end.endpoint_id]: [pin_maps[wire.end.endpoint_id][wire.end.pin_id]]}])
    return json.dumps({"metadata": {"title": "DIGITAL REVIEW: " + report["status"]},
                       "connectors": connectors, "cables": cables, "connections": connections},
                      indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"


def cut_list_csv(spec: HarnessSpecification) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["wire_id", "material_id", "from_endpoint", "from_pin", "to_endpoint", "to_pin",
                     "length_m", "color", "gauge_awg", "manufacturer", "mpn", "specification"])
    for wire in spec.wires:
        row = [wire.wire_id, wire.material_id, wire.start.endpoint_id, wire.start.pin_id,
               wire.end.endpoint_id, wire.end.pin_id, str(wire.length_m), wire.color or "",
               wire.contract.gauge_awg if wire.contract.gauge_awg is not None else "",
               wire.contract.manufacturer, wire.contract.mpn, wire.contract.specification]
        writer.writerow(["'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value for value in row])
    return output.getvalue()

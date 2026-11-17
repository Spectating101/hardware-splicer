"""Bounded, declaration-based part substitution across an explicit assembly.

The evaluator checks supplied facts; it does not identify parts, infer missing
ratings, insert adapters, generate wiring, or grant physical authority. Geometry
is limited to axis-aligned nominal envelopes and declared XY mount patterns.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEMA = "hardware_splicer.part_substitution.v1"
Identifier = Annotated[str, Field(min_length=1, max_length=128)]
Text = Annotated[str, Field(min_length=1, max_length=512)]
Number = Annotated[float, Field(ge=0, le=1_000_000, allow_inf_nan=False)]
Current = Annotated[float, Field(ge=0, le=1000, allow_inf_nan=False)]
Voltage = Annotated[float, Field(ge=0, le=60, allow_inf_nan=False)]
Coordinate = Annotated[float, Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False)]
Dimension = Annotated[float, Field(gt=0, le=10000, allow_inf_nan=False)]
Point3 = Annotated[list[Coordinate], Field(min_length=3, max_length=3)]
Point2 = Annotated[list[Coordinate], Field(min_length=2, max_length=2)]
Dimensions = Annotated[list[Dimension], Field(min_length=3, max_length=3)]
VoltageRange = Annotated[list[Voltage], Field(min_length=2, max_length=2)]


class SubstitutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class SourceBinding(SubstitutionModel):
    source_id: Identifier
    content_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    pointer: str = Field(default="", max_length=512)


class Port(SubstitutionModel):
    port_id: Identifier
    kind: Literal["power", "signal"]
    direction: Literal["input", "output", "bidirectional", "passive", "unknown"] = "unknown"
    required: bool = True
    connector: Text | None = None
    pin_functions: dict[Identifier, Text] | None = Field(default=None, max_length=64)
    protocol: Text | None = None
    voltage_range_v: VoltageRange | None = None
    # Output/passive: current capacity. Input: worst-case current demand.
    current_a: Current | None = None
    # Explicitly joins power ports on the SAME part into one electrical rail.
    power_group: Identifier | None = None

    @model_validator(mode="after")
    def ordered_voltage(self):
        if self.voltage_range_v is not None and self.voltage_range_v[0] > self.voltage_range_v[1]:
            raise ValueError("voltage_range_v must be ordered")
        if self.kind != "power" and self.power_group is not None:
            raise ValueError("power_group applies only to power ports")
        return self


class Mount(SubstitutionModel):
    holes_mm: list[Point2] = Field(min_length=1, max_length=32)
    hole_diameter_mm: Dimension
    plane_z_mm: Coordinate = 0.0
    fastener: Text | None = None

    @model_validator(mode="after")
    def distinct_holes(self):
        if len({tuple(row) for row in self.holes_mm}) != len(self.holes_mm):
            raise ValueError("mount hole coordinates must be distinct")
        return self


class PartProfile(SubstitutionModel):
    part_id: Identifier
    replacement_profile_id: Identifier | None = None
    name: Text
    manufacturer: Text | None = None
    mpn: Text | None = None
    functions: list[Text] = Field(default_factory=list, max_length=32)
    dimensions_mm: Dimensions | None = None
    # Assembly lower corner. No implicit origin or orientation is inferred.
    position_mm: Point3 | None = None
    mount: Mount | None = None
    ports: list[Port] = Field(default_factory=list, max_length=64)
    energy_wh: Number | None = None
    usable_fraction: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] | None = None
    shared_output_limit_a: Current | None = None
    mass_g: Number | None = None
    source: SourceBinding | None = None

    @model_validator(mode="after")
    def distinct_ports(self):
        if len({row.port_id for row in self.ports}) != len(self.ports):
            raise ValueError("part port IDs must be distinct")
        if len(set(self.functions)) != len(self.functions):
            raise ValueError("part functions must be distinct")
        return self


class Terminal(SubstitutionModel):
    part_id: Identifier
    port_id: Identifier


class Connection(SubstitutionModel):
    connection_id: Identifier
    from_: Terminal = Field(alias="from")
    to: Terminal
    pin_map: dict[Identifier, Identifier] | None = Field(default=None, max_length=64)


class Enclosure(SubstitutionModel):
    minimum_mm: Point3
    maximum_mm: Point3

    @model_validator(mode="after")
    def ordered(self):
        if any(a >= b for a, b in zip(self.minimum_mm, self.maximum_mm)):
            raise ValueError("enclosure minimum must be below maximum on every axis")
        return self


class CurrentOverride(SubstitutionModel):
    part_id: Identifier
    port_id: Identifier
    current_a: Current


class OperatingScenario(SubstitutionModel):
    scenario_id: Identifier
    current_overrides: list[CurrentOverride] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def distinct_overrides(self):
        keys = [(row.part_id, row.port_id) for row in self.current_overrides]
        if len(set(keys)) != len(keys):
            raise ValueError("scenario overrides must identify distinct input ports")
        return self


class MountAdapterRequest(SubstitutionModel):
    thickness_mm: Dimension
    edge_margin_mm: Dimension


class SubstitutionSpecification(SubstitutionModel):
    parts: list[PartProfile] = Field(min_length=1, max_length=32)
    connections: list[Connection] = Field(default_factory=list, max_length=128)
    replace_part_id: Identifier
    candidate: PartProfile
    enclosure: Enclosure | None = None
    scenarios: list[OperatingScenario] = Field(default_factory=list, max_length=16)
    mount_adapter: MountAdapterRequest | None = None

    @model_validator(mode="after")
    def identities(self):
        parts = {part.part_id: part for part in self.parts}
        if len(parts) != len(self.parts):
            raise ValueError("assembly part IDs must be distinct")
        if self.replace_part_id not in parts:
            raise ValueError("replace_part_id must identify an assembly part")
        if self.candidate.part_id in parts and self.candidate.part_id != self.replace_part_id:
            raise ValueError("candidate profile identity collides with an unchanged assembly part")
        ports = {(part.part_id, port.port_id): port for part in self.parts for port in part.ports}
        if len({row.connection_id for row in self.connections}) != len(self.connections):
            raise ValueError("connection IDs must be distinct")
        pairs = set()
        for row in self.connections:
            a, b = _terminal(row.from_), _terminal(row.to)
            if a not in ports or b not in ports:
                raise ValueError("baseline connection references an unknown part or port")
            pair = tuple(sorted((a, b)))
            if a == b or pair in pairs:
                raise ValueError("duplicate or self-connected ports")
            pairs.add(pair)
        if len({row.scenario_id for row in self.scenarios}) != len(self.scenarios):
            raise ValueError("scenario IDs must be distinct")
        for scenario in self.scenarios:
            if scenario.scenario_id == "declared":
                raise ValueError("scenario_id 'declared' is reserved for the unmodified declared demand baseline")
            for override in scenario.current_overrides:
                port = ports.get((override.part_id, override.port_id))
                if port is None or port.kind != "power" or port.direction != "input":
                    raise ValueError("scenario current overrides require an existing power input")
        return self


def _terminal(value: Terminal) -> tuple[str, str]:
    return value.part_id, value.port_id


def _dump(value: BaseModel) -> dict:
    return value.model_dump(mode="json", by_alias=True)


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class _Findings:
    def __init__(self):
        self.checks: list[dict] = []
        self.adaptations: list[dict] = []

    def add(self, code: str, status: str, domain: str, message: str, *, parts=(), adaptation=False, **details):
        row = {"check_id": f"check-{len(self.checks) + 1}", "code": code, "status": status,
               "domain": domain, "message": message, "part_ids": list(dict.fromkeys(parts)),
               "basis": "supplied_digital_declarations", **details}
        row["requires_adaptation"] = adaptation
        self.checks.append(row)
        return row

    def adapt(self, kind: str, message: str, *, parts=(), connections=(), **details):
        row = {"adaptation_id": f"adaptation-{len(self.adaptations) + 1}", "kind": kind,
               "status": "required", "message": message, "part_ids": list(parts),
               "connection_ids": list(connections), "automatically_applied": False, **details}
        self.adaptations.append(row)
        return row


def _same_mount(left: Mount, right: Mount) -> bool:
    return (sorted(left.holes_mm) == sorted(right.holes_mm)
            and left.hole_diameter_mm == right.hole_diameter_mm
            and left.plane_z_mm == right.plane_z_mm and left.fastener == right.fastener)


def _mechanical(spec: SubstitutionSpecification, parts: list[PartProfile], original: PartProfile,
                findings: _Findings) -> dict:
    envelopes = []
    selected = next(part for part in parts if part.part_id == spec.replace_part_id)
    for part in parts:
        if part.dimensions_mm is None or part.position_mm is None:
            findings.add("mechanical_envelope_unknown", "unknown", "mechanical",
                         "Nominal dimensions and a position in the shared assembly frame are required.", parts=[part.part_id])
            continue
        minimum = part.position_mm
        maximum = [a + b for a, b in zip(minimum, part.dimensions_mm)]
        envelopes.append({"part_id": part.part_id, "name": part.name,
                          "dimensions_mm": part.dimensions_mm, "position_mm": minimum,
                          "role": "replacement" if part.part_id == spec.replace_part_id else "unchanged",
                          "source": _dump(part.source) if part.source else None})
        if part.mount is not None:
            mount = part.mount
            within = (all(0 <= x <= part.dimensions_mm[0] and 0 <= y <= part.dimensions_mm[1] for x, y in mount.holes_mm)
                      and 0 <= mount.plane_z_mm <= part.dimensions_mm[2])
            findings.add("mount_nominal_bounds", "pass" if within else "fail", "mechanical",
                         "Declared attachment coordinates must lie within the complete nominal part envelope.", parts=[part.part_id])
        if spec.enclosure is not None:
            fits = all(a >= lo and b <= hi for a, b, lo, hi in zip(minimum, maximum, spec.enclosure.minimum_mm, spec.enclosure.maximum_mm))
            findings.add("enclosure_fit", "pass" if fits else "fail", "mechanical",
                         "Nominal part envelope lies inside the declared available enclosure." if fits else "Nominal part envelope exceeds the declared enclosure.",
                         parts=[part.part_id], minimum_mm=minimum, maximum_mm=maximum)
            if not fits:
                findings.adapt("enclosure_redesign", "Change the enclosure or placement and reassess the complete assembly.", parts=[part.part_id])
    if spec.enclosure is None:
        findings.add("available_space_unknown", "unknown", "mechanical", "No available enclosure volume was declared.", parts=[selected.part_id])
    for index, first in enumerate(envelopes):
        for second in envelopes[index + 1:]:
            overlap = all(min(a + da, b + db) > max(a, b) for a, da, b, db in zip(
                first["position_mm"], first["dimensions_mm"], second["position_mm"], second["dimensions_mm"]))
            findings.add("envelope_collision", "fail" if overlap else "pass", "mechanical",
                         "Nominal envelopes overlap; exact shape/contact intent needs separate assessment." if overlap else "Axis-aligned nominal envelopes do not overlap.",
                         parts=[first["part_id"], second["part_id"]], aabb_only=True)
            if overlap:
                findings.adapt("placement_or_enclosure_change", "Resolve the envelope overlap with declared geometry; this evaluator does not relocate parts.", parts=[first["part_id"], second["part_id"]])
    adapters = []
    left, right = original.mount, selected.mount
    if left is None or right is None:
        findings.add("mount_interface_unknown", "unknown", "mechanical", "Both original and replacement mount patterns are needed to assess attachment.", parts=[selected.part_id])
    elif _same_mount(left, right):
        findings.add("mount_pattern", "pass", "mechanical", "Declared mount coordinates, bore sizes, plane and fastener text match exactly.", parts=[selected.part_id], tolerance_modelled=False)
        if left.fastener is None:
            findings.add("fastener_unknown", "unknown", "mechanical", "Matching hole patterns do not identify a fastening method.", parts=[selected.part_id])
    else:
        findings.add("mount_pattern", "fail", "mechanical", "The replacement changes the declared attachment interface.", parts=[selected.part_id], adaptation=True)
        row = findings.adapt("mount_adapter", "Design and verify an adapter, spacers or a changed mount; original attachment geometry is not preserved.", parts=[selected.part_id])
        if (spec.mount_adapter is not None and selected.position_mm is not None
                and original.dimensions_mm is not None and selected.dimensions_mm is not None
                and left.plane_z_mm == right.plane_z_mm):
            adapters.append({"adaptation_id": row["adaptation_id"], "target_part_id": selected.part_id,
                             "status": "nominal_geometry_requested", "base_holes_mm": left.holes_mm,
                             "replacement_holes_mm": right.holes_mm,
                             "base_hole_diameter_mm": left.hole_diameter_mm,
                             "replacement_hole_diameter_mm": right.hole_diameter_mm,
                             **_dump(spec.mount_adapter), "plane_z_mm": left.plane_z_mm,
                             "position_mm": selected.position_mm, "basis": "declared_mount_patterns",
                             "structural_fit_verified": False})
    return {"basis": "declared_axis_aligned_envelopes", "envelopes": envelopes,
            "adapter_requirements": adapters, "exact_geometry_verified": False}


def _connection_checks(parts: list[PartProfile], connections: list[Connection], findings: _Findings):
    ports = {(part.part_id, port.port_id): port for part in parts for port in part.ports}
    connected = set()
    for row in connections:
        a, b = _terminal(row.from_), _terminal(row.to)
        left, right = ports.get(a), ports.get(b)
        ids = [a[0], b[0]]
        details = {"connection_id": row.connection_id}
        if left is None or right is None:
            findings.add("replacement_port_missing", "unknown", "electrical", "The revised assembly lacks a referenced port; an explicit mapping is required.", parts=ids, **details)
            findings.adapt("port_mapping", "Map the original connection to a declared replacement port.", parts=ids, connections=[row.connection_id])
            continue
        connected.update((a, b))
        if left.kind != right.kind:
            findings.add("port_kind_mismatch", "fail", "electrical", "Connection joins different electrical interface kinds.", parts=ids, **details)
        if left.connector is None or right.connector is None:
            findings.add("connector_unknown", "unknown", "connection", "Both mating connector interface identities are required.", parts=ids, **details)
        elif left.connector != right.connector:
            findings.add("connector_mismatch", "fail", "connection", "Connector interfaces differ; an explicit adapter is needed.", parts=ids, adaptation=True, **details)
            findings.adapt("connector_adapter", "Specify adapter connectors, every pin mapping, voltage/current limits and any added power load, then include it in the graph.", parts=ids, connections=[row.connection_id])
        else:
            findings.add("connector_identity", "pass", "connection", "Declared mating connector interface identities match.", parts=ids, **details)
        lp, rp = left.pin_functions, right.pin_functions
        if not lp or not rp:
            findings.add("pin_mapping_unknown", "unknown", "connection", "Physical contact numbers and their functions are required on both endpoints.", parts=ids, **details)
        else:
            mapping = row.pin_map if row.pin_map is not None else {pin: pin for pin in lp}
            complete = set(mapping) == set(lp) and set(mapping.values()) == set(rp) and len(set(mapping.values())) == len(mapping)
            functions_match = complete and all(lp[pin] == rp[target] for pin, target in mapping.items())
            if not functions_match:
                findings.add("pin_function_mismatch", "fail", "connection", "The contact mapping is incomplete, non-bijective, or joins different pin functions/polarities.", parts=ids, **details)
                findings.adapt("repin_or_adapter", "Supply a complete function-preserving pin map and a rated adapter; do not connect mismatched contacts.", parts=ids, connections=[row.connection_id])
            elif any(pin != target for pin, target in mapping.items()):
                findings.add("repin_required", "fail", "connection", "The explicit mapping preserves functions but requires a different physical pin assignment.", parts=ids, adaptation=True, **details)
                findings.adapt("repin_or_adapter", "Implement and verify the declared non-identity pin map; it is not a direct mating connection.", parts=ids, connections=[row.connection_id], pin_map=mapping)
            else:
                findings.add("pin_function_mapping", "pass", "connection", "Physical contact numbers and declared functions match.", parts=ids, **details)
        if left.kind == right.kind == "signal" or left.protocol is not None or right.protocol is not None:
            if left.protocol is None or right.protocol is None:
                findings.add("protocol_unknown", "unknown", "electrical", "Both protocol declarations are required; connector shape is not a protocol.", parts=ids, **details)
            elif left.protocol != right.protocol:
                findings.add("protocol_mismatch", "fail", "electrical", "Protocols differ; a cable or pin remapping does not implement a protocol bridge.", parts=ids, **details)
                findings.adapt("protocol_bridge", "Model a bridge as an actual part with distinct declared ports, supply demand and graph connections; firmware and timing need separate validation.", parts=ids, connections=[row.connection_id])
            else:
                findings.add("protocol_identity", "pass", "electrical", "Declared protocol identities match; implementation and timing remain unverified.", parts=ids, **details)
        if left.kind == right.kind == "signal":
            directions = (left.direction, right.direction)
            allowed = (set(directions) == {"input", "output"} or directions == ("bidirectional", "bidirectional"))
            findings.add("signal_direction", "unknown" if "unknown" in directions else "pass" if allowed else "fail", "electrical",
                         "Signal directions are compatible under the declared interface." if allowed else "Signal directions are missing or incompatible.", parts=ids, **details)
            voltage_pairs = []
            if directions == ("bidirectional", "bidirectional"):
                voltage_pairs = [(left, right), (right, left)]
                findings.add("bidirectional_signal_behaviour_not_assessed", "not_assessed", "electrical", "Arbitration, drive mode, loading and logic thresholds are outside this declared envelope assessment.", parts=ids, **details)
            elif allowed:
                voltage_pairs = [(left, right)] if left.direction == "output" else [(right, left)]
            for output, receiver in voltage_pairs:
                if output.voltage_range_v is None or receiver.voltage_range_v is None:
                    findings.add("signal_voltage_unknown", "unknown", "electrical", "Declared signal voltage intervals are incomplete.", parts=ids, **details)
                else:
                    fits = receiver.voltage_range_v[0] <= output.voltage_range_v[0] and output.voltage_range_v[1] <= receiver.voltage_range_v[1]
                    findings.add("signal_voltage_containment", "pass" if fits else "fail", "electrical", "Source absolute signal envelope must lie entirely inside the receiving envelope; this is not a logic-threshold proof.", parts=ids, source_port_id=output.port_id, receiver_port_id=receiver.port_id, **details)
            findings.add("signal_loading_timing_not_assessed", "not_assessed", "electrical", "Logic thresholds, loading, timing and software compatibility are outside this declared envelope assessment.", parts=ids, **details)
    for key, port in ports.items():
        if port.required and key not in connected:
            findings.add("required_port_unconnected", "unknown", "electrical", "A required revised port has no declared connection.", parts=[key[0]], port_id=key[1])
    return ports


def _power_analysis(parts: list[PartProfile], connections: list[Connection], scenario: OperatingScenario,
                    findings: _Findings | None = None) -> dict:
    ports = {(part.part_id, port.port_id): port for part in parts for port in part.ports}
    parent = {key: key for key, port in ports.items() if port.kind == "power"}
    connected = set()
    connection_coverage = True

    def find(key):
        while parent[key] != key:
            key = parent[key]
        return key

    def union(a, b):
        parent[find(a)] = find(b)

    for row in connections:
        a, b = _terminal(row.from_), _terminal(row.to)
        if a in parent and b in parent:
            union(a, b)
            connected.update((a, b))
            left, right = ports[a], ports[b]
            lp, rp = left.pin_functions, right.pin_functions
            mapping = row.pin_map if row.pin_map is not None else {pin: pin for pin in (lp or {})}
            mapped = bool(lp and rp and set(mapping) == set(lp) and set(mapping.values()) == set(rp)
                          and len(set(mapping.values())) == len(mapping)
                          and all(lp[pin] == rp[target] for pin, target in mapping.items()))
            if (not mapped or left.connector is None or left.connector != right.connector
                    or left.protocol != right.protocol):
                connection_coverage = False
        elif a not in ports or b not in ports or ports[a].kind != ports[b].kind:
            connection_coverage = False
    for part in parts:
        groups = {}
        for port in part.ports:
            if port.kind == "power" and port.power_group is not None:
                key = (part.part_id, port.port_id)
                if port.power_group in groups:
                    union(key, groups[port.power_group])
                else:
                    groups[port.power_group] = key
    groups = {}
    for key in parent:
        if key in connected:
            groups.setdefault(find(key), []).append(key)
    overrides = {(row.part_id, row.port_id): row.current_a for row in scenario.current_overrides}
    rails, supply_demands, supply_power = [], {}, {}
    all_power_known = connection_coverage

    def issue(code, status, message, keys, **details):
        if findings is not None:
            findings.add(code, status, "power", message, parts=[key[0] for key in keys], scenario_id=scenario.scenario_id, **details)

    def power_adaptation(keys, demand, capacity, scope):
        if findings is not None:
            findings.adapt("power_budget",
                          "Reduce the declared load or provide an explicitly rated power path meeting this current requirement; no replacement hardware has been selected.",
                          parts=list(dict.fromkeys(key[0] for key in keys)),
                          scenario_id=scenario.scenario_id, budget_scope=scope,
                          demand_a=demand, required_capacity_a=demand, declared_capacity_a=capacity,
                          current_margin_a=capacity - demand, additional_design_margin_specified=False,
                          required_evidence=["explicit source and path current ratings at the operating conditions"],
                          hardware_selected=False)

    for key in overrides:
        if key not in connected or key not in ports or ports[key].kind != "power" or ports[key].direction != "input":
            issue("scenario_input_unconnected", "unknown", "The scenario's overridden power input is absent, disconnected or no longer a power input after replacement.", [key])
            all_power_known = False

    for index, keys in enumerate(sorted(groups.values())):
        outputs = [key for key in keys if ports[key].direction == "output"]
        inputs = [key for key in keys if ports[key].direction == "input"]
        unknown_roles = [key for key in keys if ports[key].direction not in {"output", "input", "passive"}]
        rail = {"rail_id": f"rail-{index + 1}", "ports": [{"part_id": key[0], "port_id": key[1]} for key in sorted(keys)],
                "current_a": None, "capacity_a": None, "power_w": None, "status": "unknown"}
        if unknown_roles:
            issue("power_direction_unknown", "unknown", "A power rail includes an undeclared or bidirectional source role.", unknown_roles)
        if len(outputs) != 1:
            issue("power_source_count", "fail" if len(outputs) > 1 else "unknown", "Each assessed rail requires one explicit source; source sharing is not inferred.", keys, source_count=len(outputs))
            all_power_known = False
            rails.append(rail)
            continue
        if not inputs:
            issue("power_load_missing", "unknown", "No load demand is declared for this powered rail.", keys)
            all_power_known = False
            rails.append(rail)
            continue
        source_key = outputs[0]
        source = ports[source_key]
        demands = [overrides.get(key, ports[key].current_a) for key in inputs]
        demand = sum(demands) if all(value is not None for value in demands) else None
        rail.update(current_a=demand, capacity_a=source.current_a, source_part_id=source_key[0])
        rail_states = []
        if demand is None or source.current_a is None:
            issue("power_current_unknown", "unknown", "Every connected load demand and the source current capacity are required.", keys)
            rail_states.append("unknown")
        else:
            fits = demand <= source.current_a
            issue("power_current_budget", "pass" if fits else "fail", "Full connected-rail load is compared with the declared source capacity.", keys, demand_a=demand, capacity_a=source.current_a, margin_a=source.current_a - demand)
            rail_states.append("pass" if fits else "fail")
            if not fits:
                power_adaptation(keys, demand, source.current_a, "source_rail")
        if source.voltage_range_v is None:
            issue("supply_voltage_unknown", "unknown", "Source operating voltage range is missing.", keys)
            rail_states.append("unknown")
        for key in inputs:
            allowed = ports[key].voltage_range_v
            if allowed is None:
                issue("load_voltage_unknown", "unknown", "Load operating voltage range is missing.", [key])
                rail_states.append("unknown")
            elif source.voltage_range_v is not None:
                fits = allowed[0] <= source.voltage_range_v[0] and source.voltage_range_v[1] <= allowed[1]
                issue("supply_voltage_containment", "pass" if fits else "fail", "The complete supply interval must lie within each load's operating interval.", [source_key, key], source_voltage_range_v=source.voltage_range_v, load_voltage_range_v=allowed)
                rail_states.append("pass" if fits else "fail")
                if not fits and findings is not None:
                    findings.adapt("regulated_power_path",
                                   "Provide a power path whose complete output interval fits the load's permitted range, or revise the source/load selection; regulator topology and parts remain unspecified.",
                                   parts=list(dict.fromkeys([source_key[0], key[0]])),
                                   scenario_id=scenario.scenario_id,
                                   source_port={"part_id": source_key[0], "port_id": source_key[1]},
                                   load_port={"part_id": key[0], "port_id": key[1]},
                                   source_voltage_range_v=source.voltage_range_v,
                                   permitted_voltage_range_v=allowed,
                                   required_output_current_a=overrides.get(key, ports[key].current_a),
                                   required_evidence=["output regulation across the complete declared input range",
                                                      "load current capacity and added upstream demand or conversion losses"],
                                   hardware_selected=False)
        for key in [key for key in keys if ports[key].direction == "passive"]:
            path = ports[key]
            if path.current_a is None or demand is None:
                issue("passive_path_current_unknown", "unknown", "Passive power-path capacity and complete net demand must be declared.", [key])
                rail_states.append("unknown")
            else:
                fits = demand <= path.current_a
                issue("passive_path_current_budget", "pass" if fits else "fail", "Each passive path is conservatively checked against full rail demand.", [key], demand_a=demand, capacity_a=path.current_a)
                rail_states.append("pass" if fits else "fail")
                if not fits:
                    power_adaptation([key], demand, path.current_a, "passive_path")
            if path.voltage_range_v is None or source.voltage_range_v is None:
                issue("passive_path_voltage_unknown", "unknown", "Passive power-path voltage rating is incomplete.", [key])
                rail_states.append("unknown")
            else:
                fits = path.voltage_range_v[0] <= source.voltage_range_v[0] and source.voltage_range_v[1] <= path.voltage_range_v[1]
                issue("passive_path_voltage_containment", "pass" if fits else "fail", "The supply interval must fit the passive path's voltage rating.", [key])
                rail_states.append("pass" if fits else "fail")
        previous_demand = supply_demands.get(source_key[0], 0.0)
        supply_demands[source_key[0]] = previous_demand + demand if previous_demand is not None and demand is not None and not unknown_roles else None
        if demand is not None and source.voltage_range_v is not None and not unknown_roles:
            rail["power_w"] = [v * demand for v in source.voltage_range_v]
            old = supply_power.get(source_key[0], [0.0, 0.0])
            supply_power[source_key[0]] = [a + b for a, b in zip(old, rail["power_w"])]
        else:
            all_power_known = False
        rail["status"] = "fail" if "fail" in rail_states else "unknown" if "unknown" in rail_states or unknown_roles else "pass"
        rails.append(rail)
    unconnected = [key for key, port in ports.items() if port.kind == "power" and port.required and key not in connected]
    if unconnected:
        all_power_known = False
    for part in parts:
        outputs = [port for port in part.ports if port.kind == "power" and port.direction == "output"]
        if len(outputs) > 1 or part.shared_output_limit_a is not None:
            demand = supply_demands.get(part.part_id)
            if part.shared_output_limit_a is None or demand is None:
                issue("shared_supply_budget_unknown", "unknown", "A multi-output part needs an explicit shared output limit and complete connected load demands.", [(part.part_id, port.port_id) for port in outputs])
                all_power_known = False
            else:
                issue("shared_supply_budget", "pass" if demand <= part.shared_output_limit_a else "fail", "Sum of the part's output-rail demands is compared with its shared limit.", [(part.part_id, port.port_id) for port in outputs], demand_a=demand, capacity_a=part.shared_output_limit_a)
                if demand > part.shared_output_limit_a:
                    all_power_known = False
                    power_adaptation([(part.part_id, port.port_id) for port in outputs], demand,
                                     part.shared_output_limit_a, "shared_source")
    # Adding converter-input and converter-output watts double-counts power. A
    # device total is only reported when every source part has no power inputs.
    nested_sources = [part.part_id for part in parts if part.part_id in supply_power and any(port.kind == "power" and port.direction == "input" for port in part.ports)]
    if nested_sources:
        all_power_known = False
        issue("conversion_power_model_unknown", "unknown", "An internal powered source needs an explicit conversion/loss model before total power or runtime can be calculated.", [(value, "") for value in nested_sources])
    power_path_valid = all_power_known and bool(rails) and all(rail["status"] == "pass" for rail in rails)
    power = [sum(values[index] for values in supply_power.values()) for index in (0, 1)] if power_path_valid else None
    runtimes = []
    for part in parts:
        if part.energy_wh is None:
            continue
        own_power = supply_power.get(part.part_id)
        hours = None
        if part.usable_fraction is not None and own_power and own_power[0] > 0 and power_path_valid:
            usable = part.energy_wh * part.usable_fraction
            hours = [usable / own_power[1], usable / own_power[0]]
            if not all(math.isfinite(value) for value in hours):
                hours = None
                issue("runtime_numeric_range_unknown", "unknown", "The declared energy/load ratio exceeds the finite numerical model range.", [(part.part_id, "")])
        elif findings is not None:
            issue("runtime_unknown", "unknown", "Runtime requires usable stored energy, complete valid source/load data and an assessed power path.", [(part.part_id, "")])
        runtimes.append({"part_id": part.part_id, "runtime_h": hours})
    return {"scenario_id": scenario.scenario_id, "rails": rails, "total_power_w": power,
            "runtime_by_source": runtimes, "basis": "declared_steady_state_demands",
            "transients_thermal_and_regulation_verified": False}


def evaluate_substitution(specification: Mapping[str, Any] | SubstitutionSpecification) -> dict:
    """Assess one replacement against all supplied assembly connections and loads."""
    spec = specification if isinstance(specification, SubstitutionSpecification) else SubstitutionSpecification.model_validate(specification)
    original = next(part for part in spec.parts if part.part_id == spec.replace_part_id)
    effective = spec.candidate.model_copy(deep=True, update={"part_id": original.part_id, "position_mm": deepcopy(original.position_mm),
                                                         "replacement_profile_id": spec.candidate.part_id})
    parts = [effective if part.part_id == original.part_id else part.model_copy(deep=True) for part in spec.parts]
    findings = _Findings()
    if not original.functions or not effective.functions:
        findings.add("function_unknown", "unknown", "function", "Both original required functions and candidate functions must be explicit.", parts=[original.part_id])
    else:
        missing = sorted(set(original.functions) - set(effective.functions))
        findings.add("required_functions", "fail" if missing else "pass", "function", "The replacement must provide every declared required function.", parts=[original.part_id], missing_functions=missing)
    if not spec.candidate.manufacturer or not spec.candidate.mpn:
        findings.add("replacement_identity_unknown", "unknown", "identity", "Replacement manufacturer/MPN is not resolved; the supplied donor profile remains a declared hypothesis.", parts=[original.part_id])
    geometry = _mechanical(spec, parts, original, findings)
    _connection_checks(parts, spec.connections, findings)
    scenarios = [OperatingScenario(scenario_id="declared"), *spec.scenarios]
    scenario_results = []
    for scenario in scenarios:
        before = _power_analysis(spec.parts, spec.connections, scenario)
        after = _power_analysis(parts, spec.connections, scenario, findings)
        before_power, after_power = before["total_power_w"], after["total_power_w"]
        power_delta = [after_power[0] - before_power[1], after_power[1] - before_power[0]] if before_power is not None and after_power is not None else None
        old_runtime = {row["part_id"]: row["runtime_h"] for row in before["runtime_by_source"]}
        runtime_deltas = []
        for row in after["runtime_by_source"]:
            old, new = old_runtime.get(row["part_id"]), row["runtime_h"]
            runtime_deltas.append({"part_id": row["part_id"], "runtime_delta_h": [new[0] - old[1], new[1] - old[0]] if old is not None and new is not None else None})
        scenario_results.append({"scenario_id": scenario.scenario_id, "before": before, "after": after,
                                 "power_delta_w": power_delta, "runtime_deltas": runtime_deltas})
    revised_parts = [_dump(part) for part in parts]
    for part in revised_parts:
        if part["part_id"] == original.part_id:
            part["replacement_profile_id"] = spec.candidate.part_id
    blocked = any(row["status"] == "fail" and not row["requires_adaptation"] for row in findings.checks)
    unresolved = [row for row in findings.checks if row["status"] == "unknown"]
    status = "blocked" if blocked else "unresolved" if unresolved else "requires_adaptation" if findings.adaptations else "passes_declared_checks"
    bom = [{"material_id": part.part_id, "description": part.name, "manufacturer": part.manufacturer,
            "mpn": part.mpn, "quantity": 1, "unit": "ea", "source": _dump(part.source) if part.source else None,
            "inventory_status": "not_assessed"} for part in parts]
    result = {
        "schema_version": SCHEMA, "specification_sha256": _digest(_dump(spec)), "status": status,
        "direct_replacement_within_declared_scope": status == "passes_declared_checks", "checks": findings.checks,
        "required_adaptations": findings.adaptations, "unresolved": unresolved,
        "unassessed": [row for row in findings.checks if row["status"] == "not_assessed"],
        "assessment_scope": {"basis": "declared_contract_checks_only",
                             "included": ["required_function_labels", "connector_and_pin_identity", "protocol_labels_and_directions",
                                          "declared_voltage_envelopes", "connected_load_current_budgets", "nominal_enclosure_and_collision",
                                          "declared_mount_patterns", "steady_state_power_and_energy"],
                             "excluded": ["logic_thresholds_and_timing", "firmware_drivers", "power_negotiation_and_transients",
                                          "thermal_performance", "manufactured_fit_and_strength", "physical_condition", "inventory_availability"]},
        "replacement": {"target_part_id": original.part_id, "replacement_profile_id": spec.candidate.part_id,
                        "original_profile": _dump(original), "candidate_profile": _dump(spec.candidate),
                        "placement_preserved": True},
        "revised": {"parts": revised_parts, "connections": [_dump(row) for row in spec.connections], "bom": bom},
        "scenarios": scenario_results,
        "delta": {"mass_g": effective.mass_g - original.mass_g if effective.mass_g is not None and original.mass_g is not None else None,
                  "dimensions_mm": [a - b for a, b in zip(effective.dimensions_mm, original.dimensions_mm)] if effective.dimensions_mm is not None and original.dimensions_mm is not None else None},
        "geometry": geometry, "declaration_basis": "supplied_digital_assumptions",
        "source_bindings_verified": False, "inventory_reconciled": False,
        "complete_device_compatibility_verified": False, "physical_authority_granted": False,
        "construction_ready": False, "physical_validation_performed": False,
        "manufacturing_approved": False, "automatic_design_changes_applied": False,
        "limitations": ["Nominal envelopes and exact declared hole coordinates do not establish manufactured fit, tolerances, fastener strength or connector access.",
                        "Declared steady-state intervals do not establish transients, thermal behavior, USB negotiation, driver support or protocol implementation.",
                        "Source bindings are preserved for the project service to verify; this pure evaluator does not read source files or claim ownership of stock."],
    }
    # Ensure every computed quantity remains finite and the report is JSON safe.
    json.dumps(result, allow_nan=False)
    return result

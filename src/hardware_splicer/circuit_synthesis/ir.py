"""Circuit synthesis intermediate representation.

This is not a full schematic engine. It is the first bounded language for
representing user intent, parts, ports, topology operators, constraints, and
candidate plans before existing compile/readiness gates take over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping


SCHEMA_VERSION = "hardware_splicer.circuit_synthesis.v1"

PORT_DIRECTIONS = {"input", "output", "bidirectional", "power", "ground"}
SIGNAL_TYPES = {
    "analog",
    "digital",
    "power",
    "ground",
    "pwm",
    "i2c",
    "spi",
    "uart",
    "motor",
    "unknown",
}
TOPOLOGY_OPERATOR_TYPES = {
    "buck_regulator",
    "boost_regulator",
    "ldo_regulator",
    "series",
    "parallel",
    "voltage_divider",
    "pull_up",
    "pull_down",
    "low_side_switch",
    "high_side_switch",
    "rc_filter",
    "decoupling",
    "protection_diode",
    "h_bridge",
    "relay_driver",
    "sensor_interface",
    "analog_conditioning",
    "adc_interface",
    "motor_driver",
    "battery_charger",
    "level_shifter",
}
CONSTRAINT_TYPES = {
    "voltage",
    "current",
    "frequency",
    "thermal",
    "trace_current",
    "isolation",
    "measurement_required",
    "fabrication_requirement",
    "evidence_required",
    "logic_level",
    "protection",
    "unsupported_goal",
}
CANDIDATE_RESULTS = {"candidate", "blocked", "ready_for_review"}
CONSTRAINT_STATUSES = {"pass", "warn", "blocked", "open"}


def _choice(value: Any, allowed: set[str], *, field_name: str, default: str | None = None) -> str:
    text = str(value if value is not None else default or "").strip().lower()
    if text not in allowed:
        raise ValueError(f"{field_name} must be one of {sorted(allowed)}, got {value!r}")
    return text


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, Iterable):
        return []
    return [str(row) for row in value if str(row).strip()]


def _dict_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _range_dict(value: Any, *, low_key: str, high_key: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return {low_key: value[0], high_key: value[1]}
    return {}


@dataclass(frozen=True)
class Port:
    name: str
    direction: str
    signal_type: str = "unknown"
    voltage_range: Dict[str, Any] = field(default_factory=dict)
    current_limit_a: float | None = None
    required: bool = True
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "direction", _choice(self.direction, PORT_DIRECTIONS, field_name="direction"))
        object.__setattr__(
            self,
            "signal_type",
            _choice(self.signal_type or "unknown", SIGNAL_TYPES, field_name="signal_type", default="unknown"),
        )
        if not self.name:
            raise ValueError("port name is required")

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "Port":
        return cls(
            name=str(row.get("name") or row.get("id") or ""),
            direction=str(row.get("direction") or "input"),
            signal_type=str(row.get("signal_type") or row.get("type") or "unknown"),
            voltage_range=_range_dict(row.get("voltage_range"), low_key="min_v", high_key="max_v"),
            current_limit_a=_float_or_none(row.get("current_limit_a") or row.get("current_limit")),
            required=bool(row.get("required", True)),
            notes=str(row.get("notes") or ""),
            metadata=dict(row.get("metadata") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "direction": self.direction,
            "signal_type": self.signal_type,
            "voltage_range": dict(self.voltage_range),
            "current_limit_a": self.current_limit_a,
            "required": self.required,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class FunctionalPart:
    id: str
    type: str
    module_id: str = ""
    ports: List[Port] = field(default_factory=list)
    voltage_range: Dict[str, Any] = field(default_factory=dict)
    current_range: Dict[str, Any] = field(default_factory=dict)
    function_tags: List[str] = field(default_factory=list)
    behavior_class: str = ""
    required_support_components: List[str] = field(default_factory=list)
    thermal_notes: str = ""
    current_notes: str = ""
    verification_requirements: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", str(self.id).strip())
        object.__setattr__(self, "type", str(self.type).strip().lower())
        if not self.id:
            raise ValueError("functional part id is required")
        if not self.type:
            raise ValueError("functional part type is required")

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "FunctionalPart":
        return cls(
            id=str(row.get("id") or row.get("name") or ""),
            type=str(row.get("type") or row.get("kind") or ""),
            module_id=str(row.get("module_id") or ""),
            ports=[Port.from_dict(port) for port in _dict_list(row.get("ports"))],
            voltage_range=_range_dict(row.get("voltage_range"), low_key="min_v", high_key="max_v"),
            current_range=_range_dict(row.get("current_range"), low_key="min_a", high_key="max_a"),
            function_tags=_string_list(row.get("function_tags")),
            behavior_class=str(row.get("behavior_class") or ""),
            required_support_components=_string_list(row.get("required_support_components")),
            thermal_notes=str(row.get("thermal_notes") or ""),
            current_notes=str(row.get("current_notes") or ""),
            verification_requirements=_string_list(row.get("verification_requirements")),
            metadata=dict(row.get("metadata") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "module_id": self.module_id,
            "ports": [port.to_dict() for port in self.ports],
            "voltage_range": dict(self.voltage_range),
            "current_range": dict(self.current_range),
            "function_tags": list(self.function_tags),
            "behavior_class": self.behavior_class,
            "required_support_components": list(self.required_support_components),
            "thermal_notes": self.thermal_notes,
            "current_notes": self.current_notes,
            "verification_requirements": list(self.verification_requirements),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Constraint:
    constraint_id: str
    type: str
    target: str
    requirement: str
    severity: str = "blocker"
    status: str = "open"
    value: Any = None
    unit: str = ""
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", str(self.constraint_id).strip())
        object.__setattr__(self, "type", _choice(self.type, CONSTRAINT_TYPES, field_name="constraint type"))
        object.__setattr__(self, "status", _choice(self.status, CONSTRAINT_STATUSES, field_name="constraint status"))
        if not self.constraint_id:
            raise ValueError("constraint_id is required")

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "Constraint":
        return cls(
            constraint_id=str(row.get("constraint_id") or row.get("id") or ""),
            type=str(row.get("type") or ""),
            target=str(row.get("target") or ""),
            requirement=str(row.get("requirement") or ""),
            severity=str(row.get("severity") or "blocker"),
            status=str(row.get("status") or "open"),
            value=row.get("value"),
            unit=str(row.get("unit") or ""),
            notes=str(row.get("notes") or ""),
            metadata=dict(row.get("metadata") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "type": self.type,
            "target": self.target,
            "requirement": self.requirement,
            "severity": self.severity,
            "status": self.status,
            "value": self.value,
            "unit": self.unit,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TopologyOperator:
    operator_id: str
    operator_type: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    required_part_types: List[str] = field(default_factory=list)
    required_ports: List[str] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    missing_evidence_conditions: List[str] = field(default_factory=list)
    verification_gates: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "operator_id", str(self.operator_id).strip())
        object.__setattr__(
            self,
            "operator_type",
            _choice(self.operator_type, TOPOLOGY_OPERATOR_TYPES, field_name="operator_type"),
        )
        if not self.operator_id:
            raise ValueError("operator_id is required")

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "TopologyOperator":
        return cls(
            operator_id=str(row.get("operator_id") or row.get("id") or ""),
            operator_type=str(row.get("operator_type") or row.get("type") or ""),
            inputs=_string_list(row.get("inputs")),
            outputs=_string_list(row.get("outputs")),
            required_part_types=_string_list(row.get("required_part_types")),
            required_ports=_string_list(row.get("required_ports")),
            constraints=[Constraint.from_dict(c) for c in _dict_list(row.get("constraints"))],
            missing_evidence_conditions=_string_list(row.get("missing_evidence_conditions")),
            verification_gates=_dict_list(row.get("verification_gates")),
            notes=str(row.get("notes") or ""),
            metadata=dict(row.get("metadata") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "operator_type": self.operator_type,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "required_part_types": list(self.required_part_types),
            "required_ports": list(self.required_ports),
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "missing_evidence_conditions": list(self.missing_evidence_conditions),
            "verification_gates": [dict(gate) for gate in self.verification_gates],
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CircuitIntent:
    goal: str
    supply_rails: List[Dict[str, Any]] = field(default_factory=list)
    load_requirements: List[Dict[str, Any]] = field(default_factory=list)
    signal_requirements: List[Dict[str, Any]] = field(default_factory=list)
    current_constraints: List[Dict[str, Any]] = field(default_factory=list)
    voltage_constraints: List[Dict[str, Any]] = field(default_factory=list)
    frequency_constraints: List[Dict[str, Any]] = field(default_factory=list)
    allowed_parts: List[Dict[str, Any]] = field(default_factory=list)
    allowed_modules: List[str] = field(default_factory=list)
    required_evidence: List[str] = field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal", str(self.goal).strip())
        if not self.goal:
            raise ValueError("circuit intent goal is required")

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "CircuitIntent":
        return cls(
            goal=str(row.get("goal") or ""),
            supply_rails=_dict_list(row.get("supply_rails")),
            load_requirements=_dict_list(row.get("load_requirements")),
            signal_requirements=_dict_list(row.get("signal_requirements")),
            current_constraints=_dict_list(row.get("current_constraints")),
            voltage_constraints=_dict_list(row.get("voltage_constraints")),
            frequency_constraints=_dict_list(row.get("frequency_constraints")),
            allowed_parts=_dict_list(row.get("allowed_parts")),
            allowed_modules=_string_list(row.get("allowed_modules")),
            required_evidence=_string_list(row.get("required_evidence")),
            notes=str(row.get("notes") or ""),
            metadata=dict(row.get("metadata") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "goal": self.goal,
            "supply_rails": [dict(row) for row in self.supply_rails],
            "load_requirements": [dict(row) for row in self.load_requirements],
            "signal_requirements": [dict(row) for row in self.signal_requirements],
            "current_constraints": [dict(row) for row in self.current_constraints],
            "voltage_constraints": [dict(row) for row in self.voltage_constraints],
            "frequency_constraints": [dict(row) for row in self.frequency_constraints],
            "allowed_parts": [dict(row) for row in self.allowed_parts],
            "allowed_modules": list(self.allowed_modules),
            "required_evidence": list(self.required_evidence),
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SynthesisCandidate:
    candidate_id: str
    selected_parts: List[Dict[str, Any]] = field(default_factory=list)
    selected_modules: List[str] = field(default_factory=list)
    generated_topology: List[TopologyOperator] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    verification_gates: List[Dict[str, Any]] = field(default_factory=list)
    recommended_build_path: Dict[str, Any] = field(default_factory=dict)
    result: str = "candidate"
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id).strip())
        object.__setattr__(self, "result", _choice(self.result, CANDIDATE_RESULTS, field_name="result"))
        if not self.candidate_id:
            raise ValueError("candidate_id is required")

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "SynthesisCandidate":
        return cls(
            candidate_id=str(row.get("candidate_id") or row.get("id") or ""),
            selected_parts=_dict_list(row.get("selected_parts")),
            selected_modules=_string_list(row.get("selected_modules")),
            generated_topology=[TopologyOperator.from_dict(t) for t in _dict_list(row.get("generated_topology"))],
            assumptions=_string_list(row.get("assumptions")),
            missing_evidence=_string_list(row.get("missing_evidence")),
            constraints=[Constraint.from_dict(c) for c in _dict_list(row.get("constraints"))],
            verification_gates=_dict_list(row.get("verification_gates")),
            recommended_build_path=dict(row.get("recommended_build_path") or {}),
            result=str(row.get("result") or "candidate"),
            notes=str(row.get("notes") or ""),
            metadata=dict(row.get("metadata") or {}),
        )

    @property
    def blocked(self) -> bool:
        return self.result == "blocked"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "selected_parts": [dict(row) for row in self.selected_parts],
            "selected_modules": list(self.selected_modules),
            "generated_topology": [topology.to_dict() for topology in self.generated_topology],
            "assumptions": list(self.assumptions),
            "missing_evidence": list(self.missing_evidence),
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "verification_gates": [dict(gate) for gate in self.verification_gates],
            "recommended_build_path": dict(self.recommended_build_path),
            "result": self.result,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

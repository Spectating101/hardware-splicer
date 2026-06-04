"""Netlist schema for deterministic circuit simulation.

Design goals:
- Deterministic, solver-oriented core (DC first)
- Small set of primitives that unlock high-ROI validation (power trees, droop, dropout)
- Extensible toward PCB and breadboard by swapping interconnect models

Supported / planned modeling:
- DC MNA kernel: resistors + independent sources
- PCB traces as resistors (DC copper loss)
- LDO abstraction (used by operating-point solver + validators)
- Nonlinear load models (constant current / constant power) for power-tree realism
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

Node = str


def is_ground(node: Node) -> bool:
    return node.strip().upper() in {"0", "GND", "GROUND"}


@dataclass(frozen=True)
class Resistor:
    name: str
    n1: Node
    n2: Node
    ohms: float


@dataclass(frozen=True)
class CurrentSource:
    """Independent DC current source.

    `amps` flows from `n_plus` -> `n_minus`.
    """

    name: str
    n_plus: Node
    n_minus: Node
    amps: float


@dataclass(frozen=True)
class VoltageSource:
    """Independent DC voltage source.

    Enforces: V(n_plus) - V(n_minus) = volts
    """

    name: str
    n_plus: Node
    n_minus: Node
    volts: float


@dataclass(frozen=True)
class TraceSpec:
    """Simple PCB copper trace model (DC only)."""

    length_m: float
    width_m: float
    copper_oz: float = 1.0

    def resistance_ohms(self) -> float:
        # Copper resistivity at 20°C (ohm·m)
        rho = 1.724e-8
        thickness_m = 35e-6 * self.copper_oz  # ~35 µm for 1 oz
        if self.width_m <= 0 or thickness_m <= 0 or self.length_m < 0:
            raise ValueError("Invalid trace geometry")
        area = self.width_m * thickness_m
        return rho * self.length_m / area


@dataclass(frozen=True)
class TraceResistor:
    name: str
    n1: Node
    n2: Node
    spec: TraceSpec

    @property
    def ohms(self) -> float:
        return self.spec.resistance_ohms()


@dataclass(frozen=True)
class LDO:
    """PCB-focused LDO abstraction.

    Used by the operating-point solver:
    - Models Vout as regulated to `vout_nom_v` *unless* Vin is too low, in which
      case Vout droops to approximately Vin - dropout.
    - Adds an input current draw on Vin derived from solved output current.

    Validation then checks dropout, dissipation, and limits.
    """

    name: str
    vin: Node
    vout: Node
    gnd: Node = "0"

    vout_nom_v: float = 3.3
    dropout_v: float = 0.3
    max_current_a: float = 1.0
    quiescent_current_a: float = 0.001

    r_theta_ja_c_per_w: float = 50.0
    tj_max_c: float = 125.0
    ambient_c: float = 25.0


@dataclass(frozen=True)
class ConstantCurrentLoad:
    """A load that draws a fixed current from `node` to `gnd` (DC)."""

    name: str
    node: Node
    amps: float
    gnd: Node = "0"
    min_v_off: Optional[float] = None  # if V(node,gnd) < min_v_off -> 0A


@dataclass(frozen=True)
class ConstantPowerLoad:
    """A load that draws fixed power from `node` to `gnd` (DC).

    Current draw is I = P / V, clamped by `v_min` and optional `max_amps`.
    """

    name: str
    node: Node
    watts: float
    gnd: Node = "0"

    v_min: float = 0.1
    max_amps: Optional[float] = None
    min_v_off: Optional[float] = None


@dataclass(frozen=True)
class VoltageConstraint:
    """A solved-voltage constraint (brownout/overvoltage guardrail)."""

    name: str
    node: Node
    gnd: Node = "0"

    min_v: Optional[float] = None
    max_v: Optional[float] = None

    severity: str = "error"  # 'warning' | 'error'

@dataclass
class CircuitNetlist:
    resistors: List[Resistor] = field(default_factory=list)
    current_sources: List[CurrentSource] = field(default_factory=list)
    voltage_sources: List[VoltageSource] = field(default_factory=list)

    traces: List[TraceResistor] = field(default_factory=list)
    ldos: List[LDO] = field(default_factory=list)

    loads_cc: List[ConstantCurrentLoad] = field(default_factory=list)
    loads_cp: List[ConstantPowerLoad] = field(default_factory=list)

    voltage_constraints: List[VoltageConstraint] = field(default_factory=list)

    def all_nodes(self) -> List[Node]:
        nodes: set[Node] = set()

        for r in self.resistors:
            nodes.update([r.n1, r.n2])
        for t in self.traces:
            nodes.update([t.n1, t.n2])
        for i in self.current_sources:
            nodes.update([i.n_plus, i.n_minus])
        for v in self.voltage_sources:
            nodes.update([v.n_plus, v.n_minus])
        for ldo in self.ldos:
            nodes.update([ldo.vin, ldo.vout, ldo.gnd])
        for load in self.loads_cc:
            nodes.update([load.node, load.gnd])
        for load in self.loads_cp:
            nodes.update([load.node, load.gnd])
        for vc in self.voltage_constraints:
            nodes.update([vc.node, vc.gnd])

        # Normalize ground nodes to "0" for solver convenience.
        normalized: set[Node] = set("0" if is_ground(n) else n for n in nodes)
        if "0" not in normalized:
            normalized.add("0")
        return sorted(normalized)

    def solver_voltage_sources(self) -> List[VoltageSource]:
        """Voltage sources presented to the linear DC solver.

        This keeps `solve_dc(CircuitNetlist(...))` usable without the operating-point
        solver by treating each LDO as an *ideal* source at its nominal voltage.

        Note: the operating-point solver overrides this behavior by building its
        own iteration netlist with `ldos=[]` and explicit LDO sources.
        """

        sources: List[VoltageSource] = []
        sources.extend(self.voltage_sources)
        for ldo in self.ldos:
            sources.append(
                VoltageSource(
                    name=f"LDO::{ldo.name}",
                    n_plus=ldo.vout,
                    n_minus=ldo.gnd,
                    volts=ldo.vout_nom_v,
                )
            )
        return sources

    def solver_resistors(self) -> List[Resistor]:
        resistors: List[Resistor] = []
        resistors.extend(self.resistors)
        for t in self.traces:
            resistors.append(Resistor(name=f"TRACE::{t.name}", n1=t.n1, n2=t.n2, ohms=t.ohms))
        return resistors
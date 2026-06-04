"""Operating-point (iterative) DC solver for power-tree realism.

This wraps the linear DC MNA solver to support a small set of nonlinear /
mode-switching behaviors that matter for PCB power trees:

- LDO dropout behavior (Vout cannot exceed Vin - dropout)
- LDO input current draw derived from solved output current
- Constant-current loads
- Constant-power loads

This is not SPICE. It's a deterministic, high-ROI kernel for validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from src.engines.dc_mna import DCSolution, solve_dc
from src.engines.netlist import (
    CircuitNetlist,
    ConstantCurrentLoad,
    ConstantPowerLoad,
    CurrentSource,
    LDO,
    VoltageSource,
    is_ground,
)


def _n(node: str) -> str:
    return "0" if is_ground(node) else node


@dataclass(frozen=True)
class OperatingPointSettings:
    max_iters: int = 80
    tol_v: float = 1e-5
    tol_a: float = 1e-6

    damping_v: float = 0.6
    damping_i: float = 0.6


@dataclass(frozen=True)
class OperatingPointResult:
    solution: DCSolution
    converged: bool
    iters: int
    max_delta_v: float
    max_delta_a: float


def _load_as_current_source(load: ConstantCurrentLoad, sol: Optional[DCSolution]) -> CurrentSource:
    node = _n(load.node)
    gnd = _n(load.gnd)

    amps = max(0.0, load.amps)
    if sol is not None and load.min_v_off is not None:
        v = sol.node_v.get(node, 0.0) - sol.node_v.get(gnd, 0.0)
        if v < load.min_v_off:
            amps = 0.0

    return CurrentSource(name=f"LOADCC::{load.name}", n_plus=node, n_minus=gnd, amps=amps)


def _power_load_as_current_source(load: ConstantPowerLoad, sol: Optional[DCSolution]) -> CurrentSource:
    node = _n(load.node)
    gnd = _n(load.gnd)

    watts = max(0.0, load.watts)

    if sol is None:
        v = max(load.v_min, 1.0)
    else:
        v = sol.node_v.get(node, 0.0) - sol.node_v.get(gnd, 0.0)
        if load.min_v_off is not None and v < load.min_v_off:
            watts = 0.0
        v = max(load.v_min, v)

    amps = watts / v if v > 0 else 0.0
    if load.max_amps is not None:
        amps = min(amps, load.max_amps)

    return CurrentSource(name=f"LOADCP::{load.name}", n_plus=node, n_minus=gnd, amps=amps)


def _solve_operating_point_python(
    netlist: CircuitNetlist,
    settings: OperatingPointSettings = OperatingPointSettings(),
) -> OperatingPointResult:
    """Iteratively solve a power-tree operating point."""

    ldos: List[LDO] = list(netlist.ldos)

    vout_set: Dict[str, float] = {ldo.name: ldo.vout_nom_v for ldo in ldos}
    iin_set: Dict[str, float] = {ldo.name: 0.0 for ldo in ldos}

    prev: Optional[DCSolution] = None
    converged = False

    last_max_dv = float("inf")
    last_max_di = float("inf")

    for it in range(1, settings.max_iters + 1):
        # Build a pure-linear netlist for this iteration.
        iter_net = CircuitNetlist(
            resistors=list(netlist.resistors),
            current_sources=list(netlist.current_sources),
            voltage_sources=list(netlist.voltage_sources),
            traces=list(netlist.traces),
            ldos=[],
            loads_cc=[],
            loads_cp=[],
        )

        # Nonlinear loads as current sources (based on previous solution).
        for load in netlist.loads_cc:
            iter_net.current_sources.append(_load_as_current_source(load, prev))
        for load in netlist.loads_cp:
            iter_net.current_sources.append(_power_load_as_current_source(load, prev))

        # LDO output voltage sources + LDO input current draw.
        for ldo in ldos:
            iter_net.voltage_sources.append(
                VoltageSource(
                    name=f"LDO::{ldo.name}",
                    n_plus=_n(ldo.vout),
                    n_minus=_n(ldo.gnd),
                    volts=vout_set[ldo.name],
                )
            )

            iin = max(0.0, iin_set[ldo.name])
            if iin > 0:
                iter_net.current_sources.append(
                    CurrentSource(
                        name=f"LDOIN::{ldo.name}",
                        n_plus=_n(ldo.vin),
                        n_minus=_n(ldo.gnd),
                        amps=iin,
                    )
                )

        sol = solve_dc(iter_net)

        # Update LDO setpoints from solved Vin and solved Iout.
        max_dv = 0.0
        max_di = 0.0

        for ldo in ldos:
            vin = _n(ldo.vin)
            gnd = _n(ldo.gnd)

            vin_v = sol.node_v.get(vin, 0.0) - sol.node_v.get(gnd, 0.0)

            # Dropout mode switching: Vout cannot exceed Vin - dropout.
            vout_target = min(ldo.vout_nom_v, max(0.0, vin_v - ldo.dropout_v))

            v_prev = vout_set[ldo.name]
            v_new = v_prev + settings.damping_v * (vout_target - v_prev)
            vout_set[ldo.name] = v_new
            max_dv = max(max_dv, abs(v_new - v_prev))

            # Input current draw: approximate Iin ~= Iout + Iq.
            iout = abs(sol.vsource_i.get(f"LDO::{ldo.name}", 0.0))
            iin_target = iout + max(0.0, ldo.quiescent_current_a)

            i_prev = iin_set[ldo.name]
            i_new = i_prev + settings.damping_i * (iin_target - i_prev)
            iin_set[ldo.name] = i_new
            max_di = max(max_di, abs(i_new - i_prev))

        # Check convergence on node voltages as well.
        max_vnode = 0.0
        if prev is not None:
            for node, v in sol.node_v.items():
                max_vnode = max(max_vnode, abs(v - prev.node_v.get(node, 0.0)))

        last_max_dv = max(max_dv, max_vnode)
        last_max_di = max_di

        if prev is not None and last_max_dv < settings.tol_v and last_max_di < settings.tol_a:
            converged = True
            prev = sol
            break

        prev = sol

    assert prev is not None
    return OperatingPointResult(solution=prev, converged=converged, iters=it, max_delta_v=last_max_dv, max_delta_a=last_max_di)


import os


def solve_operating_point(
    netlist: CircuitNetlist,
    settings: OperatingPointSettings = OperatingPointSettings(),
) -> OperatingPointResult:
    """Solve operating point.

    Backend selection via `CIRCUIT_AI_OP_BACKEND` env var:
    - `python` (default): Python iteration + DC solver backend (python/rust)
    - `rust`: Rust operating-point loop + DC solve
    """

    backend = (os.getenv("CIRCUIT_AI_OP_BACKEND") or "python").strip().lower()
    if backend == "rust":
        try:
            from src.engines.rust_op import solve_operating_point_rust

            return solve_operating_point_rust(netlist, settings=settings)
        except Exception:
            return _solve_operating_point_python(netlist, settings=settings)

    return _solve_operating_point_python(netlist, settings=settings)

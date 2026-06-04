"""DC circuit solver using Modified Nodal Analysis (MNA).

Supported elements:
- Resistors
- Independent current sources
- Independent voltage sources (including ideal LDO outputs via `CircuitNetlist`)

This is meant to be a deterministic kernel that higher-level validators can rely on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from src.engines.netlist import CircuitNetlist, CurrentSource, Node, Resistor, VoltageSource, is_ground


class SingularMatrixError(RuntimeError):
    pass


@dataclass(frozen=True)
class DCSolution:
    node_v: Dict[Node, float]
    vsource_i: Dict[str, float]
    resistor_i: Dict[str, float]
    resistor_p: Dict[str, float]


def _gaussian_solve(a: List[List[float]], b: List[float]) -> List[float]:
    n = len(b)
    if any(len(row) != n for row in a):
        raise ValueError("Matrix must be square")

    # Augment
    m = [row[:] + [b_i] for row, b_i in zip(a, b)]

    # Forward elimination with partial pivot
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-14:
            raise SingularMatrixError("Singular matrix")
        if pivot != col:
            m[col], m[pivot] = m[pivot], m[col]

        piv = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= piv

        for r in range(col + 1, n):
            factor = m[r][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                m[r][j] -= factor * m[col][j]

    # Back substitution
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))
    return x


def _solve_dc_python(netlist: CircuitNetlist, ground: Node = "0") -> DCSolution:
    """Solve a DC circuit with MNA.

    Conventions:
    - Ground node voltage is forced to 0V.
    - Current source `amps` flows from n_plus -> n_minus.
    - Voltage source current is reported as positive from n_plus -> n_minus.
    """

    all_nodes = ["0" if is_ground(n) else n for n in netlist.all_nodes()]
    gnd = "0" if is_ground(ground) else ground

    node_list = [n for n in all_nodes if n != gnd]
    node_index = {n: i for i, n in enumerate(node_list)}

    resistors = netlist.solver_resistors()
    isources = netlist.current_sources
    vsources = netlist.solver_voltage_sources()

    n = len(node_list)
    m = len(vsources)
    size = n + m

    a = [[0.0 for _ in range(size)] for _ in range(size)]
    z = [0.0 for _ in range(size)]

    def idx(node: Node) -> int:
        return node_index[node]

    # Stamp resistors
    for r in resistors:
        if r.ohms <= 0:
            raise ValueError(f"Invalid resistor {r.name}: ohms must be > 0")
        n1 = "0" if is_ground(r.n1) else r.n1
        n2 = "0" if is_ground(r.n2) else r.n2
        g = 1.0 / r.ohms

        if n1 != gnd:
            a[idx(n1)][idx(n1)] += g
        if n2 != gnd:
            a[idx(n2)][idx(n2)] += g
        if n1 != gnd and n2 != gnd:
            a[idx(n1)][idx(n2)] -= g
            a[idx(n2)][idx(n1)] -= g

    # Stamp current sources (as current injections)
    for cs in isources:
        p = "0" if is_ground(cs.n_plus) else cs.n_plus
        nnode = "0" if is_ground(cs.n_minus) else cs.n_minus
        i = cs.amps
        # Inject +I into n_minus, -I into n_plus
        if p != gnd:
            z[idx(p)] -= i
        if nnode != gnd:
            z[idx(nnode)] += i

    # Stamp voltage sources
    for k, vs in enumerate(vsources):
        p = "0" if is_ground(vs.n_plus) else vs.n_plus
        nnode = "0" if is_ground(vs.n_minus) else vs.n_minus
        row = n + k

        if p != gnd:
            a[idx(p)][row] += 1.0
            a[row][idx(p)] += 1.0
        if nnode != gnd:
            a[idx(nnode)][row] -= 1.0
            a[row][idx(nnode)] -= 1.0

        z[row] = vs.volts

    x = _gaussian_solve(a, z)

    node_v: Dict[Node, float] = {gnd: 0.0}
    for node, i in node_index.items():
        node_v[node] = x[i]

    vsource_i: Dict[str, float] = {}
    for k, vs in enumerate(vsources):
        vsource_i[vs.name] = x[n + k]

    resistor_i: Dict[str, float] = {}
    resistor_p: Dict[str, float] = {}
    for r in resistors:
        n1 = "0" if is_ground(r.n1) else r.n1
        n2 = "0" if is_ground(r.n2) else r.n2
        v1 = node_v[gnd] if n1 == gnd else node_v[n1]
        v2 = node_v[gnd] if n2 == gnd else node_v[n2]
        i = (v1 - v2) / r.ohms
        resistor_i[r.name] = i
        resistor_p[r.name] = (i * i) * r.ohms

    return DCSolution(node_v=node_v, vsource_i=vsource_i, resistor_i=resistor_i, resistor_p=resistor_p)

import os


def solve_dc(netlist: CircuitNetlist, ground: Node = "0") -> DCSolution:
    """Solve DC circuit.

    Backend selection via `CIRCUIT_AI_DC_BACKEND` env var:
    - `python` (default): pure-Python MNA
    - `rust`: Rust `cdylib` via ctypes (if available)
    """

    backend = (os.getenv("CIRCUIT_AI_DC_BACKEND") or "python").strip().lower()
    if backend == "rust":
        try:
            from src.engines.rust_dc import solve_dc_rust

            return solve_dc_rust(netlist, ground=ground)
        except Exception:
            # Fall back to Python backend if Rust isn't available.
            return _solve_dc_python(netlist, ground=ground)

    return _solve_dc_python(netlist, ground=ground)

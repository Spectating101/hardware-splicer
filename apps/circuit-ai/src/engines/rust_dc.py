"""Rust-backed DC solver via `ctypes`.

This loads `rust_physics/target/{debug|release}/libcircuit_ai_physics.so` and calls
`circuit_ai_solve_dc`.

No external Python deps.
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from src.engines.dc_mna import DCSolution, SingularMatrixError
from src.engines.netlist import CircuitNetlist, Node, Resistor, VoltageSource, is_ground


class RustBackendError(RuntimeError):
    pass


class _CResistor(ctypes.Structure):
    _fields_ = [("n1", ctypes.c_uint32), ("n2", ctypes.c_uint32), ("ohms", ctypes.c_double)]


class _CCurrentSource(ctypes.Structure):
    _fields_ = [("n_plus", ctypes.c_uint32), ("n_minus", ctypes.c_uint32), ("amps", ctypes.c_double)]


class _CVoltageSource(ctypes.Structure):
    _fields_ = [("n_plus", ctypes.c_uint32), ("n_minus", ctypes.c_uint32), ("volts", ctypes.c_double)]


def _default_lib_paths() -> List[Path]:
    here = Path(__file__).resolve()
    project = here.parents[2]  # ../src/engines -> project root
    candidates = [
        project / "rust_physics" / "target" / "release" / "libcircuit_ai_physics.so",
        project / "rust_physics" / "target" / "debug" / "libcircuit_ai_physics.so",
    ]
    return candidates


def _load_lib() -> ctypes.CDLL:
    override = os.getenv("CIRCUIT_AI_RUST_DC_LIB")
    if override:
        lib_path = Path(override)
        if not lib_path.exists():
            raise RustBackendError(f"CIRCUIT_AI_RUST_DC_LIB not found: {lib_path}")
        lib = ctypes.CDLL(str(lib_path))
    else:
        for path in _default_lib_paths():
            if path.exists():
                lib = ctypes.CDLL(str(path))
                break
        else:
            raise RustBackendError("Rust DC library not found; build `rust_physics` or set CIRCUIT_AI_RUST_DC_LIB")

    fn = lib.circuit_ai_solve_dc
    fn.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(_CResistor),
        ctypes.c_uint32,
        ctypes.POINTER(_CCurrentSource),
        ctypes.c_uint32,
        ctypes.POINTER(_CVoltageSource),
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    fn.restype = ctypes.c_int32
    return lib


def _normalize_node(n: Node) -> Node:
    return "0" if is_ground(n) else n


def solve_dc_rust(netlist: CircuitNetlist, ground: Node = "0") -> DCSolution:
    lib = _load_lib()

    # Build node mapping for the linearized circuit.
    nodes = ["0" if is_ground(n) else n for n in netlist.all_nodes()]
    gnd = _normalize_node(ground)
    if gnd not in nodes:
        nodes = [gnd] + nodes

    # Stable order: keep solver's order but ensure gnd at index 0 for convenience.
    nodes = [gnd] + [n for n in nodes if n != gnd]
    node_to_id = {n: i for i, n in enumerate(nodes)}

    resistors = netlist.solver_resistors()
    vsources = netlist.solver_voltage_sources()
    isources = netlist.current_sources

    c_res = (_CResistor * len(resistors))()
    for i, r in enumerate(resistors):
        c_res[i] = _CResistor(node_to_id[_normalize_node(r.n1)], node_to_id[_normalize_node(r.n2)], float(r.ohms))

    c_is = (_CCurrentSource * len(isources))()
    for i, cs in enumerate(isources):
        c_is[i] = _CCurrentSource(node_to_id[_normalize_node(cs.n_plus)], node_to_id[_normalize_node(cs.n_minus)], float(cs.amps))

    c_vs = (_CVoltageSource * len(vsources))()
    for i, vs in enumerate(vsources):
        c_vs[i] = _CVoltageSource(node_to_id[_normalize_node(vs.n_plus)], node_to_id[_normalize_node(vs.n_minus)], float(vs.volts))

    out_node_v = (ctypes.c_double * len(nodes))()
    out_vsrc_i = (ctypes.c_double * len(vsources))()

    rc = lib.circuit_ai_solve_dc(
        ctypes.c_uint32(len(nodes)),
        ctypes.c_uint32(node_to_id[gnd]),
        ctypes.cast(c_res, ctypes.POINTER(_CResistor)),
        ctypes.c_uint32(len(resistors)),
        ctypes.cast(c_is, ctypes.POINTER(_CCurrentSource)),
        ctypes.c_uint32(len(isources)),
        ctypes.cast(c_vs, ctypes.POINTER(_CVoltageSource)),
        ctypes.c_uint32(len(vsources)),
        ctypes.cast(out_node_v, ctypes.POINTER(ctypes.c_double)),
        ctypes.cast(out_vsrc_i, ctypes.POINTER(ctypes.c_double)),
    )

    if rc == 1:
        raise SingularMatrixError("Singular matrix")
    if rc != 0:
        raise RustBackendError(f"Rust solver error rc={rc}")

    node_v: Dict[Node, float] = {n: float(out_node_v[node_to_id[n]]) for n in nodes}

    # Map currents back by voltage source name (same order)
    vsource_i: Dict[str, float] = {}
    for i, vs in enumerate(vsources):
        vsource_i[vs.name] = float(out_vsrc_i[i])

    # Recompute resistor currents/powers deterministically in Python for now.
    resistor_i: Dict[str, float] = {}
    resistor_p: Dict[str, float] = {}
    for r in resistors:
        v1 = node_v[_normalize_node(r.n1)]
        v2 = node_v[_normalize_node(r.n2)]
        i = (v1 - v2) / r.ohms
        resistor_i[r.name] = i
        resistor_p[r.name] = (i * i) * r.ohms

    return DCSolution(node_v=node_v, vsource_i=vsource_i, resistor_i=resistor_i, resistor_p=resistor_p)

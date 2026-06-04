"""Rust-backed operating-point solver via `ctypes`.

Loads `rust_physics/target/{debug|release}/libcircuit_ai_physics.so` and calls
`circuit_ai_solve_operating_point`.

No external Python deps.
"""

from __future__ import annotations

import ctypes
import math
import os
from pathlib import Path
from typing import Dict, List, Optional

from src.engines.dc_mna import DCSolution, SingularMatrixError
from src.engines.dc_operating_point import OperatingPointResult, OperatingPointSettings
from src.engines.netlist import CircuitNetlist, Node, is_ground


class RustBackendError(RuntimeError):
    pass


class _CResistor(ctypes.Structure):
    _fields_ = [("n1", ctypes.c_uint32), ("n2", ctypes.c_uint32), ("ohms", ctypes.c_double)]


class _CCurrentSource(ctypes.Structure):
    _fields_ = [("n_plus", ctypes.c_uint32), ("n_minus", ctypes.c_uint32), ("amps", ctypes.c_double)]


class _CCurrentLoad(ctypes.Structure):
    _fields_ = [("node", ctypes.c_uint32), ("gnd", ctypes.c_uint32), ("amps", ctypes.c_double), ("min_v_off", ctypes.c_double)]


class _CVoltageSource(ctypes.Structure):
    _fields_ = [("n_plus", ctypes.c_uint32), ("n_minus", ctypes.c_uint32), ("volts", ctypes.c_double)]


class _CLdo(ctypes.Structure):
    _fields_ = [
        ("vin", ctypes.c_uint32),
        ("vout", ctypes.c_uint32),
        ("gnd", ctypes.c_uint32),
        ("vout_nom_v", ctypes.c_double),
        ("dropout_v", ctypes.c_double),
        ("quiescent_current_a", ctypes.c_double),
    ]


class _CPowerLoad(ctypes.Structure):
    _fields_ = [
        ("node", ctypes.c_uint32),
        ("gnd", ctypes.c_uint32),
        ("watts", ctypes.c_double),
        ("v_min", ctypes.c_double),
        ("max_amps", ctypes.c_double),
        ("min_v_off", ctypes.c_double),
    ]


def _default_lib_paths() -> List[Path]:
    here = Path(__file__).resolve()
    project = here.parents[2]
    return [
        project / "rust_physics" / "target" / "release" / "libcircuit_ai_physics.so",
        project / "rust_physics" / "target" / "debug" / "libcircuit_ai_physics.so",
    ]


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
            raise RustBackendError("Rust physics library not found; build `rust_physics` or set CIRCUIT_AI_RUST_DC_LIB")

    fn = lib.circuit_ai_solve_operating_point
    fn.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(_CResistor),
        ctypes.c_uint32,
        ctypes.POINTER(_CCurrentSource),
        ctypes.c_uint32,
        ctypes.POINTER(_CVoltageSource),
        ctypes.c_uint32,
        ctypes.POINTER(_CLdo),
        ctypes.c_uint32,
        ctypes.POINTER(_CCurrentLoad),
        ctypes.c_uint32,
        ctypes.POINTER(_CPowerLoad),
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    fn.restype = ctypes.c_int32
    return lib


def _n(node: Node) -> Node:
    return "0" if is_ground(node) else node


def solve_operating_point_rust(netlist: CircuitNetlist, settings: OperatingPointSettings = OperatingPointSettings()) -> OperatingPointResult:
    lib = _load_lib()

    nodes = ["0" if is_ground(n) else n for n in netlist.all_nodes()]
    gnd = _n("0")
    if gnd not in nodes:
        nodes = [gnd] + nodes
    nodes = [gnd] + [n for n in nodes if n != gnd]
    node_to_id = {n: i for i, n in enumerate(nodes)}

    resistors = netlist.solver_resistors()
    base_is = netlist.current_sources
    base_vs = netlist.voltage_sources
    ldos = netlist.ldos

    c_res = (_CResistor * len(resistors))()
    for i, r in enumerate(resistors):
        c_res[i] = _CResistor(node_to_id[_n(r.n1)], node_to_id[_n(r.n2)], float(r.ohms))

    c_is = (_CCurrentSource * len(base_is))()
    for i, cs in enumerate(base_is):
        c_is[i] = _CCurrentSource(node_to_id[_n(cs.n_plus)], node_to_id[_n(cs.n_minus)], float(cs.amps))

    c_vs = (_CVoltageSource * len(base_vs))()
    for i, vs in enumerate(base_vs):
        c_vs[i] = _CVoltageSource(node_to_id[_n(vs.n_plus)], node_to_id[_n(vs.n_minus)], float(vs.volts))

    c_ldo = (_CLdo * len(ldos))()
    for i, ldo in enumerate(ldos):
        c_ldo[i] = _CLdo(
            node_to_id[_n(ldo.vin)],
            node_to_id[_n(ldo.vout)],
            node_to_id[_n(ldo.gnd)],
            float(ldo.vout_nom_v),
            float(ldo.dropout_v),
            float(ldo.quiescent_current_a),
        )

    loads_cc = netlist.loads_cc
    c_cc = (_CCurrentLoad * len(loads_cc))()
    for i, load in enumerate(loads_cc):
        min_v_off = float(load.min_v_off) if load.min_v_off is not None else math.inf
        c_cc[i] = _CCurrentLoad(node_to_id[_n(load.node)], node_to_id[_n(load.gnd)], float(load.amps), min_v_off)

    loads_cp = netlist.loads_cp
    c_cp = (_CPowerLoad * len(loads_cp))()
    for i, load in enumerate(loads_cp):
        max_amps = float(load.max_amps) if load.max_amps is not None else math.inf
        min_v_off = float(load.min_v_off) if load.min_v_off is not None else math.inf
        c_cp[i] = _CPowerLoad(
            node_to_id[_n(load.node)],
            node_to_id[_n(load.gnd)],
            float(load.watts),
            float(load.v_min),
            max_amps,
            min_v_off,
        )

    out_converged = ctypes.c_uint32(0)
    out_iters = ctypes.c_uint32(0)
    out_dv = ctypes.c_double(0.0)
    out_di = ctypes.c_double(0.0)

    out_node_v = (ctypes.c_double * len(nodes))()
    out_vsrc_i = (ctypes.c_double * (len(base_vs) + len(ldos)))()

    rc = lib.circuit_ai_solve_operating_point(
        ctypes.c_uint32(len(nodes)),
        ctypes.c_uint32(node_to_id[gnd]),
        ctypes.cast(c_res, ctypes.POINTER(_CResistor)),
        ctypes.c_uint32(len(resistors)),
        ctypes.cast(c_is, ctypes.POINTER(_CCurrentSource)),
        ctypes.c_uint32(len(base_is)),
        ctypes.cast(c_vs, ctypes.POINTER(_CVoltageSource)),
        ctypes.c_uint32(len(base_vs)),
        ctypes.cast(c_ldo, ctypes.POINTER(_CLdo)),
        ctypes.c_uint32(len(ldos)),
        ctypes.cast(c_cc, ctypes.POINTER(_CCurrentLoad)),
        ctypes.c_uint32(len(loads_cc)),
        ctypes.cast(c_cp, ctypes.POINTER(_CPowerLoad)),
        ctypes.c_uint32(len(loads_cp)),
        ctypes.c_uint32(settings.max_iters),
        ctypes.c_double(settings.tol_v),
        ctypes.c_double(settings.tol_a),
        ctypes.c_double(settings.damping_v),
        ctypes.c_double(settings.damping_i),
        ctypes.byref(out_converged),
        ctypes.byref(out_iters),
        ctypes.byref(out_dv),
        ctypes.byref(out_di),
        ctypes.cast(out_node_v, ctypes.POINTER(ctypes.c_double)),
        ctypes.cast(out_vsrc_i, ctypes.POINTER(ctypes.c_double)),
    )

    if rc == 1:
        raise SingularMatrixError("Singular matrix")
    if rc != 0:
        raise RustBackendError(f"Rust operating-point error rc={rc}")

    node_v: Dict[str, float] = {n: float(out_node_v[node_to_id[n]]) for n in nodes}

    vsource_i: Dict[str, float] = {}
    for i, vs in enumerate(base_vs):
        vsource_i[vs.name] = float(out_vsrc_i[i])
    for j, ldo in enumerate(ldos):
        vsource_i[f"LDO::{ldo.name}"] = float(out_vsrc_i[len(base_vs) + j])

    # Resistor currents/powers
    resistor_i: Dict[str, float] = {}
    resistor_p: Dict[str, float] = {}
    for r in resistors:
        v1 = node_v[_n(r.n1)]
        v2 = node_v[_n(r.n2)]
        i = (v1 - v2) / r.ohms
        resistor_i[r.name] = i
        resistor_p[r.name] = (i * i) * r.ohms

    sol = DCSolution(node_v=node_v, vsource_i=vsource_i, resistor_i=resistor_i, resistor_p=resistor_p)

    return OperatingPointResult(
        solution=sol,
        converged=bool(out_converged.value),
        iters=int(out_iters.value),
        max_delta_v=float(out_dv.value),
        max_delta_a=float(out_di.value),
    )

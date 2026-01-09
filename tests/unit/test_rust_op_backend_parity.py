import os
from pathlib import Path

import pytest

from src.engines.netlist import CircuitNetlist, LDO, Resistor, TraceResistor, TraceSpec, VoltageSource


def _rust_lib_exists() -> bool:
    root = Path(__file__).resolve().parents[2]
    return (
        (root / "rust_physics" / "target" / "debug" / "libcircuit_ai_physics.so").exists()
        or (root / "rust_physics" / "target" / "release" / "libcircuit_ai_physics.so").exists()
    )


@pytest.mark.skipif(not _rust_lib_exists(), reason="Rust physics library not built")
def test_rust_operating_point_parity_demo_like():
    net = CircuitNetlist()
    net.voltage_sources.append(VoltageSource(name="VUSB", n_plus="VBUS", n_minus="0", volts=5.0))
    net.traces.append(
        TraceResistor(
            name="VBUS_TO_LDOIN",
            n1="VBUS",
            n2="LDO_IN",
            spec=TraceSpec(length_m=0.20, width_m=0.03e-3, copper_oz=1.0),
        )
    )
    net.ldos.append(LDO(name="U1", vin="LDO_IN", vout="V3V3", vout_nom_v=3.3, dropout_v=0.3, quiescent_current_a=0.002))
    net.resistors.append(Resistor(name="RLOAD", n1="V3V3", n2="0", ohms=3.3))

    from src.engines.dc_operating_point import OperatingPointSettings, _solve_operating_point_python, solve_operating_point

    settings = OperatingPointSettings(max_iters=80, tol_v=1e-5, tol_a=1e-6, damping_v=0.6, damping_i=0.6)

    py = _solve_operating_point_python(net, settings=settings)

    os.environ["CIRCUIT_AI_OP_BACKEND"] = "rust"
    rs = solve_operating_point(net, settings=settings)

    assert abs(py.solution.node_v["V3V3"] - rs.solution.node_v["V3V3"]) < 1e-4
    assert abs(py.solution.node_v["LDO_IN"] - rs.solution.node_v["LDO_IN"]) < 1e-4

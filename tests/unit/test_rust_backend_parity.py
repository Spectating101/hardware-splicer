import os
from pathlib import Path

import pytest

from src.engines.netlist import CircuitNetlist, Resistor, VoltageSource


def _rust_lib_exists() -> bool:
    # Mirror rust_dc default paths
    root = Path(__file__).resolve().parents[2]
    return (
        (root / "rust_physics" / "target" / "debug" / "libcircuit_ai_physics.so").exists()
        or (root / "rust_physics" / "target" / "release" / "libcircuit_ai_physics.so").exists()
    )


@pytest.mark.skipif(not _rust_lib_exists(), reason="Rust dc library not built")
def test_rust_python_dc_backend_parity_voltage_divider():
    net = CircuitNetlist(
        resistors=[
            Resistor(name="R1", n1="VIN", n2="VOUT", ohms=1000.0),
            Resistor(name="R2", n1="VOUT", n2="0", ohms=1000.0),
        ],
        voltage_sources=[VoltageSource(name="V1", n_plus="VIN", n_minus="0", volts=10.0)],
    )

    from src.engines.dc_mna import _solve_dc_python

    py = _solve_dc_python(net)

    os.environ["CIRCUIT_AI_DC_BACKEND"] = "rust"
    from src.engines.dc_mna import solve_dc

    rs = solve_dc(net)

    assert abs(py.node_v["VOUT"] - rs.node_v["VOUT"]) < 1e-9

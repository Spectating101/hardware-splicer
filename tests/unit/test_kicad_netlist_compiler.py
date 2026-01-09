import math
from pathlib import Path

from src.engines.kicad_netlist_compiler import compile_kicad_netlist
from src.engines.kicad_hints import generate_hints_template
from src.engines.power_tree_validator import validate_pcb_power_tree


def test_kicad_voltage_divider_compiles_and_solves():
    net_path = Path("tests/data/kicad_divider.net")
    hints = {
        "sources": [{"name": "V1", "net": "VIN", "gnd": "GND", "volts": 10.0, "max_current_a": 1.0}],
        "voltage_constraints": [{"name": "VOUT", "net": "VOUT", "gnd": "GND", "min_v": 4.9, "max_v": 5.1}],
    }

    compiled = compile_kicad_netlist(str(net_path), hints=hints)
    results, issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)

    assert results["converged"] is True
    sol = results["solution"]

    assert math.isclose(sol.node_v["VOUT"], 5.0, abs_tol=1e-3)
    assert not any(i.issue == "Undervoltage" for i in issues)

def test_kicad_auto_hints_can_solve_resistor_only_netlist():
    net_path = Path("tests/data/kicad_divider.net")
    hints = generate_hints_template(str(net_path))["hints"]
    compiled = compile_kicad_netlist(str(net_path), hints=hints)
    results, issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)
    assert results["converged"] is True
    sol = results["solution"]
    assert math.isclose(sol.node_v["VOUT"], 2.5, abs_tol=1e-3)
    assert not issues

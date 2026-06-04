from src.engines.kicad_hints import generate_hints_template
from src.engines.kicad_netlist_compiler import compile_kicad_netlist
from src.engines.power_tree_validator import validate_pcb_power_tree


def test_kicad_hints_infers_ldo_and_skips_ldo_as_load():
    payload = generate_hints_template("tests/data/kicad_regulator_5v_to_3v3.net")
    hints = payload["hints"]

    assert hints["ldos"], "expected inferred LDO"
    assert all(l["name"] != "U1" for l in hints["loads_cc"]), "regulator should not be a load"
    assert any(l["name"] == "U2" for l in hints["loads_cc"]), "expected ESP32 load"


def test_kicad_compiled_ldo_solves_and_regulates_3v3():
    hints = generate_hints_template("tests/data/kicad_regulator_5v_to_3v3.net")["hints"]
    compiled = compile_kicad_netlist("tests/data/kicad_regulator_5v_to_3v3.net", hints=hints)

    results, issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)
    assert results["converged"] is True

    sol = results["solution"]
    # Auto-hints add a small series trace, so the regulated node is +3V3__SRC and the rail may droop slightly.
    assert abs(sol.node_v["+3V3__SRC"] - 3.3) < 1e-3
    assert 3.2 < sol.node_v["+3V3"] <= sol.node_v["+3V3__SRC"]

    # Should be within rail constraints
    assert not any(i.issue == "Undervoltage" and i.component == "RAIL::+3V3" for i in issues)

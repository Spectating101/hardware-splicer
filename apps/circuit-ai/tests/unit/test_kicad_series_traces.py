from src.engines.kicad_hints import generate_hints_template
from src.engines.kicad_netlist_compiler import compile_kicad_netlist
from src.engines.power_tree_validator import validate_pcb_power_tree


def test_kicad_auto_hints_series_traces_deduped_and_prioritized():
    hints = generate_hints_template("tests/data/kicad_regulator_5v_to_3v3.net")["hints"]
    series = hints.get("series_traces") or []

    # Should include one series trace per key net (no duplicates for the source/LDO VIN net).
    kinds_by_net = {t["net"]: t["kind"] for t in series}
    assert kinds_by_net == {"VBUS": "source_to_rail", "+3V3": "ldo_to_rail"}


def test_kicad_compiler_applies_series_traces_to_source_and_ldo_output():
    hints = generate_hints_template("tests/data/kicad_regulator_5v_to_3v3.net")["hints"]
    compiled = compile_kicad_netlist("tests/data/kicad_regulator_5v_to_3v3.net", hints=hints)

    # Source moved to VBUS__SRC with a trace to VBUS
    assert any(v.n_plus == "VBUS__SRC" for v in compiled.netlist.voltage_sources)
    assert any({t.n1, t.n2} == {"VBUS__SRC", "VBUS"} for t in compiled.netlist.traces)

    # LDO output moved to +3V3__SRC with a trace to +3V3
    assert any(ldo.vout == "+3V3__SRC" for ldo in compiled.netlist.ldos)
    assert any({t.n1, t.n2} == {"+3V3__SRC", "+3V3"} for t in compiled.netlist.traces)

    results, issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)
    assert results["converged"] is True
    assert not any(i.issue == "Undervoltage" and i.component == "RAIL::+3V3" for i in issues)

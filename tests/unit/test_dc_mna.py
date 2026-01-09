import math

import pytest

from src.engines.dc_mna import SingularMatrixError, solve_dc
from src.engines.netlist import CircuitNetlist, CurrentSource, LDO, Resistor, TraceResistor, TraceSpec, VoltageConstraint, VoltageSource
from src.engines.power_tree_validator import PowerTreeConstraints, SourceCurrentLimit, validate_pcb_power_tree


def test_voltage_divider_half():
    net = CircuitNetlist(
        resistors=[
            Resistor(name="R1", n1="VIN", n2="VOUT", ohms=1000.0),
            Resistor(name="R2", n1="VOUT", n2="0", ohms=1000.0),
        ],
        voltage_sources=[VoltageSource(name="V1", n_plus="VIN", n_minus="0", volts=10.0)],
    )

    sol = solve_dc(net)
    assert math.isclose(sol.node_v["VOUT"], 5.0, rel_tol=0, abs_tol=1e-6)


def test_current_source_into_resistor():
    net = CircuitNetlist(
        resistors=[Resistor(name="R", n1="N", n2="0", ohms=1000.0)],
        current_sources=[CurrentSource(name="I1", n_plus="0", n_minus="N", amps=0.001)],
    )

    sol = solve_dc(net)
    assert math.isclose(sol.node_v["N"], 1.0, rel_tol=0, abs_tol=1e-6)


def test_singular_raises():
    # Floating node with a voltage source between two floating nodes
    net = CircuitNetlist(voltage_sources=[VoltageSource(name="V1", n_plus="A", n_minus="B", volts=1.0)])
    with pytest.raises(SingularMatrixError):
        solve_dc(net)


def test_pcb_ldo_dropout_is_detected():
    net = CircuitNetlist()
    net.voltage_sources.append(VoltageSource(name="VUSB", n_plus="VBUS", n_minus="0", volts=5.0))

    # High resistance trace to force vin droop under load
    net.traces.append(
        TraceResistor(
            name="VBUS_TO_LDOIN",
            n1="VBUS",
            n2="LDO_IN",
            spec=TraceSpec(length_m=0.10, width_m=0.03e-3, copper_oz=1.0),
        )
    )

    net.ldos.append(LDO(name="U1", vin="LDO_IN", vout="V3V3", vout_nom_v=3.3, dropout_v=0.3, max_current_a=1.0))

    # ~1A nominal load
    net.resistors.append(Resistor(name="RLOAD", n1="V3V3", n2="0", ohms=3.3))

    net.voltage_constraints.append(VoltageConstraint(name="V3V3_RAIL", node="V3V3", min_v=3.25))

    results, issues = validate_pcb_power_tree(
        net,
        constraints=PowerTreeConstraints(source_limits=[SourceCurrentLimit(source_name="VUSB", max_current_a=0.5)]),
    )

    assert results["converged"] is True
    assert "power_report" in results
    assert "upstream_power_w" in results["power_report"]
    assert "estimated_total_consumption_w" in results["power_report"]
    assert any(i.issue == "LDO dropout" for i in issues)
    dropout = [i for i in issues if i.issue == "LDO dropout"]
    assert dropout
    assert "required_vin_v" in dropout[0].physics_data
    assert "dropout_margin_v" in dropout[0].physics_data
    assert any(i.issue == "Undervoltage" and i.component == "V3V3_RAIL" for i in issues)
    assert any(i.issue == "Source current exceeded" for i in issues)
    trace_issues = [i for i in issues if i.issue == "High trace voltage drop"]
    assert trace_issues
    assert "recommended_width_m" in trace_issues[0].physics_data
    assert trace_issues[0].physics_data["recommended_width_m"] > trace_issues[0].physics_data["width_m"]

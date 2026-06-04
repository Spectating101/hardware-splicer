from src.engines.netlist import (
    CircuitNetlist,
    ConstantCurrentLoad,
    ConstantPowerLoad,
    LDO,
    Resistor,
    TraceResistor,
    TraceSpec,
    VoltageConstraint,
    VoltageSource,
)
from src.engines.netlist_io import netlist_from_dict, netlist_to_dict


def test_netlist_round_trip_dict():
    net = CircuitNetlist()
    net.voltage_sources.append(VoltageSource(name="VUSB", n_plus="VBUS", n_minus="0", volts=5.0))
    net.traces.append(
        TraceResistor(
            name="T1",
            n1="VBUS",
            n2="VIN",
            spec=TraceSpec(length_m=0.05, width_m=0.2e-3, copper_oz=1.0),
        )
    )
    net.ldos.append(LDO(name="U1", vin="VIN", vout="V3V3", vout_nom_v=3.3, dropout_v=0.25, max_current_a=1.0))
    net.resistors.append(Resistor(name="RLOAD", n1="V3V3", n2="0", ohms=10.0))
    net.loads_cc.append(ConstantCurrentLoad(name="SENSOR", node="V3V3", amps=0.010, min_v_off=2.8))
    net.loads_cp.append(ConstantPowerLoad(name="BUCK", node="VBUS", watts=1.5, v_min=0.5, max_amps=2.0))
    net.voltage_constraints.append(VoltageConstraint(name="V3V3", node="V3V3", min_v=3.0, max_v=3.6, severity="error"))

    d = netlist_to_dict(net)
    net2 = netlist_from_dict(d)
    d2 = netlist_to_dict(net2)

    assert d == d2

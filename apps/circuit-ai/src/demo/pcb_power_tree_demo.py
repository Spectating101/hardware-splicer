#!/usr/bin/env python3

from __future__ import annotations

from src.engines.netlist import CircuitNetlist, LDO, Resistor, TraceResistor, TraceSpec, VoltageConstraint, VoltageSource
from src.engines.power_tree_validator import PowerTreeConstraints, SourceCurrentLimit, validate_pcb_power_tree


def build_demo_netlist() -> CircuitNetlist:
    # USB 5V source feeding an LDO through a too-resistive trace, with a heavy 3.3V load.
    # This demo is intentionally "bad" so the engine produces numeric, explainable failures.
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

    net.ldos.append(
        LDO(
            name="U1",
            vin="LDO_IN",
            vout="V3V3",
            gnd="0",
            vout_nom_v=3.3,
            dropout_v=0.3,
            max_current_a=1.0,
            quiescent_current_a=0.002,
            r_theta_ja_c_per_w=60.0,
            tj_max_c=125.0,
            ambient_c=25.0,
        )
    )

    net.voltage_constraints.append(VoltageConstraint(name="V3V3_RAIL", node="V3V3", min_v=3.0))

    # 3.3V load ~1A (3.3 ohm)
    net.resistors.append(Resistor(name="RLOAD", n1="V3V3", n2="0", ohms=3.3))

    return net


def main() -> None:
    net = build_demo_netlist()
    results, issues = validate_pcb_power_tree(
        net,
        constraints=PowerTreeConstraints(
            source_limits=[SourceCurrentLimit(source_name="VUSB", max_current_a=0.5)],
            max_trace_drop_v=0.25,
        ),
    )

    sol = results["solution"]
    print(f"Operating point: converged={results['converged']} iters={results['iterations']}")

    print("\nNode voltages:")
    for k in sorted(sol.node_v.keys()):
        print(f"  {k:>8s}: {sol.node_v[k]:.3f} V")

    print("\nVoltage source currents (positive from + to -):")
    for k in sorted(sol.vsource_i.keys()):
        print(f"  {k:>8s}: {sol.vsource_i[k]*1000:.1f} mA")

    print(f"\nIssues: {len(issues)}")
    for issue in issues:
        print(f"[{issue.severity.upper()}] {issue.component}: {issue.issue}")
        print(f"  {issue.explanation}")
        print(f"  Solution: {issue.solution}")


if __name__ == "__main__":
    main()

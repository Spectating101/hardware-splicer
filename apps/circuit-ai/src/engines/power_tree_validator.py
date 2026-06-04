"""PCB-oriented validation on top of DC operating-point results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from src.engines.circuit_physics import SimulationIssue
from src.engines.dc_operating_point import OperatingPointSettings, solve_operating_point
from src.engines.netlist import CircuitNetlist, LDO, is_ground


@dataclass(frozen=True)
class SourceCurrentLimit:
    source_name: str
    max_current_a: float


@dataclass(frozen=True)
class PowerTreeConstraints:
    source_limits: List[SourceCurrentLimit] = ()
    max_trace_drop_v: float = 0.25


def _n(node: str) -> str:
    return "0" if is_ground(node) else node


def validate_pcb_power_tree(
    netlist: CircuitNetlist,
    constraints: Optional[PowerTreeConstraints] = None,
    op_settings: OperatingPointSettings = OperatingPointSettings(),
) -> tuple[dict, List[SimulationIssue]]:
    """Solve + validate a PCB-style power tree.

    Returns:
        (results, issues)

    `results` is a dict containing the final operating-point solution plus metadata.
    """

    constraints = constraints or PowerTreeConstraints()
    issues: List[SimulationIssue] = []

    op = solve_operating_point(netlist, settings=op_settings)
    sol = op.solution

    if not op.converged:
        issues.append(
            SimulationIssue(
                severity="warning",
                component="solver",
                issue="Operating point did not converge",
                explanation=(f"Solver hit iteration limit ({op.iters}) with max ΔV≈{op.max_delta_v:.2e} and max ΔI≈{op.max_delta_a:.2e}."),
                physics_data={"iters": op.iters, "max_delta_v": op.max_delta_v, "max_delta_a": op.max_delta_a},
                solution="Try adjusting damping/tolerances or simplify the power tree",
            )
        )


    # Source current limits
    for limit in constraints.source_limits:
        if limit.source_name not in sol.vsource_i:
            continue
        i = abs(sol.vsource_i[limit.source_name])
        if i > limit.max_current_a:
            issues.append(
                SimulationIssue(
                    severity="error",
                    component=limit.source_name,
                    issue="Source current exceeded",
                    explanation=(
                        f"{limit.source_name} supplies {i*1000:.0f}mA but is limited to {limit.max_current_a*1000:.0f}mA."
                    ),
                    physics_data={"current_a": i, "limit_a": limit.max_current_a, "over_a": i - limit.max_current_a},
                    solution="Reduce load or use a higher-current source",
                )
            )

    # Trace drop checks (TRACE:: names come from `CircuitNetlist.solver_resistors()`)
    # Trace drop checks (quantitative fix hints)
    traces_by_solver_name = {f"TRACE::{t.name}": t for t in netlist.traces}

    for r_name, i in sol.resistor_i.items():
        if not r_name.startswith("TRACE::"):
            continue

        trace = traces_by_solver_name.get(r_name)
        if trace is None:
            continue

        current_a = abs(i)
        r_ohms = trace.ohms
        vdrop = current_a * r_ohms
        p_w = current_a * current_a * r_ohms

        if vdrop <= constraints.max_trace_drop_v:
            continue

        # Compute required width to meet the max drop at this current.
        # R_target = Vdrop_max / I ; R = rho*L/(w*t) => w = rho*L/(R_target*t)
        rho = 1.724e-8
        thickness_m = 35e-6 * trace.spec.copper_oz
        r_target = constraints.max_trace_drop_v / max(current_a, 1e-12)
        width_needed_m = (rho * trace.spec.length_m) / max(r_target * thickness_m, 1e-18)

        issues.append(
            SimulationIssue(
                severity="warning",
                component=r_name,
                issue="High trace voltage drop",
                explanation=f"Trace drop is {vdrop:.3f}V at {current_a*1000:.0f}mA; this can brown out loads.",
                physics_data={
                    "current_a": current_a,
                    "r_ohms": r_ohms,
                    "vdrop_v": vdrop,
                    "power_w": p_w,
                    "length_m": trace.spec.length_m,
                    "width_m": trace.spec.width_m,
                    "copper_oz": trace.spec.copper_oz,
                    "vdrop_max_v": constraints.max_trace_drop_v,
                    "recommended_width_m": width_needed_m,
                },
                solution=(
                    f"Increase trace width to ~{width_needed_m*1e3:.2f}mm (currently {trace.spec.width_m*1e3:.2f}mm), "
                    f"shorten the run, increase copper weight, or reduce load"
                ),
            )
        )


    # Voltage constraints (brownout/overvoltage)
    for vc in getattr(netlist, "voltage_constraints", []) or []:
        node = _n(vc.node)
        gnd = _n(vc.gnd)
        v = sol.node_v.get(node, 0.0) - sol.node_v.get(gnd, 0.0)

        if vc.min_v is not None and v < vc.min_v:
            issues.append(
                SimulationIssue(
                    severity=vc.severity,
                    component=vc.name,
                    issue="Undervoltage",
                    explanation=f"{vc.name}: V={v:.3f}V below minimum {vc.min_v:.3f}V (node {node}).",
                    physics_data={"v": v, "min_v": vc.min_v, "node": node, "gnd": gnd},
                    solution="Reduce load, improve power distribution, or adjust regulator/source",
                )
            )

        if vc.max_v is not None and v > vc.max_v:
            issues.append(
                SimulationIssue(
                    severity=vc.severity,
                    component=vc.name,
                    issue="Overvoltage",
                    explanation=f"{vc.name}: V={v:.3f}V above maximum {vc.max_v:.3f}V (node {node}).",
                    physics_data={"v": v, "max_v": vc.max_v, "node": node, "gnd": gnd},
                    solution="Check regulator setpoint, wiring, and ensure correct rail selection",
                )
            )

    # LDO checks
    ldo_by_name: Dict[str, LDO] = {ldo.name: ldo for ldo in netlist.ldos}
    for ldo_name, ldo in ldo_by_name.items():
        vsrc_name = f"LDO::{ldo.name}"
        if vsrc_name not in sol.vsource_i:
            continue

        vin_node = _n(ldo.vin)
        vout_node = _n(ldo.vout)
        gnd_node = _n(ldo.gnd)

        vin_abs = sol.node_v.get(vin_node, 0.0)
        vout_abs = sol.node_v.get(vout_node, 0.0)
        gnd_abs = sol.node_v.get(gnd_node, 0.0)

        vin_v = vin_abs - gnd_abs
        vout_v = vout_abs - gnd_abs

        iout = abs(sol.vsource_i.get(vsrc_name, 0.0))

        # Dropout: regulator cannot maintain nominal output.
        required_vin_v = ldo.vout_nom_v + ldo.dropout_v
        dropout_margin_v = vin_v - required_vin_v
        if vout_v < (ldo.vout_nom_v - 1e-3):
            # If we can identify a direct VBUS->VIN trace, compute required width to keep Vin above requirement.
            vin_trace_hint = None
            for t in netlist.traces:
                if _n(t.n1) == "VBUS" and _n(t.n2) == vin_node:
                    i_trace = abs(sol.resistor_i.get(f"TRACE::{t.name}", 0.0))
                    if i_trace > 1e-9:
                        vdrop_allow = max(0.0, sol.node_v.get("VBUS", 0.0) - required_vin_v)
                        if vdrop_allow > 0:
                            rho = 1.724e-8
                            thickness_m = 35e-6 * t.spec.copper_oz
                            r_target = vdrop_allow / i_trace
                            width_needed_reg_m = (rho * t.spec.length_m) / max(r_target * thickness_m, 1e-18)
                            # Also compute width to meet configured max trace drop (if any)
                            width_needed_policy_m = None
                            try:
                                vdrop_max = float(constraints.max_trace_drop_v)
                                if vdrop_max > 0:
                                    r_target2 = vdrop_max / i_trace
                                    width_needed_policy_m = (rho * t.spec.length_m) / max(r_target2 * thickness_m, 1e-18)
                            except Exception:
                                width_needed_policy_m = None

                            vin_trace_hint = {
                                "trace": f"TRACE::{t.name}",
                                "i_trace_a": i_trace,
                                "vdrop_allow_v": vdrop_allow,
                                "length_m": t.spec.length_m,
                                "width_m": t.spec.width_m,
                                "copper_oz": t.spec.copper_oz,
                                "recommended_width_m": width_needed_reg_m,
                                "recommended_width_for_regulation_m": width_needed_reg_m,
                                "recommended_width_for_max_drop_m": width_needed_policy_m,
                            }
                    break
            dropout_solution = "Reduce load, reduce series resistance (trace), or use a lower-dropout regulator"
            if vin_trace_hint:
                w_reg = vin_trace_hint.get("recommended_width_for_regulation_m")
                w_max = vin_trace_hint.get("recommended_width_for_max_drop_m")
                if w_reg is not None:
                    dropout_solution += f"; to avoid dropout, set {vin_trace_hint['trace']} width ≈{w_reg*1e3:.2f}mm"
                if w_max is not None:
                    dropout_solution += f"; to meet max_drop={constraints.max_trace_drop_v:.2f}V, width ≈{w_max*1e3:.2f}mm"

            issues.append(
                SimulationIssue(
                    severity="error",
                    component=ldo.name,
                    issue="LDO dropout",
                    explanation=(
                        f"Vout={vout_v:.3f}V below nominal {ldo.vout_nom_v:.3f}V; "
                        f"Vin={vin_v:.3f}V, dropout={ldo.dropout_v:.3f}V."
                    ),
                    physics_data={
                        "vin_v": vin_v,
                        "vout_v": vout_v,
                        "vout_nom_v": ldo.vout_nom_v,
                        "dropout_v": ldo.dropout_v,
                        "required_vin_v": required_vin_v,
                        "dropout_margin_v": dropout_margin_v,
                        "vbus_v": sol.node_v.get("VBUS", 0.0),
                        "vin_node": vin_node,
                        "vout_node": vout_node,
                        "iout_a": iout,
                        # Optional fix hint if Vin is fed by a modeled trace
                        # (assumes a single trace directly connecting VBUS->vin_node).
                        "vin_trace_hint": vin_trace_hint,
                    },
                    solution=dropout_solution,
                )
            )

        if iout > ldo.max_current_a:
            issues.append(
                SimulationIssue(
                    severity="error",
                    component=ldo.name,
                    issue="LDO overcurrent",
                    explanation=f"Iout={iout*1000:.0f}mA exceeds max {ldo.max_current_a*1000:.0f}mA.",
                    physics_data={"iout_a": iout, "limit_a": ldo.max_current_a},
                    solution="Use a higher-current regulator or reduce load",
                )
            )

        pd_w = max(0.0, (vin_v - vout_v) * iout + vin_v * max(0.0, ldo.quiescent_current_a))
        tj_c = ldo.ambient_c + pd_w * ldo.r_theta_ja_c_per_w

        if tj_c > ldo.tj_max_c:
            issues.append(
                SimulationIssue(
                    severity="error",
                    component=ldo.name,
                    issue="LDO thermal shutdown risk",
                    explanation=f"Estimated Tj={tj_c:.1f}°C exceeds max {ldo.tj_max_c:.1f}°C (Pd={pd_w:.2f}W).",
                    physics_data={"pd_w": pd_w, "tj_c": tj_c, "tj_max_c": ldo.tj_max_c, "iout_a": iout},
                    solution="Reduce dissipation (lower Vin, lower load), add copper/heatsinking, or choose better package",
                )
            )
        elif tj_c > ldo.tj_max_c * 0.9:
            issues.append(
                SimulationIssue(
                    severity="warning",
                    component=ldo.name,
                    issue="High LDO thermal load",
                    explanation=f"Estimated Tj={tj_c:.1f}°C near max {ldo.tj_max_c:.1f}°C (Pd={pd_w:.2f}W).",
                    physics_data={"pd_w": pd_w, "tj_c": tj_c, "tj_max_c": ldo.tj_max_c, "iout_a": iout},
                    solution="Add copper/heatsinking or reduce load",
                )
            )


    # Power balance report (sanity + debugging aid)
    def _node_v(n: str, g: str = "0") -> float:
        return sol.node_v.get(_n(n), 0.0) - sol.node_v.get(_n(g), 0.0)

    # Upstream/user-defined sources (exclude virtual LDO sources)
    upstream_power_w = 0.0
    for vs in netlist.voltage_sources:
        i = sol.vsource_i.get(vs.name)
        if i is None:
            continue
        v = _node_v(vs.n_plus, vs.n_minus)
        upstream_power_w += -(v * i)

    # Total resistive dissipation (includes traces)
    resistor_loss_w = float(sum(sol.resistor_p.values()))

    # Load power estimates (from modeled loads)
    cc_load_power_w = 0.0
    for load in getattr(netlist, "loads_cc", []) or []:
        v = _node_v(load.node, load.gnd)
        amps = max(0.0, float(load.amps))
        if load.min_v_off is not None and v < float(load.min_v_off):
            amps = 0.0
        cc_load_power_w += max(0.0, v) * amps

    cp_load_power_w = 0.0
    for load in getattr(netlist, "loads_cp", []) or []:
        v = _node_v(load.node, load.gnd)
        watts = max(0.0, float(load.watts))
        if load.min_v_off is not None and v < float(load.min_v_off):
            watts = 0.0
        cp_load_power_w += watts

    # LDO dissipation estimate (already used for thermal checks)
    ldo_dissipation_w = 0.0
    for ldo in netlist.ldos:
        vsrc_name = f"LDO::{ldo.name}"
        iout = abs(sol.vsource_i.get(vsrc_name, 0.0))
        vin_v = _node_v(ldo.vin, ldo.gnd)
        vout_v = _node_v(ldo.vout, ldo.gnd)
        ldo_dissipation_w += max(0.0, (vin_v - vout_v) * iout + vin_v * max(0.0, float(ldo.quiescent_current_a)))

    power_report = {
        "upstream_power_w": upstream_power_w,
        "resistor_loss_w": resistor_loss_w,
        "cc_load_power_w": cc_load_power_w,
        "cp_load_power_w": cp_load_power_w,
        "ldo_dissipation_w": ldo_dissipation_w,
        "estimated_total_consumption_w": resistor_loss_w + cc_load_power_w + cp_load_power_w + ldo_dissipation_w,
        "power_balance_residual_w": upstream_power_w - (resistor_loss_w + cc_load_power_w + cp_load_power_w + ldo_dissipation_w),
    }

    # If the residual is large, something is inconsistent or approximated (warn but don't fail).
    denom = max(1e-9, abs(power_report["upstream_power_w"]))
    if abs(power_report["upstream_power_w"]) > 1e-6 and abs(power_report["power_balance_residual_w"]) / denom > 0.15:
        issues.append(
            SimulationIssue(
                severity="warning",
                component="power_balance",
                issue="Power balance residual",
                explanation=
                f"Upstream power={upstream_power_w:.3f}W, estimated consumption={power_report["estimated_total_consumption_w"]:.3f}W (residual={power_report["power_balance_residual_w"]:.3f}W).",
                physics_data=power_report,
                solution="Check model assumptions (loads, regulator abstraction, missing sources) and netlist correctness",
            )
        )

    results = {
        "solution": sol,
        "converged": op.converged,
        "iterations": op.iters,
        "power_report": power_report,
    }

    return results, issues

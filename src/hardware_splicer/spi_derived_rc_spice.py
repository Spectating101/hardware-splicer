"""Low-authority RC/SPICE cross-check for the Derived Virtual Lab.

The model is intentionally simple: an ideal voltage step drives a lumped source+series
resistance and load capacitance.  It is useful for checking that the analytical RC arithmetic
and an independent ngspice transient agree, but it is NOT an IBIS replacement and cannot earn
manufacturer-model or physical-evidence credit.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .spice_runner import run_ngspice

SCHEMA_VERSION = "hardware_splicer.spi_derived_rc_spice.v1"
SWEEP_SCHEMA_VERSION = "hardware_splicer.spi_derived_rc_sweep.v1"

RAIL_POINTS_V = (1.773, 1.800, 1.827)
SOURCE_RESISTANCE_OHM = 50.0
SERIES_RESISTANCE_POINTS_OHM = (0.0, 22.0, 47.0)
LOAD_CAPACITANCE_POINTS_PF = (10.0, 25.0, 50.0, 100.0)


def _authority() -> dict[str, Any]:
    return {
        "evidence_class": "derived_surrogate_only",
        "vendor_model_campaign_credit_eligible": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def analytical_rc_step(
    *,
    rail_v: float,
    source_resistance_ohm: float,
    series_resistance_ohm: float,
    load_capacitance_pf: float,
) -> dict[str, Any]:
    """Return first-order RC 10-90% timing for explicit surrogate assumptions."""

    values = (rail_v, source_resistance_ohm, series_resistance_ohm, load_capacitance_pf)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) for v in values):
        raise ValueError("RC inputs must be finite numbers")
    if rail_v <= 0 or source_resistance_ohm <= 0 or series_resistance_ohm < 0 or load_capacitance_pf <= 0:
        raise ValueError("RC inputs are outside the supported positive domain")

    total_r = float(source_resistance_ohm) + float(series_resistance_ohm)
    capacitance_f = float(load_capacitance_pf) * 1e-12
    tau_s = total_r * capacitance_f
    t10_s = -tau_s * math.log(0.9)
    t90_s = -tau_s * math.log(0.1)
    rise_s = t90_s - t10_s

    return {
        "schema_version": SCHEMA_VERSION,
        "model": "first_order_lumped_rc",
        "rail_v": float(rail_v),
        "source_resistance_ohm": float(source_resistance_ohm),
        "series_resistance_ohm": float(series_resistance_ohm),
        "total_resistance_ohm": total_r,
        "load_capacitance_pf": float(load_capacitance_pf),
        "tau_ns": tau_s * 1e9,
        "t10_ns": t10_s * 1e9,
        "t90_ns": t90_s * 1e9,
        "rise_10_90_ns": rise_s * 1e9,
        "assumptions": [
            "ideal voltage source step",
            "single lumped source+series resistance",
            "single lumped capacitive load",
            "no package/interconnect inductance",
            "no clamp/ESD nonlinearities",
            "no manufacturer IBIS behavior",
        ],
        **_authority(),
    }


def build_rc_spice_netlist(analytic: dict[str, Any]) -> str:
    rail_v = analytic["rail_v"]
    source_r = analytic["source_resistance_ohm"]
    series_r = analytic["series_resistance_ohm"]
    cap_pf = analytic["load_capacitance_pf"]
    # A 1-ps source transition keeps source slew negligible relative to the RC cases here.
    return f"""* Hardware Splicer derived RC surrogate -- NOT IBIS
VSTEP in 0 PULSE(0 {rail_v:.9g} 0 1p 1p 1u 2u)
RSRC in n1 {source_r:.9g}
RSER n1 out {series_r:.9g}
CLOAD out 0 {cap_pf:.9g}p
.tran 1p 200n
.meas tran T10 WHEN v(out)={rail_v * 0.1:.12g} RISE=1
.meas tran T90 WHEN v(out)={rail_v * 0.9:.12g} RISE=1
.meas tran TR1090 PARAM='T90-T10'
.end
"""


def _parse_measure(stdout: str, name: str) -> float | None:
    match = re.search(rf"(?im)^\s*{re.escape(name)}\s*=\s*([-+0-9.eE]+)", stdout)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def run_rc_spice_crosscheck(
    *,
    rail_v: float = 1.8,
    source_resistance_ohm: float = SOURCE_RESISTANCE_OHM,
    series_resistance_ohm: float = 22.0,
    load_capacitance_pf: float = 25.0,
    relative_tolerance: float = 0.05,
) -> dict[str, Any]:
    """Cross-check the analytical 10-90% rise time with ngspice."""

    analytic = analytical_rc_step(
        rail_v=rail_v,
        source_resistance_ohm=source_resistance_ohm,
        series_resistance_ohm=series_resistance_ohm,
        load_capacitance_pf=load_capacitance_pf,
    )
    spice = run_ngspice(netlist_text=build_rc_spice_netlist(analytic), timeout_s=30)
    if not spice.get("ok"):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "spice_unavailable_or_failed",
            "crosscheck_pass": False,
            "analytical": analytic,
            "spice": spice,
            **_authority(),
        }

    t10_s = _parse_measure(str(spice.get("stdout") or ""), "t10")
    t90_s = _parse_measure(str(spice.get("stdout") or ""), "t90")
    tr_s = _parse_measure(str(spice.get("stdout") or ""), "tr1090")
    if tr_s is None and t10_s is not None and t90_s is not None:
        tr_s = t90_s - t10_s
    if tr_s is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "spice_measurement_missing",
            "crosscheck_pass": False,
            "analytical": analytic,
            "spice": spice,
            **_authority(),
        }

    spice_rise_ns = tr_s * 1e9
    analytical_rise_ns = float(analytic["rise_10_90_ns"])
    relative_error = abs(spice_rise_ns - analytical_rise_ns) / max(analytical_rise_ns, 1e-15)
    passed = relative_error <= float(relative_tolerance)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_rc_spice_crosscheck" if passed else "failed_rc_spice_crosscheck",
        "crosscheck_pass": passed,
        "relative_tolerance": float(relative_tolerance),
        "relative_error": relative_error,
        "analytical_rise_10_90_ns": analytical_rise_ns,
        "spice_rise_10_90_ns": spice_rise_ns,
        "spice_t10_ns": None if t10_s is None else t10_s * 1e9,
        "spice_t90_ns": None if t90_s is None else t90_s * 1e9,
        "analytical": analytic,
        "spice": {
            "returncode": spice.get("returncode"),
            "export_method": spice.get("export_method"),
        },
        **_authority(),
    }


def build_rc_sweep() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rail_v in RAIL_POINTS_V:
        for series_ohm in SERIES_RESISTANCE_POINTS_OHM:
            for load_pf in LOAD_CAPACITANCE_POINTS_PF:
                rows.append(
                    analytical_rc_step(
                        rail_v=rail_v,
                        source_resistance_ohm=SOURCE_RESISTANCE_OHM,
                        series_resistance_ohm=series_ohm,
                        load_capacitance_pf=load_pf,
                    )
                )
    return {
        "schema_version": SWEEP_SCHEMA_VERSION,
        "case_count": len(rows),
        "rows": rows,
        "assumption_grid": {
            "rail_v": list(RAIL_POINTS_V),
            "source_resistance_ohm": SOURCE_RESISTANCE_OHM,
            "series_resistance_ohm": list(SERIES_RESISTANCE_POINTS_OHM),
            "load_capacitance_pf": list(LOAD_CAPACITANCE_POINTS_PF),
        },
        **_authority(),
    }

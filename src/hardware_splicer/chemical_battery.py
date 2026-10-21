"""Bounded idealized lithium-ion discharge using a fixed PyBaMM SPM preset.

The model/parameter set are intentionally fixed: callers cannot submit custom
experiments, arbitrary parameter expressions, model code, files, or procedures.
This is neither a battery pack model nor a battery safety/repair assessment.
"""
from __future__ import annotations

import math
from typing import Any

from .chemical_engineering import EngineUnavailable, NON_AUTHORITY, SCHEMA_VERSION


def battery_discharge_report(
    *, c_rate: float, duration_s: float,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    if not math.isfinite(c_rate) or not (0.1 <= c_rate <= 1.0):
        raise ValueError("c_rate must be finite and between 0.1 and 1")
    if not math.isfinite(duration_s) or not (60 <= duration_s <= 3600):
        raise ValueError("duration_s must be finite and between 60 and 3600")

    try:
        import pybamm
    except (ImportError, OSError) as exc:
        raise EngineUnavailable("PyBaMM not installed; enable the optional battery modelling dependency") from exc

    try:
        model = pybamm.lithium_ion.SPM()
        params = pybamm.ParameterValues("Chen2020")
        nominal_capacity_ah = float(params["Nominal cell capacity [A.h]"])
        current_a = nominal_capacity_ah * c_rate
        params.update({"Current function [A]": current_a})
        simulation = pybamm.Simulation(model, parameter_values=params)
        solution = simulation.solve([0, duration_s])
        time = solution.t
        voltage = solution["Terminal voltage [V]"].entries
    except (ValueError, RuntimeError, KeyError) as exc:
        raise ValueError("Fixed PyBaMM SPM simulation could not complete") from exc

    if len(time) < 2 or len(time) != len(voltage):
        raise ValueError("PyBaMM returned incomplete time/voltage vectors")
    samples: list[dict[str, float]] = []
    sample_indices = sorted({round(index * (len(time) - 1) / 10) for index in range(11)})
    for index in sample_indices:
        ts = float(time[index])
        volts = float(voltage[index])
        if not math.isfinite(ts) or not math.isfinite(volts):
            raise ValueError("PyBaMM produced a nonfinite output")
        samples.append({"time_s": ts, "terminal_voltage_v": volts})

    end_time = float(time[-1])
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "pybamm",
        "engine_version": pybamm.__version__,
        "model": "lithium_ion.SPM",
        "parameter_set": "Chen2020",
        "nominal_capacity_ah": nominal_capacity_ah,
        "current_a": current_a,
        "c_rate": c_rate,
        "requested_duration_s": duration_s,
        "simulated_duration_s": end_time,
        "terminated_early": end_time < duration_s - 1e-5,
        "termination_reason": str(solution.termination),
        "samples": samples,
        "source_refs": list(source_refs or []),
        "limitations": [
            "Uncalibrated reference single-cell model with fixed built-in parameter set.",
            "No cell identity, pack/BMS, abuse, fault, swelling, thermal-runaway or repair safety model.",
            "Voltage prediction cannot authorize electrical connection or battery handling.",
        ],
        **NON_AUTHORITY,
    }

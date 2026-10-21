"""Controlled Cantera kinetic reference-case solver, with physical authority denied.

A fixed, built-in GRI30 mixture and isothermal ideal-gas constant-pressure
reactor are used only for numerical verification. No mechanism files, arbitrary
mixtures, vessel geometry, heating steps or physical procedures are accepted.
"""
from __future__ import annotations

import math
from typing import Any

from .chemical_engineering import EngineUnavailable, NON_AUTHORITY, SCHEMA_VERSION

_MIXTURE = {"CH4": 0.03, "O2": 0.21, "N2": 0.76}
_TRACKED = ("CH4", "O2", "N2", "CO2", "H2O", "CO", "OH")
_ELEMENTS = ("C", "H", "O", "N")


def kinetic_reference_report(
    *, temperature_k: float, pressure_pa: float, duration_s: float,
    sample_count: int = 6,
) -> dict[str, Any]:
    if not math.isfinite(temperature_k) or not 850 <= temperature_k <= 1500:
        raise ValueError("Reference temperature outside 850-1500 K")
    if not math.isfinite(pressure_pa) or not 80000 <= pressure_pa <= 250000:
        raise ValueError("Reference pressure outside 80-250 kPa")
    if not math.isfinite(duration_s) or not 0.0001 <= duration_s <= 0.05:
        raise ValueError("Reference duration outside 0.1-50 milliseconds")
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or not 2 <= sample_count <= 15:
        raise ValueError("Sample count outside 2-15")
    try:
        import cantera as ct
    except (ImportError, OSError) as exc:
        raise EngineUnavailable("Cantera is not installed; enable the chemical-process extra") from exc
    try:
        gas = ct.Solution("gri30.yaml")
        gas.TPX = temperature_k, pressure_pa, _MIXTURE
        initial_elements = {elem: float(gas.elemental_mass_fraction(elem)) for elem in _ELEMENTS}
        reactor = ct.IdealGasConstPressureReactor(gas, energy="off")
        net = ct.ReactorNet([reactor])
        net.max_steps = 6000
        net.max_time_step = min(0.005, duration_s)
        rows: list[dict[str, Any]] = []
        for i in range(sample_count):
            time_s = duration_s * i / (sample_count - 1)
            if i:
                net.advance(time_s)
            solution = reactor.thermo
            raw = {spec: float(solution[spec].X[0]) for spec in _TRACKED}
            if any(not math.isfinite(v) or v < -1e-9 or v > 1 + 1e-9 for v in raw.values()):
                raise ValueError("Kinetic solver returned invalid mole fractions")
            rows.append({
                "time_s": float(time_s),
                "tracked_mole_fractions": {spec: max(0.0, v) for spec, v in raw.items()},
                "temperature_k": float(solution.T),
                "pressure_pa": float(solution.P),
            })
        final_elements = {
            elem: float(reactor.thermo.elemental_mass_fraction(elem))
            for elem in _ELEMENTS
        }
        max_element_mass_residual = max(
            abs(initial_elements[elem] - final_elements[elem]) for elem in _ELEMENTS
        )
        if not math.isfinite(max_element_mass_residual) or max_element_mass_residual > 1e-6:
            raise ValueError("Kinetic solver failed element-mass closure")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Bounded Cantera reference kinetics model failed") from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "cantera.IdealGasConstPressureReactor",
        "engine_version": ct.__version__,
        "mechanism": "gri30.yaml",
        "initial_composition_mole_fractions": dict(_MIXTURE),
        "operating_model": "isothermal_constant_pressure_reference_reactor",
        "input_temperature_k": temperature_k,
        "input_pressure_pa": pressure_pa,
        "duration_s": duration_s,
        "trajectory": rows,
        "tracked_species": list(_TRACKED),
        "initial_element_mass_fractions": initial_elements,
        "final_element_mass_fractions": final_elements,
        "max_element_mass_balance_residual": max_element_mass_residual,
        "limitations": [
            "Fixed, artificial numerical reference mixture, not a proposed physical experiment.",
            "The isothermal constant-pressure assumption excludes actual reactor heat release and equipment.",
            "GRI30 mechanism is a modelling hypothesis, not universal experimental truth.",
            "No physical vessel, geometry, temperature control, flowsheet, hazard, or operation approval.",
        ],
        **NON_AUTHORITY,
    }

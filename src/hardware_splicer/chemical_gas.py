"""Bounded Cantera gas-state and equilibrium simulation on bundled air.yaml.

This is a computational capability, not a model of an apparatus, process safety
assessment or permission to heat, pressurize, mix, vent, or operate anything.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from .chemical_engineering import EngineUnavailable, NON_AUTHORITY, SCHEMA_VERSION


_ALLOWED_INPUT_SPECIES = frozenset({"N2", "O2", "AR"})


def _composition(fractions: Mapping[str, float]) -> dict[str, float]:
    if not fractions or len(fractions) > len(_ALLOWED_INPUT_SPECIES):
        raise ValueError("Provide one to three allowed gas species")
    composition: dict[str, float] = {}
    for species, raw in fractions.items():
        if species not in _ALLOWED_INPUT_SPECIES:
            raise ValueError("Only N2, O2 and AR are accepted for this bounded air model")
        value = float(raw)
        if not math.isfinite(value) or value < 0 or value > 1:
            raise ValueError("Mole fractions must be finite and between 0 and 1")
        composition[species] = value
    if not math.isclose(sum(composition.values()), 1.0, rel_tol=0, abs_tol=1e-6):
        raise ValueError("Gas mole fractions must sum to 1")
    return composition


def _state(solution: Any) -> dict[str, Any]:
    return {
        "temperature_k": float(solution.T),
        "pressure_pa": float(solution.P),
        "density_kg_m3": float(solution.density),
        "specific_heat_cp_j_kg_k": float(solution.cp_mass),
        "specific_heat_cv_j_kg_k": float(solution.cv_mass),
        "enthalpy_j_kg": float(solution.enthalpy_mass),
        "entropy_j_kg_k": float(solution.entropy_mass),
        "viscosity_pa_s": float(solution.viscosity),
        "thermal_conductivity_w_m_k": float(solution.thermal_conductivity),
        "mean_molecular_weight_kg_kmol": float(solution.mean_molecular_weight),
        "species_mole_fractions": {
            name: float(value) for name, value in zip(solution.species_names, solution.X)
            if value > 1e-15
        },
    }


def gas_state_report(
    *, temperature_k: float, pressure_pa: float, mole_fractions: Mapping[str, float],
    equilibrium: bool = False, source_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Compute air.yaml thermodynamics with a fixed bundled model and bounded inputs."""
    if not math.isfinite(temperature_k) or not 250 <= temperature_k <= 1200:
        raise ValueError("Temperature must be finite and 250-1200 K")
    if not math.isfinite(pressure_pa) or not 5e4 <= pressure_pa <= 5e6:
        raise ValueError("Pressure must be finite and 50 kPa-5 MPa")
    mixture = _composition(mole_fractions)
    try:
        import cantera as ct
    except (ImportError, OSError) as exc:
        raise EngineUnavailable("Cantera not installed; enable the optional chemical-process dependency") from exc
    gas = ct.Solution("air.yaml")
    gas.TPX = temperature_k, pressure_pa, mixture
    initial = _state(gas)
    final = None
    if equilibrium:
        try:
            gas.equilibrate("TP", solver="auto", max_steps=300, rtol=1e-9)
        except ct.CanteraError as exc:
            raise ValueError("Cantera TP-equilibrium did not converge") from exc
        final = _state(gas)
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "cantera",
        "engine_version": ct.__version__,
        "model": "air.yaml",
        "mode": "equilibrium_tp" if equilibrium else "gas_state",
        "input": {
            "temperature_k": temperature_k, "pressure_pa": pressure_pa,
            "mole_fractions": mixture,
        },
        "initial_state": initial,
        "equilibrium_state": final,
        "source_refs": list(source_refs or []),
        "limitations": [
            "Fixed bundled ideal-gas air model; only N2/O2/AR inlet fractions.",
            "Equilibrium is a limiting state, not a reaction rate or reactor prediction.",
            "No vessel, phase-boundary, thermal-management or exposure safety validation.",
            "An air simulation does not certify process or material compatibility.",
        ],
        **NON_AUTHORITY,
    }

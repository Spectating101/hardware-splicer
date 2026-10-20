"""Auditable reaction thermodynamic quantities from fixed Cantera GRI30 steps.

Selection is by a fixed reaction identifier and exact bundled equation. No
arbitrary mechanisms, extrapolated experimental evidence or physical process
authority are provided.
"""
from __future__ import annotations

import math
from typing import Any

from .chemical_engineering import EngineUnavailable, NON_AUTHORITY, SCHEMA_VERSION

_REFERENCE_REACTIONS = {
    "hydrogen_oxygen_exchange": "H2 + O <=> H + OH",
    "carbon_oxygen_exchange": "CO + OH <=> CO2 + H",
}


def reaction_reference_thermodynamics(
    *, reaction_id: str, temperature_k: float, pressure_pa: float,
) -> dict[str, Any]:
    if reaction_id not in _REFERENCE_REACTIONS:
        raise ValueError("Unknown restricted reference reaction")
    if not math.isfinite(temperature_k) or not 350 <= temperature_k <= 2200:
        raise ValueError("Reference temperature must be 350-2200 K")
    if not math.isfinite(pressure_pa) or not 80000 <= pressure_pa <= 250000:
        raise ValueError("Reference pressure must be 80-250 kPa")
    try:
        import cantera as ct
    except (ImportError, OSError) as exc:
        raise EngineUnavailable("Cantera unavailable; install chemical-process dependency") from exc
    try:
        gas = ct.Solution("gri30.yaml")
        gas.TPX = temperature_k, pressure_pa, {"N2": 1.0}
        expected = _REFERENCE_REACTIONS[reaction_id]
        hits = [i for i, name in enumerate(gas.reaction_equations()) if name == expected]
        if len(hits) != 1:
            raise ValueError("Pinned reaction definition missing or ambiguous in supplied GRI30 version")
        index = hits[0]
        chemical_reaction = gas.reaction(index)
        reactants = dict(chemical_reaction.reactants)
        products = dict(chemical_reaction.products)
        imbalance: dict[str, float] = {}
        for element in gas.element_names:
            difference = sum(float(count) * gas.n_atoms(spec, element)
                             for spec, count in products.items()) - sum(
                                 float(count) * gas.n_atoms(spec, element)
                                 for spec, count in reactants.items()
                             )
            if abs(difference) > 1e-10:
                imbalance[element] = difference
        if imbalance:
            raise ValueError("Reference reaction failed independent elemental conservation")
        # Cantera uses J/kmol for reaction enthalpies/Gibbs, J/kmol/K
        # for entropy, R=J/kmol/K. Convert explicitly.
        dh = float(gas.delta_standard_enthalpy[index]) / 1e6
        dg = float(gas.delta_standard_gibbs[index]) / 1e6
        ds = float(gas.delta_standard_entropy[index]) / 1000.0
        k = float(gas.equilibrium_constants[index])
        if not (math.isfinite(dh) and math.isfinite(dg) and math.isfinite(ds)
                and math.isfinite(k) and k > 0):
            raise ValueError("Nonfinite reaction thermodynamics")
        gibbs_identity_error = abs(dg - (dh - temperature_k * ds / 1000.0))
        if gibbs_identity_error > 1e-5:
            raise ValueError("Thermodynamic identity does not close")
        # All selected reactions have 2 mol gas on each side, Δν=0, so
        # dimensionless K can be compared directly to exp(-ΔG/(RT)).
        delta_nu = sum(products.values()) - sum(reactants.values())
        if abs(delta_nu) > 1e-10:
            raise ValueError("Reference reaction Δν not zero")
        reference_log_k = -dg * 1e6 / (ct.gas_constant * temperature_k)
        log_k_error = abs(math.log(k) - reference_log_k)
        if log_k_error > 1e-6:
            raise ValueError("Computed equilibrium constant disagrees with Gibbs energy")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Bounded thermodynamic calculation failed") from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "cantera.GRI30.standard_reaction_thermodynamics",
        "engine_version": ct.__version__,
        "reaction_id": reaction_id,
        "equation": expected,
        "reactants": reactants,
        "products": products,
        "elemental_balance_passed": True,
        "temperature_k": temperature_k,
        "pressure_pa": pressure_pa,
        "delta_h_kj_per_mol_reaction": dh,
        "delta_g_kj_per_mol_reaction": dg,
        "delta_s_j_per_mol_reaction_k": ds,
        "equilibrium_constant_dimensionless": k,
        "delta_nu_gas": delta_nu,
        "thermodynamic_identity_error_kj_per_mol": gibbs_identity_error,
        "log_equilibrium_constant_identity_error": log_k_error,
        "limitations": [
            "Fixed gas-phase mechanism and standard-state quantities; no real process composition or rates inferred.",
            "Neither an equilibrium constant nor reaction enthalpy proves a physical pathway or safety.",
            "No measurement or independent reference evidence; values are computational.",
        ],
        **NON_AUTHORITY,
    }

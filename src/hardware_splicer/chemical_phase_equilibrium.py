"""Restricted, auditable vapor-liquid flash analysis with thermo/Peng-Robinson.

Reference fluid systems only. Results are thermodynamic model calculations,
not a complete separations process, vessel or handling/safety recommendation.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from .chemical_engineering import EngineUnavailable, NON_AUTHORITY, SCHEMA_VERSION

_SYSTEMS = {
    "water": {
        "ids": ("water",), "t": (290.0, 450.0), "p": (50000.0, 500000.0),
        "description": "Pure water reference fluid; not high-pressure steam design",
    },
    "light_gas_reference": {
        "ids": ("methane", "ethane", "nitrogen"),
        "t": (90.0, 210.0), "p": (50000.0, 5000000.0),
        "description": "Reference light-gas mixture; fixed three species",
    },
}


def reference_systems() -> list[dict[str, Any]]:
    return [
        {"system_id": sid, "species": list(spec["ids"]),
         "temperature_bounds_k": list(spec["t"]),
         "pressure_bounds_pa": list(spec["p"]),
         "description": spec["description"]}
        for sid, spec in _SYSTEMS.items()
    ]


def phase_flash_report(
    *, system_id: str, temperature_k: float, pressure_pa: float,
    mole_fractions: Mapping[str, float],
) -> dict[str, Any]:
    if system_id not in _SYSTEMS:
        raise ValueError("Unsupported reference fluid system")
    specs = _SYSTEMS[system_id]
    t0, t1 = specs["t"]
    p0, p1 = specs["p"]
    if not math.isfinite(temperature_k) or not t0 <= temperature_k <= t1:
        raise ValueError("Temperature outside validated request envelope")
    if not math.isfinite(pressure_pa) or not p0 <= pressure_pa <= p1:
        raise ValueError("Pressure outside validated request envelope")
    if not mole_fractions or set(mole_fractions) != set(specs["ids"]):
        raise ValueError("Mole fraction map must have every and only supported species")
    zs = []
    for species in specs["ids"]:
        value = float(mole_fractions[species])
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Nonfinite or negative mixture mole fraction")
        zs.append(value)
    if not math.isclose(sum(zs), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Mole fractions must sum to 1")
    try:
        import thermo
        from thermo import (
            ChemicalConstantsPackage, PRMIX, CEOSGas, CEOSLiquid, FlashVL, FlashPureVLS,
        )
    except (ImportError, OSError) as exc:
        raise EngineUnavailable("thermo flash engine unavailable; install chemical extra") from exc
    try:
        constants, correlations = ChemicalConstantsPackage.from_IDs(list(specs["ids"]))
        eos_kwargs = {
            "Tcs": constants.Tcs, "Pcs": constants.Pcs, "omegas": constants.omegas,
        }
        interaction_source = "zero binary interaction parameters (reference approximation)"
        if system_id == "light_gas_reference":
            # Available in the thermo/ChemSep sample interaction data.
            from thermo.interaction_parameters import IPDB
            eos_kwargs["kijs"] = IPDB.get_ip_asymmetric_matrix(
                "ChemSep PR", constants.CASs, "kij",
            )
            interaction_source = "ChemSep PR sample binary interaction parameters"
        gas = CEOSGas(
            PRMIX, HeatCapacityGases=correlations.HeatCapacityGases,
            eos_kwargs=eos_kwargs,
        )
        liquid = CEOSLiquid(
            PRMIX, HeatCapacityGases=correlations.HeatCapacityGases,
            eos_kwargs=eos_kwargs,
        )
        if system_id == "water":
            flasher = FlashPureVLS(
                constants, correlations, gas=gas, liquids=[liquid], solids=[],
            )
            result = flasher.flash(T=temperature_k, P=pressure_pa)
        else:
            flasher = FlashVL(constants, correlations, gas=gas, liquid=liquid)
            result = flasher.flash(T=temperature_k, P=pressure_pa, zs=zs)
        vf = float(result.VF)
        if not math.isfinite(vf) or not -1e-10 <= vf <= 1 + 1e-10:
            raise ValueError("Flash solver returned invalid vapor fraction")
        vf = min(max(vf, 0.0), 1.0)
        liquid_fraction = 1.0 - vf
        vapor = None
        liquid_result = None
        if vf > 1e-12:
            vap = result.gas
            if vap is None:
                raise ValueError("Flash vapor phase missing")
            vapor = {species: float(value)
                     for species, value in zip(specs["ids"], vap.zs)}
        if liquid_fraction > 1e-12:
            liq = result.liquid0
            if liq is None:
                raise ValueError("Flash liquid phase missing")
            liquid_result = {species: float(value)
                             for species, value in zip(specs["ids"], liq.zs)}
        recreated = {}
        for species in specs["ids"]:
            v = vapor[species] if vapor is not None else 0.0
            l = liquid_result[species] if liquid_result is not None else 0.0
            recreated[species] = vf * v + liquid_fraction * l
        closure = max(abs(recreated[s] - mole_fractions[s]) for s in specs["ids"])
        if closure > 1e-6:
            raise ValueError("Flash phase compositions do not close material balance")
    except ValueError:
        raise
    except Exception as exc:
        # No fallback invented phase conditions or fabricated equilibrium.
        raise ValueError("Bounded flash calculation failed to converge") from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "thermo.PRMIX.flash",
        "engine_version": getattr(thermo, "__version__", "unreported"),
        "system_id": system_id,
        "species": list(specs["ids"]),
        "temperature_k": temperature_k,
        "pressure_pa": pressure_pa,
        "feed_mole_fractions": dict(zip(specs["ids"], zs)),
        "vapor_fraction_molar": vf,
        "liquid_fraction_molar": liquid_fraction,
        "vapor_mole_fractions": vapor,
        "liquid_mole_fractions": liquid_result,
        "reconstructed_feed_mole_fractions": recreated,
        "max_material_balance_residual": closure,
        "model": "Peng-Robinson cubic EOS",
        "interaction_source": interaction_source,
        "limitations": [
            "Restricted reference equilibrium: no real-mixture design accreditation.",
            "Vapor-liquid two-phase only; no solids, multi-liquid splits or reactive phase equilibrium.",
            "Results depend on EOS, correlations and binary interaction approximations.",
            "No process flowsheet, column design, materials safety or physical equipment operation authority.",
        ],
        **NON_AUTHORITY,
    }

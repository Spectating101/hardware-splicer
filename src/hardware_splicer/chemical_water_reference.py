"""Water/steam reference properties and EOS disagreement detection.

CoolProp supplies an independently implemented equation-of-state backend for
water, cross-checking the generic thermo Peng-Robinson flash. Disagreement
becomes a blocker, NEVER a quiet average or automatic safety approval.
"""
from __future__ import annotations

import math
from typing import Any

from .chemical_engineering import EngineUnavailable, NON_AUTHORITY, SCHEMA_VERSION
from .chemical_phase_equilibrium import phase_flash_report


def _validate_water_inputs(temperature_k: float, pressure_pa: float) -> None:
    if not math.isfinite(temperature_k) or not 275 <= temperature_k <= 450:
        raise ValueError("Reference water temperature must be 275-450 K")
    if not math.isfinite(pressure_pa) or not 50000 <= pressure_pa <= 500000:
        raise ValueError("Reference water pressure must be 50-500 kPa")


def coolprop_water_report(*, temperature_k: float, pressure_pa: float) -> dict[str, Any]:
    _validate_water_inputs(temperature_k, pressure_pa)
    try:
        import CoolProp
        from CoolProp import CoolProp as cp
    except (ImportError, OSError) as exc:
        raise EngineUnavailable("CoolProp missing; install the optional chemical-fluids extra") from exc
    try:
        saturation_temperature = float(cp.PropsSI("T", "P", pressure_pa, "Q", 0, "Water"))
        phase = str(cp.PhaseSI("T", temperature_k, "P", pressure_pa, "Water"))
        rho = float(cp.PropsSI("D", "T", temperature_k, "P", pressure_pa, "Water"))
        cp_mass = float(cp.PropsSI("C", "T", temperature_k, "P", pressure_pa, "Water"))
        viscosity = float(cp.PropsSI("V", "T", temperature_k, "P", pressure_pa, "Water"))
        conductivity = float(cp.PropsSI("L", "T", temperature_k, "P", pressure_pa, "Water"))
        if not all(math.isfinite(v) and v > 0
                   for v in [saturation_temperature, rho, cp_mass, viscosity, conductivity]):
            raise ValueError("CoolProp produced nonphysical reference state properties")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("CoolProp reference water state unavailable") from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "CoolProp.HEOS.Water",
        "engine_version": CoolProp.__version__,
        "fluid": "Water",
        "temperature_k": temperature_k,
        "pressure_pa": pressure_pa,
        "saturation_temperature_at_pressure_k": saturation_temperature,
        "phase": phase,
        "distance_to_saturation_temperature_k": temperature_k - saturation_temperature,
        "density_kg_m3": rho,
        "specific_heat_cp_j_kg_k": cp_mass,
        "viscosity_pa_s": viscosity,
        "thermal_conductivity_w_m_k": conductivity,
        "limitations": [
            "Water-only reference property calculation, not fluid/equipment approval.",
            "Exact saturation points can be numerically ill-conditioned; do not extrapolate design decisions.",
            "No fluid contamination, corrosion, pressure-vessel or physical operation safety assessment.",
        ],
        **NON_AUTHORITY,
    }


def water_model_crosscheck(*, temperature_k: float, pressure_pa: float) -> dict[str, Any]:
    _validate_water_inputs(temperature_k, pressure_pa)
    reference = coolprop_water_report(temperature_k=temperature_k, pressure_pa=pressure_pa)
    generic = phase_flash_report(
        system_id="water", temperature_k=temperature_k,
        pressure_pa=pressure_pa, mole_fractions={"water": 1.0},
    )
    observed_phase = reference["phase"]
    coolprop_phase = (
        "vapor" if observed_phase in {"gas", "supercritical_gas"}
        else "liquid" if observed_phase == "liquid" else "ambiguous"
    )
    pr_vf = generic["vapor_fraction_molar"]
    pr_phase = "vapor" if pr_vf > 0.99 else "liquid" if pr_vf < 0.01 else "two_phase"
    disagreement = coolprop_phase == "ambiguous" or pr_phase != coolprop_phase
    proximity_k = abs(reference["distance_to_saturation_temperature_k"])
    # Even the specialist EOS is not a substitute for independently verified
    # measured conditions close to saturation.
    close_to_boundary = proximity_k < 2.0
    blockers = []
    if disagreement:
        blockers.append("reference_models_disagree_on_phase")
    if close_to_boundary:
        blockers.append("near_water_saturation_boundary")
    status = "model_conflict_or_boundary" if blockers else "models_agree_but_unverified"
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "HS.water.multimodel_crosscheck",
        "temperature_k": temperature_k,
        "pressure_pa": pressure_pa,
        "coolprop_reference": reference,
        "peng_robinson_reference": {
            "engine": generic["engine"],
            "engine_version": generic["engine_version"],
            "vapor_fraction_molar": pr_vf,
            "phase": pr_phase,
            "material_balance_residual": generic["max_material_balance_residual"],
        },
        "phase_agreement": not disagreement,
        "near_saturation_boundary": close_to_boundary,
        "blockers": blockers,
        "result": status,
        "design_decision_authorized": False,
        "limitations": [
            "Compares two numerical property implementations, not experimental truth.",
            "Model agreement does not validate the industrial design or physical operation.",
            "Generic cubic EOS can misclassify water phase near its saturation boundary.",
        ],
        **NON_AUTHORITY,
    }

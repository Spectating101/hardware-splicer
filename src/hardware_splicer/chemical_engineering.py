"""Bounded chemical-engineering calculations with explicit evidence authority.

Third-party solvers are opt-in and imported only when their operation is called.
Computational descriptions are not toxicology, compatibility, safety or release proof.
"""
from __future__ import annotations

import importlib.util
import math
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.chemical_engineering.v0"
ENGINES = (
    ("rdkit", "rdkit", "molecular_structure"),
    ("thermo", "thermo", "thermophysical_properties"),
    ("chemicals", "chemicals", "chemical_reference_properties"),
    ("cantera", "cantera", "kinetics_and_equilibrium"),
    ("pybamm", "pybamm", "battery_electrochemistry"),
    ("pymatgen", "pymatgen", "solid_materials"),
)
NON_AUTHORITY = {
    "source_authority": "computed_or_declared_only",
    "experimentally_validated": False,
    "chemical_safety_verified": False,
    "material_compatibility_verified": False,
    "physical_action_authorized": False,
    "fabrication_authorized": False,
    "release_authorized": False,
}


class EngineUnavailable(ValueError):
    """Optional scientific engine not installed or not importable."""


def engines_report() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "engines": [
            {"id": name, "package": package, "purpose": purpose,
             "installed": importlib.util.find_spec(package) is not None,
             "adapter_implemented": name in {"rdkit", "thermo", "cantera", "pybamm", "pymatgen"}}
            for name, package, purpose in ENGINES
        ],
        "interpretation": "Presence is not validation or project evidence.",
        **NON_AUTHORITY,
    }


def molecule_report(smiles: str, *, source_refs: list[str] | None = None) -> dict[str, Any]:
    if not smiles.strip() or len(smiles) > 512:
        raise ValueError("SMILES must contain 1-512 characters")
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
    except (ImportError, OSError) as exc:
        raise EngineUnavailable("RDKit unavailable; install the optional chemical dependencies") from exc

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise ValueError("Invalid or unsupported molecular representation")
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "rdkit",
        "input_smiles": smiles,
        "canonical_smiles": Chem.MolToSmiles(molecule),
        "molecular_formula": rdMolDescriptors.CalcMolFormula(molecule),
        "molecular_weight_g_mol": round(Descriptors.MolWt(molecule), 6),
        "atom_count": molecule.GetNumAtoms(),
        "formal_charge": Chem.GetFormalCharge(molecule),
        "source_refs": list(source_refs or []),
        "limitations": [
            "Structure and descriptors do not establish compound identity, purity or safety.",
            "SMILES does not determine physical properties or reaction feasibility.",
        ],
        **NON_AUTHORITY,
    }


def _finite_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def property_report(
    chemical_id: str, temperature_k: float, pressure_pa: float, *,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Estimate properties from thermo's property package; never a safety calculation."""
    if not chemical_id.strip() or len(chemical_id) > 128:
        raise ValueError("chemical_id must contain 1-128 characters")
    if not (math.isfinite(temperature_k) and 100 <= temperature_k <= 2000):
        raise ValueError("temperature_k outside supported request bounds")
    if not (math.isfinite(pressure_pa) and 1000 <= pressure_pa <= 1e8):
        raise ValueError("pressure_pa outside supported request bounds")
    try:
        from thermo import Chemical
    except (ImportError, OSError) as exc:
        raise EngineUnavailable("thermo unavailable; install the optional chemical dependencies") from exc
    try:
        chemical = Chemical(chemical_id, T=temperature_k, P=pressure_pa)
        properties = {
            "molecular_weight_g_mol": _finite_number(chemical.MW),
            "density_kg_m3": _finite_number(chemical.rho),
            "specific_heat_capacity_j_kg_k": _finite_number(chemical.Cp),
            "dynamic_viscosity_pa_s": _finite_number(chemical.mu),
            "thermal_conductivity_w_m_k": _finite_number(chemical.k),
        }
    except (ValueError, KeyError, TypeError, AttributeError, LookupError) as exc:
        raise ValueError("Chemical identifier or property model could not be resolved") from exc
    if not any(value is not None for value in properties.values()):
        raise ValueError("No supported property estimates available")
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "thermo",
        "chemical_id_query": chemical_id,
        "resolved_identifier": str(chemical.CAS or chemical_id),
        "temperature_k": temperature_k,
        "pressure_pa": pressure_pa,
        "phase": str(chemical.phase or "unknown"),
        "properties": properties,
        "source_refs": list(source_refs or []),
        "limitations": [
            "Model/correlation values may not cover this substance or state reliably.",
            "Not qualified for pressure-vessel design, material selection or chemical safety.",
        ],
        **NON_AUTHORITY,
    }


def mass_balance_report(
    streams: list[Mapping[str, Any]], *, reaction_present: bool = False,
    absolute_tolerance_kg_h: float = 1e-6, relative_tolerance: float = 1e-4,
) -> dict[str, Any]:
    """Check declared mass flows; this is not reaction, phase or process simulation."""
    if len(streams) < 2 or len(streams) > 100:
        raise ValueError("Supply 2-100 inlet/outlet streams")
    if not (math.isfinite(absolute_tolerance_kg_h) and 0 <= absolute_tolerance_kg_h <= 1):
        raise ValueError("Invalid absolute tolerance")
    if not (math.isfinite(relative_tolerance) and 0 <= relative_tolerance <= 0.1):
        raise ValueError("Invalid relative tolerance")

    flows = {"inlet": 0.0, "outlet": 0.0}
    component_totals: dict[str, dict[str, float]] = {"inlet": {}, "outlet": {}}
    has_all_components = True
    seen: set[str] = set()
    for stream in streams:
        name = str(stream["stream_id"])
        side = str(stream["direction"])
        mass = float(stream["mass_flow_kg_h"])
        if not name or name in seen:
            raise ValueError("Stream IDs must be nonempty and unique")
        seen.add(name)
        if side not in flows or not math.isfinite(mass) or mass < 0:
            raise ValueError("Invalid stream direction or mass flow")
        flows[side] += mass
        components = stream.get("components_kg_h")
        if components is None:
            has_all_components = False
            continue
        total = 0.0
        for component, raw in components.items():
            component_id = str(component).strip()
            amount = float(raw)
            if not component_id or not math.isfinite(amount) or amount < 0:
                raise ValueError("Invalid component mass flow")
            total += amount
            side_totals = component_totals[side]
            side_totals[component_id] = side_totals.get(component_id, 0.0) + amount
        if not math.isclose(total, mass, rel_tol=relative_tolerance, abs_tol=absolute_tolerance_kg_h):
            raise ValueError(f"Component totals do not equal declared stream mass for {name}")
    if flows["inlet"] <= 0 or flows["outlet"] <= 0:
        raise ValueError("At least one positive inlet and outlet are required")
    residual = flows["inlet"] - flows["outlet"]
    limit = absolute_tolerance_kg_h + relative_tolerance * max(flows.values())
    overall_pass = abs(residual) <= limit
    component_checks = []
    if has_all_components and not reaction_present:
        for component_id in sorted(set(component_totals["inlet"]) | set(component_totals["outlet"])):
            a = component_totals["inlet"].get(component_id, 0.0)
            b = component_totals["outlet"].get(component_id, 0.0)
            tolerance = absolute_tolerance_kg_h + relative_tolerance * max(a, b)
            component_checks.append({
                "component_id": component_id,
                "inlet_kg_h": a,
                "outlet_kg_h": b,
                "residual_kg_h": a - b,
                "balanced": abs(a - b) <= tolerance,
            })
    component_pass = all(row["balanced"] for row in component_checks)
    passed = overall_pass and component_pass
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "hs-deterministic-mass-balance",
        "overall": {
            "inlet_kg_h": flows["inlet"], "outlet_kg_h": flows["outlet"],
            "residual_kg_h": residual, "tolerance_kg_h": limit,
            "balanced": overall_pass,
        },
        "component_checks": component_checks,
        "component_balance_applicable": has_all_components and not reaction_present,
        "result": "consistent_declared_flows" if passed else "inconsistent_declared_flows",
        "limitations": [
            "Inputs are user-declared; this is not measured evidence.",
            "No reaction stoichiometry, energy, phase, heat transfer, pressure drop or safety is modeled.",
        ],
        **NON_AUTHORITY,
    }

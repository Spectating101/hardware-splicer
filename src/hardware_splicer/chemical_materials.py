"""Source-unverified elemental composition analysis for engineering material candidates."""
from __future__ import annotations

import math
from typing import Any

from .chemical_engineering import EngineUnavailable, NON_AUTHORITY, SCHEMA_VERSION


def solid_composition_report(
    formula: str, *, source_refs: list[str] | None = None,
) -> dict[str, Any]:
    if not formula or len(formula) > 128 or not formula.strip():
        raise ValueError("Formula must contain 1-128 characters")
    try:
        from pymatgen.core import Composition, Element
    except (ImportError, OSError) as exc:
        raise EngineUnavailable(
            "pymatgen composition engine unavailable; install the optional chemical-materials dependency"
        ) from exc
    try:
        composition = Composition(formula)
        atoms = float(composition.num_atoms)
        elements = composition.get_el_amt_dict()
        if not 0 < atoms <= 1000 or len(elements) > 40:
            raise ValueError("Formula exceeds supported composition bounds")
        weight = float(composition.weight)
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("Molar mass was not finite")
        atomic_fractions = {
            symbol: float(composition.get_atomic_fraction(Element(symbol)))
            for symbol in sorted(elements)
        }
        mass_fractions = {
            symbol: float(composition.get_wt_fraction(Element(symbol)))
            for symbol in sorted(elements)
        }
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid or unsupported elemental composition") from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "pymatgen.core.Composition",
        "input_formula": formula,
        "reduced_formula": composition.reduced_formula,
        "formula_unit_molar_mass_g_mol": weight,
        "formula_unit_atom_count": atoms,
        "atomic_fractions": atomic_fractions,
        "mass_fractions": mass_fractions,
        "source_refs": list(source_refs or []),
        "limitations": [
            "Composition only: no phase, crystal structure, alloy processing, polymer microstructure, or materials testing.",
            "Elemental composition does not determine mechanical, electrical, corrosion or thermal performance.",
            "Values are not authenticated against any particular specimen or supplier.",
        ],
        **NON_AUTHORITY,
    }

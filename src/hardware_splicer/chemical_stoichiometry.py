"""Strict neutral-formula reaction inventory and elemental conservation checks.

A reaction is a declarative species inventory, NOT a procedure, kinetic model,
reaction feasibility assessment, or a statement that products will form.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from decimal import Decimal
import math
import re
from typing import Any, Mapping

from .chemical_engineering import NON_AUTHORITY, SCHEMA_VERSION

# Neutral-element molecular-weight references, in grams per mole, deliberately
# limited to common chemistry elements. Unrecognized elements fail closed.
# These are nominal atomic weights, not isotope-specific accurate-mass values.
_ATOMIC_WEIGHTS = {
    "H":1.008, "He":4.002602, "Li":6.94, "Be":9.0121831, "B":10.81,
    "C":12.011, "N":14.007, "O":15.999, "F":18.998403163, "Ne":20.1797,
    "Na":22.98976928, "Mg":24.305, "Al":26.9815385, "Si":28.085,
    "P":30.973761998, "S":32.06, "Cl":35.45, "Ar":39.948, "K":39.0983,
    "Ca":40.078, "Cr":51.9961, "Mn":54.938044, "Fe":55.845,
    "Co":58.933194, "Ni":58.6934, "Cu":63.546, "Zn":65.38,
    "Br":79.904, "Ag":107.8682, "I":126.90447, "Ba":137.327,
    "W":183.84, "Pt":195.084, "Au":196.966569, "Pb":207.2,
}
_FORMULA_LENGTH_LIMIT = 96
_MAX_ATOMS = 100000


def parse_neutral_formula(formula: str) -> dict[str, int]:
    """Parse formulas with nested parentheses and positive integer subscripts.

    Does not silently remove charges, hydrates, stereochemistry or phases.
    """
    if not isinstance(formula, str) or not 1 <= len(formula) <= _FORMULA_LENGTH_LIMIT:
        raise ValueError("Neutral formula must be 1-96 characters")
    if not re.fullmatch(r"[A-Za-z0-9()]+", formula, flags=re.ASCII):
        raise ValueError("Unsupported syntax: use neutral formulas and parentheses only")
    i = 0
    def read_multiplier() -> int:
        nonlocal i
        start = i
        while i < len(formula) and formula[i].isdigit():
            i += 1
        if start == i:
            return 1
        token = formula[start:i]
        if token.startswith("0") or len(token) > 6:
            raise ValueError("Zero-prefixed or oversized atom multipliers are not permitted")
        count = int(token)
        if count < 1 or count > _MAX_ATOMS:
            raise ValueError("Atom multiplier is out of bounds")
        return count

    def parse_group(depth: int = 0) -> dict[str, int]:
        nonlocal i
        if depth > 8:
            raise ValueError("Formula nesting is too deep")
        elements: dict[str, int] = defaultdict(int)
        has_token = False
        while i < len(formula) and formula[i] != ")":
            char = formula[i]
            if char == "(":
                i += 1
                inner = parse_group(depth + 1)
                if i == len(formula) or formula[i] != ")":
                    raise ValueError("Unmatched formula parenthesis")
                i += 1
                multiple = read_multiplier()
                for symbol, number in inner.items():
                    elements[symbol] += number * multiple
                has_token = True
            elif char.isupper():
                i += 1
                symbol = char
                if i < len(formula) and formula[i].islower():
                    symbol += formula[i]
                    i += 1
                if symbol not in _ATOMIC_WEIGHTS:
                    raise ValueError(f"Unsupported element: {symbol}")
                elements[symbol] += read_multiplier()
                has_token = True
            else:
                raise ValueError("Invalid token or leading coefficient inside neutral formula")
            if sum(elements.values()) > _MAX_ATOMS:
                raise ValueError("Formula exceeds supported atom count")
        if not has_token:
            raise ValueError("Empty formula group")
        return dict(elements)
    result = parse_group()
    if i != len(formula):
        raise ValueError("Unmatched closing parenthesis")
    return dict(sorted(result.items()))


def _fraction(value: Any, label: str, *, allow_zero: bool = False) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero) or number > 1e6:
        raise ValueError(f"{label} must be finite and in its supported range")
    return Fraction(Decimal(str(value)))


def stoichiometry_report(
    *, reactants: list[Mapping[str, Any]], products: list[Mapping[str, Any]],
    conversion_fraction: float = 1.0,
) -> dict[str, Any]:
    if not 1 <= len(reactants) <= 20 or not 1 <= len(products) <= 20:
        raise ValueError("Provide between one and twenty reactants and products")
    conversion = _fraction(conversion_fraction, "conversion_fraction", allow_zero=True)
    if conversion > 1:
        raise ValueError("Conversion fraction must be <= 1")
    totals = {"reactants": defaultdict(Fraction), "products": defaultdict(Fraction)}
    records: dict[str, list[dict[str, Any]]] = {"reactants": [], "products": []}
    names: set[str] = set()
    for direction, rows in (("reactants", reactants), ("products", products)):
        for row in rows:
            formula = str(row.get("formula") or "")
            if formula in names:
                raise ValueError("Formula appears multiple times; aggregate species by neutral formula")
            names.add(formula)
            atoms = parse_neutral_formula(formula)
            coeff = _fraction(row.get("coefficient"), "coefficient")
            if coeff > 1000:
                raise ValueError("Stoichiometric coefficients must be <= 1000")
            if "available_mol" in row and direction == "products":
                raise ValueError("Product inventories cannot declare available reactant moles")
            available = None
            if direction == "reactants" and row.get("available_mol") is not None:
                available = _fraction(row["available_mol"], "available_mol", allow_zero=True)
            mass_g_mol = sum(_ATOMIC_WEIGHTS[k] * count for k, count in atoms.items())
            for element, count in atoms.items():
                totals[direction][element] += coeff * count
            records[direction].append({
                "formula": formula,
                "coefficient": float(coeff),
                "atoms": atoms,
                "formula_mass_g_mol": round(mass_g_mol, 8),
                "available_mol": float(available) if available is not None else None,
            })
    all_elements = sorted(set(totals["reactants"]) | set(totals["products"]))
    differences = {
        elem: totals["products"][elem] - totals["reactants"][elem]
        for elem in all_elements
    }
    balanced = all(v == 0 for v in differences.values())
    residual = {elem: float(value) for elem, value in differences.items()}
    all_supplies_known = all(row["available_mol"] is not None for row in records["reactants"])
    # Even one absent supply makes limiting-reagent results unknowable.
    theoretical: dict[str, Any] | None = None
    if balanced and all_supplies_known:
        ratios = [
            Fraction(str(row["available_mol"])) / Fraction(str(row["coefficient"]))
            for row in records["reactants"]
        ]
        limiting_extent = min(ratios)
        actual_extent = limiting_extent * conversion
        limiting_species = [
            row["formula"] for row, ratio in zip(records["reactants"], ratios)
            if ratio == limiting_extent
        ]
        remaining = {
            row["formula"]: float(Fraction(str(row["available_mol"]))
                                  - Fraction(str(row["coefficient"])) * actual_extent)
            for row in records["reactants"]
        }
        formed_mol = {
            row["formula"]: float(Fraction(str(row["coefficient"])) * actual_extent)
            for row in records["products"]
        }
        formed_g = {
            row["formula"]: round(formed_mol[row["formula"]] * row["formula_mass_g_mol"], 8)
            for row in records["products"]
        }
        theoretical = {
            "limiting_reactants": limiting_species,
            "maximum_theoretical_extent_mol": float(limiting_extent),
            "assumed_reaction_extent_mol": float(actual_extent),
            "remaining_reactants_mol": remaining,
            "ideal_product_inventory_mol": formed_mol,
            "ideal_product_mass_g": formed_g,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "hs-deterministic-neutral-reaction-stoichiometry",
        "reactants": records["reactants"],
        "products": records["products"],
        "elements": all_elements,
        "elemental_residual_product_minus_reactant": residual,
        "elementally_balanced": balanced,
        "charge_balance_assessed": False,
        "conversion_fraction_assumed": float(conversion),
        "reaction_extent": theoretical,
        "result": "balanced_inventory" if balanced else "elementally_unbalanced",
        "limitations": [
            "Formula parser assumes neutral compounds; ionic charge and radical states are not modelled.",
            "Stoichiometry cannot establish reaction feasibility, yield, selectivity, reaction rates or safety.",
            "The limiting-reagent result is a conditional ideal material inventory, not a prediction.",
            "Compound phases, equilibria, kinetics, heat effects, impurities and losses are excluded.",
        ],
        **NON_AUTHORITY,
    }

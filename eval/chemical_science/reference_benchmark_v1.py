"""Chemistry-only numerical consistency and known-reference smoke benchmark.

This is not blind experimental validation. Cases are published physical
reference landmarks, mathematical conservation identities, and authored
bad-input tests. No hazardous physical experiment is prescribed.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

from hardware_splicer.chemical_stoichiometry import (
    parse_neutral_formula, stoichiometry_report,
)
from hardware_splicer.chemical_phase_equilibrium import phase_flash_report
from hardware_splicer.chemical_kinetics import kinetic_reference_report
from hardware_splicer.chemical_reaction_thermodynamics import (
    reaction_reference_thermodynamics,
)
from hardware_splicer.chemical_water_reference import (
    water_model_crosscheck, coolprop_water_report,
)
from hardware_splicer.chemical_process_network import validate_process_network
from hardware_splicer.chemical_engineering import property_report


def _mixing_example() -> dict[str, Any]:
    return {
        "units": [
            {"unit_id": "mixer", "kind": "mixer"},
            {"unit_id": "splitter", "kind": "splitter"},
        ],
        "streams": [
            {"stream_id": "feed-water", "source_unit_id": None,
             "target_unit_id": "mixer", "components_kg_h": {"water": 2}},
            {"stream_id": "feed-mix", "source_unit_id": None,
             "target_unit_id": "mixer",
             "components_kg_h": {"water": 1, "NaCl": .5}},
            {"stream_id": "mixed", "source_unit_id": "mixer",
             "target_unit_id": "splitter",
             "components_kg_h": {"water": 3, "NaCl": .5}},
            {"stream_id": "out-1", "source_unit_id": "splitter",
             "target_unit_id": None,
             "components_kg_h": {"water": 1, "NaCl": .1}},
            {"stream_id": "out-2", "source_unit_id": "splitter",
             "target_unit_id": None,
             "components_kg_h": {"water": 2, "NaCl": .4}},
        ],
    }


def run() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def check(name: str, func: Callable[[], dict[str, Any]]) -> None:
        started = time.perf_counter()
        try:
            result = func()
            passed = result.pop("_passed")
            rows.append({"case": name, "passed": bool(passed),
                         "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                         "observations": result})
        except Exception as exc:
            rows.append({"case": name, "passed": False,
                         "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                         "error": type(exc).__name__ + ": " + str(exc)[:250]})

    def stoich():
        x = stoichiometry_report(
            reactants=[{"formula": "CaCO3", "coefficient": 1, "available_mol": 5}],
            products=[{"formula": "CaO", "coefficient": 1},
                      {"formula": "CO2", "coefficient": 1}],
            conversion_fraction=.75,
        )
        return {
            "_passed": x["elementally_balanced"]
                       and x["reaction_extent"]["assumed_reaction_extent_mol"] == 3.75
                       and not x["release_authorized"],
            "ideal_extent_mol": x["reaction_extent"]["assumed_reaction_extent_mol"],
            "elemental_residuals": x["elemental_residual_product_minus_reactant"],
        }
    check("stoichiometric_conservation_and_extent", stoich)

    def nested_formula():
        result = parse_neutral_formula("Al2(SO4)3")
        return {"_passed": result == {"Al": 2, "S": 3, "O": 12}, "atom_counts": result}
    check("nested_neutral_formula_parsing", nested_formula)

    def intentionally_unbalanced():
        x = stoichiometry_report(
            reactants=[{"formula": "H2O", "coefficient": 1}],
            products=[{"formula": "H2", "coefficient": 1}],
        )
        return {"_passed": not x["elementally_balanced"] and x["reaction_extent"] is None,
                "elementally_balanced": x["elementally_balanced"]}
    check("unbalanced_reaction_no_fabricated_yield", intentionally_unbalanced)

    for temp, expected in [(300, 0.0), (400, 1.0)]:
        def test_pure(temp=temp, expected=expected):
            x = phase_flash_report(
                system_id="water", temperature_k=temp,
                pressure_pa=101325, mole_fractions={"water": 1.0},
            )
            return {
                "_passed": abs(x["vapor_fraction_molar"] - expected) < .01
                           and x["max_material_balance_residual"] < 1e-12,
                "vapor_fraction": x["vapor_fraction_molar"],
                "mass_residual": x["max_material_balance_residual"],
            }
        check(f"peng_robinson_water_{temp}K", test_pure)

    def light_gas():
        x = phase_flash_report(
            system_id="light_gas_reference", temperature_k=110,
            pressure_pa=100000, mole_fractions={
                "methane": .965, "ethane": .018, "nitrogen": .017,
            },
        )
        return {
            "_passed": .04 < x["vapor_fraction_molar"] < .16
                       and x["max_material_balance_residual"] < 1e-7,
            "vapor_fraction": x["vapor_fraction_molar"],
            "mass_residual": x["max_material_balance_residual"],
        }
    check("two_phase_light_gas_reference", light_gas)

    def water_reference():
        x = coolprop_water_report(temperature_k=300, pressure_pa=101325)
        return {"_passed": 373.0 < x["saturation_temperature_at_pressure_k"] < 373.25
                           and 995 < x["density_kg_m3"] < 998,
                "saturation_temperature_at_1atm_k": x["saturation_temperature_at_pressure_k"],
                "density_at_300k_kg_m3": x["density_kg_m3"]}
    check("coolprop_water_reference_landmark", water_reference)

    def water_density_crosscheck():
        conventional = property_report("water", 300, 101325)["properties"]["density_kg_m3"]
        specialist = coolprop_water_report(temperature_k=300, pressure_pa=101325)
        reference = specialist["density_kg_m3"]
        relative_difference = abs(conventional - reference) / reference
        return {
            "_passed": relative_difference < .02,
            "thermo_density_kg_m3": conventional,
            "coolprop_density_kg_m3": reference,
            "relative_difference": relative_difference,
        }
    check("thermo_coolprop_water_density_300k", water_density_crosscheck)

    for temp, expected_conflict in [(300, False), (374, True), (400, False)]:
        def compare(temp=temp, expected_conflict=expected_conflict):
            x = water_model_crosscheck(temperature_k=temp, pressure_pa=101325)
            return {"_passed": ("reference_models_disagree_on_phase" in x["blockers"])
                               == expected_conflict and not x["design_decision_authorized"],
                    "coolprop_phase": x["coolprop_reference"]["phase"],
                    "peng_robinson_phase": x["peng_robinson_reference"]["phase"],
                    "blockers": x["blockers"]}
        check(f"cross_model_water_{temp}K", compare)

    for reaction in ["hydrogen_oxygen_exchange", "carbon_oxygen_exchange"]:
        def thermo(reaction=reaction):
            x = reaction_reference_thermodynamics(
                reaction_id=reaction, temperature_k=1200, pressure_pa=101325)
            return {"_passed": x["elemental_balance_passed"]
                              and x["thermodynamic_identity_error_kj_per_mol"] < 1e-6
                              and x["log_equilibrium_constant_identity_error"] < 1e-6,
                    "standard_delta_h_kj_mol": x["delta_h_kj_per_mol_reaction"],
                    "standard_delta_g_kj_mol": x["delta_g_kj_per_mol_reaction"],
                    "equilibrium_constant": x["equilibrium_constant_dimensionless"]}
        check(f"cantera_reaction_thermodynamics_{reaction}", thermo)

    def kinetics():
        x = kinetic_reference_report(
            temperature_k=1200, pressure_pa=101325,
            duration_s=.05, sample_count=6,
        )
        first = x["trajectory"][0]["tracked_mole_fractions"]["CH4"]
        last = x["trajectory"][-1]["tracked_mole_fractions"]["CH4"]
        return {"_passed": first > last
                           and x["max_element_mass_balance_residual"] < 1e-8,
                "methane_initial": first, "methane_final": last,
                "element_mass_residual": x["max_element_mass_balance_residual"]}
    check("cantera_reference_kinetic_trajectory", kinetics)

    def flowsheet():
        x = validate_process_network(**_mixing_example())
        return {"_passed": x["result"] == "declared_network_consistent_but_unverified"
                           and len(x["unit_results"]) == 2
                           and not x["process_behavior_simulated"],
                "topological_units": x["topological_unit_order"],
                "global_mass_residual_kg_h": x["global_balance"]["overall"]["residual_kg_h"]}
    check("species_conserving_two_unit_process_graph", flowsheet)

    return {
        "schema_version": "hardware_splicer.chemical_independent_benchmark.v1",
        "authored_cases": len(rows),
        "passed": sum(r["passed"] for r in rows),
        "cases": rows,
        "description": "Cross-library reference landmarks, identities and implementation regressions, not blinded physical validation.",
        "bench_validation": False,
        "physical_action_authorized": False,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2))
    if report["passed"] != report["authored_cases"]:
        raise SystemExit(1)

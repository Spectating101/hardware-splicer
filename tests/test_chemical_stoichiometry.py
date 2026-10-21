from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.chemical_stoichiometry import parse_neutral_formula, stoichiometry_report
from hardware_splicer.mcp_backend_gateway import operation_catalog, dispatch_operation, task_operation_manifest
from hardware_splicer.product_api import create_product_app


def _case():
    return {
        "reactants": [
            {"formula": "CaCO3", "coefficient": 1, "available_mol": 4},
        ],
        "products": [
            {"formula": "CaO", "coefficient": 1},
            {"formula": "CO2", "coefficient": 1},
        ],
        "conversion_fraction": 0.5,
    }


@pytest.mark.parametrize("formula,expected", [
    ("Ca(OH)2", {"Ca": 1, "O": 2, "H": 2}),
    ("Al2(SO4)3", {"Al": 2, "S": 3, "O": 12}),
    ("(NH4)2SO4", {"N": 2, "H": 8, "S": 1, "O": 4}),
    ("H2O", {"H": 2, "O": 1}),
    ("NaCl", {"Na": 1, "Cl": 1}),
])
def test_valid_formula_parser(formula, expected):
    assert parse_neutral_formula(formula) == expected


@pytest.mark.parametrize("formula", [
    "H2O+", "Na+", "H2O·2H2O", "0H", "2H2O", "H0", "H02", "Ca(OH",
    "Ca)OH(", "()", "(OH)0", "Fe(SO4))", "Zz2", "Ca(())", "H"*100,
    "H9999999999",
])
def test_invalid_or_ambiguous_formulas_fail_closed(formula):
    with pytest.raises(ValueError):
        parse_neutral_formula(formula)


def test_stoichiometry_mass_balance_and_extent():
    report = stoichiometry_report(**_case())
    assert report["elementally_balanced"]
    assert report["result"] == "balanced_inventory"
    assert report["charge_balance_assessed"] is False
    assert all(value == 0 for value in report["elemental_residual_product_minus_reactant"].values())
    extent = report["reaction_extent"]
    assert extent["limiting_reactants"] == ["CaCO3"]
    assert extent["maximum_theoretical_extent_mol"] == 4
    assert extent["assumed_reaction_extent_mol"] == 2
    assert extent["remaining_reactants_mol"]["CaCO3"] == 2
    assert extent["ideal_product_inventory_mol"] == {"CaO": 2, "CO2": 2}
    assert not report["physical_action_authorized"]


def test_second_reactant_limiting_species():
    report = stoichiometry_report(
        reactants=[
            {"formula": "NaOH", "coefficient": 1, "available_mol": 2},
            {"formula": "HCl", "coefficient": 1, "available_mol": 1},
        ],
        products=[
            {"formula": "NaCl", "coefficient": 1},
            {"formula": "H2O", "coefficient": 1},
        ],
    )
    assert report["elementally_balanced"]
    assert report["reaction_extent"]["limiting_reactants"] == ["HCl"]
    assert report["reaction_extent"]["remaining_reactants_mol"]["NaOH"] == 1


def test_unbalanced_reaction_no_fictitious_product_yield():
    case = _case()
    case["products"][1]["coefficient"] = 0.5
    report = stoichiometry_report(**case)
    assert not report["elementally_balanced"]
    assert report["reaction_extent"] is None
    assert report["elemental_residual_product_minus_reactant"]["C"] != 0


def test_partial_supply_does_not_claim_limiting_reactant():
    report = stoichiometry_report(
        reactants=[
            {"formula": "NaOH", "coefficient": 1},
            {"formula": "HCl", "coefficient": 1, "available_mol": 1},
        ],
        products=[{"formula": "NaCl", "coefficient": 1},
                  {"formula": "H2O", "coefficient": 1}],
    )
    assert report["elementally_balanced"] and report["reaction_extent"] is None


def test_scaled_coefficients_exact_balancing():
    report = stoichiometry_report(
        reactants=[{"formula": "H2O", "coefficient": 0.5}],
        products=[{"formula": "H2", "coefficient": 0.5},
                  {"formula": "O2", "coefficient": 0.25}],
    )
    assert report["elementally_balanced"]


@pytest.mark.parametrize("value", [float("inf"), float("nan"), -1, 1.1])
def test_invalid_conversion(value):
    with pytest.raises(ValueError):
        stoichiometry_report(**{**_case(), "conversion_fraction": value})


def test_excess_or_negative_species_supply_rejected():
    for supply in [float("nan"), -1, float("inf")]:
        case = _case()
        case["reactants"][0]["available_mol"] = supply
        with pytest.raises(ValueError):
            stoichiometry_report(**case)


def test_stoichiometry_api_and_mcp():
    app = create_product_app()
    client = TestClient(app)
    response = client.post("/v1/engineering/chemical/reactions/stoichiometry", json=_case())
    assert response.status_code == 200, response.text
    assert response.json()["elementally_balanced"]
    op = next(row for row in operation_catalog(app)
              if row["path"] == "/v1/engineering/chemical/reactions/stoichiometry")
    result = asyncio.run(dispatch_operation(op["operation_id"], app=app, json_body=_case()))
    assert result["status_code"] == 200
    assert result["body"]["reaction_extent"]["assumed_reaction_extent_mol"] == 2
    manifest = task_operation_manifest("chemical_reaction_analysis", app=app)
    assert op["operation_id"] in manifest["workflow_operation_ids"]
    assert not manifest["authority_contract"]["automatic_execution"]

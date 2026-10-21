from __future__ import annotations

import importlib.util
import math

import pytest
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.chemical_phase_equilibrium import phase_flash_report, reference_systems


@pytest.fixture(scope="module")
def client():
    return TestClient(create_product_app())


def _gas():
    return {
        "system_id": "light_gas_reference",
        "temperature_k": 110.0,
        "pressure_pa": 100000.0,
        "mole_fractions": {"methane": 0.965, "ethane": 0.018, "nitrogen": 0.017},
    }


def test_reference_system_discovery(client):
    response = client.get("/v1/engineering/chemical/phases/reference-systems")
    assert response.status_code == 200
    listed = response.json()["systems"]
    assert {row["system_id"] for row in listed} == {"water", "light_gas_reference"}
    assert len(reference_systems()) == 2


def test_two_phase_flash_solves_real_thermo_engine(client):
    response = client.post("/v1/engineering/chemical/phases/flash", json=_gas())
    if importlib.util.find_spec("thermo") is None:
        assert response.status_code == 503
    else:
        assert response.status_code == 200, response.text
        result = response.json()
        # Wide tolerance to avoid over-fitting to a particular implementation.
        assert 0.04 < result["vapor_fraction_molar"] < 0.16
        assert result["vapor_mole_fractions"]["nitrogen"] > result["liquid_mole_fractions"]["nitrogen"]
        assert result["max_material_balance_residual"] < 1e-7
        assert abs(sum(result["vapor_mole_fractions"].values()) - 1) < 1e-8
        assert abs(sum(result["liquid_mole_fractions"].values()) - 1) < 1e-8
        assert result["interaction_source"] == "ChemSep PR sample binary interaction parameters"
        assert not result["material_compatibility_verified"]


def test_water_phase_change_reference(client):
    if importlib.util.find_spec("thermo") is None:
        pytest.skip("thermo optional dependency absent")
    for t,phase in [(300, "liquid"), (400, "vapor")]:
        response = client.post(
            "/v1/engineering/chemical/phases/flash",
            json={
                "system_id": "water", "temperature_k": t,
                "pressure_pa": 101325, "mole_fractions": {"water": 1},
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        vf = result["vapor_fraction_molar"]
        assert vf < 0.01 if phase == "liquid" else vf > 0.99
        assert result["max_material_balance_residual"] < 1e-12


@pytest.mark.parametrize("patch", [
    {"temperature_k": 400},
    {"pressure_pa": 1e9},
    {"mole_fractions": {"methane": 1}},
    {"mole_fractions": {"methane": 1, "ethane": 0, "nitrogen": -1}},
    {"mole_fractions": {"methane": 0.9, "ethane": 0.01, "nitrogen": 0.02}},
    {"mole_fractions": {"methane": float("nan"), "ethane": 0, "nitrogen": 0}},
])
def test_flash_invalid_conditions_fail_closed(patch):
    with pytest.raises(ValueError):
        phase_flash_report(**{**_gas(), **patch})


def test_flash_api_and_mcp_discoverable(client):
    from hardware_splicer.mcp_backend_gateway import operation_catalog, task_operation_manifest
    path = "/v1/engineering/chemical/phases/flash"
    op = next(row for row in operation_catalog(client.app) if row["path"] == path)
    tasks = task_operation_manifest("chemical_phase_equilibrium", client.app)
    assert op["operation_id"] in tasks["workflow_operation_ids"]
    assert not tasks["authority_contract"]["automatic_execution"]

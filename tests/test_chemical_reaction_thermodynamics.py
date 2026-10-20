from __future__ import annotations

import importlib.util
import math
import pytest

from fastapi.testclient import TestClient
from hardware_splicer.chemical_reaction_thermodynamics import reaction_reference_thermodynamics
from hardware_splicer.mcp_backend_gateway import operation_catalog, task_operation_manifest
from hardware_splicer.product_api import create_product_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_product_app())


@pytest.mark.parametrize("reaction_id", [
    "hydrogen_oxygen_exchange",
    "carbon_oxygen_exchange",
])
@pytest.mark.parametrize("temperature_k", [500, 1200, 1900])
def test_reaction_thermodynamic_identities_with_real_cantera(client, reaction_id, temperature_k):
    reply = client.post("/v1/engineering/chemical/reactions/thermodynamics/reference",
                        json={"reaction_id": reaction_id,
                              "temperature_k": temperature_k, "pressure_pa": 101325})
    if importlib.util.find_spec("cantera") is None:
        assert reply.status_code == 503
        return
    assert reply.status_code == 200, reply.text
    row = reply.json()
    assert row["elemental_balance_passed"]
    assert row["delta_nu_gas"] == 0
    assert row["thermodynamic_identity_error_kj_per_mol"] < 1e-5
    assert row["log_equilibrium_constant_identity_error"] < 1e-6
    assert row["equilibrium_constant_dimensionless"] > 0
    assert not row["chemical_safety_verified"]


def test_reference_reaction_gibbs_sign_and_equilibrium_trend():
    if importlib.util.find_spec("cantera") is None:
        pytest.skip("Cantera not installed")
    low = reaction_reference_thermodynamics(
        reaction_id="hydrogen_oxygen_exchange", temperature_k=500, pressure_pa=101325)
    high = reaction_reference_thermodynamics(
        reaction_id="hydrogen_oxygen_exchange", temperature_k=1900, pressure_pa=101325)
    assert low["delta_g_kj_per_mol_reaction"] > 0
    assert high["delta_g_kj_per_mol_reaction"] < 0
    assert low["equilibrium_constant_dimensionless"] < 1
    assert high["equilibrium_constant_dimensionless"] > 1


@pytest.mark.parametrize("case", [
    {"reaction_id": "outside_chemical_scope", "temperature_k": 900, "pressure_pa": 101325},
    {"reaction_id": "hydrogen_oxygen_exchange", "temperature_k": 100, "pressure_pa": 101325},
    {"reaction_id": "carbon_oxygen_exchange", "temperature_k": float("nan"), "pressure_pa": 101325},
    {"reaction_id": "carbon_oxygen_exchange", "temperature_k": 800, "pressure_pa": 1e9},
])
def test_unbounded_reference_query_rejected(case):
    with pytest.raises(ValueError):
        reaction_reference_thermodynamics(**case)


def test_reaction_thermodynamics_mcp_discovery(client):
    op = next(
        row for row in operation_catalog(client.app)
        if row["path"] == "/v1/engineering/chemical/reactions/thermodynamics/reference"
    )
    manifest = task_operation_manifest("chemical_reaction_analysis", app=client.app)
    assert op["operation_id"] in manifest["workflow_operation_ids"]
    assert not manifest["authority_contract"]["automatic_execution"]

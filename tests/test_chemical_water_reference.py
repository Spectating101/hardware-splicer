from __future__ import annotations

import importlib.util
import pytest
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.chemical_water_reference import water_model_crosscheck


@pytest.fixture(scope="module")
def client():
    return TestClient(create_product_app())


def _available():
    return (importlib.util.find_spec("CoolProp") is not None
            and importlib.util.find_spec("thermo") is not None)


def test_water_reference_saturation_and_density(client):
    response = client.post("/v1/engineering/chemical/phases/water-properties",
                           json={"temperature_k": 300, "pressure_pa": 101325})
    if importlib.util.find_spec("CoolProp") is None:
        assert response.status_code == 503
        return
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["phase"] == "liquid"
    assert 995 < data["density_kg_m3"] < 998
    assert 373.0 < data["saturation_temperature_at_pressure_k"] < 373.25
    assert not data["physical_action_authorized"]


@pytest.mark.parametrize("temperature_k,expected_status", [
    (300, "models_agree_but_unverified"),
    (360, "models_agree_but_unverified"),
    (373.15, "model_conflict_or_boundary"),
    (374, "model_conflict_or_boundary"),
    (400, "models_agree_but_unverified"),
])
def test_water_eos_comparison_flags_disagreement(client, temperature_k, expected_status):
    response = client.post("/v1/engineering/chemical/phases/water-crosscheck",
                           json={"temperature_k": temperature_k, "pressure_pa": 101325})
    if not _available():
        assert response.status_code == 503
        return
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["result"] == expected_status
    assert data["design_decision_authorized"] is False
    if temperature_k in {373.15, 374}:
        assert data["phase_agreement"] is False
        assert "reference_models_disagree_on_phase" in data["blockers"]
    if temperature_k in {300, 400}:
        assert data["phase_agreement"] is True
        assert data["blockers"] == []


@pytest.mark.parametrize("value", [-10, 1000, float("nan"), float("inf")])
def test_water_out_of_range_fails_closed(value):
    with pytest.raises(ValueError):
        water_model_crosscheck(temperature_k=value, pressure_pa=101325)


def test_water_capability_mcp_manifest(client):
    from hardware_splicer.mcp_backend_gateway import operation_catalog, task_operation_manifest
    rows = operation_catalog(client.app)
    entry = next(row for row in rows
                 if row["path"] == "/v1/engineering/chemical/phases/water-crosscheck")
    manifest = task_operation_manifest("chemical_phase_equilibrium", client.app)
    assert entry["operation_id"] in manifest["workflow_operation_ids"]
    assert manifest["authority_contract"]["automatic_execution"] is False

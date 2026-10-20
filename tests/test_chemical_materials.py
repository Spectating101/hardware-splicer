from __future__ import annotations

import importlib.util
from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app


def test_solid_elemental_composition_is_numeric_only():
    client = TestClient(create_product_app())
    response = client.post("/v1/engineering/chemical/materials/composition",
                           json={"formula": "Al2O3", "source_refs": ["spec:unverified"]})
    if importlib.util.find_spec("pymatgen") is None:
        assert response.status_code == 503
        assert response.json()["detail"]["type"] == "optional_engine_missing"
    else:
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["reduced_formula"] == "Al2O3"
        assert 101.9 < result["formula_unit_molar_mass_g_mol"] < 102.1
        assert abs(result["atomic_fractions"]["O"] - 0.6) < 1e-6
        assert abs(sum(result["mass_fractions"].values()) - 1) < 1e-6
        assert result["material_compatibility_verified"] is False
        assert result["release_authorized"] is False


def test_invalid_formula_or_long_payload_cannot_be_analyzed():
    client = TestClient(create_product_app())
    response = client.post("/v1/engineering/chemical/materials/composition",
                           json={"formula": "x" * 129})
    assert response.status_code == 422

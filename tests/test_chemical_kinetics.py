from __future__ import annotations

import importlib.util
import math

import pytest
from fastapi.testclient import TestClient
from hardware_splicer.chemical_kinetics import kinetic_reference_report
from hardware_splicer.product_api import create_product_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_product_app())


def _input():
    return {
        "temperature_k": 1200.0,
        "pressure_pa": 101325.0,
        "duration_s": 0.05,
        "sample_count": 6,
    }


def test_reference_kinetic_trajectory_is_real_and_mass_conserving(client):
    response = client.post("/v1/engineering/chemical/reactions/kinetics/reference", json=_input())
    if importlib.util.find_spec("cantera") is None:
        assert response.status_code == 503
        return
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["mechanism"] == "gri30.yaml"
    assert report["max_element_mass_balance_residual"] < 1e-8
    assert len(report["trajectory"]) == 6
    assert report["trajectory"][0]["tracked_mole_fractions"]["CH4"] > (
        report["trajectory"][-1]["tracked_mole_fractions"]["CH4"]
    )
    assert all(abs(row["temperature_k"] - 1200) < 1e-6
               for row in report["trajectory"])
    assert report["physical_action_authorized"] is False
    assert report["chemical_safety_verified"] is False


@pytest.mark.parametrize("change", [
    {"temperature_k": 500},
    {"pressure_pa": 4e6},
    {"duration_s": 1},
    {"sample_count": 100},
    {"duration_s": float("nan")},
])
def test_kinetics_reference_rejects_unbounded_cases(change):
    with pytest.raises(ValueError):
        kinetic_reference_report(**{**_input(), **change})


def test_kinetics_covered_by_chemical_task_manifest(client):
    from hardware_splicer.mcp_backend_gateway import operation_catalog, task_operation_manifest
    rows = operation_catalog(client.app)
    op = next(x for x in rows if x["path"] == "/v1/engineering/chemical/reactions/kinetics/reference")
    manifest = task_operation_manifest("chemical_reaction_analysis", client.app)
    assert op["operation_id"] in manifest["workflow_operation_ids"]

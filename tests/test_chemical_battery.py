from __future__ import annotations

import asyncio
import importlib.util

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.mcp_backend_gateway import dispatch_operation, operation_catalog
from hardware_splicer.product_api import create_product_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_product_app())


def _battery():
    return {"c_rate": 0.5, "duration_s": 600, "source_refs": ["builtin:Chen2020"]}


def test_battery_engine_is_registered_and_fails_closed_if_missing(client):
    report = client.get("/v1/engineering/chemical/engines")
    assert report.status_code == 200
    entry = next(e for e in report.json()["engines"] if e["id"] == "pybamm")
    assert entry["adapter_implemented"]
    assert entry["installed"] == (importlib.util.find_spec("pybamm") is not None)


def test_battery_discharge_executes_real_model_and_never_authorizes(client):
    result = client.post("/v1/engineering/chemical/battery/discharge", json=_battery())
    if importlib.util.find_spec("pybamm") is None:
        assert result.status_code == 503
        assert result.json()["detail"]["type"] == "optional_engine_missing"
    else:
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["model"] == "lithium_ion.SPM"
        assert body["parameter_set"] == "Chen2020"
        assert len(body["samples"]) >= 2
        assert body["samples"][0]["terminal_voltage_v"] > body["samples"][-1]["terminal_voltage_v"]
        assert body["nominal_capacity_ah"] > 0
        assert not body["chemical_safety_verified"]
        assert not body["physical_action_authorized"]
        assert not body["release_authorized"]


@pytest.mark.parametrize("data", [
    {"c_rate": 0, "duration_s": 600},
    {"c_rate": 1.1, "duration_s": 600},
    {"c_rate": 0.5, "duration_s": 10},
    {"c_rate": 0.5, "duration_s": 4000},
])
def test_battery_experiment_bounds(client, data):
    assert client.post("/v1/engineering/chemical/battery/discharge",
                       json=data).status_code == 422


def test_battery_route_mcp_gateway_discovers_and_rejects_invalid_job(client):
    op = next(o for o in operation_catalog(client.app)
              if o["path"] == "/v1/engineering/chemical/battery/discharge")
    result = asyncio.run(dispatch_operation(
        op["operation_id"], app=client.app,
        json_body={"c_rate": 10, "duration_s": 600},
    ))
    assert result["status_code"] == 422

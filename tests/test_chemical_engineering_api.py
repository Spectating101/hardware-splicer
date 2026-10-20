from __future__ import annotations

import importlib.util

from fastapi.testclient import TestClient
import pytest

from hardware_splicer.chemical_engineering import mass_balance_report
from hardware_splicer.machine_project import MachineProject
from hardware_splicer.mcp_backend_gateway import operation_catalog
from hardware_splicer.product_api import create_product_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_product_app())


def _streams():
    return [
        {"stream_id": "supply", "direction": "inlet", "mass_flow_kg_h": 20,
         "components_kg_h": {"water": 20}},
        {"stream_id": "recover", "direction": "outlet", "mass_flow_kg_h": 20,
         "components_kg_h": {"water": 20}},
    ]


def test_chemical_domain_is_canonical_machine_project():
    project = MachineProject.model_validate({
        "project_id": "chemistry-v0",
        "name": "Materials test",
        "purpose": "Trace design evidence",
        "subsystems": [{"subsystem_id": "chem-1", "name": "Chemical process",
                        "domain": "chemical"}],
    })
    assert project.subsystems[0].domain.value == "chemical"
    assert project.subsystems[0].authority.value == "proposed"


def test_mass_balance_consistency_and_authority(client):
    reply = client.post("/v1/engineering/chemical/process/mass-balance",
                        json={"streams": _streams()})
    assert reply.status_code == 200, reply.text
    report = reply.json()
    assert report["result"] == "consistent_declared_flows"
    assert report["component_checks"][0]["balanced"]
    assert not report["release_authorized"]
    assert not report["chemical_safety_verified"]


def test_mass_balance_missing_mass_not_released(client):
    streams = _streams()
    streams[1]["mass_flow_kg_h"] = 18
    streams[1]["components_kg_h"] = {"water": 18}
    report = client.post("/v1/engineering/chemical/process/mass-balance",
                         json={"streams": streams}).json()
    assert report["result"] == "inconsistent_declared_flows"
    assert report["overall"]["residual_kg_h"] == 2
    assert not report["physical_action_authorized"]


def test_component_mismatch_is_blocked(client):
    streams = _streams()
    streams[1]["components_kg_h"] = {"water": 19}
    response = client.post("/v1/engineering/chemical/process/mass-balance",
                           json={"streams": streams})
    assert response.status_code == 422


def test_nonreactive_component_swap_not_consistent(client):
    streams = _streams()
    streams[1]["components_kg_h"] = {"ethanol": 20}
    response = client.post("/v1/engineering/chemical/process/mass-balance",
                           json={"streams": streams})
    assert response.status_code == 200
    assert response.json()["result"] == "inconsistent_declared_flows"


def test_reaction_flag_does_not_pretend_stoichiometry(client):
    streams = _streams()
    streams[1]["components_kg_h"] = {"ethanol": 20}
    report = client.post("/v1/engineering/chemical/process/mass-balance",
                         json={"streams": streams, "reaction_present": True}).json()
    assert report["component_checks"] == []
    assert not report["component_balance_applicable"]
    assert not report["experimentally_validated"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_flow_rejected(value):
    streams = _streams()
    streams[1]["mass_flow_kg_h"] = value
    with pytest.raises(ValueError):
        mass_balance_report(streams)


def test_engine_discovery_and_mcp_auto_exposure(client):
    response = client.get("/v1/engineering/chemical/engines")
    assert response.status_code == 200
    names = {entry["id"] for entry in response.json()["engines"]}
    assert {"rdkit", "thermo", "chemicals", "cantera", "pybamm", "pymatgen"} <= names
    ops = {(row["method"], row["path"]) for row in operation_catalog(client.app)}
    assert ("POST", "/v1/engineering/chemical/process/mass-balance") in ops
    assert ("POST", "/v1/engineering/chemical/molecule/inspect") in ops


def test_rdkit_produces_real_molecular_descriptors_or_declares_missing(client):
    response = client.post("/v1/engineering/chemical/molecule/inspect",
                           json={"smiles": "CCO", "source_refs": ["lab:placeholder"]})
    if importlib.util.find_spec("rdkit") is None:
        assert response.status_code == 503
        assert response.json()["detail"]["type"] == "optional_engine_missing"
    else:
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["molecular_formula"] == "C2H6O"
        assert 46 < payload["molecular_weight_g_mol"] < 47
        assert payload["source_refs"] == ["lab:placeholder"]
        assert payload["release_authorized"] is False


def test_thermo_without_optional_package_fails_closed(client):
    response = client.post("/v1/engineering/chemical/properties/inspect",
                           json={"chemical_id": "water", "temperature_k": 298.15,
                                 "pressure_pa": 101325})
    if importlib.util.find_spec("thermo") is None:
        assert response.status_code == 503
    else:
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["properties"]["density_kg_m3"] is not None
        assert not payload["material_compatibility_verified"]


def test_chemical_check_executes_via_canonical_mcp_gateway(client):
    import asyncio
    from hardware_splicer.mcp_backend_gateway import dispatch_operation
    op = next(row for row in operation_catalog(client.app)
              if row["path"] == "/v1/engineering/chemical/process/mass-balance")
    response = asyncio.run(dispatch_operation(
        op["operation_id"], app=client.app, json_body={"streams": _streams()}
    ))
    assert response["status_code"] == 200
    assert response["body"]["result"] == "consistent_declared_flows"
    assert response["body"]["release_authorized"] is False

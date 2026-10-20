from __future__ import annotations

import asyncio
import copy
import importlib.util
import math

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.chemical_engineering import engines_report
from hardware_splicer.mcp_backend_gateway import dispatch_operation, operation_catalog
from hardware_splicer.product_api import create_product_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_product_app())


def _gas(**overrides):
    result = {
        "temperature_k": 300.0,
        "pressure_pa": 101325.0,
        "mole_fractions": {"N2": 0.79, "O2": 0.21},
    }
    result.update(overrides)
    return result


def _machine_project():
    return {
        "project_id": "material-bridge-demo",
        "name": "Enclosure material candidate",
        "purpose": "Review thermal evidence for electrical assembly enclosure",
        "subsystems": [
            {"subsystem_id": "enclosure-subsystem", "name": "Enclosure", "domain": "mechanical"}
        ],
        "components": [
            {"component_id": "housing", "name": "Housing", "domain": "mechanical",
             "subsystem_id": "enclosure-subsystem",
             "metadata": {"material_id": "polymer-variant-A"}}
        ],
        "constraints": [
            {"constraint_id": "thermal-threshold", "name": "Thermal property criterion",
             "domain": "chemical", "statement": "Must meet the documented material threshold",
             "applies_to": ["housing"],
             "metadata": {"material_property": "max_service_temperature",
                          "unit": "K", "min_value": 340.0}},
            {"constraint_id": "electrical-threshold", "name": "Electrical insulation criterion",
             "domain": "electrical", "statement": "Candidate must meet declared resistivity floor",
             "applies_to": ["housing"],
             "metadata": {"material_property": "electrical_resistivity",
                          "unit": "ohm*m", "min_value": 1e9}},
        ],
        "evidence": [
            {"evidence_id": "datasheet-thermal", "kind": "datasheet", "basis": "vendor_declared",
             "ref": "vendor-datasheet-v1-section-4",
             "authority": "observed", "supports": ["housing", "thermal-threshold"],
             "metadata": {"material_id": "polymer-variant-A",
                          "material_property": "max_service_temperature",
                          "unit": "K", "value": 350.0}},
            {"evidence_id": "datasheet-electrical", "kind": "datasheet", "basis": "vendor_declared",
             "ref": "vendor-datasheet-v1-section-5",
             "authority": "observed", "supports": ["housing", "electrical-threshold"],
             "metadata": {"material_id": "polymer-variant-A",
                          "material_property": "electrical_resistivity",
                          "unit": "ohm*m", "value": 1e10}},
        ],
    }


def test_cantera_gas_state_is_bounded_and_runtime_discovered(client):
    engine = next(e for e in engines_report()["engines"] if e["id"] == "cantera")
    assert engine["adapter_implemented"]
    reply = client.post("/v1/engineering/chemical/gas/state", json=_gas())
    if importlib.util.find_spec("cantera") is None:
        assert reply.status_code == 503
        return
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["model"] == "air.yaml"
    assert math.isclose(body["initial_state"]["density_kg_m3"], 1.17, rel_tol=0.02)
    assert body["equilibrium_state"] is None
    assert not body["physical_action_authorized"]


def test_cantera_equilibrium_is_computational_only(client):
    reply = client.post("/v1/engineering/chemical/gas/state",
                        json=_gas(equilibrium=True))
    if importlib.util.find_spec("cantera") is None:
        assert reply.status_code == 503
    else:
        assert reply.status_code == 200, reply.text
        body = reply.json()
        assert body["equilibrium_state"] is not None
        assert body["equilibrium_state"]["density_kg_m3"] > 0
        assert body["mode"] == "equilibrium_tp"
        assert body["chemical_safety_verified"] is False


@pytest.mark.parametrize("fractions", [
    {"H2": 1.0},
    {"N2": 0.7, "O2": 0.2},
    {"N2": 1.1, "O2": -0.1},
    {"O2": 0.0},
])
def test_cantera_refuses_unsupported_mixtures(client, fractions):
    # On systems without Cantera, the input should still be schema-bounded.
    from hardware_splicer.chemical_gas import _composition
    with pytest.raises(ValueError):
        _composition(fractions)


def test_material_cross_domain_reconciliation_is_read_only(client):
    project = _machine_project()
    snapshot = copy.deepcopy(project)
    response = client.post("/v1/engineering/chemical/materials/evidence-check",
                           json={"project": project, "component_id": "housing"})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["result"] == "numerically_consistent_but_unverified"
    assert {row["constraint_domain"] for row in report["checks"]} == {"electrical", "chemical"}
    assert all(check["numerically_within_declared_limits"] for check in report["checks"])
    assert report["project_modified"] is False
    assert report["material_compatibility_verified"] is False
    assert report["release_authorized"] is False
    assert project == snapshot


def test_material_failure_is_not_promoted_to_verified(client):
    project = _machine_project()
    project["evidence"][0]["metadata"]["value"] = 320
    response = client.post("/v1/engineering/chemical/materials/evidence-check",
                           json={"project": project, "component_id": "housing"})
    assert response.status_code == 200, response.text
    report = response.json()
    assert "declared_numeric_limit_not_met" in report["blockers"]
    assert report["result"] == "blocked"


def test_material_identity_mismatch_is_blocked(client):
    project = _machine_project()
    project["evidence"][0]["metadata"]["material_id"] = "polymer-variant-B"
    response = client.post("/v1/engineering/chemical/materials/evidence-check",
                           json={"project": project, "component_id": "housing"})
    assert "evidence_material_identity_mismatch" in response.json()["blockers"]


def test_material_evidence_disagreement_is_blocked(client):
    project = _machine_project()
    another = copy.deepcopy(project["evidence"][0])
    another["evidence_id"] = "second-thermal-source"
    another["ref"] = "datasheet-revision-2"
    another["metadata"]["value"] = 355
    project["evidence"].append(another)
    report = client.post("/v1/engineering/chemical/materials/evidence-check",
                         json={"project": project, "component_id": "housing"}).json()
    assert "unreconciled_source_disagreement" in report["blockers"]
    assert not report["checks"][0]["numerically_within_declared_limits"]


def test_material_no_constraints_is_insufficient_evidence(client):
    project = _machine_project()
    project["constraints"].clear()
    project["evidence"].clear()
    response = client.post("/v1/engineering/chemical/materials/evidence-check",
                           json={"project": project, "component_id": "housing"})
    assert response.status_code == 200
    assert "no_material_constraints_for_component" in response.json()["blockers"]


def test_material_unknown_component_is_invalid(client):
    response = client.post("/v1/engineering/chemical/materials/evidence-check",
                           json={"project": _machine_project(), "component_id": "not-found"})
    assert response.status_code == 422


def test_material_check_is_mcp_callable(client):
    op = next(row for row in operation_catalog(client.app)
              if row["path"] == "/v1/engineering/chemical/materials/evidence-check")
    result = asyncio.run(dispatch_operation(
        op["operation_id"], app=client.app,
        json_body={"project": _machine_project(), "component_id": "housing"}
    ))
    assert result["status_code"] == 200
    assert result["body"]["result"] == "numerically_consistent_but_unverified"

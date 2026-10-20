from __future__ import annotations

import copy
import math
import pytest
from fastapi.testclient import TestClient

from hardware_splicer.chemical_process_network import validate_process_network
from hardware_splicer.mcp_backend_gateway import operation_catalog, task_operation_manifest
from hardware_splicer.product_api import create_product_app


def _network():
    return {
        "units": [
            {"unit_id": "mix", "kind": "mixer"},
            {"unit_id": "split", "kind": "splitter"},
        ],
        "streams": [
            {"stream_id": "water", "source_unit_id": None, "target_unit_id": "mix",
             "components_kg_h": {"water": 2}},
            {"stream_id": "brine", "source_unit_id": None, "target_unit_id": "mix",
             "components_kg_h": {"water": 1, "NaCl": 0.5}},
            {"stream_id": "mixture", "source_unit_id": "mix", "target_unit_id": "split",
             "components_kg_h": {"water": 3, "NaCl": 0.5}},
            {"stream_id": "first_out", "source_unit_id": "split", "target_unit_id": None,
             "components_kg_h": {"water": 1, "NaCl": 0.1}},
            {"stream_id": "second_out", "source_unit_id": "split", "target_unit_id": None,
             "components_kg_h": {"water": 2, "NaCl": 0.4}},
        ],
    }


def test_multi_unit_declared_flowsheet_closure():
    response = validate_process_network(**_network())
    assert response["result"] == "declared_network_consistent_but_unverified"
    assert response["topological_unit_order"] == ["mix", "split"]
    assert len(response["unit_results"]) == 2
    assert response["global_balance"]["overall"]["residual_kg_h"] == 0
    assert all(row["conservation_result"] == "consistent_declared_flows"
               for row in response["unit_results"])
    assert response["blocking_findings"] == []
    assert response["process_behavior_simulated"] is False
    assert response["reaction_stoichiometry_modeled"] is False
    assert response["release_authorized"] is False


def test_mass_inconsistency_blocks_without_fabricating_mixing():
    item = _network()
    item["streams"][2]["components_kg_h"]["water"] = 2.5
    report = validate_process_network(**item)
    assert report["result"] == "declared_network_blocked"
    assert any(row["code"] == "unit_declared_component_balance_failed"
               for row in report["blocking_findings"])


def test_component_swap_blocks_even_if_mass_totals_match():
    item = _network()
    item["streams"][3]["components_kg_h"] = {"water": 0.1, "NaCl": 1}
    report = validate_process_network(**item)
    assert report["result"] == "declared_network_blocked"
    assert any(row["component_id"] == "NaCl" and not row["balanced"]
               for unit in report["unit_results"]
               for row in unit["components"])


@pytest.mark.parametrize("mutation", [
    lambda d: d["streams"].append({
        "stream_id": "water", "source_unit_id": "split",
        "target_unit_id": None, "components_kg_h": {"water": 1},
    }),
    lambda d: d["streams"][0].update({"target_unit_id": "missing"}),
    lambda d: d["streams"][0].update({"target_unit_id": None}),
    lambda d: d["streams"][0]["components_kg_h"].update({"water": float("nan")}),
    lambda d: d["streams"][0]["components_kg_h"].update({"water": -2}),
    lambda d: d["units"][0].update({"kind": "unknown"}),
    lambda d: d["streams"][2].update({"source_unit_id": "split", "target_unit_id": "mix"}),
])
def test_invalid_graph_invariants_are_rejected(mutation):
    network = _network()
    mutation(network)
    with pytest.raises(ValueError):
        validate_process_network(**network)


def test_process_graph_api_and_mcp_task():
    app = create_product_app()
    client = TestClient(app)
    response = client.post("/v1/engineering/chemical/process/network/validate", json=_network())
    assert response.status_code == 200, response.text
    assert response.json()["result"] == "declared_network_consistent_but_unverified"
    op = next(row for row in operation_catalog(app)
              if row["path"] == "/v1/engineering/chemical/process/network/validate")
    manifest = task_operation_manifest("chemical_process_review", app)
    assert op["operation_id"] in manifest["workflow_operation_ids"]
    assert manifest["authority_contract"]["automatic_execution"] is False

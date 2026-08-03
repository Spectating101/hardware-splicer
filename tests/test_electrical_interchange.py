from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.electrical_interchange import electrical_design_from_interchange
from hardware_splicer.integrations.circuit_json_import import circuit_json_to_netlist
from hardware_splicer.machine_project import AuthorityState

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app

FIXTURE = Path(__file__).parent / "fixtures" / "upstream_circuit_json.json"


def _documents() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _design(documents: list[dict] | None = None):
    docs = documents or _documents()
    netlist = circuit_json_to_netlist(docs, source="upstream_fixture")
    return electrical_design_from_interchange(
        netlist,
        docs,
        project_id="identity-demo",
    )


def test_projects_source_graph_into_stable_canonical_electrical_identity() -> None:
    design = _design()

    components = {component.reference: component for component in design.components}
    assert components["J1"].component_id == (
        "electrical:source-component:source_component_0"
    )
    assert components["R1"].component_id == (
        "electrical:source-component:source_component_1"
    )
    assert components["LED1"].component_id == (
        "electrical:source-component:source_component_2"
    )
    assert components["J1"].metadata["identity"] == {
        "canonical_component_id": "electrical:source-component:source_component_0",
        "source_component_id": "source_component_0",
        "kicad_reference": "J1",
        "module_id": "simple_chip",
    }

    identity = design.metadata["identity_map"]
    assert identity["pins_by_key"]["J1.1"] == (
        "electrical:source-port:source_port_0"
    )
    assert identity["pins_by_key"]["LED1.2"] == (
        "electrical:source-port:source_port_5"
    )
    assert identity["nets_by_name"]["VBUS"] == (
        "electrical:source-net:source_net_0"
    )
    assert identity["nets_by_name"]["GND"] == (
        "electrical:source-net:source_net_1"
    )
    assert identity["nets_by_name"]["R1.2 to LED1.anode"].startswith(
        "electrical:net:"
    )


def test_preserves_reciprocal_pin_net_membership_and_proposed_authority() -> None:
    design = _design()
    pins = {pin.pin_id: pin for pin in design.pins}

    assert len(design.components) == 3
    assert len(design.pins) == 6
    assert len(design.nets) == 3
    assert all(component.authority is AuthorityState.PROPOSED for component in design.components)
    assert all(pin.authority is AuthorityState.PROPOSED for pin in design.pins)
    assert all(net.authority is AuthorityState.PROPOSED for net in design.nets)
    assert design.metadata["authority_ceiling"] == "proposed"

    for component in design.components:
        for pin_id in component.pin_ids:
            assert pins[pin_id].component_id == component.component_id

    for net in design.nets:
        for pin_id in net.pin_ids:
            assert pins[pin_id].net_id == net.net_id

    warning = design.metadata["import_diagnostics"]["upstream_diagnostics"][0]
    assert warning["type"] == "source_pin_missing_trace_warning"
    assert warning["source_component_id"] == "source_component_0"


def test_direct_trace_identity_is_deterministic() -> None:
    first = _design()
    second = _design()

    assert first.metadata["identity_map"] == second.metadata["identity_map"]
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_duplicate_source_port_is_unresolved_without_replacing_first_identity() -> None:
    documents = _documents()
    documents.append(
        {
            "type": "source_port",
            "source_port_id": "source_port_duplicate",
            "source_component_id": "source_component_0",
            "name": "VBUS_DUPLICATE",
            "pin_number": 1,
        }
    )

    design = _design(documents)

    assert design.metadata["identity_map"]["pins_by_key"]["J1.1"] == (
        "electrical:source-port:source_port_0"
    )
    ambiguity = next(
        row
        for row in design.metadata["unresolved_identity"]
        if row["kind"] == "ambiguous_source_port"
    )
    assert ambiguity["pin_key"] == "J1.1"
    assert ambiguity["source_port_ids"] == [
        "source_port_0",
        "source_port_duplicate",
    ]


def test_product_api_returns_canonical_identity_and_erc() -> None:
    client = TestClient(create_product_app())
    response = client.post(
        "/v1/interchange/circuit-json/electrical-design",
        json={
            "project_id": "identity-demo",
            "documents": _documents(),
            "source_label": "upstream_fixture",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "hardware_splicer.electrical_interchange.v1"
    assert body["authority"] == "proposed"
    assert body["summary"]["component_count"] == 3
    assert body["summary"]["pin_count"] == 6
    assert body["summary"]["net_count"] == 3
    assert body["summary"]["unresolved_identity_count"] == 0
    assert body["identity_map"]["components_by_reference"]["R1"] == (
        "electrical:source-component:source_component_1"
    )
    assert body["electrical_design"]["project_id"] == "identity-demo"
    assert body["electrical_design"]["metadata"]["authority_ceiling"] == "proposed"

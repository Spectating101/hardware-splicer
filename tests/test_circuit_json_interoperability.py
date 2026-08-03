from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.integrations.circuit_json_import import circuit_json_to_netlist

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app

FIXTURE = Path(__file__).parent / "fixtures" / "upstream_circuit_json.json"


def _documents() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_imports_upstream_source_port_trace_and_net_graph() -> None:
    netlist = circuit_json_to_netlist(_documents(), source="upstream_fixture")

    assert [component.ref for component in netlist.components] == ["J1", "R1", "LED1"]
    assert netlist.components[1].value == "1kΩ"
    assert netlist.components[1].metadata["source_component_id"] == "source_component_1"

    nets = {net.name: {pin.key() for pin in net.pins} for net in netlist.nets}
    assert nets["VBUS"] == {"J1.1", "R1.1"}
    assert nets["GND"] == {"J1.2", "LED1.2"}
    assert nets["R1.2 to LED1.anode"] == {"R1.2", "LED1.1"}

    metadata = netlist.metadata["circuit_json"]
    assert metadata["source_component_count"] == 3
    assert metadata["source_port_count"] == 6
    assert metadata["source_trace_count"] == 5
    assert metadata["imported_net_count"] == 3
    assert metadata["upstream_diagnostics"][0]["type"] == "source_pin_missing_trace_warning"


def test_import_records_unresolved_ports_without_inventing_connectivity() -> None:
    documents = _documents()
    documents.append(
        {
            "type": "source_trace",
            "source_trace_id": "source_trace_missing",
            "connected_source_port_ids": ["source_port_does_not_exist"],
            "connected_source_net_ids": ["source_net_0"],
        }
    )

    netlist = circuit_json_to_netlist(documents)
    diagnostics = netlist.metadata["circuit_json"]
    assert diagnostics["unresolved_trace_ports"] == [
        {
            "trace_id": "source_trace_missing",
            "source_port_ids": ["source_port_does_not_exist"],
        }
    ]
    vbus = next(net for net in netlist.nets if net.name == "VBUS")
    assert {pin.key() for pin in vbus.pins} == {"J1.1", "R1.1"}


def test_import_preserves_legacy_simplified_documents() -> None:
    documents = [
        {
            "type": "source_component",
            "source_component_id": "u1",
            "name": "U1",
            "footprint": "U1",
        },
        {
            "type": "source_component",
            "source_component_id": "u2",
            "name": "U2",
            "footprint": "U2",
        },
        {
            "type": "schematic_trace",
            "source_net_id": "SIGNAL",
            "connected_source_port_ids": ["U1.1", "U2.2"],
        },
    ]

    netlist = circuit_json_to_netlist(documents)
    assert len(netlist.nets) == 1
    assert netlist.nets[0].name == "SIGNAL"
    assert {pin.key() for pin in netlist.nets[0].pins} == {"U1.1", "U2.2"}


def test_product_api_exposes_interchange_and_review_routes_together() -> None:
    client = TestClient(create_product_app())
    inspection = client.post(
        "/v1/interchange/circuit-json/inspect",
        json={"documents": _documents(), "source_label": "test_fixture"},
    )

    assert inspection.status_code == 200
    body = inspection.json()
    assert body["status"] == "review_required"
    assert body["compilable"] is True
    assert body["authority"] == "proposed"
    assert body["summary"] == {
        "document_count": len(_documents()),
        "component_count": 3,
        "net_count": 3,
        "unresolved_count": 0,
        "single_pin_net_count": 0,
        "upstream_diagnostic_count": 1,
    }
    assert body["netlist"]["metadata"]["interchange"] == "circuit-json"

    route_paths = {
        path
        for route in client.app.routes
        if (path := getattr(route, "path", None)) is not None
    }
    assert "/v1/interchange/circuit-json/inspect" in route_paths
    assert "/v1/build-files/engineering-review/status" in route_paths
    assert "/v1/build-files/engineering-review/run" in route_paths


def test_product_api_surfaces_incomplete_source_graph() -> None:
    documents = [
        {
            "type": "source_component",
            "source_component_id": "source_component_0",
            "name": "U1",
        },
        {
            "type": "source_port",
            "source_port_id": "source_port_0",
            "source_component_id": "source_component_0",
            "name": "OUT",
            "pin_number": 1,
        },
        {
            "type": "source_net",
            "source_net_id": "source_net_0",
            "name": "OUT",
            "member_source_group_ids": [],
        },
        {
            "type": "source_trace",
            "source_trace_id": "source_trace_0",
            "connected_source_port_ids": ["source_port_0"],
            "connected_source_net_ids": ["source_net_0"],
        },
    ]
    client = TestClient(create_product_app())
    response = client.post(
        "/v1/interchange/circuit-json/inspect",
        json={"documents": documents},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["compilable"] is False
    assert body["summary"]["single_pin_net_count"] == 1

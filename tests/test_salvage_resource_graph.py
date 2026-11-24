from __future__ import annotations

import pytest

from hardware_splicer.donor_errors import DonorValidationError
from hardware_splicer.salvage_resource_graph import (
    _project_salvage_resource_graph, build_salvage_resource_graph, resource_index,
)


def _graph():
    return _project_salvage_resource_graph(
        project_id="resource-test",
        donors=[
            {
                "donor_id": "donor:printer:switch",
                "label": "Printer front-panel switch",
                "contract_state": "partial",
                "capabilities": [{"role": "momentary_button", "grade": "document"}],
                "missing_facts": ["signals.SW1.voltage_max_v"],
            }
        ],
        fabrication_resources=[
            {
                "operator_id": "printer-1",
                "kind": "printer",
                "display_name": "Bench FDM printer",
                "capabilities": ["fdm.print"],
                "limits": {"x_mm": 220, "y_mm": 220, "z_mm": 250},
                "available": True,
                "simulated_only": False,
            },
            {
                "operator_id": "meter-1",
                "kind": "instrument",
                "display_name": "Bench meter",
                "capabilities": ["measure.voltage"],
                "limits": {"max_voltage_v": 30},
                "available": False,
                "simulated_only": False,
            },
        ],
    )


def test_resource_graph_is_projection_and_preserves_donor_uncertainty():
    graph = _graph()
    assert graph["truth_contract"]["projection_only"] is True
    assert graph["truth_contract"]["persists_independent_truth"] is False
    assert graph["truth_contract"]["availability_grants_physical_authority"] is False

    indexed = resource_index(graph)
    donor = indexed["donor:printer:switch"]
    assert donor["kind"] == "donor"
    assert donor["support"]["weakest_grade"] == "document"
    assert donor["capabilities"][0]["capability_id"] == "donor.role:momentary_button"
    assert donor["unresolved_facts"] == ["signals.SW1.voltage_max_v"]
    assert donor["usable_for_architecture"] is True
    assert donor["verified_for_ready"] is False
    assert donor["grants_physical_authority"] is False

    printer = indexed["operator:printer-1"]
    assert printer["support"]["kind"] == "caller_supplied_descriptor"
    assert printer["available"] is True
    assert printer["grants_physical_authority"] is False


def test_built_graph_never_marks_an_unevidenced_donor_ready(tmp_path):
    from test_mission_feedback import _store

    missions = _store(tmp_path)
    graph = build_salvage_resource_graph(
        project_store=missions.project_store,
        project_id="monitor",
        donor_references=[{"donor_id": "donor:radio:buttons", "label": "Buttons"}],
    )
    donor = resource_index(graph)["donor:radio:buttons"]
    assert donor["contract_state"] == "unknown"
    assert donor["usable_for_architecture"] is False
    assert donor["verified_for_ready"] is False
    assert donor["grants_physical_authority"] is False


def test_lab_tool_descriptors_are_recorded_as_unverified_and_malformed_ones_rejected():
    graph = _graph()
    printer = resource_index(graph)["operator:printer-1"]
    assert printer["source"]["kind"] == "caller_supplied_descriptor"
    assert graph["truth_contract"]["lab_truth_owner"] == "caller_supplied_descriptor_unverified"
    with pytest.raises(DonorValidationError):
        _project_salvage_resource_graph(
            project_id="monitor", donors=[],
            fabrication_resources=[{"operator_id": "x", "display_name": "x", "capabilities": ["a"],
                                    "available": "yes", "simulated_only": False}],
        )

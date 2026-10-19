from __future__ import annotations

import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.salvage_investigation import project_investigation_queue
from hardware_splicer.salvage_resource_graph import project_salvage_resource_graph


def _graph():
    return project_salvage_resource_graph(
        project_id="test-salvage",
        donors=[
            {"donor_id": "donor:b", "label": "Motor", "contract_state": "partial",
             "missing_facts": ["voltage", "pinout", "pinout"], "capabilities": []},
            {"donor_id": "donor:a", "label": "Mystery", "contract_state": "unknown",
             "missing_facts": [], "capabilities": []},
        ],
    )


def test_queue_is_deterministic_and_does_not_promote_truth():
    graph = _graph()
    before = repr(graph)
    first = project_investigation_queue(graph)
    assert first == project_investigation_queue(graph)
    assert repr(graph) == before
    assert [(x["resource_id"], x["missing_fact"]) for x in first["items"]] == [
        ("donor:a", "contract"), ("donor:b", "pinout"), ("donor:b", "voltage")
    ]
    assert all(x["verified"] is False and x["physical_authority_granted"] is False
               and x["suggested_physical_action"] is None for x in first["items"])


def test_queue_caps_output_without_losing_unresolved_count():
    result = project_investigation_queue(_graph(), max_items=1)
    assert len(result["items"]) == 1
    assert result["total_unresolved"] == 3
    assert result["truncated"] is True


@pytest.mark.parametrize("limit", [0, 129, True, 1.5])
def test_invalid_limits_fail_closed(limit):
    with pytest.raises(FabricationValidationError):
        project_investigation_queue(_graph(), max_items=limit)


def test_lab_tools_are_not_donor_investigations():
    graph = project_salvage_resource_graph(project_id="test-salvage", donors=[],
        fabrication_resources=[{"operator_id": "scope", "display_name": "Oscilloscope",
                                "capabilities": ["measure_voltage"], "available": True,
                                "simulated_only": False}])
    assert project_investigation_queue(graph)["items"] == []

from __future__ import annotations

import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.fabrication_option_tradeoff import FabricationOptionTradeoff
from hardware_splicer.procurement_quotes import ProcurementQuoteBook
from hardware_splicer.salvage_resource_graph import project_salvage_resource_graph, resource_index


def _graph():
    return project_salvage_resource_graph(
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


def _quotes() -> ProcurementQuoteBook:
    quotes = ProcurementQuoteBook()
    quotes.add(
        quote_id="q-mcu",
        supplier_id="supplier-a",
        part_key="mcu",
        currency="USD",
        unit_price="5.00",
        stock_quantity=100,
        lead_time_days=2,
        source_ref="snapshot-1",
        observed_at="2026-10-17T00:00:00+00:00",
    )
    return quotes


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
    assert printer["support"]["kind"] == "server_configuration"
    assert printer["available"] is True
    assert printer["grants_physical_authority"] is False


def test_tradeoff_derives_resource_burden_instead_of_trusting_agent_counts():
    graph = _graph()
    tradeoff = FabricationOptionTradeoff(procurement=_quotes())
    comparison = tradeoff.compare(
        options=[
            {
                "option_id": "clean",
                "kind": "clean_sheet",
                "bom": [{"part_key": "mcu", "quantity": 1}],
                "resource_refs": ["operator:printer-1"],
                "unresolved_evidence": 0,
                "fabrication_operations": 1,
                "manual_steps": 2,
            },
            {
                "option_id": "reclaim",
                "kind": "reclaim_heavy",
                "bom": [{"part_key": "mcu", "quantity": 1}],
                "resource_refs": ["donor:printer:switch", "operator:meter-1"],
                "unresolved_evidence": 0,
                "fabrication_operations": 1,
                "manual_steps": 2,
            },
        ],
        currency="USD",
        as_of="2026-10-17T01:00:00+00:00",
        resource_graph=graph,
    )
    assert comparison["resource_graph_used"] is True
    reclaim = next(row for row in comparison["options"] if row["option_id"] == "reclaim")
    assert reclaim["metrics"]["resource_dependencies"] == 2
    assert reclaim["metrics"]["donor_dependencies"] == 1
    assert reclaim["metrics"]["unresolved_resource_facts"] == 1
    assert reclaim["metrics"]["unavailable_resource_dependencies"] == 1


def test_tradeoff_rejects_agent_donor_count_that_disagrees_with_graph():
    tradeoff = FabricationOptionTradeoff(procurement=_quotes())
    with pytest.raises(FabricationValidationError, match="donor_dependencies disagrees"):
        tradeoff.compare(
            options=[
                {
                    "option_id": "reclaim",
                    "kind": "reclaim_heavy",
                    "bom": [{"part_key": "mcu", "quantity": 1}],
                    "resource_refs": ["donor:printer:switch"],
                    "donor_dependencies": 0,
                    "unresolved_evidence": 0,
                    "fabrication_operations": 1,
                    "manual_steps": 1,
                },
                {
                    "option_id": "clean",
                    "kind": "clean_sheet",
                    "bom": [{"part_key": "mcu", "quantity": 1}],
                    "resource_refs": [],
                    "unresolved_evidence": 0,
                    "fabrication_operations": 1,
                    "manual_steps": 1,
                },
            ],
            currency="USD",
            as_of="2026-10-17T01:00:00+00:00",
            resource_graph=_graph(),
        )


def test_resource_refs_fail_closed_without_graph_or_on_unknown_id():
    tradeoff = FabricationOptionTradeoff(procurement=_quotes())
    options = [
        {
            "option_id": "a",
            "kind": "clean_sheet",
            "bom": [{"part_key": "mcu", "quantity": 1}],
            "resource_refs": ["operator:printer-1"],
            "unresolved_evidence": 0,
            "fabrication_operations": 1,
            "manual_steps": 1,
        },
        {
            "option_id": "b",
            "kind": "hybrid",
            "bom": [{"part_key": "mcu", "quantity": 1}],
            "resource_refs": [],
            "unresolved_evidence": 0,
            "fabrication_operations": 1,
            "manual_steps": 1,
        },
    ]
    with pytest.raises(FabricationValidationError, match="resource_refs require resource_graph"):
        tradeoff.compare(options=options, currency="USD")

    options[0]["resource_refs"] = ["operator:not-registered"]
    with pytest.raises(FabricationValidationError, match="unknown resource_ref"):
        tradeoff.compare(options=options, currency="USD", resource_graph=_graph())

"""Prospective economics only: advertised prices cannot authorize purchasing."""
import copy
import json
import math
from pathlib import Path

import pytest

from hardware_splicer.salvage_purchase_screen import (
    PurchaseScreenRefused, SCHEMA, screen, sensitivity,
)

INPUT = Path(__file__).resolve().parents[1] / "docs/research/tw_salvage_sourcing_scenarios_2026-10-19.json"


def scenarios():
    data = json.loads(INPUT.read_text())
    assert data["schema_version"] == "hardware_splicer.salvage_sourcing_research.v1"
    return {x["id"]: x for x in data["opportunities"]}


def test_research_frozen_listing_pairs_and_all_scores():
    rows = scenarios()
    assert len(rows) == 5
    assert all(x["source_urls"] for x in rows.values())
    results = {key: screen(row) for key, row in rows.items()}
    assert all(x["purchase_authorized"] is False for x in results.values())
    assert all(x["acquisition_price_basis"] == "advertised_asking_price" for x in results.values())
    assert results["tsc-ttp244plus-budget-fault"]["expected_net_per_acquired_unit_twd"] == 339
    assert results["tsc-ttp244plus-budget-fault"]["max_purchase_for_target_profit_twd"] == 539
    assert results["brother-ql800-untested"]["expected_net_per_acquired_unit_twd"] == 24.25
    assert results["hp-p1505n-failed"]["expected_net_per_acquired_unit_twd"] == -476
    assert results["acer-sa241y-broken-display"]["expected_net_per_acquired_unit_twd"] == -480
    assert results["old-parts-only-laptop"]["expected_net_per_acquired_unit_twd"] == -667


def test_yield_downside_rejects_fake_high_expected_profit():
    tsc = scenarios()["tsc-ttp244plus-budget-fault"]
    ref = screen(tsc)
    weak = {**tsc, "success_yield": 0.4, "modeled_sale_twd": 2200}
    assert screen(weak)["expected_net_per_acquired_unit_twd"] < 0
    assert screen(weak)["break_even_max_purchase_twd"] < tsc["ask_twd"]
    assert ref["status"] == "INSUFFICIENT_SAME_MODEL_COMPS"


def test_max_bid_equals_expected_net_at_zero_and_target_bid_at_target_profit():
    row = scenarios()["tsc-ttp244plus-budget-fault"]
    score = screen(row)
    neutral = {**row, "ask_twd": score["break_even_max_purchase_twd"]}
    assert screen(neutral)["expected_net_per_acquired_unit_twd"] == 0
    target = {**row, "ask_twd": score["max_purchase_for_target_profit_twd"]}
    assert screen(target)["expected_net_per_acquired_unit_twd"] == 300


def test_sale_breakeven_sensitivity_is_monotonic():
    row = scenarios()["brother-ql800-untested"]
    base = screen(row)
    lower = screen({**row, "modeled_sale_twd": row["modeled_sale_twd"] - 200})
    higher = screen({**row, "modeled_sale_twd": row["modeled_sale_twd"] + 200})
    assert lower["expected_net_per_acquired_unit_twd"] < base["expected_net_per_acquired_unit_twd"]
    assert higher["expected_net_per_acquired_unit_twd"] > base["expected_net_per_acquired_unit_twd"]
    assert abs(screen({**row, "modeled_sale_twd": base["minimum_sale_to_break_even_twd"]})["expected_net_per_acquired_unit_twd"]) <= 0.01


@pytest.mark.parametrize("field,value", [
    ("success_yield", 1.2),
    ("platform_fee_rate", 1.001),
    ("ask_twd", -1),
    ("modeled_sale_twd", None),
    ("labor_rate_twd_hour", float("nan")),
    ("outbound_shipping_twd", float("inf")),
    ("successful_labor_hours", True),
])
def test_invalid_uncertainty_or_cost_does_not_turn_into_zero(field, value):
    row = {**scenarios()["tsc-ttp244plus-budget-fault"], field: value}
    with pytest.raises(PurchaseScreenRefused):
        screen(row)


def test_no_comparable_cannot_be_labeled_verified():
    row = scenarios()["brother-ql800-untested"]
    assert screen(row)["status"] == "INSUFFICIENT_SAME_MODEL_COMPS"
    with pytest.raises(PurchaseScreenRefused):
        screen({**row, "working_comparable": "brand_new_retail_equal_to_resale"})


def test_calculator_does_not_guess_source_purchase_status():
    row = scenarios()["old-parts-only-laptop"]
    with pytest.raises(PurchaseScreenRefused):
        screen({**row, "source_ask_status": "sold_price_verified"})


def test_sensitivity_is_stated_scenarios_not_forecasts():
    row = scenarios()["tsc-ttp244plus-budget-fault"]
    output = sensitivity(row)
    assert len(output) == 9
    assert all("assumed_success_yield" in x and "sale_factor" in x for x in output)
    assert output[0]["expected_net_twd"] < output[-1]["expected_net_twd"]
    assert screen(row)["purchase_authorized"] is False

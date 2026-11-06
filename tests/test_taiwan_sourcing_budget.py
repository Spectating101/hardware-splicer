"""Sourcing arithmetic, stale availability, model confusion and truth boundaries."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.taiwan_sourcing_budget import SourcingEvidenceError, calculate

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "examples/cyberdeck/dual_touch/sourcing/taiwan_snapshot_20261106.json"
SNAP = FILE.read_bytes()


def change(fn):
    v = json.loads(SNAP)
    fn(v)
    return json.dumps(v, ensure_ascii=False).encode()


def test_real_source_scenarios_recalculate_and_buyer_boundaries_hold():
    r = calculate(SNAP)
    assert r["architecture"] == "dual_esp32_touch_4p3_rs485"
    assert r["manufacturer_sku"] == "25948"
    assert r["non_touch_not_equivalent_sku"] == "30493"
    assert r["scenarios"]["one_board_bench"]["total_twd"] == 2058
    assert r["scenarios"]["two_board_bench"]["total_twd"] == 3827
    assert r["scenarios"]["full_exterior_concept"]["total_twd"] == 4277
    assert r["scenarios"]["unavailable_icshop_price_counterfactual"]["total_twd"] == 3477
    assert all(not x["delivered_quote"] and not x["inventory_orderable"] for x in r["scenarios"].values())
    assert not r["purchase_authorized"]
    assert not r["physical_release_authorized"]
    assert r["no_battery_integrated"]


@pytest.mark.parametrize("patch", [
    lambda x: x.update(orders_placed=1),
    lambda x: x.update(quotes_obtained=2),
    lambda x: x.update(exact_retail_stock_confirmed=True),
    lambda x: x.update(purchase_authorized=True),
    lambda x: x.update(parts_received=1),
])
def test_cannot_claim_purchase_or_confirmed_stock(patch):
    with pytest.raises(SourcingEvidenceError):
        calculate(change(patch))


def test_non_touch_variant_never_replaces_touchscreen():
    def wrong(x):
        next(y for y in x["sources"] if y["id"] == "waveshare_25948")["sku"] = "30493"
    with pytest.raises(SourcingEvidenceError, match="manufacturer"):
        calculate(change(wrong))


def test_seller_variant_price_min_cannot_be_silently_claimed_as_touch_price():
    def wrong(x):
        next(y for y in x["components"] if y["id"] == "display_boards")["unit_twd"] = 1371
    with pytest.raises(SourcingEvidenceError, match="upper price envelope"):
        calculate(change(wrong))


def test_local_sold_out_price_cannot_be_called_in_stock():
    def wrong(x):
        next(y for y in x["sources"] if y["id"] == "icshop_25948")["availability"] = "IN_STOCK"
    with pytest.raises(SourcingEvidenceError, match="orderable"):
        calculate(change(wrong))


def test_priced_print_150g_is_not_fabrication_quote():
    def wrong(x):
        next(y for y in x["sources"] if y["id"] == "wancai_petg")["weight_known"] = True
    with pytest.raises(SourcingEvidenceError, match="slicing"):
        calculate(change(wrong))


def test_budget_cannot_assign_fictional_3d_print_total():
    def wrong(x):
        next(y for y in x["components"] if y["id"] == "printed_shells_petg")["unit_twd"] = 1
    with pytest.raises(SourcingEvidenceError, match="PETG"):
        calculate(change(wrong))


def test_no_unknown_part_codes_or_negative_cash():
    def wrong(x):
        x["components"][0]["source_id"] = "no_real_vendor"
    with pytest.raises(SourcingEvidenceError, match="unknown source"):
        calculate(change(wrong))
    def bad_price(x):
        x["components"][0]["unit_twd"] = -150
    with pytest.raises(SourcingEvidenceError, match="invalid money"):
        calculate(change(bad_price))


def test_no_silent_pi_reference_reclassification():
    def wrong(x):
        x["comparison_ref_architecture"] = x["architecture"]
    with pytest.raises(SourcingEvidenceError, match="Pi5"):
        calculate(change(wrong))

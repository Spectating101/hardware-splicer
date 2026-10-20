"""A repair-spread advertisement cannot turn into an automatically safe purchase."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.evaluate_repair_arbitrage import score

SOURCE=json.loads((Path(__file__).resolve().parents[1]/"examples/procurement/taiwan_repair_resale_arbitrage_20261020.json").read_text())
def evaluated():return score(SOURCE)["results"]

def test_cheap_nonboot_iphone_not_mistaken_for_profit():
 d={v["id"]:v for v in evaluated()}
 p=d["iphone12_nonboot_broken_screen_lot"]
 assert p["seller_ask_twd"]==699
 assert p["expected_contribution_at_observed_ask_or_test_bid_twd"]<0
 assert p["decision"]=="REJECT_LOCK_IDENTITY_UNVERIFIED"
 assert p["max_purchase_price_for_target_expected_contribution_twd"]==0
 assert not p["buy_authorized"]

def test_laptop_and_psp_are_losing_at_seller_asks():
 d=evaluated()
 for id in ("lenovo_b51_30_nonboot_parts_laptop","psp1007_umd_drive_fault"):
  r=next(v for v in d if v["id"]==id)
  assert r["decision"]=="REJECT_LISTED_ASK"
  assert r["max_purchase_price_for_target_expected_contribution_twd"]<r["seller_ask_twd"]
  assert r["expected_contribution_at_observed_ask_or_test_bid_twd"]<0

def test_diagnosed_switch_only_a_target_not_real_offer():
 r=next(v for v in evaluated() if v["id"]=="switch_lite_joystick_only_target")
 assert r["seller_ask_twd"] is None
 assert r["conditional_hypothetical_bid_twd"]==1600
 assert r["max_purchase_price_for_target_expected_contribution_twd"]>1600
 assert r["decision"]=="NO_ACTUAL_DONOR_FOUND"
 assert r["buy_authorized"] is False

def test_undervalued_iphone_conditional_screen_can_still_fail_hurdle():
 r=next(v for v in evaluated() if v["id"]=="iphone12_visible_boot_single_screen_target")
 assert r["expected_contribution_at_observed_ask_or_test_bid_twd"]<250
 assert r["seller_ask_twd"] is None
 assert r["max_purchase_price_for_target_expected_contribution_twd"]<1800
 assert r["decision"]=="NO_ACTUAL_DONOR_FOUND"

def test_zero_probability_means_salvage_only_and_positive_price_not_guarantee():
 x=deepcopy(SOURCE)
 row=x["cases"][3]
 row["successful_repair_probability_assumed"]=0.0
 r=score(x)["results"][3]
 assert r["unit_profit_if_repair_succeeds_twd"] is not None
 assert r["expected_contribution_at_observed_ask_or_test_bid_twd"] == (
   r["unit_loss_if_repair_fails_twd"]
 )
 assert not r["buy_authorized"]

def test_must_not_conflate_seller_ask_and_executed_revenue():
 a=score(SOURCE)
 assert a["resale_actual_executed_sales"]==0
 assert a["real_donors_acquired"]==0
 assert a["real_repair_yields_observed"]==0
 assert a["no_purchases_approved"]

@pytest.mark.parametrize("key,value",[
 ("successful_repair_probability_assumed",1.2),
 ("successful_repair_probability_assumed",-0.1),
 ("resale_target_twd",-100),
 ("part_cost_estimate_twd",float("nan")),
 ("shipping_out_twd",-20),
])
def test_invalid_arbitrage_numbers_rejected(key,value):
 x=deepcopy(SOURCE)
 x["cases"][0][key]=value
 with pytest.raises(ValueError):
  score(x)

def test_higher_failure_risk_reduces_allowed_bid():
 a=deepcopy(SOURCE)
 b=deepcopy(SOURCE)
 a["cases"][3]["successful_repair_probability_assumed"]=0.65
 b["cases"][3]["successful_repair_probability_assumed"]=0.95
 assert score(a)["results"][3]["max_purchase_price_for_target_expected_contribution_twd"] < score(b)["results"][3]["max_purchase_price_for_target_expected_contribution_twd"]

def test_price_higher_than_bid_ceiling_is_not_buy_signal():
 a=deepcopy(SOURCE)
 a["cases"][3]["source_purchase_twd"]=2800
 r=score(a)["results"][3]
 assert r["decision"]=="REJECT_LISTED_ASK"
 assert r["expected_contribution_at_observed_ask_or_test_bid_twd"]<250
 assert r["buy_authorized"] is False

"""Screen repair/flipping acquisitions from cited seller asks and explicitly hypothetical repair risks.

MaxBid(EV target) = p * net_success_before_bid + (1-p) * net_failure_before_bid - target;
both success and failure contain the same acquisition cost. Never turn an
unknown fault into a certain repair, or a listed asking price into observed
transaction price.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path

def value(v,label):
 if type(v) not in (int,float) or not math.isfinite(v) or v < 0:
  raise ValueError("invalid "+label)
 return float(v)

def score(data:dict):
 if data.get("authority")!="SELLER_LISTED_PRICES_NOT_ACTUAL_SALES":
  raise ValueError("observed resale authority not supported")
 fee=value(data["default_marketplace_fee_fraction_assumed"],"fee")
 if fee>=1:raise ValueError("fee >= 100%")
 target=value(data["target_expected_contribution_twd"],"target")
 results=[]
 for case in data["cases"]:
  p=value(case["successful_repair_probability_assumed"],"p")
  if p>1:raise ValueError("p > 1")
  sale=value(case["resale_target_twd"],"resale ask")
  parts=value(case["part_cost_estimate_twd"],"parts")
  salvage=value(case["failure_salvage_value_assumed_twd"],"salvage")
  inbound=value(case["shipping_in_twd"],"inbound")
  outbound=value(case["shipping_out_twd"],"outbound")
  labor=value(case["successful_repair_labor_twd"],"labor")
  diag=value(case["failed_diagnosis_labor_twd"],"diag")
  reserve=value(case["warranty_return_reserve_twd"],"reserve")
  success_before_bid=sale*(1-fee)-parts-inbound-outbound-labor-reserve
  failure_before_bid=salvage-inbound-diag
  weighted=p*success_before_bid+(1-p)*failure_before_bid
  maxbid=max(0,weighted-target)
  asking=case.get("source_purchase_twd")
  candidate=case.get("candidate_test_bid_twd")
  if asking is not None:asking=value(asking,"seller ask")
  if candidate is not None:candidate=value(candidate,"hypothetical bid")
  offer=asking if asking is not None else candidate
  failed_if_bought=round(failure_before_bid-offer,2) if offer is not None else None
  prof_if_bought=round(success_before_bid-offer,2) if offer is not None else None
  expected_if_bought=round(weighted-offer,2) if offer is not None else None
  threshold_at_observed_price=asking is not None and asking<=maxbid
  if asking is None:
   decision="NO_ACTUAL_DONOR_FOUND"
  elif threshold_at_observed_price:
   decision="REQUIRES_DIAGNOSTIC_AND_LEGAL_REVIEW"
  else:
   decision="REJECT_LISTED_ASK"
  if case.get("device_identity_legitimate") == "UNKNOWN":
   decision="REJECT_LOCK_IDENTITY_UNVERIFIED"
  results.append({
    "id":case["id"],"category":case["category"],
    "seller_ask_twd":asking,
    "conditional_hypothetical_bid_twd":candidate,
    "resale_seller_ask_reference_twd":sale,
    "repair_success_probability_is_hypothetical":p,
    "unit_profit_if_repair_succeeds_twd":prof_if_bought,
    "unit_loss_if_repair_fails_twd":failed_if_bought,
    "expected_contribution_at_observed_ask_or_test_bid_twd":expected_if_bought,
    "max_purchase_price_for_target_expected_contribution_twd":round(maxbid,2),
    "expected_repair_contribution_before_acquisition_cost_twd":round(weighted,2),
    "decision":decision,
    "buy_authorized":False,"device_actually_examined":False,
    "source_url":case.get("source_url"),"resale_comparator_url":case["resale_comparator_url"],
    "salvage_if_repair_fails_is_estimated":True,
    "profitability_is_not_validated":True,
    "hard_stop":case["hard_stop"]
  })
 return {
  "schema_version":"hs.repair_arbitrage_screen.v1",
  "target_expected_contribution_twd":target,
  "resale_actual_executed_sales":0,
  "real_donors_acquired":0,
  "real_repair_yields_observed":0,
  "customer_demand_unverified":True,
  "no_purchases_approved":True,
  "results":results
 }

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--input',required=True,type=Path)
 p.add_argument('--output',required=True,type=Path)
 a=p.parse_args()
 v=score(json.loads(a.input.read_text()))
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps(v,indent=2)+'\n')
 for row in v['results']:
  print(row['id'],"decision",row['decision'],"max_bid",row['max_purchase_price_for_target_expected_contribution_twd'],"EV",row['expected_contribution_at_observed_ask_or_test_bid_twd'])
if __name__=="__main__":main()

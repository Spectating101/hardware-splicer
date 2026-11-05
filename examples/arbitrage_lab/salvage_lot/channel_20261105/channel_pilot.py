"""HS live-source salvage channel: distinguish scrap buyback from stock-for-sale.

All economic outputs are conditional, not purchase instructions, predicted
repairs or realized profits. The real Circuit-AI salvage engine is invoked on
zero verified assets: market listings are never magically converted into stock.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
SOURCES=HERE/"sources.json"
SCHEMA="hs.salvage_channel.v1"

def _round(x:float)->int:
    return round(x)

def batch_unit(sources:dict, recover_probability:float, offered_price_twd:int|None=None)->dict:
    h=sources["commercial_hypotheses"]
    if not (0<=recover_probability<=1):
        raise ValueError("Recovery probability must be 0..1")
    b=h["assumed_negotiated_purchase_price_per_scrap_pc_twd"] if offered_price_twd is None else offered_price_twd
    if b<0:raise ValueError("Price must be >=0")
    n=h["example_batch_size"]
    c=h["buyer_costs_twd"]
    shipping=c["collection_transport_total"]/n
    ask=h["resale_price_assumption_per_success_twd"]
    success=ask*(1-h["seller_fee_rate"])-b-shipping-c["successful_test_refurb_labor"]-c["completion_parts_and_cleaning"]-c["packing_and_outbound"]-c["returns_reserve"]
    fail=-b-shipping-c["failed_triage_labor"]-c["failed_disposal"]
    expected=recover_probability*success+(1-recover_probability)*fail
    target=h["desired_expected_contribution_per_acquired_pc_twd"]
    max_bid=expected+b-target
    recovery_breakeven=(-fail)/(success-fail) if success>fail else None
    # upper limit on per-unit purchase bid for TARGET profit (all else constant)
    return {
        "price_per_unit_assumption_twd":b,
        "batch_size_hypothesis":n,
        "resale_asp_per_success_assumption_twd":ask,
        "probability_scenario":recover_probability,
        "net_if_functionally_verified_twd":_round(success),
        "loss_if_unrecoverable_twd":_round(fail),
        "expected_per_unit_twd":_round(expected),
        "expected_per_batch_twd":_round(expected*n),
        "break_even_success_probability":round(recovery_breakeven,4) if recovery_breakeven is not None else None,
        "max_price_per_unit_for_expected_target_twd":max(0, math.floor(max_bid)),
        "seller_sale_quote_obtained":False,
        "batch_obtained":False,
        "transfer_documented":False,
        "physical_passed_units":0,
        "commercial_authorization":"HOLD_NOT_ACTUAL_STOCK",
        "provenance":"Hypothetical five-PC bundle economics, not verified supply, price or yield"
    }

def whole_working_control(sources:dict, ask:dict, resale_asp:int, success_probability:float)->dict:
    if not (0<=success_probability<=1) or resale_asp<0:raise ValueError("invalid input")
    a=sources["used_acer_control_assumptions"]
    costs=(a["verification_and_cleaning_labor_twd"]+a["minor_parts_twd"]+
           a["outbound_packing_twd"]+a["warranty_reserve_twd"])
    success=resale_asp*(1-a["seller_fee_rate"])-ask["ask_price_twd"]-ask["shipping_scenario_twd"]-costs
    failure=-ask["ask_price_twd"]-ask["shipping_scenario_twd"]-200-100
    ev=success*success_probability+failure*(1-success_probability)
    required_p=(-failure)/(success-failure) if success>failure else None
    threshold=math.ceil((ask["ask_price_twd"]+ask["shipping_scenario_twd"]+costs)/(1-a["seller_fee_rate"]))
    return {
      "source":ask["source"],"product":ask["model"],
      "resale_price_assumption_twd":resale_asp,
      "recovery_probability_assumption":success_probability,
      "success_conditional_profit_twd":_round(success),
      "fail_loss_twd":_round(failure),
      "expected_contribution_twd":_round(ev),
      "asp_required_to_break_even_on_success_twd":threshold,
      "break_even_success_probability":round(required_p,4) if required_p is not None else None,
      "price_not_realized":True,
      "physically_validated":False,
      "commercial_authorization":"HOLD_CONDITION_UNVERIFIED",
      "comparability_warning":"High asking comparators have better GPU/storage/warranty; not a like-for-like resale target"
    }

def reject_unverified_ram(lead:dict)->dict:
    return {
        "source":lead["source"], "ask_twd":lead["ask_price_twd"],
        "identity_verified":False,"working_verified":False,"returns":False,
        "decision":"REJECT_BROKEN_RAM_WITH_UNKNOWN_CAPACITY_NO_TEST_FIXTURE",
        "minimum_budget":lead["ask_price_twd"]+lead["shipping_scenario_twd"],
        "component_salvage_revenue_proved":0,
        "physical_observations":0
    }

def commercial_status(s:dict)->list[dict]:
    out=[]
    for c in s["counterparties"]:
        out.append({
          "supplier":c["name"],
          "source":c["source"],
          "quote_direction":c["quote_direction"],
          "advertised_scrap_buyback_per_complete_pc_twd":(
            c["published_buyback_price_twd"]["complete_desktop"]
            if c["published_buyback_price_twd"] is not None else None),
          "is_this_an_offer_to_sell_scrap_to_HS":False,
          "available_lot_confirmed":c["available_refurb_lot_verified"],
          "disposition_rights_confirmed":c["consent_for_commercial_disposition_obtained"],
          "contact_sent":False,
          "status":"SUPPLIER_RFI_REQUIRED"
        })
    return out

def hs_inventory_readout()->dict:
    repo=HERE.parents[3]
    sys.path.insert(0,str(repo/"apps/circuit-ai"))
    try:
        from src.intelligence.salvage_splice_planner import SalvageSplicePlanner
        res=SalvageSplicePlanner().plan({"goal":"Use legitimately acquired and functionally tested salvage to build an actual product",
              "inventory":[],"use_llm":False,"use_llm_reasoner":False})
        return {"existing_engine":"Circuit-AI SalvageSplicePlanner",
                "verdict":res["verdict"],"real_inventory_count":0,
                "designs_authorized_as_real_products":0,"build_candidates":len(res["build_candidates"])}
    except Exception as exc:
        return {"existing_engine":"Circuit-AI SalvageSplicePlanner","verdict":"UNAVAILABLE",
                "real_inventory_count":0,"designs_authorized_as_real_products":0,
                "error":type(exc).__name__}

def compute(sources:dict)->dict:
    control=next(x for x in sources["candidate_listings"] if x["id"]=="acer_tc865_working_claimed")
    broken=next(x for x in sources["candidate_listings"] if x["id"]=="bade_unidentified_ddr4")
    batch=[batch_unit(sources,p) for p in sources["commercial_hypotheses"]["recovery_probabilities_for_sensitivity"]]
    whole=[whole_working_control(sources,control,asp,p)
           for asp in control["possible_resale_asking_scenarios_twd"] for p in (.8,.95)]
    return {
      "schema":SCHEMA,"as_of":sources["as_of"],
      "all_transaction_status":"NO_COMMERCIALLY_ACQUIRED_HARDWARE",
      "supplier_count":len(sources["counterparties"]),
      "confirmed_supplier_salvage_sale_quotes":0,
      "verified_scrap_pc_available":0,
      "confirmed_recovered_functional_products":0,
      "recycler_channels":commercial_status(sources),
      "verified_asking_price_comparables":False,
      "working_acer_conditional_scenarios":whole,
      "bade_ddr4":reject_unverified_ram(broken),
      "hypothetical_batch_recovery_scenarios":batch,
      "existing_engine":hs_inventory_readout(),
      "critical_next_questions":[
        "Does recycler have 3-5 legally transferable desktops from own stock, preferably i5 6th–8th gen with RAM and SSD? Sold per unit or by kilo?",
        "How much is the recycler's *selling price to HS* (NOT the advertised 140 NT buyback), including tax and transport?",
        "Can a small batch be inspected and single machines tested before money changes hands?",
        "Which machines have documented owner disposal/title and secure storage-data handling?",
        "Are units missing storage, RAM, CPU, PSU or front-panel cables? Request SKU-level model inventory and photos.",
        "Can irreparable units be returned or disposed through authorized channel? Confirm written policy."
      ],
      "disclosures":[
        "The publicly quoted recycler buyback price is NOT an HS acquisition price",
        "Full desktop model asks are NOT achieved resale prices",
        "Never turn public listings into confirmed physical inventory",
        "Probability inputs are made-up sensitivity assumptions, not measured business recovery rates",
        "No buyer, sale, contact, purchase, teardown or operational hardware test was performed by this source screen"
      ]
    }

def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--sources",type=Path,default=SOURCES)
    ap.add_argument("--out",type=Path,default=HERE/"evidence")
    args=ap.parse_args()
    report=compute(json.loads(args.sources.read_text(encoding="utf-8")))
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"channel_decision.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    with (args.out/"batch_sensitivity.csv").open("w",newline="",encoding="utf-8") as f:
      w=csv.writer(f,lineterminator="\n")
      w.writerow(["batch_size","assumed_bid_per_pc","recovery_yield_assumption",
        "profit_if_working_per_pc","loss_per_failed_pc","expected_per_pc",
        "expected_total_batch","max_bid_for_150_ev_per_pc"])
      for x in report["hypothetical_batch_recovery_scenarios"]:
        w.writerow([x["batch_size_hypothesis"],x["price_per_unit_assumption_twd"],
          x["probability_scenario"],x["net_if_functionally_verified_twd"],
          x["loss_if_unrecoverable_twd"],x["expected_per_unit_twd"],
          x["expected_per_batch_twd"],x["max_price_per_unit_for_expected_target_twd"]])
    print("SUPPLIERS",report["supplier_count"],
        "confirmed scrap sale quotes",report["confirmed_supplier_salvage_sale_quotes"])
    for s in report["hypothetical_batch_recovery_scenarios"]:
      print("batch 5 hypothetical offer",s["price_per_unit_assumption_twd"],
        "success_p",s["probability_scenario"],"EV per unit",s["expected_per_unit_twd"],
        "maximum purchase bid for EV150",s["max_price_per_unit_for_expected_target_twd"])
    for s in report["working_acer_conditional_scenarios"]:
      if s["recovery_probability_assumption"]==.8:
        print("used ACER ASP",s["resale_price_assumption_twd"],
          "gross-if-working",s["success_conditional_profit_twd"],"EV",s["expected_contribution_twd"])
    print("DECISION",report["all_transaction_status"])
if __name__=="__main__":
    main()

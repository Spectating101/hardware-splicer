"""HS legitimate salvage-to-functional-product acquisition screen.

Reuses the existing Circuit-AI salvage planner; never treats seller-listed
components as verified inventory, nor generated project candidates as products.
No dumpster trespass, unapproved donation resale, power-on, purchases or sales.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
MODEL_YEAR=2026
SCHEMA="hs.salvage_pilot_20261105.v1"
HYPOTHETICAL_ONLY=("direct_owner_cleanout_hypothetical",)

def valid_transfer(lead:dict)->bool:
    """Require documented rights plus transferred possession for product disposition."""
    if lead.get("platform") in ("PTT Give", "not_sourced_scenario"):
        return False  # Cannot override platform no-resale or synthesize a donor lot.
    return (
        lead.get("commercial_disposition_rights")=="verified_unrestricted_transfer"
        and lead.get("physical_acquired") is True
        and lead.get("donor_owner_permission") is True
        and lead.get("source_availability")=="received_and_documented"
    )

def candidate_valuation(lead:dict)->list[dict]:
    """Only conditional scenarios, never prices for untested physical inventory.

    No part may be priced as actually recoverable until there are real tests.
    Inventory status, resale claims and rights are separately evaluated.
    """
    id=lead["id"]
    if id=="taoyuan_damaged_cpu_board_20261026":
        return [{
            "product_id":"tested_i5_7400_cpu_for_resale",
            "name":"Tested Intel i5-7400 CPU recovered from possibly wet Z170M board",
            "list_ask_or_proxy_revenue_twd":500,
            "pricing_evidence":"Taiwan Ruten i5-7400 asks NT$450-600",
            "revenue_verified":False,
            "paid_parts_and_rework_twd":0,
            "diagnosis_and_build_labor_twd":200,
            "finish_pack_shipping_twd":70,
            "warranty_reserve_twd":100,
            "selling_fee_rate":0.10,
            "outcome_hazards":["CPU still untested", "suspected motherboard moisture; no certified board reuse"],
            "functional_acceptance":["independent socket-1151 CPU bench POST", "stress and temperature verified", "photographic CPU marking"]
        }]
    if id in HYPOTHETICAL_ONLY:
        return [
            {
                "product_id":"refurbished_complete_desktop",
                "name":"Complete repaired, sanitized, tested desktop PC",
                "list_ask_or_proxy_revenue_twd":2200,
                "pricing_evidence":"PTT Taoyuan i5-7500 / 4GB RAM / 120GB SSD asks NT$2,200; assumes comparable tested owner-sourced i5/8GB/256GB unit, not a sale",
                "revenue_verified":False,
                "paid_parts_and_rework_twd":100,
                "diagnosis_and_build_labor_twd":500,
                "finish_pack_shipping_twd":250,
                "warranty_reserve_twd":200,
                "selling_fee_rate":0.10,
                "outcome_hazards":["source not actually found","old power supply requires electrical inspection","data wipe proof missing"],
                "functional_acceptance":["POST on real unit","SMART and secure wipe","memory diagnostics","CPU thermal stability","all necessary ports tested"]
            },
            {
                "product_id":"tested_cpu_ram_ssd_partout",
                "name":"Verified working CPU + DDR4 8GB + SSD sold individually",
                "list_ask_or_proxy_revenue_twd":2050,
                "pricing_evidence":"CPU NT$500 / DDR4 UDIMM 8GB NT$850 observed asks, plus NT$700 SSD non-identical interface proxy, all THREE hypothetical",
                "revenue_verified":False,
                "paid_parts_and_rework_twd":100,
                "diagnosis_and_build_labor_twd":600,
                "finish_pack_shipping_twd":150,
                "warranty_reserve_twd":200,
                "selling_fee_rate":0.10,
                "outcome_hazards":["CPU/RAM/SSD not actually sourced","SSD interface comparator not like-for-like","multiple separate sales assumed"],
                "functional_acceptance":["CPU stress test","RAM diagnostic","SSD SMART and successful erasure","three confirmed buyers"]
            },
            {
                "product_id":"nas_from_scrap_unverified_market",
                "name":"Working, customer-supported NAS appliance from salvaged PC",
                "list_ask_or_proxy_revenue_twd":2600,
                "pricing_evidence":"PTT i3-8100 6-bay NAS asking NT$2,600; different hardware and not sale proof",
                "revenue_verified":False,
                "paid_parts_and_rework_twd":700,
                "diagnosis_and_build_labor_twd":900,
                "finish_pack_shipping_twd":300,
                "warranty_reserve_twd":300,
                "selling_fee_rate":0.10,
                "outcome_hazards":["unknown NAS bay count and drives","no actual NAS production run","unclear service premium"],
                "functional_acceptance":["installed and booted OS","disk SMART","storage scrub / recovery","network reliability","customer acceptance"]
            }
        ]
    return []

def economics(lead:dict, product:dict,p:float)->dict:
    if not (0<=p<=1):raise ValueError("p 0..1")
    ask=lead["asking_price_twd"]
    inbound=lead["shipping_twd"]
    price=product["list_ask_or_proxy_revenue_twd"]
    fees=round(price*product["selling_fee_rate"])
    successful=price-ask-inbound-product["paid_parts_and_rework_twd"]-product["diagnosis_and_build_labor_twd"]-product["finish_pack_shipping_twd"]-product["warranty_reserve_twd"]-fees
    loss=-ask-inbound-200-100 # failed-triage labor and disposal, zero salvage recovery
    expected=p*successful+(1-p)*loss
    fee_multiplier=1-product["selling_fee_rate"]
    min_price=math.ceil((ask+inbound+product["paid_parts_and_rework_twd"]+product["diagnosis_and_build_labor_twd"]+product["finish_pack_shipping_twd"]+product["warranty_reserve_twd"])/fee_multiplier)
    break_even_p=(-loss)/(successful-loss) if successful>loss else None
    max_bid_ev500=expected+ask-500
    return {
        "lead_id":lead["id"],"product_id":product["product_id"],
        "conditional_asp_asking_proxy_twd":price,
        "success_probability_hypothesis":p,
        "profit_if_functionally_verified_and_sold_twd":round(successful),
        "loss_if_failed_twd":round(loss),
        "hypothetical_expected_contribution_twd":round(expected),
        "break_even_p":round(break_even_p,4) if break_even_p is not None else None,
        "required_asp_to_break_even_on_success_twd":min_price,
        "max_bid_for_500_expected_profit_twd":max(0,math.floor(max_bid_ev500)),
        "acquisition_or_transfer_authorized":valid_transfer(lead),
        "sellable_and_bench_verified":False,
        "commercial_action":"BLOCKED_NOT_OWNED_OR_RIGHTS" if not valid_transfer(lead) else "BLOCKED_PENDING_PHYSICAL_FUNCTION_TEST",
        "provenance":"Scenario modeled from public asks and hypothetical probabilities; not generated/realized sale or physical part test"
    }

def existing_hs_salvage_engine()->dict:
    """Actually invoke native Circuit-AI to surface its candidate-only verdict.

    Zero operator-held inventory because nothing is currently acquired or tested.
    Do NOT convert unverified online photos or sale descriptions to stock.
    """
    root=HERE.parents[2]
    ci=root/"apps/circuit-ai"
    sys.path.insert(0,str(ci))
    try:
        from src.intelligence.salvage_splice_planner import SalvageSplicePlanner
        plan=SalvageSplicePlanner().plan({
            "goal":"Identify functional low-voltage product options ONLY from owned, tested salvage assets",
            "inventory":[], "use_llm":False,"use_llm_reasoner":False})
        return {
            "backend":"Existing Circuit-AI SalvageSplicePlanner",
            "vendor":"first_party_original_HS_repo",
            "real_verified_salvage_asset_count":0,
            "backend_verdict":plan["verdict"],
            "backend_candidate_count":len(plan.get("build_candidates",[])),
            "no_inventory_authority":True,
            "backend_candidate_values_used_for_profitability":False
        }
    except Exception as exc:
        return {
            "backend":"Existing Circuit-AI SalvageSplicePlanner",
            "backend_verdict":"UNAVAILABLE_DO_NOT_INFER_ASSETS",
            "backend_candidate_count":0,
            "error":type(exc).__name__+":"+str(exc)[:130],
            "no_inventory_authority":True
        }

def lead_status(lead:dict)->str:
    if lead["platform"]=="PTT Give":
        return "NONCOMMERCIAL_ONLY_BOARD_RESALE_PROHIBITED"
    if lead["platform"]=="not_sourced_scenario":
        return "HYPOTHETICAL_NOT_AN_ACQUISITION_LEAD"
    if lead["platform"]=="PTT HardwareSale":
        return "PAID_UNVERIFIED_POOR_MARGIN_REVIEW_ONLY"
    return "UNCLASSIFIED_NO_ACQUISITION"

def decision_run(data:dict)->dict:
    scenarios=[]
    leads=[]
    for lead in data["donor_leads"]:
        products=candidate_valuation(lead)
        for product in products:
            for p in (0.25,0.50,0.75):
                scenarios.append(economics(lead,product,p))
        leads.append({
            "id":lead["id"],"source":lead["url"],"date":lead["date"],
            "rights":lead["commercial_disposition_rights"],
            "identified_actual_items":lead["reported_included"],
            "claimed_working_assets":0,"unverified":lead["unverified"],
            "physical_acquired":lead["physical_acquired"],
            "commercial_rights_validated":valid_transfer(lead),
            "availability":lead["source_availability"],"status":lead_status(lead),
            "acquisition_action":"DO_NOT_COLLECT_OR_BUY_WITHOUT_CONFIRMED_OWNER_PERMISSION",
            "products_examined":[p["product_id"] for p in products],
        })
    commercially_usable=[x for x in leads if x["commercial_rights_validated"]]
    return {
        "schema":SCHEMA,"as_of":data["date"],
        "source_count":len(leads),
        "confirmed_resale_authorized_lots":len(commercially_usable),
        "verified_usable_assets":0,
        "functional_products_produced":0,
        "sales_recorded":0,
        "physical_validation_status":"NONE",
        "overall_decision":"NO_COMMERCIAL_SALVAGE_AVAILABLE_YET",
        "legal_boundary":"PTT Give is non-commercial; third-party recycling stock is NOT public free inventory. Require explicit transfer and disposition authorization.",
        "sourcing":leads,
        "hs_salvage_core":existing_hs_salvage_engine(),
        "market_comparables":data["comparables"],
        "scenarios":scenarios,
        "next_action":"Find one direct owner/commercial shop who explicitly agrees to transfer an item for refurbishment/resale; then acquire only with documented consent and test existing components.",
        "nonclaims":["PTT Give donor items are not commercial inventory",
                     "No poster or recycle shop has been contacted",
                     "No printed or physically tested parts from salvage",
                     "No owner authorization to take trash or recycler property",
                     "No resale yield, sales margin or physical proof"]
    }

def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--sources",type=Path,default=HERE/"salvage_sources.json")
    ap.add_argument("--out",type=Path,default=HERE/"evidence")
    args=ap.parse_args()
    data=json.loads(args.sources.read_text(encoding="utf-8"))
    report=decision_run(data)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"salvage_decision.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    with (args.out/"route_sensitivity.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f,lineterminator="\n")
        w.writerow(["lead","product","ASP_ask_proxy_NT","scenario_success_probability",
                    "success_profit_NT","failure_loss_NT","scenario_EV_NT","required_ASP_break_even_NT",
                    "max_bid_for_target_EV500_NT","resale_rights_verified","commercial_action"])
        for r in report["scenarios"]:
            w.writerow([r["lead_id"],r["product_id"],r["conditional_asp_asking_proxy_twd"],
                r["success_probability_hypothesis"],r["profit_if_functionally_verified_and_sold_twd"],
                r["loss_if_failed_twd"],r["hypothetical_expected_contribution_twd"],
                r["required_asp_to_break_even_on_success_twd"],r["max_bid_for_500_expected_profit_twd"],
                r["acquisition_or_transfer_authorized"],r["commercial_action"]])
    print("SALVAGE SOURCE LEADS",report["source_count"],"LEGAL COMMERCIAL STOCK",report["confirmed_resale_authorized_lots"])
    print("HS BACKEND",report["hs_salvage_core"])
    for l in report["sourcing"]:
        print("LEAD",l["id"],l["status"],"confirmed parts",l["claimed_working_assets"])
    for r in report["scenarios"]:
        if r["success_probability_hypothesis"]==0.5:
            print("SCENARIO",r["lead_id"],r["product_id"],
                  "success",r["profit_if_functionally_verified_and_sold_twd"],
                  "failed",r["loss_if_failed_twd"],
                  "EV@0.5",r["hypothetical_expected_contribution_twd"],
                  r["commercial_action"])
    print("DECISION",report["overall_decision"],"; no bins searched, no lot acquired.")
if __name__=="__main__":
    main()

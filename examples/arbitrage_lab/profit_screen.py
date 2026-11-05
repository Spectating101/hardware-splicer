"""HS product-arbitrage preflight: observed listings vs explicit unit-cost scenarios.

Not financial returns: listing prices are not realized ASP, print masses for
unbuilt products are assumptions, and marketplace costs vary by seller/category.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def unit_contribution(price_idr: int, print_g: float, assumptions: dict,
                      rate_idr_per_g: int = 1000, fee_rate: float | None = None) -> dict:
    if price_idr < 0 or print_g < 0 or rate_idr_per_g < 0:
        raise ValueError("price, mass and per-gram rate must be nonnegative")
    f = assumptions["marketplace_total_fee_rate"] if fee_rate is None else fee_rate
    if f < 0 or f >= 1:
        raise ValueError("platform fee fraction must be in [0,1)")
    mass_billed_g = max(10, print_g)  # supplier 10g minimum per fulfilled order
    print_cost = int(math.ceil(mass_billed_g * rate_idr_per_g))
    fees = int(round(price_idr * f))
    fixed = sum(assumptions[k] for k in (
        "order_processing_fee_idr", "packaging_idr", "fulfillment_and_quality_labor_idr",
        "customer_acquisition_idr", "returns_warranty_allowance_idr",
        "fasteners_idr", "design_cost_amortization_idr"))
    contribution = price_idr - print_cost - fees - fixed
    breakeven_price = math.ceil((print_cost + fixed)/(1-f))
    target_price_25pct = math.ceil((print_cost + fixed)/(0.75-f)) if f < 0.75 else None
    return {
        "price_idr":price_idr,"print_mass_assumed_g":round(print_g,3),
        "supplier_billed_mass_g":round(mass_billed_g,3),
        "print_cost_idr":print_cost,"marketplace_fees_idr":fees,
        "fixed_expenses_and_reserves_idr":fixed,
        "contribution_idr":contribution,
        "contribution_margin_pct":round(100*contribution/price_idr,2) if price_idr else None,
        "break_even_price_idr":breakeven_price,
        "target_25pct_contribution_price_idr":target_price_25pct,
        "positive_contribution":contribution>0,
    }


def evaluate_candidate(c:dict, cfg:dict, *, override_grams:float | None = None)->dict:
    a=cfg["assumptions"]
    weight=c["grams_per_sale_assumption"] if override_grams is None else override_grams
    base=unit_contribution(c["listed_price_idr"],weight,a,cfg["outsourced_petg"]["price_per_sliced_g_idr"])
    stressed=unit_contribution(
        round(c["listed_price_idr"]*0.85),weight*1.4,
        {**a,"returns_warranty_allowance_idr":a["returns_warranty_allowance_idr"]+10000},
        cfg["outsourced_petg"]["price_per_sliced_g_idr"],fee_rate=0.23)
    return {
        "id":c["id"],"product":c["product"],"price_source":c["listing_source"],
        "mass_provenance":"STL geometry/assumed solid PETG (not sliced/quoted)" if override_grams is not None else "hypothesis only",
        "reported_cumulative_sales":c["reported_cumulative_sales"],
        "release_status":c["candidate_status"],
        "base":base,"stress":stressed,
        "passes_base_20pct_margin":(base["contribution_margin_pct"] or -100)>=20,
        "passes_stress_nonnegative":stressed["positive_contribution"],
    }


def rank(cfg:dict, *, router_mass_g:float | None=None)->list[dict]:
    rows=[]
    for c in cfg["candidates"]:
        rows.append(evaluate_candidate(c,cfg,override_grams=router_mass_g if c["id"]=="router3-indoor-support" else None))
    return sorted(rows,key=lambda x:x["base"]["contribution_idr"],reverse=True)


def run()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,default=Path(__file__).with_name("market_snapshot_20261105.json"))
    p.add_argument("--out",type=Path,default=Path(__file__).with_name("outputs"))
    p.add_argument("--router-mass-g",type=float)
    args=p.parse_args()
    cfg=json.loads(args.snapshot.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True,exist_ok=True)
    results=rank(cfg,router_mass_g=args.router_mass_g)
    (args.out/"market_screen.json").write_text(json.dumps({
        "snapshot_date":cfg["snapshot_date"],"material_price_source":cfg["outsourced_petg"]["source"],
        "market_snapshot_note":cfg["warning"],"assumptions":cfg["assumptions"],
        "candidates":results
    },indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    with (args.out/"market_screen.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f)
        w.writerow(["sku","listed_asp_idr","estimated_billable_mass_g","print_cost_idr",
                    "base_contribution_idr","base_margin_pct","stress_contribution_idr",
                    "base_20pct_margin_gate","stress_positive_gate","status","source"])
        for r in results:
            b=r["base"]
            w.writerow([r["id"],b["price_idr"],b["supplier_billed_mass_g"],
                        b["print_cost_idr"],b["contribution_idr"],b["contribution_margin_pct"],
                        r["stress"]["contribution_idr"],r["passes_base_20pct_margin"],
                        r["passes_stress_nonnegative"],r["release_status"],r["price_source"]])
    print("ID".ljust(29),"ASP".rjust(9),"G".rjust(6),"BASE".rjust(10),"STRESS".rjust(10),"GATE")
    for r in results:
        print(r["id"].ljust(29),str(r["base"]["price_idr"]).rjust(9),
              str(r["base"]["supplier_billed_mass_g"]).rjust(6),
              str(r["base"]["contribution_idr"]).rjust(10),
              str(r["stress"]["contribution_idr"]).rjust(10),
              "candidate" if r["passes_base_20pct_margin"] and r["passes_stress_nonnegative"] else "reject/validate")
    print("Sources and assumptions: ",args.out)


if __name__=="__main__":
    run()

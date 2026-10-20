"""Cost small physical products using explicit observed offers vs estimated costs.

These are sales hypotheses, never revenue forecasts. Printed service cost
includes material and vendor labor, while owned-machine mode includes raw
filament + allocated wear/power/scrap. Never double-count both.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path

def _nonneg(value,name):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError("invalid nonnegative number: "+name)
    return float(value)

def compute_scenarios(data:dict)->dict:
    if data["pricing_authority"]!="SELLER_ADVERTISED_LISTINGS_NOT_CHECKOUT_QUOTES":
        raise ValueError("cannot claim unverified seller checkout authority")
    offers=data["component_quotes"]
    printbase=data["material_quotes"]
    petg_self=_nonneg(printbase["petg_per_kg_twd"]["price"],"PETG")/1000
    petg_out=_nonneg(printbase["petg_outsource_per_g_twd"]["price"],"outsource PETG")
    min_out=_nonneg(printbase["petg_outsource_per_g_twd"]["minimum_order_twd"],"min outsource")
    high_out=_nonneg(printbase["petg_outsource_high_cost_sensitivity_per_g_twd"]["price"],"high outsource")
    if high_out<petg_out:raise ValueError("high sensitivity price below base quote")
    fee=_nonneg(data["platform_fee_assumption_fraction"],"fee")
    labor=_nonneg(data["labor_benchmark_twd_hour"],"labor")
    if fee>=1:raise ValueError("platform fees too high")
    results=[]
    for item in data["candidates"]:
        sale=_nonneg(item["sale_price_hypothesis_twd"],"sale")
        grams=_nonneg(item["benchmark_printed_petg_grams"],"grams")
        if grams==0:raise ValueError("zero printed grams not a usable assumption")
        parts=0
        lineitems=[]
        for row in item["parts"]:
            offer=offers[row["id"]]
            unit=_nonneg(offer["price"],"part price")
            q=row["qty"]
            if type(q) is not int or not 0<q<10000:raise ValueError("invalid quantity")
            parts+=unit*q
            lineitems.append({"id":row["id"],"quantity":q,"total_twd":round(unit*q,2),
                              "source_status":offer["basis"],"url":offer.get("url")})
        labor_cost=labor*_nonneg(item["assembly_hours_assumed"],"labor hours")
        selling_fee=sale*fee
        other=sum(_nonneg(item[k],k) for k in ("qa_warranty_reserve_twd",
                                              "packaging_twd","outbound_fulfillment_twd"))
        result={"id":item["id"],"role":item["role"],"sale_price_hypothesis_twd":sale,
                "parts_material_hardware_twd":round(parts,2),
                "line_items":lineitems,"hours_assumed":item["assembly_hours_assumed"],
                "selling_fee_assumed_twd":round(selling_fee,2),
                "printed_mass_assumption_grams":grams,
                "physical_sample_built":False,"actual_customer_demand_verified":False,
                "physical_sale_authorized":False}
        for mode,print_cost in (
            ("self_print",grams*petg_self+_nonneg(item["self_print_machine_time_and_scrap_twd"],"own print")),
            ("outsource",max(min_out,grams*petg_out))):
            total=parts+print_cost+other+labor_cost+selling_fee
            contribution=sale-total
            # Price at a specified minimum contribution margin, under
            # a fee charged as a fraction of selling price.
            direct_fixed=parts+print_cost+other+labor_cost
            breakeven=direct_fixed/(1-fee)
            target20=direct_fixed/(1-fee-0.2)
            stress_print=print_cost*1.25
            stress_additional_return=0.05*sale
            stressed=sale-(parts+stress_print+other+labor_cost+selling_fee+stress_additional_return)
            result[mode]={
                "printed_piece_cost_twd":round(print_cost,2),
                "other_packaging_shipping_qa_twd":round(other,2),
                "labor_cost_twd":round(labor_cost,2),
                "assumed_unit_total_twd":round(total,2),
                "unit_contribution_before_fixed_overhead_and_taxes_twd":round(contribution,2),
                "contribution_margin_fraction":round(contribution/sale,4),
                "break_even_list_price_twd":round(breakeven,2),
                "list_price_for_20pct_contribution_twd":round(target20,2),
                "contribution_with_25pct_print_cost_overrun_and_extra_5pct_returns_twd":round(stressed,2)
            }
        high_print=max(min_out,grams*high_out)
        total_high=parts+high_print+other+labor_cost+selling_fee
        result["outsource_higher_quote_sensitivity"]={
            "test_rate_twd_per_gram":high_out,
            "actual_supplier_quote_confirmed":False,
            "printed_piece_cost_twd":round(high_print,2),
            "unit_contribution_before_fixed_overhead_and_taxes_twd":round(sale-total_high,2),
            "contribution_margin_fraction":round((sale-total_high)/sale,4)
        }
        results.append(result)
    return {
        "schema_version":"hardware_splicer.low_cost_physical_product_decision_model.v1",
        "seller_prices_are_checkout_verified":False,
        "finished_goods_ever_physically_built":False,
        "unit_economics_have_observed_sales":False,
        "marketing_conversion_rate_known":False,
        "printer_fixed_cost_included":False,
        "design_development_hours_amortized":False,
        "customer_revenue_realized_twd":0,
        "products":results,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    d=json.loads(a.input.read_text())
    report=compute_scenarios(d)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    for item in report["products"]:
        print(item["id"],"sale",item["sale_price_hypothesis_twd"],
              "own_margin",item["self_print"]["contribution_margin_fraction"],
              "outsource_margin",item["outsource"]["contribution_margin_fraction"],
              "outsource_stress_surplus",item["outsource"]["contribution_with_25pct_print_cost_overrun_and_extra_5pct_returns_twd"])
if __name__=='__main__':main()

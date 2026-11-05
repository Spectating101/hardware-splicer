"""Hardware Splicer: a *real-listed* industrial-printer recovery/business screen.

Never connects to hardware, sends ZPL, orders a printer, or grants physical proof.
Uses Zebra official fault categories and existing Circuit-AI authority readout.
ZPL acceptance file is generated offline, with a fixed synthetic barcode only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/"sources_20261105.json"

EVIDENCE_GATES={
    "device_model_and_dpi":"Actual nameplate/model and 203/300 dpi variant photo",
    "genuine_printhead_present_and_no_auth_errors":"Actual head installed, correct dpi, LCD not showing PH NOT AUTHENTICATED",
    "power_and_lcd_status":"Power on and capture complete LCD/LED state",
    "printhead_self_test":"Manufacturer PAUSE self-test with clear dot coverage without missing stripes",
    "platen_feed_and_sensor_calibration":"Feed test, measured media alignment and proper sensor response",
    "printed_code128_readback":"Actual label barcode scanned and decoded; payload exactly HSZT230QC001",
    "usb_or_network_transport":"Actual host-to-printer label flow via verified USB or Ethernet",
    "sustained_printing":"Multiple sample labels, no repeated errors or thermal/feeding issues",
    "sale_condition_and_support_disclosure":"Report repair/printhead age and APAC service end-of-life; no hidden defect",
}


def scenario(d:dict,asp:int,p:float,*,replaced_head:bool=False)->dict:
    if not 0<=p<=1 or asp<0:raise ValueError("Invalid probability or price")
    target=d["target"]
    a=d["unit_cost_assumptions"]
    cost_on_success=sum(a[x] for x in (
        "consumable_media_labels_ribbon","cleaning_parts","bench_and_functional_validation_labor",
        "outgoing_shipping_packing","returns_and_quality_reserve"))
    acquired=target["price"]+target["inbound_shipping_scenario"]
    head_cost=d["zebra_parts"]["head_replacement_offer"]["price_scenario"] if replaced_head else 0
    fees=round(asp*a["selling_fee_fraction"])
    profit_on_success=asp-acquired-cost_on_success-head_cost-fees
    loss_if_failed=-(acquired+a["failed_diagnostic_labor"]+a["failed_disposal_and_storage"])+a["salvage_value_if_failed"]
    ev=profit_on_success*p+loss_if_failed*(1-p)
    # max bid for TARGET EV, with fixed per-unit costs and no purchase in base;
    # entered purchase affects both success/failure once, so subtract once.
    max_bid_raw=ev+target["price"]-a["desired_expected_profit"]
    breakeven_p=(-loss_if_failed)/(profit_on_success-loss_if_failed) if profit_on_success>loss_if_failed else None
    return {
        "resale_price_hypothesis_twd":asp,
        "probability_hypothesis":p,
        "conditional_success_profit_twd":profit_on_success,
        "failed_unit_loss_twd":loss_if_failed,
        "expected_value_twd":round(ev),
        "max_purchase_offer_for_target_ev_twd":max(0,math.floor(max_bid_raw)),
        "unconstrained_max_bid_raw_twd":round(max_bid_raw,2),
        "p_break_even":round(breakeven_p,4) if breakeven_p is not None else None,
        "head_replacement_assumed":replaced_head,
        "head_cost_twd":head_cost,
        "working_equipment_verified":False,
        "valuation_scope":"Scenario using unconfirmed asking prices and assumed repair outcome, not sale or actual yield"
    }


def tsc_missing_head_control(d:dict)->dict:
    x=d["control"]
    sale=x["working_comparable"]["price"]
    cost=d["unit_cost_assumptions"]
    # Even without a printhead, optimistic positive closing economics fail.
    # Lower PSU offer is from a related TTP series; not declared fit verified.
    supply=min(x["psu_reference"]["price_range"])
    revenue_after_fees=sale-round(sale*cost["selling_fee_fraction"])
    fixed=(x["price"]+60+supply
           +cost["consumable_media_labels_ribbon"]
           +cost["cleaning_parts"]+cost["bench_and_functional_validation_labor"]
           +cost["outgoing_shipping_packing"]+cost["returns_and_quality_reserve"])
    return {
        "sku":x["id"],"acquisition_twd":x["price"],
        "critical_missing_component":"printhead assembly (seller explicitly excludes)","compatible_printhead_cost_verified":False,
        "known_supplier_claim":"Seller powered on but printing untested, printhead missing, power adapter missing",
        "resale_price_asking_twd":sale,
        "optimistic_profit_before_printhead_and_tax_twd":revenue_after_fees-fixed,
        "break_even_printhead_budget_twd":max(0,revenue_after_fees-fixed),
        "decision":"REJECT_MISSING_CRITICAL_PART_AND_NEGATIVE_MARGIN"
    }


def render_zpl()->str:
    """Safe constant printable ZPL sample for OFFLINE future operator use only."""
    return (
        "^XA\n"
        "^CI28\n"
        "^PW812\n"
        "^LL609\n"
        "^FO35,35^A0N,40,40^FDHS ZT230 TEST (NO DEVICE CONNECTED)^FS\n"
        "^FO35,100^BY3,2,110^BCN,110,Y,N,N^FDHSZT230QC001^FS\n"
        "^FO35,315^GB720,3,3^FS\n"
        "^FO35,340^GB720,130,4^FS\n"
        "^FO35,520^A0N,24,24^FDSCAN 1D BARCODE AND CHECK FULL DENSITY^FS\n"
        "^XZ\n"
    )


def existing_hs_repair_authority()->dict:
    """Invoke existing Circuit-AI — never accept speculative parts suggestions as real."""
    repo=ROOT.parents[2]
    ci=repo/"apps/circuit-ai"
    sys.path.insert(0,str(ci))
    try:
        from src.intelligence.hardware_plan import HardwarePlanOrchestrator
        result=HardwarePlanOrchestrator().plan({
            "goal":"Unpurchased Zebra ZT230 printer: powered-on claimed, no real print, head or sensor evidence; classify diagnostic/repair readiness only",
            "device_hint":"Zebra ZT230 industrial barcode label printer",
            "strategy_mode":"repair","use_llm":False,"use_reference_catalog":False})
        a=result.get("analysis",{}).get("hardware_plan_summary",{}).get("authority",{})
        return {"engine":"existing Circuit-AI HardwarePlanOrchestrator",
                "schema":result.get("schema_version"),
                "physical_repair_authority":False,
                "generic_planner_reported_availability":bool(a.get("available",False)),
                "status":"NO_MEASURED_PRINTER_EVIDENCE; generic fabricated BOM discarded"}
    except Exception as exc:
        return {"engine":"existing Circuit-AI HardwarePlanOrchestrator",
                "physical_repair_authority":False,"error":type(exc).__name__+":"+str(exc)[:140]}


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,default=SOURCE)
    ap.add_argument("--out",type=Path,default=ROOT/"evidence")
    args=ap.parse_args()
    d=json.loads(args.source.read_text(encoding="utf-8"))
    prices=d["resale"]["price_scenarios"]
    probs=d["success_probability_scenarios"]
    outputs=[scenario(d,price,p) for price in prices for p in probs]
    head_case=[scenario(d,price,1.0,replaced_head=True) for price in prices]
    tsc=tsc_missing_head_control(d)
    report={
        "case_id":"industrial_zebra_zt230_20261105",
        "as_of":d["as_of"],
        "device_acquired":False,
        "physical_prints_made":0,
        "evidence_received":False,
        "passed_evidence_gates":[],
        "required_evidence":EVIDENCE_GATES,
        "release_status":"NOT_PURCHASED_NOT_REPAIRED_NOT_VERIFIED",
        "decision":"HOLD_NO_PURCHASE_PREBID_PRINTHEAD_SELFTEST_REQUIRED",
        "hardware_important_hazards":["Electronics power supply contains mains: do NOT open or probe mains circuits",
                                      "Power off for platen/printhead inspection and cleaning; avoid hot printhead"],
        "commercial_data_status":"seller asking and source documentation, no verified sale, yield or actual parts quote",
        "zebra_head_replacement_scenarios":head_case,
        "zebra_repair_economics_scenarios":outputs,
        "tsc_false_bargain_negative_control":tsc,
        "competitor_price_sources":d["resale"]["sources"],
        "zpl_fixture":"ZT230_BENCH_QC_OFFLINE.zpl is a synthetic test command; it has never been sent to a printer.",
        "hardware_splicer_backend":existing_hs_repair_authority(),
    }
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"industrial_refurb_screen.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    (args.out/"ZT230_BENCH_QC_OFFLINE.zpl").write_text(render_zpl(),encoding="ascii")
    with (args.out/"zebra_profit_sensitivity.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f,lineterminator="\n")
        w.writerow(["asp_hypothesis","repair_success_p_hypothesis","success_profit","failure_loss",
                    "expected_profit","max_bid_for_500_expected_profit","head_replacement_cost"])
        for x in outputs:
            w.writerow([x["resale_price_hypothesis_twd"],x["probability_hypothesis"],
                    x["conditional_success_profit_twd"],x["failed_unit_loss_twd"],
                    x["expected_value_twd"],x["max_purchase_offer_for_target_ev_twd"],x["head_cost_twd"]])
    print("ZEBRA TARGET",d["target"]["price"],"TWD, + inbound shipping",d["target"]["inbound_shipping_scenario"])
    print("CONTROL TSC",tsc["decision"],"profit before head",tsc["optimistic_profit_before_printhead_and_tax_twd"])
    for x in outputs:
        if x["probability_hypothesis"] in (0.5,0.65):
            print("ASP",x["resale_price_hypothesis_twd"],"p",x["probability_hypothesis"],
                "success",x["conditional_success_profit_twd"],"failure",x["failed_unit_loss_twd"],
                "EV",x["expected_value_twd"],"maxbid",x["max_purchase_offer_for_target_ev_twd"])
    print("NO HARDWARE, NO PRINT, NO ORDER, NO SALE")


if __name__=="__main__":
    main()

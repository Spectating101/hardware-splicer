"""Real-listed NUC11PAH hardware-refurbishment arbitrage *pre-purchase* pilot.

The case contains source URLs and seller claims; **no device** is purchased or
controlled. Existing Circuit-AI HardwarePlanOrchestrator contributes an honest
authority/readiness signal only. Scenario prices are NOT realized sale prices,
conditional repair profitability is NOT a measured success probability.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
OBSERVED_GATES={
    "cpu_variant_identified":"Photograph board/model label; NUC11PAH alone cannot distinguish i3/i5/i7",
    "working_compatible_psu_verified":"Known-good 19V 90W 5.5x2.5mm adapter verified; do not open AC adapter",
    "physical_board_inspection_pass":"Inspect DC socket, corrosion, missing parts, previous rework while unplugged",
    "power_led_response_recorded":"Observe LED after compatible PSU test, including a dark LED as a legitimate failure",
    "boot_post_pass":"Evidence of successful BIOS/UEFI POST on THIS unit; not a simulated system",
    "ram_memtest_pass":"Actual installed SO-DIMM memory test evidence",
    "ssd_smart_pass":"SSD health status evidence, not an assumption from seller",
    "thermal_stress_pass":"Recorded temperature and throttling under sustained run",
    "ports_network_pass":"Evidence of network, storage and display/USB functionality",
    "storage_wipe_pass":"Prior owner's storage erased or newly sourced; no unlicensed OS claims",
    "warranty_and_sale_disclosure":"Accurate repair disclosure and required legal warranty/returns reviewed"
}
OBS_BENCH=tuple(OBSERVED_GATES)


def money(x:float)->int:
    return round(x)


def economics(case:dict, resale_price:int, p:float)->dict:
    """Expected outcome assumes completion parts bought only if bench diagnosis succeeds.

    Failed inspection losses include purchase, shipping, diagnosis and disposal;
    salvage recovery is ZERO unless a verified salvage sale changes this case.
    """
    if not (0<=p<=1): raise ValueError("probability must be 0..1")
    if resale_price<0: raise ValueError("resale price cannot be negative")
    m=case["model"]
    ask=case["target"]["listing_price"]
    inbound=case["target"]["inbound_shipping"]
    completion=sum(row["price"] for row in case["parts"])
    extra_success=sum(m[k] for k in (
        "repair_consumables_allowance", "successful_repair_and_validation_labor",
        "packing_and_outgoing_handling","warranty_returns_reserve"))
    selling_fee=money(resale_price*m["all_in_seller_fee_rate"])
    successful_net=resale_price-ask-inbound-completion-extra_success-selling_fee
    failed_net=-ask-inbound-m["failed_diagnostic_labor"]-m["failed_disposal_allowance"]+m["unrecovered_salvage_value"]
    expected=p*successful_net+(1-p)*failed_net
    # Seller bid max at target positive expected contribution (not a recommendation to bid).
    # Since both success and failure entail buying the unit, bid enters EV with slope -1.
    successful_net_at_zero_bid=successful_net+ask
    failed_net_at_zero_bid=failed_net+ask
    max_bid=p*successful_net_at_zero_bid+(1-p)*failed_net_at_zero_bid-m["target_expected_net_profit"]
    p_break_even=(-failed_net)/(successful_net-failed_net) if successful_net>failed_net else None
    return {
        "resale_price_scenario_twd":resale_price,
        "assumed_repair_success_probability":p,
        "acquisition_price_twd":ask,
        "completion_parts_cost_twd":completion,
        "resale_fee_twd":selling_fee,
        "net_if_verified_repaired_and_sold_twd":successful_net,
        "net_if_diagnosed_irreparable_twd":failed_net,
        "expected_profit_twd":money(expected),
        "expected_profit_raw_twd":round(expected,2),
        "max_bid_for_target_EV_twd":max(0,money(max_bid)),
        "raw_max_bid_twd":money(max_bid),
        "p_break_even_under_scenario":round(p_break_even,4) if p_break_even is not None else None,
        "conditional_success_margin_pct":round(100*successful_net/resale_price,2) if resale_price else None,
        "interpretation":"Conditional HYPOTHETICAL economics; p is a sensitivity input and is NOT a measured repair probability."
    }


def technical_route(obs:dict)->list[dict]:
    """Evidence-dependent safe service decision support, NOT a bench measurement."""
    led=obs.get("power_led_state")
    if led in ("dark","no_light"):
        return [
            {"step":"check_verified_adapter","intent":"Confirm correct certified 19V 90W barrel PSU and outlet, connector/polarity, measured externally by qualified technician","source":"https://rog.asus.com/support/faq/1052686/"},
            {"step":"inspect_dc_entry","intent":"Unplug first; inspect external DC jack/board for physical damage and corrosion. Do not open or alter mains PSU.","source":"https://rog.asus.com/support/faq/1052686/"},
            {"step":"escalate_if_board_fault","intent":"If correct adapter is verified but still no standby/LED, stop power attempts; authorized low-voltage board diagnosis needed. Never invent repair from listing.","source":"https://www.asus.com/support/faq/1052510/"}
        ]
    if led=="blink":
        return [
            {"step":"decode_led","intent":"Count exact blinks and colors, identify error per ASUS reference and memory condition; never label no-power as BIOS corruption.","source":"https://www.asus.com/support/faq/1052510/"},
            {"step":"known_good_ram","intent":"With input power unplugged, install compatible DDR4-3200 1.2V SO-DIMM for controlled POST test.","source":"https://www.intel.com/content/dam/support/us/en/documents/intel-nuc/NUC11PA_TechProdSpec.pdf"}
        ]
    if led=="solid_no_video":
        return [
            {"step":"diagnose_post","intent":"Different cable/display, RAM test and peripheral removal; collect BIOS/POST logs when possible.","source":"https://www.asus.com/support/faq/1052510/"},
            {"step":"drive_isolation","intent":"Check storage device/connection after power-down; no storage purchase until POST issue isolated.","source":"https://www.intel.com/content/www/us/en/support/articles/000087897/intel-nuc.html"}
        ]
    if led=="solid_and_posts":
        return [
            {"step":"functional_validation","intent":"Perform actual memory, SMART, thermal stress, video/network/USB testing, privacy wipe before sale; no 'repaired' claim yet.","source":"https://www.asus.com/support/faq/1052510/"}
        ]
    return [
        {"step":"prebid_identity","intent":"Request actual underside label and SO-DIMM-area board AA markings to identify CPU variant; manufacturer NUC11PAH family includes i3/i5/i7.","source":"https://www.intel.com/content/dam/support/us/en/documents/intel-nuc/NUC11PA_TechProdSpec.pdf"},
        {"step":"prebid_accessory_and_failure","intent":"Confirm PSU included and exact test performed, get board/circuit photos and repair history; seller currently says no LED and may have been dismantled.","source":"https://www.ruten.com.tw/item/22635470508103/"},
        {"step":"no_bench_yet","intent":"Do not authorize paid acquisition from seller-only observations; route to a local repair/inspection bench first.","source":"https://rog.asus.com/support/faq/1052686/"}
    ]


def load_observations(path:Path|None)->dict:
    if path is None:return {}
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):raise ValueError("observations must be a JSON object")
    return payload


def checked_evidence(obs:dict)->tuple[list[str],list[str]]:
    """Evidence paths must exist locally, but authenticity remains operator-supplied."""
    missing=[]
    operator_evidence=[]
    for gate,desc in OBSERVED_GATES.items():
        row=obs.get(gate)
        if not isinstance(row,dict) or row.get("pass") is not True or not isinstance(row.get("evidence_path"),str):
            missing.append(gate)
            continue
        p=HERE / row["evidence_path"]
        if not p.is_file() or not p.resolve().is_relative_to(HERE.resolve()) or p.stat().st_size==0:
            missing.append(gate)
            continue
        operator_evidence.append(f"{gate}: {p}")
    return missing,operator_evidence


def hs_existing_authority(case:dict)->dict:
    """Use existing non-LLM Circuit-AI hardware plan, DISCARD unsupported generic suggested parts/cost."""
    repo=HERE.parents[2] # examples/arbitrage_lab/refurb_nuc11 -> repository
    ci=repo/"apps"/"circuit-ai"
    sys.path.insert(0,str(ci))
    try:
        from src.intelligence.hardware_plan import HardwarePlanOrchestrator
        payload={
            "goal":"Diagnose seller-reported no-power NUC11PAH; no purchased unit, no photos, no physical bench; no inferred circuit values",
            "device_hint":"Intel NUC11PAH unidentified i3/i5/i7",
            "strategy_mode":"repair",
            "use_llm":False,
            "use_reference_catalog":False,
            "include_debug_plans":False,
        }
        plan=HardwarePlanOrchestrator().plan(payload)
        authority=plan.get("analysis",{}).get("hardware_plan_summary",{}).get("authority",{})
        return {
            "engine":"existing Circuit-AI HardwarePlanOrchestrator",
            "schema_version":plan.get("schema_version"),
            "authority_available":bool(authority.get("available",False)),
            "authority_status":authority.get("repair_authority_status","not_established"),
            "source_board_evidence_count":0,
            "claim_boundary":"Generic planning engine not trained on this measured NUC board. Its hypothetical procurement/circuit suggestions are explicitly NOT used for repairs or costs.",
        }
    except Exception as exc:
        return {"engine":"existing Circuit-AI HardwarePlanOrchestrator","authority_available":False,"error":type(exc).__name__+":"+str(exc)[:160],"claim_boundary":"Missing integration cannot grant repair approval."}


def run(case:dict,obs:dict)->dict:
    m=case["model"]
    rows=[economics(case,price,p) for price in m["selling_price_scenarios"] for p in m["success_probability_scenarios"]]
    missing,evidence=checked_evidence(obs)
    # Distinguish unknown CPU & no real bench from hypothetical economics.
    prebid=[
        "CPU/board AA identification unavailable",
        "seller's 'no power' not independently tested",
        "adapter presence, board damage and repair history unknown",
        "working-price comparator sold out and asks not realized resale",
    ]
    model_verified=obs.get("cpu_variant_identified",{})
    cpu_verified=bool(case["target"].get("exact_cpu") in ("i3","i5","i7") and
        isinstance(model_verified,dict) and model_verified.get("pass") is True and
        isinstance(model_verified.get("evidence_path"),str) and
        (HERE/model_verified["evidence_path"]).is_file())
    # All marked 'passed' cannot be enough: unit must have been actually acquired.
    acquired=case["target"].get("acquired") is True
    returned={
      "case_id":"ruten-nuc11pah-no-power-20261105",
      "as_of":case["as_of"],"source_listing_url":case["target"]["url"],
      "listing_price_twd":case["target"]["listing_price"],
      "actual_acquired":acquired,"observed_cpu_variant":case["target"].get("exact_cpu"),
      "decision":"DO_NOT_BUY_UNVERIFIED_UNIT" if not (acquired or cpu_verified) else "PENDING_BENCH_RELEASE",
      "operator_reported_bench_complete":bool(acquired and cpu_verified and not missing),
      "released_as_functional":False,
      "functional_release_policy":"Never grant independent physical proof from locally supplied JSON/paths; requires independently reviewed technician records, the real machine and authenticated hardware evidence external to this pre-purchase screen.",
      "seller_claim":"seller-reported no-power; never independently verified",
      "prepurchase_blockers":prebid if not cpu_verified else prebid[1:],
      "bench_missing_gates":missing,"operator_supplied_evidence":evidence,
      "oem_diagnostic_decision_tree":technical_route(obs),
      "economics_model":{
        "currency":"TWD","resale_price_scenarios":[int(p) for p in m["selling_price_scenarios"]],
        "probabilities_are_scenarios_not_inferred":True,"results":rows,
        "unverified_resale_compares":case["price_comparators"],
        "parts":case["parts"],
        "model_assumptions":m,
        "unknown_externalities":["taxes","sales realizations","seller listing validity","actual board fault and yield","technician labor variance"]
      },
      "existing_hs_engine":hs_existing_authority(case),
      "physical_proof":"NONE: no acquired mini-PC, no inspected board, no measurements, no functional boot, no refurbishment sale"
    }
    return returned


def main()->None:
    ap=argparse.ArgumentParser(description="Real-listed, unpurchased NUC11PAH risk/repair model")
    ap.add_argument("--case",type=Path,default=HERE/"market_case.json")
    ap.add_argument("--observations",type=Path,default=None)
    ap.add_argument("--out",type=Path,default=HERE/"evidence")
    args=ap.parse_args()
    case=json.loads(args.case.read_text(encoding="utf-8"))
    obs=load_observations(args.observations)
    result=run(case,obs)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"refurb_decision.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    with (args.out/"sensitivity.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f,lineterminator="\n")
        w.writerow(["asp_twd","scenario_probability","net_success_twd","net_failure_twd","expected_twd","max_bid_target_EV_twd","break_even_p","conditional_success_margin_pct"])
        for r in result["economics_model"]["results"]:
            w.writerow([r["resale_price_scenario_twd"],r["assumed_repair_success_probability"],
                r["net_if_verified_repaired_and_sold_twd"],r["net_if_diagnosed_irreparable_twd"],
                r["expected_profit_twd"],r["max_bid_for_target_EV_twd"],r["p_break_even_under_scenario"],r["conditional_success_margin_pct"]])
    print("CASE",result["case_id"],"DECISION",result["decision"],"HS AUTHORITY",result["existing_hs_engine"].get("authority_available"))
    for r in result["economics_model"]["results"]:
        if r["assumed_repair_success_probability"] in (0.5,0.75):
            print("ASP",r["resale_price_scenario_twd"],"p",r["assumed_repair_success_probability"],
                  "net_on_success",r["net_if_verified_repaired_and_sold_twd"],
                  "failure_loss",r["net_if_diagnosed_irreparable_twd"],
                  "expected",r["expected_profit_twd"],"max_bid_ev500",r["max_bid_for_target_EV_twd"])
    print("No actual hardware work, purchasing, repair or sale.")
if __name__=="__main__":
    main()

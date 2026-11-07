"""Hardware Splicer value engineering: source-linked buy/build architecture gate.

No consumer-product launch requirement. Fail closed on missing exact prices,
dual-display interface readiness, physical fit, safe power, and real SSH tests.
Uses existing canonical MachineProject authority checks and CM5 MechanicalFit
output; calculations only concern declared seller asking-price subtotals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .machine_project import (
    AuthorityState, MachineProject, ReleaseState, Requirement,
    RequirementKind, VerificationMethod, VerificationType,
)

SCHEMA = "hardware_splicer.cyberdeck_architecture_options.v1"
REPORT_SCHEMA = "hardware_splicer.cyberdeck_architecture_value_review.v1"

# Ordered only for deciding which UNVERIFIED trial gives the most useful next
# engineering result; NEVER represents measured product quality or cost.
TRIAL_ORDER = ("cm4_narrow_custom", "cm4_narrow_50_dsi", "esp32_dual_43", "radxa_cm5_dual_50")
RIGID_SCREEN_REJECT = {"used_fold4", "stripped_phone_mainboard"}
EXPLICIT_FORM_REJECT = {"intact_phone_dual_display", "used_fold4"}
MANDATORY_EVIDENCE = (
    "two_touch_panels_operating_together",
    "pocket_closed_155x80x18_fit",
    "safe_protected_portable_power",
    "functional_secure_ssh_and_editing",
    "actual_delivered_BOM_and_assembly_cost",
    "hinge_cable_bend_and_serviceability",
)


def _canonical(value: dict) -> bytes:
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode()


def _validate(payload: dict) -> None:
    if payload.get("schema")!=SCHEMA:
        raise ValueError("HS architecture comparison schema mismatch")
    requirements=payload.get("product_requirement",{})
    if requirements.get("two_touchscreens_mandatory") is not True:
        raise ValueError("two screens were a user constraint")
    if requirements.get("physical_keyboard_forbidden") is not True:
        raise ValueError("a physical keyboard is explicitly forbidden")
    if requirements.get("commercialization_required") is not False:
        raise ValueError("marketing / selling is OUT of this engineering decision")
    if requirements.get("security_and_safe_power_mandatory") is not True:
        raise ValueError("security and electrical safety must remain mandatory")
    if requirements.get("max_closed_size_mm") != [155,80,18]:
        raise ValueError("do not silently relax pocket or thickness constraint")
    budget=requirements.get("target_budget_ntd")
    if type(budget)!=int or not 0<budget<100000:
        raise ValueError("budget must be an explicit integer NTD target")
    if not isinstance(payload.get("candidates"),list) or len(payload["candidates"])<3:
        raise ValueError("needs credible architecture competitors")
    seen=set()
    for candidate in payload["candidates"]:
        cid=candidate.get("id")
        if not isinstance(cid,str) or not cid or cid in seen:
            raise ValueError("missing or duplicate architecture ID")
        seen.add(cid)
        if candidate.get("category") not in {"build","hybrid","buy","salvage"}:
            raise ValueError("unknown candidate class")
        for key in ("screen_controllers_independent","touch_controllers_independent",
                    "fit_155x80x18","safety_power","role"):
            if not isinstance(candidate.get(key),str) or not candidate[key]:
                raise ValueError(f"{cid} has no declared {key}")
        for key in ("critical_unknowns","cost_exclusions","sourced_items"):
            if not isinstance(candidate.get(key),list):
                raise ValueError(f"{cid} missing {key}")
        for row in candidate["sourced_items"]:
            q,p=row.get("qty"),row.get("ask_ntd")
            if type(q)!=int or q<=0 or type(p)!=int or p<=0:
                raise ValueError(f"{cid} has a malformed or invented-free price")
            if not (isinstance(row.get("url"),str) and row["url"].startswith("https://")
                    and isinstance(row.get("price_kind"),str)
                    and isinstance(row.get("availability"),str)):
                raise ValueError(f"{cid}: asking price must carry provenance and qualification")
        if candidate.get("manufacturer_quote_total_ntd") is not None:
            raise ValueError("no candidate has a real delivered total quotation")


def _canonical_release(candidate_id: str, reference: str) -> dict:
    requirements=[
        ("dual-touch","Two individually usable touchscreens, no physical keyboard",RequirementKind.FUNCTIONAL),
        ("portable","Verified physically closed 155 x 80 x 18 mm or less",RequirementKind.PERFORMANCE),
        ("secure-ssh","Functional secure SSH and code editing, measured on device",RequirementKind.FUNCTIONAL),
        ("safe-power","Protected charging and powered thermal proof",RequirementKind.SAFETY),
        ("repair","Serviceable panel, cable, hinge and cell demonstrated",RequirementKind.PERFORMANCE),
        ("full-price","Delivered end-to-end BOM and assembly cost within engineering target",RequirementKind.CONSTRAINT),
    ]
    mp=MachineProject(
        project_id=f"hs-pocket-{candidate_id}",
        name=f"Cyberdeck architecture study: {candidate_id}",
        purpose="Commercial-grade product engineering without go-to-market obligations",
        requested_release_state=ReleaseState.OPERATIONALLY_AUTHORIZED,
        requirements=[
          Requirement(requirement_id=f"r-{rid}",statement=statement,kind=kind,
                      verification_method_ids=[f"v-{rid}"],authority=AuthorityState.DECLARED)
          for rid,statement,kind in requirements
        ],
        verifications=[
          VerificationMethod(verification_id=f"v-{rid}",name=f"Qualification of {rid}",
                             method_type=VerificationType.TEST,requirement_ids=[f"r-{rid}"])
          for rid,statement,kind in requirements
        ],
        metadata={"source_evidence":"seller asking prices + manufacturer architecture declarations",
                  "input_manifest_sha256":reference,"no_sale_business_mandate":True},
    )
    a=mp.assess_release()
    return {
        "requested_state":a.requested_state.value,
        "achieved_state":a.achieved_state.value,
        "allowed":a.allowed,
        "blocking_issue_codes":sorted({v.code for v in a.blockers}),
        "all_six_product_verifications":"planned_not_executed",
    }


def evaluate(data: dict, *, repo_root: Path) -> dict:
    _validate(data)
    digest="sha256:"+hashlib.sha256(_canonical(data)).hexdigest()
    budget=data["product_requirement"]["target_budget_ntd"]
    results=[]
    for c in data["candidates"]:
        cid=c["id"]
        subtotal=sum(x["ask_ntd"]*x["qty"] for x in c["sourced_items"])
        quote_n=len(c["sourced_items"])
        quote_kind="contingent_mixed_variant" if any(
            "mixed_variant" in x["price_kind"] for x in c["sourced_items"]
        ) else "seller_asking_price_only"
        if not quote_n:
            quote_kind="no_comparable_NTD_seller_asks"
        if quote_n and subtotal>budget:
            budget_gate="asking_price_subtotal_already_above_budget"
        else:
            budget_gate="all_in_budget_unknown_components_and_delivery_unquoted"
        native_mechanical=None
        if cid=="radxa_cm5_dual_50":
            link=c.get("native_fit_report")
            if not isinstance(link,str) or link.startswith("/") or ".." in Path(link).parts:
                raise ValueError("CM5 must reference prior HS mechanical evidence")
            f=repo_root/link
            report=json.loads(f.read_text())
            if report.get("schema")!="hs.cyberdeck_dual_touch_packaging.v1":
                raise ValueError("CM5 source is not native HS fit report")
            if report.get("requirements",{}).get("hard_max_thickness_mm")!=18:
                raise ValueError("CM5 source attempted to relax user's pocket constraint")
            target=next((x for x in report.get("profiles",[])
                         if x.get("closed_thickness_mm")==18),None)
            if target is None or target.get("nominal_research_fit") is not False:
                raise ValueError("native HS evidence no longer rejects CM5 18mm design")
            native_mechanical={
                "source_path":link,
                "source_sha256":"sha256:"+hashlib.sha256(f.read_bytes()).hexdigest(),
                "18mm_nominal_gap_mm":target["compute_to_panel_clearance_mm"],
                "hard_constraint_met":report["hard_constraint_met"],
                "note":"native HS AABB stack, assumed components, not full part or tolerance validation",
            }
        if cid in RIGID_SCREEN_REJECT:
            topology="not_this_two_rigid_touchscreen_product"
        elif cid=="intact_phone_dual_display":
            topology="two_displays_possible_but_no_verified_pocket_hinge"
        elif cid=="esp32_dual_43":
            topology="two_rigid_touch_modules_declared_no_live_terminal"
        else:
            topology="two_screen_port_design_documented_no_simultaneous_validation"
        footprint_check=None
        declared=c.get("module_footprint_mm")
        if declared is not None:
            if not (isinstance(declared,list) and len(declared)==2 and
                    all(type(v) in (int,float) and v>0 for v in declared) and
                    c.get("module_size_source"," ").startswith("https://")):
                raise ValueError("source-backed full physical module XY required")
            length,width=max(declared),min(declared)
            usable_length,usable_width=155-2*1.6,80-2*1.6
            footprint_check={"module_oriented_length_mm":length,
                "module_oriented_width_mm":width,
                "native_FDM_usable_length_mm":usable_length,
                "native_FDM_usable_width_mm":usable_width,
                "source_url":c["module_size_source"],
                "fits_nominal_xy":length<=usable_length and width<=usable_width}
        complete_module_thickness=c.get("full_module_depth_mm")
        if complete_module_thickness is not None and (type(complete_module_thickness) not in (float,int) or complete_module_thickness<=0):
            raise ValueError("bad full module thickness")
        two_module_minimum=round(complete_module_thickness*2,3) if complete_module_thickness is not None else None
        if cid=="radxa_cm5_dual_50":
            packaging="failed_18mm_declared_HS_stack"
        elif footprint_check is not None and not footprint_check["fits_nominal_xy"]:
            packaging="manufacturer_panel_xy_exceeds_155x80_case"
        elif two_module_minimum is not None and two_module_minimum>18:
            packaging="two_unmodified_display_modules_exceed_18mm_alone"
        elif cid=="esp32_dual_43":
            packaging="existing_HS_shell_29_6mm_not_18mm"
        elif cid=="intact_phone_dual_display":
            packaging="external_assembly_not_self_contained_pocket"
        elif cid=="used_fold4":
            packaging="pocketable_but_flexible_OLED_and_used_hinge_risk"
        else:
            packaging="not_measured_for_155x80x18"
        results.append({
            "candidate_id":cid,"name":c["name"],"category":c["category"],
            "engineering_role":c["role"],
            "declared_native_linux":c["native_linux"],
            "asking_price_subtotal_ntd":subtotal if quote_n else None,
            "number_of_listed_price_items":quote_n,
            "price_confidence":quote_kind,
            "sourced_price_items":[{"name":x["name"],"qty":x["qty"],
                 "ask_ntd":x["ask_ntd"],"url":x["url"],"price_kind":x["price_kind"],
                 "availability":x["availability"]} for x in c["sourced_items"]],
            "all_in_prototype_price_ntd":None,
            "budget_status":budget_gate,
            "display_topology":topology,
            "pocketability":packaging,
            "module_footprint_gate":footprint_check,
            "two_module_minimum_thickness_mm":two_module_minimum,
            "native_hs_mechanical_fit_evidence":native_mechanical,
            "unresolved_requirements":list(MANDATORY_EVIDENCE),
            "critical_unknowns":c["critical_unknowns"],
            "unpriced_subsystems":c["cost_exclusions"],
            "machine_release":_canonical_release(cid,digest),
            "product_qualified":False,
            "purchasing_authorized":False,
            "manufacturing_authorized":False,
        })
    by_id={row["candidate_id"]:row for row in results}
    if not {"cm4_dual_dsi","cm4_narrow_50_dsi","cm4_43_dsi",
            "cm4_narrow_custom","esp32_dual_43","radxa_cm5_dual_50","used_fold4"}<=by_id.keys():
        raise ValueError("missing controlled Linux/MCU/CM5/used-fold price comparison")
    # A low asking-price subset cannot "win" if its LCD is too wide, the two
    # module envelopes are already too thick, or the screen prices are absent.
    # A surviving form factor is still NOT proof of <=18mm Z or a delivered BOM.
    priced_linux_footprint_leads=[r for r in results if r["declared_native_linux"] and
                      r["candidate_id"]!="radxa_cm5_dual_50" and
                      r["module_footprint_gate"] is not None and
                      r["module_footprint_gate"]["fits_nominal_xy"] and
                      r["pocketability"] not in {
                          "two_unmodified_display_modules_exceed_18mm_alone",
                          "manufacturer_panel_xy_exceeds_155x80_case"} and
                      not any("DISPLAY MODULE" in x.upper() for x in r["unpriced_subsystems"]) and
                      r["asking_price_subtotal_ntd"] is not None and
                      r["asking_price_subtotal_ntd"]<=budget]
    priced_linux_footprint_leads.sort(key=lambda r:(r["asking_price_subtotal_ntd"],r["candidate_id"]))
    preferred=priced_linux_footprint_leads[0]["candidate_id"] if priced_linux_footprint_leads else None
    return {
        "schema":REPORT_SCHEMA,
        "input_sha256":digest,
        "comparison_date":data["as_of"],
        "product_requirement":data["product_requirement"],
        "results":results,
        "preferred_linux_research_candidate_id":preferred,
        "preferred_lowest_integrated_cost_experiment_id":"esp32_dual_43",
        "highest_information_gain_thin_linux_study":"cm4_narrow_custom",
        "no_priced_Linux_architecture_meets_both_footprint_and_budget":preferred is None,
        "reject_current_cm5_18mm_package":True,
        "decision":"RESEARCH_CONTINUE_NO_FULL_BUILD_OR_PURCHASE_AUTHORITY",
        "rationale":{
           "linux_choice":"CM4 has dual DSI ports, but the cheap 5in B display exceeds 80mm width, the cheap 4.3in module is 14.05mm each, and the narrower 5in D display plus CM4 already exceeds NT$8000 before the carrier. Bare narrow panel remains an unquoted research lead, not a chosen product",
           "mcu_choice":"Dual integrated displays are useful for low-cost remote terminal proof, but no native Linux or full GUI benchmark",
           "phone_choice":"Keep intact phone as buy-vs-build functional benchmark; salvaged OEM mainboard not a generic second-display controller",
           "constraint":"No candidate has verified both panels, 18 mm fit, protected power, delivered cost and actual programming workflow",
        },
        "commercialization_required":False,
        "marketing_and_distribution_out_of_scope":True,
        "buyer_demand_measured":False,
        "any_candidate_manufacturing_authorized":False,
        "any_candidate_purchasing_authorized":False,
        "supplier_checkout_quote_confirmed":False,
    }


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--candidates",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    content=json.loads(args.candidates.read_text())
    repo_root=Path(__file__).resolve().parents[2]
    result=evaluate(content,repo_root=repo_root)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        "decision":result["decision"],
        "linux_research_candidate":result["preferred_linux_research_candidate_id"],
        "cost_trial":result["preferred_lowest_integrated_cost_experiment_id"],
        "sourced_subtotals_ntd":{
            r["candidate_id"]:r["asking_price_subtotal_ntd"] for r in result["results"]
        },
        "manufacturing_authorized":result["any_candidate_manufacturing_authorized"],
    },indent=2))


if __name__=="__main__":
    main()

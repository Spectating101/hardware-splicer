"""HS local-first dual portrait workstation buy/build and usability decision.

Evidence layers:
  manufacturer-sourced parts + asking prices (not delivered cost);
  real manufacturer STEP measured by OpenCascade (not an assembled product);
  real Chromium/xterm.js SSH input (not actual glass, CM5, or human typing).

Pass one layer never authorizes the others. Unlike earlier CM4 studies, local
Linux development and 4GB/8GB RAM are explicit RESEARCH targets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA="hs.dual_portrait_workstation_sources.v1"
CAD_SCHEMA="hs.vendor_step_waveshare_5inch_D_open_cascade.v1"
BROWSER_SCHEMA="hs.dual_portrait_vs_DS_real_browser_benchmark.v1"
RESULT_SCHEMA="hs.dual_portrait_workstation_tradeoff_result.v1"


def _require(ok:bool,msg:str)->None:
    if not ok:
        raise ValueError("HS dual portrait study: "+msg)


def evaluate(s:dict,c:dict,b:dict)->dict:
    _require(s.get("schema")==SCHEMA,"invalid vendor evidence schema")
    r=s.get("requirements",{})
    _require(r.get("dual_screen_count")==2 and r.get("both_panels_capacitive_touch") is True
             and r.get("physical_keyboard") is False and r.get("screen_orientation")=="portrait",
             "do not replace two portrait touchscreens with a gaming handheld")
    _require(r.get("screen_resolution_each_px")==[720,1280],"screen specification changed")
    _require(r.get("local_development_required") is True,
             "local Linux development must not be replaced by SSH-only")
    _require(r.get("research_ram_floor_gb")==4 and r.get("research_ram_preferred_gb")==8,
             "cannot redefine provisional performance tiers silently")
    _require(r.get("closed_xyz_stretch_goal_mm")==[155,80,18]
             and r.get("stretch_goal_is_not_a_user_approved_hard_constraint") is True,
             "18mm is stretch goal, not a user-mandated hard dimension")
    _require(r.get("assistant_proposed_cost_goal_ntd")==8000
             and r.get("assistant_cost_goal_user_approved") is False,
             "NT8000 is assistant-proposed, not confirmed budget")
    _require(r.get("safe_power_thermal_and_hinge_cable_required") is True
             and r.get("commercial_launch_required") is False,
             "safety requirement cannot be removed for a business comparison")
    disp=s.get("displays",{})
    _require(disp.get("sku")=="Waveshare 5inch DSI LCD (D) SKU 28970"
             and disp.get("qty")==2 and disp.get("twd_ask_each")==2319
             and disp.get("outer_front_mm")==[70.7,126.9]
             and disp.get("active_view_area_mm")==[62.28,110.32],
             "do not replace narrow portrait panel with cheaper wide one")
    _require(disp.get("both_simultaneous_validated") is False
             and disp.get("after_electronics_relocation_drivers_validated") is False,
             "no CM5 pair driver or panel disassembly has been tested")
    _require(disp.get("local_url","").startswith("https://")
             and disp.get("CAD_zip_url","").startswith("https://"),
             "vendor and seller provenance required")
    computes=s.get("computes",[])
    ids=[x.get("id") for x in computes]
    _require(len(ids)>=5 and len(ids)==len(set(ids)),"compare distinct sourced compute options")
    screen_cost=disp["qty"]*disp["twd_ask_each"]
    prices=[]
    for option in computes:
        _require(option.get("source_url","").startswith("https://"),
                 "compute price lacks listing source")
        _require(option.get("ram_gb",0)>0 and option.get("availability"),
                 "compute RAM and availability must be declared")
        ntd=option.get("price_ntd")
        usd=option.get("price_usd")
        _require((ntd is None) != (usd is None),
                 "seller price must use exactly one declared original currency")
        _require(option.get("emmc_gb") is not None,
                 "Lite vs eMMC is not a negligible build difference")
        if ntd is not None:
            _require(type(ntd) in (float,int) and ntd>0,"positive NTD ask")
            price_total=round(ntd+screen_cost,2)
            remainder=round(r["assistant_proposed_cost_goal_ntd"]-price_total,2)
        else:
            _require(type(usd) in (float,int) and usd>0,"positive USD ask")
            price_total=None
            remainder=None
        prices.append({
            "candidate_id":option["id"],"platform":option["platform"],"mpn":option["mpn"],
            "ram_gb":option["ram_gb"],"emmc_gb":option["emmc_gb"],
            "wifi_on_module":option["wifi"],"availability_at_research":option["availability"],
            "compute_ask_currency":"NTD" if ntd is not None else "USD",
            "compute_ask_original":ntd if ntd is not None else usd,
            "two_Waveshare_D_asks_NTD":screen_cost,
            "compute_and_two_panels_subtotal_NTD":price_total,
            "remaining_to_assistant_proposed_budget_NTD":remainder,
            "power_architecture":option.get("operating_voltage_recommendation"),
            "RAM_research_floor_met":option["ram_gb"]>=r["research_ram_floor_gb"],
            "RAM_research_preference_met":option["ram_gb"]>=r["research_ram_preferred_gb"],
            "known_full_delivered_BOM_NTD":None,
            "simultaneous_dual_DSI_bench_test_passed":False,
            "manufacturing_authorized":False,
        })

    _require(c.get("schema")==CAD_SCHEMA
             and c.get("vendor_model","").startswith("Waveshare 5inch DSI LCD (D)"),
             "actual manufacturer STEP measurement not present")
    _require(c.get("source_zip_url")==disp["CAD_zip_url"]
             and len(c.get("step_sha256",""))==64
             and c.get("analysis_engine","").startswith("OpenCascade"),
             "vendor STEP provenance must be retained")
    outer=c.get("outer_bbox_xyz_mm")
    face=c.get("one_full_face_solid_bbox_mm")
    _require(outer==[70.708,126.908,13.608]
             and face==[70.7,126.9,5.8]
             and c.get("number_solid_components")==365,
             "OpenCascade original model changed, remeasure and requalify")
    _require(c.get("claim_safe_to_remove_standoffs") is False
             and c.get("software_driver_after_disassembly_qualified") is False,
             "dismantling vendor display hardware requires evidence")
    _require(c.get("remaining_after_omitting_deep_solid_envelope_mm")==10.8,
             "vendor STEP component categorization changed")
    _require(c.get("fabrication_qualified") is False,
             "cannot promote manufacturer 3D source into a build-ready product")

    _require(b.get("schema")==BROWSER_SCHEMA
             and b.get("physical_touchscreen_or_CM5_tested") is False
             and b.get("human_typing_tested") is False
             and b.get("device_pixel_ratio_assumed_1_no_OS_scaling_proof") is True,
             "browser layout is not a physical touch/DPI benchmark")
    measurements=b.get("results",[])
    hs=next((m for m in measurements if m.get("device")=="hs_dual_5in_portrait"
             and m.get("fontsize_css_px")==24),None)
    ds=next((m for m in measurements if m.get("device")=="anbernic_rgds_4in_landscape"
             and m.get("fontsize_css_px")==24),None)
    _require(hs is not None and ds is not None,"missing 24px matched-screen comparison")
    _require(hs.get("keyboard_layout")=="wide" and hs.get("smallest_letter_nominal_mm")>=7
             and hs.get("wide_vs_legacy_key_width_gain",0)>=1.7,
             "portrait virtual keyboard must demonstrate improved key width")
    _require(hs.get("cols",0)>0 and hs.get("rows",0)>0
             and not hs.get("horizontal_overflow"),"real viewport shell fit failed")
    _require(any(m.get("symbol_layer_to_real_SSH_verified") is True
                 for m in measurements if m.get("device")=="hs_dual_5in_portrait"),
             "symbol-layer touch SSH interaction not performed")
    _require(any(m.get("real_ssh_touch_pwd_passed") is True
                 for m in measurements if m.get("device")=="hs_dual_5in_portrait"),
             "portrait touch interface must reach real sandboxed SSH")
    flags=s.get("truth",{})
    for k in ("real_two_panels_on_compute_tested","real_flex_under_hinge_tested",
              "real_battery_protection_and_cooling_tested","full_landed_twd_bom",
              "real_ergonomics_and_30min_code_tested","owner_approved_budget",
              "hardware_purchased"):
        _require(flags.get(k) is False,"cannot claim untested physical milestone "+k)
    _require(flags.get("no_full_product_fab_authority") is True,
             "fabrication authority is not available")

    # Screen-only thickness, before any chassis/battery/SoM.
    base=round(c["module_2x_full_assembly_Z_mm"],3)
    no_deep=round(c["module_2x_without_deep_solid_Z_mm"],3)
    face_only=round(c["panel_2x_face_solid_Z_mm"],3)
    _require(base==round(outer[2]*2,3)
             and no_deep==round(c["remaining_after_omitting_deep_solid_envelope_mm"]*2,3)
             and face_only==round(face[2]*2,3), "STEP source thickness arithmetic wrong")
    theoretical_face_only_plus_shells_gap=round(face_only+2*1.6+0.8,3)
    # The mounting structure is not qualified; this is NOT a new valid design.
    return {
       "schema":RESULT_SCHEMA,
       "decision":"PORTRAIT_WORKFLOW_CANDIDATE_PASS_FULL_HARDWARE_UNPROVEN",
       "product_direction":"keep dual portrait 720x1280 touchscreens + native local Linux; DS as mechanical integration reference",
       "revised_evaluation":"CM5-class Linux SoM competing against 2-screen face electronics and thermal packaging, not old CM4-only optimization",
       "price_screen_pair_ask_NTD":screen_cost,
       "sourced_compute_and_screen_subtotals":prices,
       "not_a_shippable_or_verified_BOM":True,
       "vendor_CAD_geometry":{
         "full_single_display_assembled_xyz_mm":outer,
         "full_module_pair_only_depth_mm":base,
         "pair_without_deep_mount_hardware_mm":no_deep,
         "front_solid_pair_only_depth_mm":face_only,
         "front_solids_plus_two_1p6mm_shells_and_0p8mm_gap_mm":theoretical_face_only_plus_shells_gap,
         "remaining_in_assistant_18mm_stretch_goal_without_any_compute_or_battery_mm":
            round(18-theoretical_face_only_plus_shells_gap,3),
         "assembled_two_displays_alone_exceed_18mm":base>18,
         "removing_only_deep_mount_hardware_not_sufficient":no_deep>18,
         "front_solid_electronics_compatible_after_separation_proven":False,
         "no_18mm_hardware_fab_approval":True,
       },
       "browser_portrait":{
         "real_xterm_cells_24px":[hs["cols"],hs["rows"]],
         "compared_rgds_cells_24px":[ds["cols"],ds["rows"]],
         "wide_key_nominal_mm":hs["smallest_letter_nominal_mm"],
         "wide_vs_previous_key_width_gain":hs["wide_vs_legacy_key_width_gain"],
         "real_touch_to_sandboxed_ssh_tested":True,
         "real_symbol_page_to_sandboxed_ssh_tested":True,
         "actual_touch_controller_or_DSI_tested":False,
         "human_ergonomics_tested":False,
         "CSS_pixel_to_physical_mm_is_projection_only":True,
       },
       "research_leads":[
         "4GB WiFi CM5 Lite is a cost-conscious native Linux baseline; missing eMMC, SD card and carrier cost must be added",
         "8GB WiFi CM5 Lite is better aligned to local compile/browser multitasking, but is not a measured performance winner",
         "RK3588S2 Radxa CM5 offers 4xA76+4xA55 but requires a documented 4V3A power architecture and verified local stock",
         "Investigate removable/relocated Waveshare bridge PCB without assuming the panel will retain vendor driver support",
         "Validate both independent physical touch devices and real keyboard hit rate before custom PCB fabrication",
         "Derive a real thermal/battery/FPC/case BOM and realistic thickness goal; do not quietly assume 18mm can be met",
       ],
       "physical_release":{"procure_display_pair":False,"build_custom_carrier":False,
                           "power_with_battery":False,"manufacture_case":False},
    }


def _sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(source:Path,cad:Path,browser:Path,out:Path)->dict:
    result=evaluate(json.loads(source.read_text()),json.loads(cad.read_text()),
                    json.loads(browser.read_text()))
    result["provenance"]={
        "sourced_options_sha256":_sha(source),
        "measured_vendor_STEP_receipt_sha256":_sha(cad),
        "real_Chrome_viewport_result_sha256":_sha(browser),
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    return result


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--sources",required=True,type=Path)
    parser.add_argument("--cad",required=True,type=Path)
    parser.add_argument("--browser",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    a=parser.parse_args()
    result=run(a.sources,a.cad,a.browser,a.out)
    print(json.dumps({"decision":result["decision"],
        "sourced_subtotals_NTD":{
           r["candidate_id"]:r["compute_and_two_panels_subtotal_NTD"]
           for r in result["sourced_compute_and_screen_subtotals"]},
        "full_display_pair_depth_mm":result["vendor_CAD_geometry"]["full_module_pair_only_depth_mm"],
        "portrait_wide_key_mm":result["browser_portrait"]["wide_key_nominal_mm"],
        "fabrication_authorized":result["physical_release"]["manufacture_case"]},indent=2))


if __name__=="__main__":
    main()

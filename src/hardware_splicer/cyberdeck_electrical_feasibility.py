"""HS exact-panel DSI, protected-pack and full-stack qualification.

Evidence/release gate, not a hardware driver or an electrical circuit.
The CM4's TWO physical DSI ports do not imply that an arbitrary ILI9881C
panel will be initialized by the official Touch Display 2 overlay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


INPUT_SCHEMA = "hs.cm4_two_panel_feasibility.v1"
RESULT_SCHEMA = "hs.cm4_two_panel_feasibility_result.v1"


def _need(test: bool, reason: str) -> None:
    if not test:
        raise ValueError("HS component feasibility refused: "+reason)


def evaluate(source: dict, previous: dict) -> dict:
    r = source.get("user_constraints", {})
    c = source.get("cm4", {})
    p = source.get("panel", {})
    kernel = source.get("kernel", {})
    control = source.get("official_control", {})
    pack = source.get("protected_pack", {})
    old = previous
    stack = source.get("stack", {})

    _need(source.get("schema")==INPUT_SCHEMA, "input schema")
    _need(r.get("two_touchscreens") is True and r.get("no_physical_keyboard") is True,
          "two touchscreens and no physical keyboard are mandatory")
    _need(r.get("max_closed_mm")==[155,80,18] and r.get("marketing_business_out_of_scope") is True,
          "pocket size and personal engineering scope cannot be rewritten")
    _need(r.get("budget_user_approved") is False,
          "NTD8000 was an assistant target, not a user-approved budget")
    _need(c.get("exact_mpn")=="CM4102000" and c.get("dsi0_lanes")==2
          and c.get("dsi1_lanes")==4 and c.get("max_gbps_per_lane")==1.0,
          "CM4 source hardware must not be mutated into a different chip")
    _need(p.get("exact_mpn")=="WF50DTYA3MNG10-000" and p.get("count")==2
          and p.get("dsi_lanes")==2 and p.get("controller")=="ILI9881C",
          "exact 2-lane Winstar SKU is required; generic parent is 4-lane")
    _need(p.get("resolution_px")==[720,1280] and p.get("fps_assumption")==60
          and p.get("bpp_assumption")==24, "undeclared pixel-link rate assumptions")
    _need(p.get("fpc_lcd_pins")==40 and p.get("fpc_touch_pins")==6
          and p.get("gt928_touch") is True, "separate DSI/CTP harness is mandatory")
    _need(p.get("datasheet")=="https://www.winstar.com.tw/d/676/WF50DTYA3MNG10-000.pdf",
          "actual Winstar two-lane revision proof missing")
    _need(p.get("thickness_nominal_mm")==3.45
          and p.get("thickness_tolerance_mm")==0.5,
          "vendor maximum thickness cannot be erased")
    _need(kernel.get("repository")=="raspberrypi/linux"
          and kernel.get("ref")=="rpi-6.12.y"
          and kernel.get("driver_blob_sha")=="416ff6fe6d8995fc42a37ea3565a9faabdbde427"
          and kernel.get("overlay_blob_sha")=="830e28703e57ca43c831f2c82ad9bc2e5b0a8e11",
          "reviewed driver/overlay identity must be exact, not a claim about latest kernel")
    _need(kernel.get("reviewed_file_does_not_name_exact_winstar") is True
          and kernel.get("official_5inch_compatibility")=="raspberrypi,dsi-5inch"
          and control.get("not_interchangeable_with_winstar") is True,
          "a supported ILI9881C-based official panel DOES NOT qualify Winstar")
    _need(control.get("display_module_xy_mm")==[143.5,91.5]
          and control.get("display_module_depth_mm")==16,
          "official driver reference panel physical envelope is different")
    _need(pack.get("mpn")=="LP525178" and pack.get("overall_depth_mm")==5.2
          and pack.get("overall_length_mm")==78.6
          and pack.get("overall_width_mm")==50.3
          and pack.get("PCM_included") is True
          and pack.get("NTC_included") is False,
          "protected pack source / thermistor limitation not preserved")
    _need(pack.get("source","").startswith("https://")
          and pack.get("shipping_and_local_price_unknown") is True
          and pack.get("connector_and_swelling_fit_not_qualified") is True,
          "seller pack dimensions are not certified assembled fit")
    _need(p.get("vendor_init_table_confirmed") is False
          and p.get("timing_and_DSI_mode_validated") is False
          and p.get("linux_exact_panel_driver_confirmed") is False,
          "no actual Winstar driver proof; do not declare software ready")
    _need(c.get("official_firmware_supported_panels_only") is True,
          "CM4 docs warn about DSI support")
    _need(source.get("release",{}).get("hardware_purchased") is False
          and source["release"].get("hardware_powered") is False
          and source["release"].get("fabrication_authorized") is False,
          "actual bench release cannot be invented")
    for key in ("dual_exact_panels_bench_verified", "independent_touch_axes_verified",
                "protected_battery_and_charger_measured", "backlight_current_controller_verified",
                "hinge_FPC_cycle_qualified", "full_NTD_BOM_confirmed",
                "source_panel_init_table_obtained"):
        _need(source.get("gate_truth",{}).get(key) is False,
              "bench verification has not occurred: "+key)
    _need(old.get("schema")=="hardware_splicer.inset_hinge_qualification.v1"
          and old.get("manufacturing_authorized") is False,
          "previous native inset hinge was not hardware authorized")
    _need(old.get("retention",{}).get("screen_retention_gate")=="BLOCKED",
          "previous HS retained screen support failure")
    _need(old.get("worst_case_packaging",{}).get("minimum_closed_thickness_mm")==19.05,
          "prior nominal protected-pack-free thickness source changed")
    _need([stack.get(k) for k in ("base_shell_floor_mm","lid_shell_floor_mm",
          "closed_gap_mm","screen_bondline_assumption_mm","min_component_research_clearance_mm")]
          ==[1.6,1.6,0.8,0.15,1.0], "don't silently loosen research layer margins")

    # Simple ACTIVE PIXEL BANDWIDTH, not a proven DSI pixel-clock setting.
    # MIPI protocol/blanking overhead, PHY clock limits, lane mapping and
    # panel init are not proved by this optimistic calculation.
    active_lane_gbps = (p["resolution_px"][0]*p["resolution_px"][1]*
                       p["fps_assumption"]*p["bpp_assumption"]/
                       p["dsi_lanes"]/1e9)
    panel_max = p["thickness_nominal_mm"]+p["thickness_tolerance_mm"]
    cm4_upper = c["mated_height_mm"]+c["carrier_pcb_mm"]
    def closed_lower_bound(battery_depth:float)->float:
        lower=stack["base_shell_floor_mm"]+max(cm4_upper,battery_depth)+(
              stack["min_component_research_clearance_mm"]+panel_max)
        upper=stack["lid_shell_floor_mm"]+panel_max+stack["screen_bondline_assumption_mm"]
        return round(lower+stack["closed_gap_mm"]+upper,3)

    old_battery=closed_lower_bound(source["previous_battery_placeholder_depth_mm"])
    protected_pack=closed_lower_bound(pack["overall_depth_mm"])
    _need(old_battery==old["worst_case_packaging"]["minimum_closed_thickness_mm"],
          "mismatch with predecessor packaging equation")
    led_min=p["backlight_voltage_min_v"]*p["backlight_current_a"]*2
    led_max=p["backlight_voltage_max_v"]*p["backlight_current_a"]*2
    _need([round(led_min,3),round(led_max,3)]==
          old["electrical"]["two_backlights_w"],
          "voltage/current model diverges from earlier HS report")

    return {
      "schema":RESULT_SCHEMA,
      "product":"CM4 Lite + 2x exact 2-lane Winstar thin touchscreens",
      "engineering_goal":"commercially credible physical product, no commercial launch",
      "technical_decision":"NO_GO_COMPONENT_ORDER_WITHOUT_PANEL_DRIVER_AND_BENCH_PLAN",
      "display":{
        "dsi0_hardware_lanes":c["dsi0_lanes"],
        "dsi1_hardware_lanes":c["dsi1_lanes"],
        "exact_panel_lanes":p["dsi_lanes"],
        "active_pixel_only_gbps_per_lane":round(active_lane_gbps,6),
        "hardware_lane_rate_limit_gbps":c["max_gbps_per_lane"],
        "active_data_rate_below_raw_limit":active_lane_gbps<c["max_gbps_per_lane"],
        "actual_Phy_clock_or_blanking_timing_verified":False,
        "same_chip_as_official_panel_does_not_mean_same_init":True,
        "reviewed_kernel_driver_names_exact_vendor_panel":False,
        "panel_specific_initialization_and_display_mode_available":False,
        "two_independent_Linux_DSI_outputs_tested":False,
        "two_GT928_touch_devices_tested":False,
        "vendor_panel_software_gate":"BLOCKED",
        "required_pin_interfaces_per_panel":{"DSI_FPC":40,"touch_FPC":6},
      },
      "official_reference":{
        "name":control["name"],
        "known_supported_software_reference":True,
        "outer_xy_mm":control["display_module_xy_mm"],
        "depth_mm":control["display_module_depth_mm"],
        "fits_80mm_body":False,
        "drop_in_winstar_driver_equivalent":False,
      },
      "protected_pack_comparison":{
        "previous_assumed_unprotected_cell_depth_mm":source["previous_battery_placeholder_depth_mm"],
        "candidate_part":pack["mpn"],
        "manufacturer_claimed_protected_pack_depth_mm":pack["overall_depth_mm"],
        "nominal_pack_Wh":pack["nominal_wh"],
        "NTC_present":False,
        "seller_minimum_order":pack["seller_min_order"],
        "price_and_shipping_validated":False,
        "pack_thermal_and_protection_system_qualified":False,
        "CM4_mated_plus_carrier_height_mm":round(cm4_upper,3),
        "primary_lower_stack_dominant_component":"CM4" if cm4_upper>pack["overall_depth_mm"] else "battery",
        "old_6mm_cell_nominal_lower_bound_mm":old_battery,
        "new_protected_5p2mm_pack_nominal_lower_bound_mm":protected_pack,
        "nominal_thickness_saved_mm":round(old_battery-protected_pack,3),
        "remaining_shortfall_to_18mm_mm":round(protected_pack-18,3),
        "min_calculation_excludes_connector_placement_and_swelling":True,
      },
      "backlight":{
        "two_panel_range_W":[round(led_min,3),round(led_max,3)],
        "driver_needed":"two channels or independently switched constant-current LED drive + boost voltage",
        "5V_direct_connection_acceptable":False,
        "driver_schematic_or_SPICE_test_completed":False,
      },
      "root_blockers":[
        "Exact WF50DTYA3MNG10-000 DSI init/timing mode not in reviewed Raspberry Pi driver/overlay",
        "Dual DSI0/DSI1, separate GT928 touch/IRQ/reset and compositor mapping not on-bench",
        "Protected pack narrows height but CM4/connector stack dominates minimum closed thickness",
        "Physical 18mm, screen bonding, rear hinge support, thermal and flex fatigue not qualified",
        "LED backlight current-controlled 20-24V boost and safe cell charger not designed/tested",
        "No exact Taiwan all-in component+fabrication quote or physical product build",
      ],
      "next_cheapest_experiment":{
        "name":"Firmware feasibility and supplier capability gate BEFORE buying two screens",
        "vendor_request":["Exact -000 2-lane ILI9881C panel DSI command-init table and pixel timing",
          "Known Raspberry Pi 4/CM4 Linux device-tree or tested reference driver",
          "Power sequencing for VCI/IOVCC/GT928 and LED backlight reference circuit",
          "Pin/FPC bending data, minimum radius, permissible repeated cycles, connector+retainer drawings",
          "Sample purchase price delivered Taiwan for ONE panel; availability and warranty"],
        "software_work":["Review Raspberry Pi 6.12 ILI9881C descriptor for exact compatible panel rather than copying Touch Display 2",
          "Plan two 2-lane DSI channels and two independent I2C/IRQ/reset paths",
          "Use official supported Touch Display 2 only as bench software control, not a pocket geometry substitute"],
        "first_physical_purchase_authorized":False,
        "two_panel_purchase_authorized":False,
      },
      "release":{"safe_to_power":False,"manufacturing_authorized":False,"component_purchase_authorized":False},
    }


def main() -> None:
    cli=argparse.ArgumentParser()
    cli.add_argument("--input",type=Path,required=True)
    cli.add_argument("--out",type=Path,required=True)
    a=cli.parse_args()
    raw=a.input.read_bytes()
    source=json.loads(raw)
    previous_file=a.input.parent/source["existing_HS_mechanical_report"]
    previous=json.loads(previous_file.read_text())
    result=evaluate(source,previous)
    result["evidence_receipt"]={
        "input_sha256":hashlib.sha256(raw).hexdigest(),
        "prior_inset_gate_sha256":hashlib.sha256(previous_file.read_bytes()).hexdigest(),
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({
        "decision":result["technical_decision"],
        "active_pixel_bandwidth_gbps_per_lane":result["display"]["active_pixel_only_gbps_per_lane"],
        "protected_pack_new_lower_bound_mm":result["protected_pack_comparison"]["new_protected_5p2mm_pack_nominal_lower_bound_mm"],
        "DSI_boot_proven":result["display"]["two_independent_Linux_DSI_outputs_tested"],
        "component_order_authorized":result["release"]["component_purchase_authorized"],
    },indent=2))


if __name__=="__main__":
    main()

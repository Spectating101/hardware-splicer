"""Electrically compatible candidate: active SGM2590 replacing obsolete SGM2576.

The manufacturer explicitly recommends SGM2590 for SGM2576. The five pin
functions and SOT-23-5 class are preserved, but the ILIM equation changes:
SGM2590 nominal ILIM(mA) = 6612 / R_ILIM(kOhm)^0.982.
Package geometry, ESD, currents and approval remain unqualified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import hs_cm5_5v4v_usb_power_reference as design

PROJECT="CM5_POWER_USB_SGM2590_NO_FAB"
SOURCE_DATASHEET="https://www.sg-micro.com/product/SGM2590"
PART="SGM2590XN5G/TR"
R_KOHM=4.53
ILIM_MA=6612/(R_KOHM**0.982)


def generate_candidate(out: Path,manifest:Path):
    design.USB_SWITCH_MODEL="SGM2590"
    design.b.PROJECT=PROJECT
    design.b.ROOTNS="hs.cm5.power.usb.sgm2590.20261107"
    design.COMPONENTS=[
        (ref,("HS_Power:SGM2590" if ref=="U2" else lib),
         ("SGM2590XN5G_TR_ACTIVE_PIN_EQUIVALENT_NOT_LAYOUT_APPROVED" if ref=="U2"
          else "4.53k_1pct_USB_ILIM" if ref=="R6" else val),
         x,y,pins)
        for ref,lib,val,x,y,pins in design.COMPONENTS
    ]
    design.DATA={
        **design.DATA,
        "usb_switch":"SGM2590",
        "usb_switch_mpn":PART,
        "usb_switch_status":"ACTIVE_VIA_MANUFACTURER_PRODUCT_PAGE",
        "usb_switch_manufacturer_recommends_replacing":"SGM2576",
        "usb_switch_pin_count":5,
        "usb_switch_form_factor":"SOT-23-5",
        "usb_switch_pin3_name_vendor_datasheet":"ILIM",
        "usb_pin3_name_vendor_datasheet":"ILIM",
        "usb_pin3_name_reference_pdf":"OCB",
        "usb_current_limit_formula":"ILIM_mA=6612/(RILIM_kOhm**0.982)",
        "usb_rilim_ohm":4530,
        "usb_ilim_typical_a":ILIM_MA/1000,
        "sgm2590_en_pulldown_ohm":1_200_000,
        "sgm2590_recommended_successor_ref":SOURCE_DATASHEET,
        "sgm2590_datasheet_url":"https://www.sg-micro.com/rect/assets/28859410-24d5-43f6-8723-76d4c3a5d0e7/SGM2590_SGM2590D.pdf",
        "vendor_website_price_usd_single_unit_reference":0.525,
        "supplier_actual_order_placed":False,
        "replacement_footprint_dimension_compared":False,
        "replacement_thermal_behavior_validated":False,
        "usb_esd_present":False,
        "fabrication_authorized":False,
    }
    root=Path("/usr/share/kicad/symbols")
    return design.generate(
        (root/"Connector_Generic.kicad_sym").read_text(),
        (root/"Connector.kicad_sym").read_text(),
        (root/"Device.kicad_sym").read_text(),
        (root/"power.kicad_sym").read_text(),
        out,manifest)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--manifest",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(generate_candidate(args.out,args.manifest),indent=2))

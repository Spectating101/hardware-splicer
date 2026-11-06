"""CM5 5V input -> MP8759 4V / SGM2576 USB host reference-power schematic.

Manufacturer-supported component pin numbers, but NOT approved for fabrication.
Uses live KiCad EDA symbol/netlist checks and component-datasheet provenance.
SGM2576 is OBSOLETE and Radxa's OCB label conflicts with official ILIM pin.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import hs_cm5_connected_bench_schematic as b

PROJECT="CM5_POWER_USB_REFERENCE_NO_FAB"
b.PROJECT=PROJECT
b.ROOTNS="hs.cm5.power.usb.20261107"
MP_PINS={
 1:("VIN",-15.24,10.16,0,"power_in"),
 2:("PGND",15.24,-10.16,180,"power_in"),
 3:("PG",-15.24,-10.16,0,"open_collector"),
 4:("NC",-15.24,-15.24,0,"no_connect"),
 5:("VOUT",15.24,5.08,180,"input"),
 6:("MODE",-15.24,0,0,"input"),
 7:("SW",15.24,10.16,180,"power_out"),
 8:("BST",15.24,0,180,"input"),
 9:("VCC",15.24,-5.08,180,"power_out"),
 10:("AGND",15.24,-15.24,180,"power_in"),
 11:("FB",-15.24,-5.08,0,"input"),
 12:("EN",-15.24,5.08,0,"input"),
}
SGM_PINS={
 1:("VOUT",12.70,5.08,180,"power_out"),
 2:("GND",12.70,-5.08,180,"power_in"),
 3:("ILIM",-12.70,-5.08,0,"input"),
 4:("EN",-12.70,0,0,"input"),
 5:("VIN",-12.70,5.08,0,"power_in"),
}
COMPONENTS=[
 ("J1","Connector_Generic:Conn_01x02","EXTERNAL_5V_BENCH_ONLY",73.66,99.06,
      {1:"VCC5V0_SYS",2:"GND"}),
 ("J2","Connector_Generic:Conn_01x06","CM5_HARNESS_LOGICAL_NOT_PINOUT",381.00,99.06,
      {1:"VCC_SYSIN",2:"GND",3:"USB20_HOST0_DP",4:"USB20_HOST0_DM",
       5:"USB_HOST_PWREN_H",6:"GND"}),
 ("J3","Connector:USB_A","USB2_A_HOST_ESD_NOT_DESIGNED",327.66,99.06,
      {1:"USB_VBUS_SW",2:"USB20_HOST0_DM",3:"USB20_HOST0_DP",4:"GND"}),
 ("U1","HS_Power:MP8759GD","MP8759GD-Z_REQUIRES_SI_REVIEW",132.08,99.06,
      {1:"VCC5V0_SYS",2:"GND",5:"VCC_SYSIN",7:"SW_MPS",8:"BST_MPS",
       9:"VCC_MPS",10:"GND",11:"FB_MPS",12:"EN_MPS"}),
 ("U2","HS_Power:SGM2576","SGM2576_OBSOLETE_SUBSTITUTE_NEEDED",259.08,99.06,
      {1:"USB_VBUS_SW",2:"GND",3:"ILIM_USB",4:"USB_HOST_PWREN_H",
       5:"VCC5V0_SYS"}),
 ("L1","Device:L","1.5uH_ISAT_UNVERIFIED",172.72,210.82,
      {1:"SW_MPS",2:"VCC_SYSIN"}),
 ("R1","Device:R","47k_1pct_RFB_TOP",66.04,210.82,
      {1:"VCC_SYSIN",2:"FB_MPS"}),
 ("R2","Device:R","8.2k_1pct_RFB_BOTTOM",86.36,210.82,
      {1:"FB_MPS",2:"GND"}),
 ("R3","Device:R","510k_REN_TOP",106.68,210.82,
      {1:"VCC5V0_SYS",2:"EN_MPS"}),
 ("R4","Device:R","510k_REN_BOTTOM",127.00,210.82,
      {1:"EN_MPS",2:"GND"}),
 ("R5","Device:R","3.3R_BOOT_SERIES",147.32,210.82,
      {1:"BST_MPS",2:"BST_SERIES"}),
 ("R6","Device:R","4.7k_1pct_USB_ILIM",193.04,210.82,
      {1:"ILIM_USB",2:"GND"}),
 ("C1","Device:C","10uF_10V_VIN",66.04,248.92,
      {1:"VCC5V0_SYS",2:"GND"}),
 ("C2","Device:C","100nF_10V_VIN",86.36,248.92,
      {1:"VCC5V0_SYS",2:"GND"}),
 ("C3","Device:C","22uF_10V_VOUT",106.68,248.92,
      {1:"VCC_SYSIN",2:"GND"}),
 ("C4","Device:C","22uF_10V_VOUT",127.00,248.92,
      {1:"VCC_SYSIN",2:"GND"}),
 ("C5","Device:C","100nF_10V_VOUT",147.32,248.92,
      {1:"VCC_SYSIN",2:"GND"}),
 ("C6","Device:C","220nF_10V_BOOT",167.64,248.92,
      {1:"BST_SERIES",2:"SW_MPS"}),
 ("C7","Device:C","1uF_10V_REG_VCC",187.96,248.92,
      {1:"VCC_MPS",2:"GND"}),
 ("C8","Device:C","1uF_10V_USB_IN",208.28,248.92,
      {1:"VCC5V0_SYS",2:"GND"}),
 ("C9","Device:C","22uF_10V_USB_OUT",228.60,248.92,
      {1:"USB_VBUS_SW",2:"GND"}),
]
DATA={
 "scope":"connected_5v_to_4v_and_switched_usb_reference_design_no_fab",
 "module_supply_recommendation_v":4.0,"module_supply_recommendation_a":3.0,
 "regulator":"MP8759GD-Z","regulator_min_vin_v":4.5,
 "feedback_vref_v":0.6,"feedback_high_ohm":47000,
 "feedback_low_ohm":8200,
 "expected_nominal_vout_v":0.6*(1+47000/8200),
 "usb_switch":"SGM2576","usb_switch_status":"OBSOLETE",
 "usb_pin3_name_vendor_datasheet":"ILIM",
 "usb_pin3_name_reference_pdf":"OCB",
 "usb_rilim_ohm":4700,
 "usb_ilim_typical_a":6800/4700,
 "usb_limit_variation_and_thermal_unverified":True,
 "vendor_ref":"https://dl.radxa.com/cm5/v2200/radxa_cm5_io_v2200_schematic.pdf",
 "mp_datasheet":"https://www.monolithicpower.com/en/documentview/productdocument/index/version/2/document_type/Datasheet/lang/en/sku/MP8759GD-Z/document_id/1011/",
 "sgm_datasheet":"https://www.sg-micro.com/rect/assets/281ce0d1-eaf9-4b8e-97e0-dc17087ed2fe/SGM2576_SGM2576B.pdf",
 "upstream_board_revisions_verified_compatible":False,
 "battery_charging_present":False,
 "usb_esd_present":False,
 "usb_data_common_mode_protection_present":False,
 "rated_inductor_selected":False,
 "full_bom_mpn_footprints_qualified":False,
 "power_up_test_passed":False,
 "fabrication_authorized":False
}

def unit_symbol(local: str,ref_prefix: str,pins:dict[int,tuple]) -> str:
    symbol_name="HS_Power:"+local
    rows=[f'(symbol {b.kquote(symbol_name)}',
          '(exclude_from_sim no) (in_bom yes) (on_board yes)',
          f'(property "Reference" "{ref_prefix}" (at 0 23 0) (effects (font (size 1.27 1.27))))',
          f'(property "Value" {b.kquote(local)} (at 0 21 0) (effects (font (size 1.27 1.27))))',
          '(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
          f'(symbol {b.kquote(local+"_1_1")}',
          '(rectangle (start -10.16 17.78) (end 10.16 -17.78) '
          '(stroke (width 0.254) (type default)) (fill (type background)))']
    for n,(label,x,y,angle,kind) in sorted(pins.items()):
        rows.append(f'(pin {kind} line (at {x:.4f} {y:.4f} {angle}) (length 5.08)'
                    f' (name {b.kquote(label)} (effects (font (size 1.0 1.0))))'
                    f' (number "{n}" (effects (font (size 1.0 1.0)))))')
    rows+=[')',' )']
    return '\n'.join(rows)

def generate(conn_lib:str,connector_lib:str,dev_lib:str,power_lib:str, out:Path,manifest:Path) -> dict:
    specs={
      "HS_Power:MP8759GD":(unit_symbol("MP8759GD","U",MP_PINS),MP_PINS),
      "HS_Power:SGM2576":(unit_symbol("SGM2576","U",SGM_PINS),SGM_PINS),
    }
    builtin={
      "Connector_Generic:Conn_01x02":(conn_lib,"Conn_01x02"),
      "Connector_Generic:Conn_01x06":(conn_lib,"Conn_01x06"),
      "Connector:USB_A":(connector_lib,"USB_A"),
      "Device:L":(dev_lib,"L"),
      "Device:R":(dev_lib,"R"),
      "Device:C":(dev_lib,"C"),
    }
    symbols=[v[0] for v in specs.values()]
    symbols.append(b.inner_library(b.extract_symbol(power_lib,"PWR_FLAG"),"PWR_FLAG","power:PWR_FLAG"))
    for lib,(data,name) in builtin.items():
        original=b.extract_symbol(data,name)
        symbols.append(b.inner_library(original,name,lib))
        coords=b.pin_coordinates(original,name,{1})[1]
        specs[lib]=(original,{n:(p[4],p[1],p[2],p[3],p[0]) for n,p in coords.items()})
    if len({x[0] for x in COMPONENTS})!=len(COMPONENTS):
        raise ValueError("duplicated reference designator")
    if {lib for _,lib,_,_,_,_ in COMPONENTS}-set(specs):
        raise ValueError("missing component symbol")
    used_net=__import__("collections").defaultdict(list)
    drawing=[]
    for ref,lib,value,x,y,expected in COMPONENTS:
        definition,signal_pins=specs[lib]
        if not set(expected).issubset(signal_pins):
            raise ValueError("not all requested pad numbers are in symbol "+ref)
        drawing.append(b.sym_instance(lib,ref,value,x,y,1,ref))
        for n,net in expected.items():
            _,px,py,angle,kind=signal_pins[n]
            start_x=x+px
            start_y=y-py
            # Native Device:R/C/L pins point inward. Wires must leave the
            # top/bottom pin outward; otherwise both ends short internally.
            if lib in ("Device:R","Device:C","Device:L"):
                angle={90:270,270:90}.get(angle,angle)
            wire,label=b.wire_label(net,start_x,start_y,angle,ref+"-"+str(n))
            drawing.extend((wire,label))
            used_net[net].append((ref,n))
        if ref=="U1":
            # MP8759 datasheet: NC pin4 must float, MODE pin6 float => USM
            # optional open-drain PG pin3 no user monitoring in rev0.
            for n in (3,4,6):
                _,px,py,_,_=signal_pins[n]
                drawing.append(f'(no_connect (at {x+px:.4f} {y-py:.4f}) '
                               f'(uuid {b.kquote(b.uid("nc-"+ref+"-"+str(n)))}) )')
        elif ref=="J3":
            # Shield-to-chassis grounding strategy unresolved; not grounded
            _,px,py,_,_=signal_pins[5]
            drawing.append(f'(no_connect (at {x+px:.4f} {y-py:.4f}) '
                           f'(uuid {b.kquote(b.uid("nc-"+ref+"-5"))}) )')
    # Explicit ERC flags identify the *external bench supply* assumed at J1.
    # They do not constitute a regulator, fuse, ESD rating, or physical test.
    for num,(x,y,net) in enumerate(((50.8,170.18,"VCC5V0_SYS"),(76.2,170.18,"GND")),1):
        drawing.append(b.sym_instance("power:PWR_FLAG","#FLG0"+str(num),"PWR_FLAG",x,y,1,"bench-powerflag-"+str(num)))
        wire,label=b.wire_label(net,x,y,90,"bench-powerflag-"+str(num))
        drawing.extend((wire,label))
    if any((ref,pin) in used_net["GND"] for ref,pin in used_net["VCC5V0_SYS"]):
        raise ValueError("5V and GND shorted in generator")
    for ref,value,x,y in [
        ("note-vin","EXTERNAL REGULATED 5V SUPPLY ONLY - NO USB-C PD",45.72,295.91),
        ("note-vout","VCC_SYSIN NOMINAL 4.04V - POWER STABILITY NOT MEASURED",45.72,306.07),
        ("note-sgm","SGM2576 IS OBSOLETE; ITS PIN3 IS ILIM, NOT OCB",45.72,316.23),
        ("note-esd","USB DATA ESD/EMC, PORT SHIELD, AND VBUS SAFETY NOT VALIDATED",45.72,326.39),
        ("note-nofab","CONCEPT REFERENCE ONLY - NO MANUFACTURING OR POWER AUTHORIZATION",45.72,336.55),
    ]:
        drawing.append(f'(text {b.kquote(value)} (at {x:.4f} {y:.4f} 0)'
                       f' (effects (font (size 1.27 1.27)) (justify left bottom))'
                       f' (uuid {b.kquote(b.uid(ref))}))')
    sheet=(
      f'(kicad_sch (version 20250114) (generator "eeschema") '
      f'(uuid {b.kquote(b.uid("root"))}) (paper "A2")'
      f' (title_block (title "CM5 5V to 4V / USB 2.0 power reference NOT FOR FAB") '
      f'(rev "BENCH DESIGN REVIEW"))'
      '(lib_symbols\n'+'\n'.join(symbols)+')\n'+
      '\n'.join(drawing)+' (embedded_fonts no))\n'
    )
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(sheet,encoding="utf-8")
    # Local, editable KiCad symbols from published pin functions.
    local_lib=[unit_symbol("MP8759GD","U",MP_PINS).replace(
                   '(symbol "HS_Power:MP8759GD"','(symbol "MP8759GD"',1),
               unit_symbol("SGM2576","U",SGM_PINS).replace(
                   '(symbol "HS_Power:SGM2576"','(symbol "SGM2576"',1)]
    (out.parent/"HS_Power.kicad_sym").write_text(
        '(kicad_symbol_lib (version 20231120) (generator "kicad_symbol_editor")\n'+
        "\n".join(local_lib)+'(embedded_fonts no))\n',encoding="utf-8")
    table=['(sym_lib_table']
    for name in ("Connector","Connector_Generic","Device","power"):
        table.append(f' (lib (name "{name}")(type "KiCad")'
                     f'(uri "${{KICAD9_SYMBOL_DIR}}/{name}.kicad_sym")'
                     '(options "")(descr "KiCad 9 stock symbols"))')
    table.append(' (lib (name "HS_Power")(type "KiCad")'
                 '(uri "${KIPRJMOD}/HS_Power.kicad_sym")'
                 '(options "")(descr "CM5 sourced power stage pin identities"))')
    table.append(")")
    (out.parent/"sym-lib-table").write_text("\n".join(table)+"\n",encoding="utf-8")
    manifest.write_text(json.dumps(DATA,indent=2)+"\n",encoding="utf-8")
    return {**DATA,"parts":len(COMPONENTS),"separate_nets":len(used_net),
            "component_net_connection_counts":{k:len(v) for k,v in sorted(used_net.items())}}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--connector-generic",type=Path,
                    default=Path("/usr/share/kicad/symbols/Connector_Generic.kicad_sym"))
    ap.add_argument("--connector",type=Path,
                    default=Path("/usr/share/kicad/symbols/Connector.kicad_sym"))
    ap.add_argument("--power",type=Path,
                    default=Path("/usr/share/kicad/symbols/power.kicad_sym"))
    ap.add_argument("--device",type=Path,
                    default=Path("/usr/share/kicad/symbols/Device.kicad_sym"))
    args=ap.parse_args()
    print(json.dumps(generate(args.connector_generic.read_text(),
           args.connector.read_text(),args.device.read_text(),args.power.read_text(),
           args.out,args.manifest),indent=2))

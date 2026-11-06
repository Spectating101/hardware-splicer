"""Integrate actual manufacturer-vetted 300-pad CM5 with active SGM2590 power stage.

Schematic study only. All six CM5 VCC_SYSIN and all 76 ground pins connect
to the previously source-audited MP8759/SGM2590 nets. Unqualified pins
remain explicitly unresolved in real KiCad ERC, no fabrication authority.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import hs_cm5_connected_bench_schematic as k
import hs_cm5_sgm2590_successor as successor

MODULE="HS_CM5_OFFICIAL:Radxa_CM5"
POSITIONS={1:(139.70,449.58),2:(381.00,449.58),3:(622.30,449.58)}

def generate(out:Path,contract:Path,pinout_path:Path,symbol_path:Path)->dict:
    out.parent.mkdir(parents=True,exist_ok=True)
    successor.generate_candidate(out,contract)
    vendor=json.loads(pinout_path.read_text())
    names={int(p):v for p,v in vendor.get("pin_names",{}).items()}
    if vendor.get("manufacturer_revision")!="V2.21" or set(names)!=set(range(1,301)):
        raise ValueError("vendor pin mapping missing")
    lib=symbol_path.read_text()
    symbol=k.extract_symbol(lib,"Radxa_CM5")
    units=k.pin_coordinates(symbol,"Radxa_CM5",{1,2,3})
    by_pin={}
    for u,items in units.items():
        for n,(kind,px,py,angle,label) in items.items():
            if n in by_pin or names[n]!=label:
                raise ValueError(f"manufacturer CM5 contact mismatch {n}")
            by_pin[n]=(u,px,py,angle)
    if set(by_pin)!=set(range(1,301)) or names[290]!="NC":
        raise ValueError("wrong manufacturer CM5 electrical identity")
    use={n:v for n,v in names.items() if v in {"VCC_SYSIN","GND",
            "USB_HOST_PWREN_H","USB20_HOST0_DP","USB20_HOST0_DM"}}
    expected={"GND":76,"VCC_SYSIN":6,"USB_HOST_PWREN_H":1,
              "USB20_HOST0_DP":1,"USB20_HOST0_DM":1}
    if {v:sum(t==v for t in use.values()) for v in expected}!=expected:
        raise ValueError("required CM5 pin mapping changed")
    if any(use.get(n)!=v for n,v in ((97,"USB_HOST_PWREN_H"),
             (263,"USB20_HOST0_DP"),(265,"USB20_HOST0_DM"))):
        raise ValueError("wrong host physical contacts")
    original=out.read_text()
    lib_block=k.sexpr_form(original,original.index("(lib_symbols"))
    embed=k.inner_library(symbol,"Radxa_CM5",MODULE)
    original=original.replace(lib_block,lib_block[:-1]+"\n"+embed+"\n)",1)
    original=original.replace('(paper "A2")','(paper "A1")',1)
    drawings=[]
    for u,(x,y) in POSITIONS.items():
        drawings.append(k.sym_instance(MODULE,"U3","Radxa_CM5_V2.21",
                        x,y,u,f"U3-unit{u}",MODULE))
    for n,net in use.items():
        u,px,py,angle=by_pin[n]
        ox,oy=POSITIONS[u]
        drawings.extend(k.wire_label(net,ox+px,oy-py,angle,f"U3-pin{n}"))
    for n,label in names.items():
        if label!="NC":continue
        u,px,py,_=by_pin[n]
        ox,oy=POSITIONS[u]
        drawings.append(f'(no_connect (at {ox+px:.4f} {oy-py:.4f}) '
                        f'(uuid {k.kquote(k.uid("U3-nc"+str(n)))}) )')
    for i,(x,y,note) in enumerate([
        (80,568,"CM5 V2.21 pin 290 NC vs older reference V2200 RTC_32K_SOC -- NOT VERIFIED"),
        (80,577,"UNQUALIFIED SIGNALS NOT CONNECTED: INCOMPLETE ERC, NO PCB, NO FAB")]):
        drawings.append(f'(text {k.kquote(note)} (at {x} {y} 0)'
                       f' (effects (font (size 1.27 1.27)) (justify left bottom))'
                       f' (uuid {k.kquote(k.uid("note"+str(i)))}) )')
    suffix=' (embedded_fonts no))\n'
    if original.count(suffix)!=1:raise ValueError("schematic footer unknown")
    original=original.replace(suffix,"\n"+"\n".join(drawings)+suffix,1)
    out.write_text(original)
    shutil.copyfile(symbol_path,out.parent/"HS_CM5_OFFICIAL.kicad_sym")
    table=out.parent/"sym-lib-table"
    old=table.read_text()
    if not old.strip().endswith(")"):raise ValueError("missing KiCad symbol table")
    line=(' (lib (name "HS_CM5_OFFICIAL")(type "KiCad")'
          '(uri "${KIPRJMOD}/HS_CM5_OFFICIAL.kicad_sym")'
          '(options "")(descr "CM5 manufacturer pin map"))\n')
    table.write_text(old.rstrip()[:-1]+line+")\n")
    return {"schema":"hs.cm5_integrated_power_usb_schematic.v1",
            "manufacturer_revision":"V2.21","cm5_component":"U3",
            "cm5_symbol_units":3,"cm5_contacts":len(by_pin),
            "cm5_gnd_contacts":76,"cm5_vcc_sysin_contacts":6,
            "host_usb_power_enable_pin":97,
            "host_usb_dp_pin":263,"host_usb_dm_pin":265,
            "manufacturer_nc_count":sum(x=="NC" for x in names.values()),
            "cm5_pin290_nc":True,
            "regulator":"MP8759GD-Z","usb_switch":"SGM2590XN5G/TR",
            "power_up_tested":False,"all_pins_reviewed":False,
            "erc_clean":False,"routed_board":False,"fabrication_authorized":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for flag in ("--out","--contract","--pinout","--symbol","--report"):
        p.add_argument(flag,required=True,type=Path)
    a=p.parse_args()
    report=generate(a.out,a.contract,a.pinout,a.symbol)
    a.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

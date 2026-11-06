"""Real KiCad electrical bring-up: CM5 V2.21 5V_HDMI and control keys.

Derived from #305. A study, never safe to power, purchase or fabricate.
"""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hs_cm5_connected_bench_schematic as k
from hs_cm5_integrated_power_usb_schematic import POSITIONS

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "examples/cyberdeck/compute_carrier/cm5_reference"
UP = REF / "integrated_candidate"
OUT = REF / "bringup_candidate"
KEYS = (
    ("PWRON_L", 99, "PWRON", 8, 1, 457.20),
    ("RESET_L", 92, "RESET", 9, 2, 518.16),
    ("SARADC_VIN0_BOOT", 93, "MASKROM", 10, 3, 579.12),
    ("SARADC_VIN1_KEY/RECOVERY", 226, "RECOVERY", 11, 4, 640.08),
)

def generate():
    OUT.mkdir(parents=True, exist_ok=True)
    sch = (UP / "CM5_FULL_SYMBOL_POWER_USB_NOT_FOR_FAB.kicad_sch").read_text()
    vendor = json.loads((REF / "vendor_pin_names.json").read_text())
    names = {int(n): v for n, v in vendor["pin_names"].items()}
    if vendor.get("manufacturer_revision") != "V2.21" or len(names) != 300:
        raise ValueError("manufacturer V2.21 pinout required")
    if names.get(106) != "5V_HDMI":
        raise ValueError("pin106 no longer official 5V_HDMI: stop")
    for net, pin, *_ in KEYS:
        if names.get(pin) != net:
            raise ValueError(f"unqualified button pin {pin}")
    cm5 = k.extract_symbol((UP / "HS_CM5_OFFICIAL.kicad_sym").read_text(), "Radxa_CM5")
    units = k.pin_coordinates(cm5, "Radxa_CM5", {1,2,3})
    physical = {}
    for unit, pins in units.items():
        for n, (_,px,py,angle,label) in pins.items():
            if n in physical or label != names[n]:
                raise ValueError(f"manufacturer contact changed: {n}")
            x,y = POSITIONS[unit]
            physical[n] = (x+px, y-py, angle)
    if len(physical) != 300:
        raise ValueError("incomplete contact set")
    lib = k.extract_symbol((OUT / "HS_Switch_Reference.kicad_sym").read_text(),"SW_Push")
    if '(symbol "SW_Push_0_1"' not in lib:
        raise ValueError("unrecognized KiCad switch symbol")
    old = k.sexpr_form(sch,sch.index("(lib_symbols"))
    sch = sch.replace(old,old[:-1]+"\n"+k.inner_library(lib,"SW_Push","Switch:SW_Push")+"\n)",1)
    k.PROJECT = "CM5_BENCH_HARNESS_NOT_FOR_FAB"
    draw = []
    draw.extend(k.wire_label("5V_HDMI",*physical[106],"U3-106-5v-hdmi"))
    draw.append(k.sym_instance("Device:R","R7","0R_5V_HDMI_LINK_UNQUALIFIED",716.28,290.83,1,"R7"))
    draw.extend(k.wire_label("VCC5V0_SYS",716.28,287.02,90,"R7-input-5v"))
    draw.extend(k.wire_label("5V_HDMI",716.28,294.64,270,"R7-out-hdmi"))
    for net,pin,kind,rnum,snum,x in KEYS:
        draw.extend(k.wire_label(net,*physical[pin],f"U3-{pin}-{kind}"))
        draw.append(k.sym_instance("Device:R",f"R{rnum}",
                                   f"100R_{kind}_SERIES_UNQUALIFIED",x,290.83,1,f"R{rnum}"))
        mid=f"BTN_{kind}_GND_ON_PRESS"
        draw.extend(k.wire_label(net,x,287.02,90,f"R{rnum}-input"))
        draw.extend(k.wire_label(mid,x,294.64,270,f"R{rnum}-out"))
        draw.append(k.sym_instance("Switch:SW_Push",f"SW{snum}",
                    f"{kind}_NORMALLY_OPEN_TO_GND_UNQUALIFIED",x,325.12,1,f"SW{snum}"))
        draw.extend(k.wire_label(mid,x-5.08,325.12,0,f"SW{snum}-in"))
        draw.extend(k.wire_label("GND",x+5.08,325.12,180,f"SW{snum}-gnd"))
    for i,(x,y,t) in enumerate((
        (445,348,"V2.21 4V SYSIN: ADD 5V AT PIN106 VIA 0R LINK"),
        (445,357,"RADXA IO V2.2 KEY CIRCUITS: 100R + N.O. TO GND"),
        (445,366,"NO ESD / INPUT PROTECTION / QUALIFIED SWITCH FOOTPRINT"),
        (445,375,"GPIO_VREF / VCCIO_FLASH / POWER LOAD / PCB NOT QUALIFIED"),
    )):
        draw.append(f'(text {k.kquote(t)} (at {x} {y} 0)'
                    f' (effects (font (size 1.27 1.27)) (justify left bottom))'
                    f' (uuid {k.kquote(k.uid("bringup-note-"+str(i)))}) )')
    suffix=' (embedded_fonts no))\n'
    if sch.count(suffix)!=1: raise ValueError("unknown original KiCad footer")
    sch=sch.replace(suffix,"\n"+"\n".join(draw)+suffix,1)
    filename=OUT/"CM5_POWER_BOOT_ELECTRIC_NOT_FOR_FAB.kicad_sch"
    filename.write_text(sch)
    for name in ("HS_Power.kicad_sym","HS_CM5_OFFICIAL.kicad_sym"):
        shutil.copyfile(UP/name,OUT/name)
    table=(UP/"sym-lib-table").read_text()
    table=table.rstrip()[:-1]+(
        '\n (lib (name "Switch")(type "KiCad")(uri "'+'$'+'{KICAD9_SYMBOL_DIR}/Switch.kicad_sym")'
        '(options "")(descr "Official KiCad symbol library"))\n)\n')
    (OUT/"sym-lib-table").write_text(table)
    report=dict(
        schema="hs.cm5_power_boot_bringup.v1",
        manufacturer_revision="V2.21",auxiliary_5v_pin=106,
        auxiliary_5v_name="5V_HDMI",auxiliary_5v_link="R7 0R from VCC5V0_SYS",
        keys=[dict(function=n,cm5_pin=p,series=f"R{r}",button=f"SW{s}")
              for n,p,k,r,s,x in KEYS],
        gpio_vref_qualified=False,flash_voltage_qualified=False,
        input_protection_present=False,usb_data_esd_present=False,
        current_limit_measured=False,buck_droop_test_passed=False,
        power_on_tested=False,full_erc_clean=False,
        pcb_routed=False,fabrication_authorized=False)
    (OUT/"bringup_manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    return report

if __name__=="__main__":
    print(json.dumps(generate(),indent=2))

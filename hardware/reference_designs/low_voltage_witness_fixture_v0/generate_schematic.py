#!/usr/bin/env python3
"""Deterministically author a KiCad 9 electrical schematic for the 5 V witness fixture.

Pin geometries are copied from installed KiCad library symbols. All measurements
remain UNBUILT and require electrical/physical review; generation is not safety approval.
"""
from __future__ import annotations
import json
import re
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = "low_voltage_witness_fixture_v0"
OUTPUT = HERE / f"{PROJECT}.kicad_sch"
LIBROOT = Path("/usr/share/kicad/symbols")
SID = "5a8d1fa3-f2dc-48eb-99a6-dca90b04a2b5"

# Power series path J1(+) -> F1 -> Adafruit INA228 VIN+/VIN- OUTSIDE PCB
# -> WSK2512 four-terminal REF shunt -> J2(+); J1(-) -> J2(-) return.
# The Adafruit VBUS jumper must remain OPEN; its VBUS goes to J2 LOAD_PLUS.
PARTS = [
 ("Connector_Generic:Conn_01x02","J1","SOURCE_5V_0P5A",(42,56),
  "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal"),
 ("Device:Fuse","F1","1A_FUSE_CANDIDATE",(87,56),
  "Fuse:Fuseholder_Cylinder-5x20mm_Schurter_FAB_0031-355x_Horizontal_Closed"),
 ("Connector_Generic:Conn_01x02","J3","ADA_IN_PLUS_MINUS",(130,56),
  "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal"),
 ("Device:R_Shunt","R1","WSK2512R0100FEA_10mOhm_1pct",(178,56),
  "Resistor_SMD:R_Shunt_Vishay_WSK2512_6332Metric_T1.19mm"),
 ("Connector_Generic:Conn_01x02","J2","LOAD_5V_0P5A",(217,56),
  "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal"),
 ("Connector_Generic:Conn_01x02","J4","ADA_VBUS_GND",(217,89),
  "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"),
 ("Connector_Generic:Conn_01x02","J5","REF_SHUNT_KELVIN",(176,89),
  "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"),
 ("Connector_Generic:Conn_01x02","J6","REF_LOAD_VBUS",(217,118),
  "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"),
 ("Connector:TestPoint","TP1","REF_SENSE_P",(159,117),"TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm"),
 ("Connector:TestPoint","TP2","REF_SENSE_N",(176,117),"TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm"),
 ("Connector:TestPoint","TP3","LOAD_PLUS",(193,145),"TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm"),
 ("Connector:TestPoint","TP4","RETURN",(217,145),"TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm"),
]
NETS={
 "J1":{"1":"SRC_PLUS","2":"RETURN"},
 "F1":{"1":"SRC_PLUS","2":"FUSED_PLUS"},
 "J3":{"1":"FUSED_PLUS","2":"ADA_OUT"},
 "R1":{"1":"ADA_OUT","4":"LOAD_PLUS","2":"REF_SENSE_P","3":"REF_SENSE_N"},
 "J2":{"1":"LOAD_PLUS","2":"RETURN"},
 "J4":{"1":"LOAD_PLUS","2":"RETURN"},
 "J5":{"1":"REF_SENSE_P","2":"REF_SENSE_N"},
 "J6":{"1":"LOAD_PLUS","2":"RETURN"},
 "TP1":{"1":"REF_SENSE_P"},"TP2":{"1":"REF_SENSE_N"},
 "TP3":{"1":"LOAD_PLUS"},"TP4":{"1":"RETURN"},
}
def unique(tag: str)->str: return str(uuid.uuid5(uuid.UUID(SID),tag))
def block(s:str,begin:int)->str:
 depth=0; quoted=False; escape=False
 for i in range(begin,len(s)):
  c=s[i]
  if escape: escape=False;continue
  if quoted and c=="\\": escape=True;continue
  if c=='"':quoted=not quoted;continue
  if quoted:continue
  if c=="(":depth+=1
  if c==")":
   depth-=1
   if depth==0:return s[begin:i+1]
 raise ValueError("incomplete KiCad s-expression")
def installed_symbol(libid:str):
 library, name=libid.split(":")
 s=(LIBROOT/f"{library}.kicad_sym").read_text(encoding="utf8")
 match=re.search(r'(?m)^\s*\(symbol "'+re.escape(name)+r'"[\s\n]',s)
 if match is None: raise ValueError(f"Missing installed symbol {libid}")
 b=block(s,s.index("(symbol",match.start()))
 if '(extends ' in b:raise ValueError("library inheritance requires resolving")
 b=b.replace(f'(symbol "{name}"', f'(symbol "{libid}"',1)
 pins={}
 for hit in re.finditer(r'\(pin (?:passive|input|output|power_in|power_out|bidirectional|no_connect) ',b):
  piece=block(b,hit.start())
  n=re.search(r'\(number "([^"]+)"',piece)
  pt=re.search(r'\(at (-?[\d.]+) (-?[\d.]+) ([0-9]+)\)',piece)
  if n and pt: pins[n.group(1)]=(float(pt.group(1)),float(pt.group(2)),int(pt.group(3)))
 if not pins:raise ValueError(f"No pins in {libid}")
 return b,pins
def fmt(v:float)->str: return f"{v:.4f}".rstrip("0").rstrip(".") if abs(v)>1e-8 else "0"
def q(s:str)->str: return json.dumps(s,ensure_ascii=False)
def prop(name,value,x,y,hide=False):
 return (f'(property {q(name)} {q(value)} (at {fmt(x)} {fmt(y)} 0)'
         f' (effects (font (size 1.0 1.0))'+(' (hide yes)' if hide else '')+'))')
def generate():
 built={t[0]:installed_symbol(t[0]) for t in PARTS}
 doc=['(kicad_sch','(version 20250114)','(generator "eeschema")',
      '(generator_version "9.0")',f'(uuid "{SID}")','(paper "A4")',
      '(title_block (title "5V 0.5A dual-path DC witness fixture, carrier OUTSIDE PCB")',
      '(date "2026-11-20") (rev "v0 candidate - unbuilt")',
      '(company "Hardware Splicer") (comment 1 "Physical review required; low-power 5V/0.5A commissioning only")',
      '(comment 2 "Adafruit INA228 HIGH SIDE VBUS jumper OPEN, VBUS = LOAD_PLUS")',
      '(comment 3 "No test equipment, assembly, calibration or electrical power-on performed"))',
      '(lib_symbols']
 for libid in sorted(built):doc.append(built[libid][0])
 doc.append(')')
 for libid,ref,value,(x,y),fp in PARTS:
  x,y=round(x/1.27)*1.27,round(y/1.27)*1.27
  pins=built[libid][1]
  doc+=['(symbol',f'(lib_id "{libid}")',f'(at {fmt(x)} {fmt(y)} 0)',
        '(unit 1)','(exclude_from_sim no)',
        '(in_bom no)' if ref.startswith('TP') else '(in_bom yes)','(on_board yes)',
        '(dnp no)',f'(uuid "{unique("sym:"+ref)}")',
        prop("Reference",ref,x+7.62,y-8),prop("Value",value,x+7.62,y-5),
        prop("Footprint",fp,x,y,True)]
  for n in pins:doc.append(f'(pin "{n}" (uuid "{unique("pin:"+ref+":"+n)}"))')
  doc.append(f'(instances (project "{PROJECT}" (path "/{SID}" (reference "{ref}") (unit 1))))')
  doc.append(')')
  wanted=NETS[ref]
  if set(wanted)!=set(pins): raise ValueError(f"Pin coverage {ref}: {wanted.keys()} vs {pins.keys()}")
  for pin,(px,py,angle) in pins.items():
   net=wanted[pin]
   start=(x+px,y-py)
   # Pin angle 0 = projects right, 180 = projects left;
   # 90 = up in symbol coordinates, 270 = down in symbol coordinates.
   ux={0:1,180:-1,90:0,270:0}[angle]
   uy={0:0,180:0,90:-1,270:1}[angle]
   end=(start[0]+ux*2.54,start[1]+uy*2.54)
   doc += [f'(wire (pts (xy {fmt(start[0])} {fmt(start[1])})'
           f' (xy {fmt(end[0])} {fmt(end[1])}))'
           f' (stroke (width 0) (type default)) (uuid "{unique("wire:"+ref+":"+pin)}"))',
           f'(label "{net}" (at {fmt(end[0])} {fmt(end[1])} 0)'
           f' (effects (font (size 1.0 1.0)) (justify left bottom))'
           f' (uuid "{unique("label:"+ref+":"+pin)}"))']
 doc.append(f'(text "POWER OFF before connecting J1/J3/J2. J3 is NOT a shorting jumper: route full load current through the external Adafruit INA228 VIN+ -> VIN- terminals.\\n'
            f'R1 uses 4-terminal WSK2512; pad 1/4 carry load, pad 2/3 are sense ONLY.\\n'
            f'J4 is Adafruit VBUS at the J2 load boundary + return. Leave board VBUS-to-VIN+ jumper OPEN.\\n'
            f'J5/J6 require independent reference equipment with documented paired readings; not 2 independent meters in this PCB.\\n'
            f'5V max, 0.5A nominal; current-limited isolated DC supply, proper 1A fuse, 10 ohm / 10W load external.\\n'
            f'UNBUILT and NOT POWER-AUTHORIZED. No mains, solar, battery, or 24V high-power operation."'
            f' (exclude_from_sim no) (at 130 173 0) (effects (font (size 1.1 1.1)))'
            f' (uuid "{unique("text:caution")}"))')
 doc.append(')')
 OUTPUT.write_text("\n".join(doc)+"\n",encoding="utf8")
 table=['(sym_lib_table','(version 7)']
 for name in sorted({lib.split(':')[0] for lib in built}):
  table.append(f' (lib (name "{name}") (type "KiCad") (uri "${{KICAD9_SYMBOL_DIR}}/{name}.kicad_sym") (options "") (descr ""))')
 table.append(')')
 (HERE/'sym-lib-table').write_text("\n".join(table)+"\n")
 print(OUTPUT)
if __name__=="__main__": generate()

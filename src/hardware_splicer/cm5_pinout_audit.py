"""Audited CM5 KiCad symbol fixture from official Radxa V2.21 pinout.

No board circuit, power architecture or manufacturing authority is implied.
The community KiCad library contains outdated/RPi-compatible names:
the official XLSX names take priority, including explicit NC contacts.

Only the standard library is required. Workbook OOXML is read in source mode
as a vendor pinout table, never modified or re-exported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

SCHEMA = "hs.cm5_pinout_audit.v1"
SHEETS = {1: ("Radxa CM5 V2.21 U13-A Pinout", "E", 0),
          2: ("Radxa CM5 V2.21 U13-B Pinout", "C", 0),
          3: ("Radxa CM5 V2.21 J1 Pinout", "B", 200)}
NS = {"x":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
PIN_RE = re.compile(
    r'(?P<before>\(pin\s+\w+\s+\w+\s+\(at\b.*?\(name\s+")'
    r'(?P<label>[^"]*)(?P<between>".*?\(number\s+")(?P<number>\d+)(?P<after>")',
    re.DOTALL,
)
PAD_RE = re.compile(r'\(pad\s+"(\d+)"')
GIT_SHA = "33add7f768b313ddef58c81eca8f2d1c8004ac66"
XLSX_SHA = "191052d98a057384b6659bab2626aae81cfc6b565f3216f20433c26046029b9c"
SYM_SHA = "389141960fdc4f4023b631edec4e0002edf962d79d4be56dca786b81c606954c"
FP_SHA = "92d2f4aca9df8f6723458639537c99e17396198f986d7e7258f4a7b567bb2439"
XLSX_URL = "https://dl.radxa.com/cm5/v2210/radxa_cm5_v2210_pinout.xlsx"
SYM_URL = f"https://raw.githubusercontent.com/swdee/radxa-cm5-kicad/{GIT_SHA}/symbols/Radxa_CM5.kicad_sym"
FP_URL = f"https://raw.githubusercontent.com/swdee/radxa-cm5-kicad/{GIT_SHA}/footprints/Radxa_CM5.kicad_mod"


class PinoutError(ValueError):
    """Source or 300-pad pinout does not match a verified contract."""


def digest(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def require_hash(contents: bytes, sha: str, name: str) -> None:
    if digest(contents) != sha:
        raise PinoutError(f"{name}: source SHA256 differs from pinned reference")


def vendor_pinout(contents: bytes) -> dict[int, str]:
    require_hash(contents, XLSX_SHA, "official Radxa CM5 pinout XLSX")
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(contents)) as z:
            strings=ET.fromstring(z.read("xl/sharedStrings.xml"))
            s=[''.join(t.text or '' for t in row.findall('.//x:t', NS))
               for row in strings.findall("x:si", NS)]
            contacts={}
            for sheet_id, (title, vendor_column, offset) in SHEETS.items():
                root=ET.fromstring(z.read(f"xl/worksheets/sheet{sheet_id}.xml"))
                rows=root.findall('.//x:sheetData/x:row', NS)
                first=rows[0].find('x:c/x:v', NS)
                if first is None or s[int(first.text)] != title:
                    raise PinoutError(f"vendor sheet{sheet_id} title not expected")
                n_in_sheet=0
                for row in rows[2:]:
                    cells={}
                    for cell in row.findall("x:c",NS):
                        v=cell.find("x:v",NS)
                        if v is None:continue
                        col=re.match(r"[A-Z]+", cell.get("r",""))
                        if not col:continue
                        raw=v.text or ''
                        cells[col.group()]=s[int(raw)] if cell.get("t")=="s" and raw else raw
                    if not cells.get("A","").isdigit():
                        continue
                    local=int(cells["A"])
                    if not 1 <= local-(100 if sheet_id==2 else 0) <= 100:
                        raise PinoutError(f"unexpected pin number on sheet{sheet_id}: {local}")
                    n=local+offset
                    label=cells.get(vendor_column,"").strip()
                    if n in contacts or not label or any(c in label for c in ('"', '\n', '\r')):
                        raise PinoutError(f"duplicate, empty or invalid official pin: {n}")
                    contacts[n]=label
                    n_in_sheet+=1
                if n_in_sheet != 100:
                    raise PinoutError(f"sheet{sheet_id} contains {n_in_sheet} contacts, expected 100")
    except (zipfile.BadZipFile, KeyError, ET.ParseError, IndexError) as exc:
        raise PinoutError("malformed vendor workbook") from exc
    if set(contacts)!=set(range(1,301)):
        raise PinoutError("vendor connector coverage is incomplete")
    return contacts


def symbol_pins(symbol: str) -> dict[int,str]:
    pins=PIN_RE.findall(symbol)
    if len(pins)!=300:
        raise PinoutError(f"KiCad symbol pin count {len(pins)} != 300")
    got={}
    for _,label,_,num,_ in pins:
        n=int(num)
        if n in got:
            raise PinoutError(f"duplicated symbol contact {n}")
        got[n]=label
    if set(got)!=set(range(1,301)):
        raise PinoutError("KiCad symbol contact numbering incomplete")
    return got


def footprint_pads(footprint: str) -> list[int]:
    pads=[int(x) for x in PAD_RE.findall(footprint)]
    if len(pads)!=300 or set(pads)!=set(range(1,301)):
        raise PinoutError("community footprint does not contain exactly 300 distinct pads")
    return pads


def repair_symbol(original: str, authoritative: dict[int,str]) -> str:
    def replace(match: re.Match[str]) -> str:
        n=int(match.group("number"))
        if n not in authoritative:
            raise PinoutError(f"unrecognized KiCad contact number: {n}")
        return match.group("before")+authoritative[n]+match.group("between")+str(n)+match.group("after")
    patched, count = PIN_RE.subn(replace, original)
    if count != 300:
        raise PinoutError("not all KiCad pins were patched")
    if symbol_pins(patched)!=authoritative:
        raise PinoutError("result differs from official manufacturer source")
    # The upstream community symbol also has a misspelled footprint library
    # identifier and unverified standalone current figures. Fail closed:
    # point to the dedicated audited library, not an unresolved Radax alias.
    known='(property "Footprint" "Radax:Radxa_CM5"'
    if patched.count(known) != 1:
        raise PinoutError("unexpected upstream footprint linkage")
    patched=patched.replace(known,'(property "Footprint" "HS_CM5_OFFICIAL:Radxa_CM5"',1)
    current_value='(property "Value" "Hirose DF40C-100DS-0.4V"'
    if patched.count(current_value) != 1:
        raise PinoutError("upstream connector value changed")
    patched=patched.replace(current_value,'(property "Value" "Radxa_CM5_V2.21"',1)
    current_desc='(property "Description" "Radxa CM5"'
    if patched.count(current_desc) != 1:
        raise PinoutError("upstream description changed")
    patched=patched.replace(current_desc,
       '(property "Description" "Radxa CM5 V2.21 - manufacturer contact labels; electrical types unverified"',1)
    if patched.count('text "600mA Max"') != 2:
        raise PinoutError("upstream current-limit annotations changed")
    patched=patched.replace('text "600mA Max"','text "MAX CURRENT NOT VERIFIED"')
    return patched


def audit(xlsx: bytes, sym: bytes, fp: bytes) -> tuple[dict,str]:
    contacts=vendor_pinout(xlsx)
    require_hash(sym,SYM_SHA,"MIT community symbol")
    require_hash(fp,FP_SHA,"MIT community footprint")
    symbol=sym.decode("utf-8")
    footprint=fp.decode("utf-8")
    old=symbol_pins(symbol)
    pads=footprint_pads(footprint)
    changed=[{"pin":n,"upstream":old[n],"vendor":contacts[n],
              "manufacturer_no_connect":contacts[n].upper() in {"NC","N.C.","N/C"}}
             for n in contacts if old[n]!=contacts[n]]
    corrected=repair_symbol(symbol,contacts)
    potential_nc=[x for x in changed if x["manufacturer_no_connect"]]
    report={
       "schema":SCHEMA, "module":"Radxa CM5 V2.21",
       "manufacturer_xlsx_url":XLSX_URL, "manufacturer_xlsx_sha256":XLSX_SHA,
       "community_repo":"swdee/radxa-cm5-kicad", "community_repo_commit":GIT_SHA,
       "community_symbol_sha256":SYM_SHA, "community_footprint_sha256":FP_SHA,
       "symbol_pin_count":len(old), "footprint_pad_count":len(pads),
       "vendor_contact_count":len(contacts), "pin_name_differences":len(changed),
       "manufacturer_NC_conflicts":len(potential_nc),
       "changed_contacts":changed, "pin_names_after_patch_match_vendor":True,
       "kicad_symbol_sha256":digest(corrected.encode()),
       "source_footprint_identifier_corrected":True,
       "unverified_symbol_current_annotations_removed":True,
       "physical_pad_geometry_independently_validated":False,
       "pin_electrical_types_independently_validated":False,
       "released_for_fabrication":False,
       "blockers":[
        "Connector pad geometry and placement not independently dimension-checked against CM5 module DXF/STEP.",
        "Pin electrical types in the community symbol have NOT been checked against manufacturer datasheet.",
        "No carrier schematic nets, power regulation, USB/HDMI/DSI routing, ESD or controlled impedance design.",
        "No ERC/DRC of a complete connected board, no prototype boot or physical electrical tests.",
       ],
    }
    return report,corrected


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--official",required=True,type=Path)
    p.add_argument("--symbol",required=True,type=Path)
    p.add_argument("--footprint",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args()
    report,corrected=audit(a.official.read_bytes(),a.symbol.read_bytes(),a.footprint.read_bytes())
    output=a.output_dir
    output.mkdir(parents=True,exist_ok=True)
    (output/"HS_CM5_OFFICIAL.kicad_sym").write_text(corrected)
    (output/"HS_CM5_OFFICIAL.pretty").mkdir(exist_ok=True)
    (output/"HS_CM5_OFFICIAL.pretty"/"Radxa_CM5.kicad_mod").write_bytes(a.footprint.read_bytes())
    (output/"pinout_audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"CM5 contacts: {report['vendor_contact_count']}; pad match: {report['footprint_pad_count']}; corrected names: {report['pin_name_differences']}; NC conflicts: {report['manufacturer_NC_conflicts']}")
    print("FABRICATION AUTHORIZED:",report["released_for_fabrication"])
    return 0

if __name__=="__main__":
    raise SystemExit(main())


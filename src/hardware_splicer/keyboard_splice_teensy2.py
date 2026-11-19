"""Original Teensy 2.0 (AVR C pin names) to f.60 KiCad pad mapping audit.

Physical pin order source: PJRC Teensy 2.0 C-language pinout card:
https://www.pjrc.com/teensy/card2a_rev5_web.pdf

KiCad pad coordinate order source: original f.60 hardware/lib/
footprints.pretty/Teensy_20.kicad_mod (external pinned copy).

This proves source pad placement/label and TMK GPIO assignments in a
*reference file*, not physical Teensy condition or loaded firmware.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import re


# KiCad f.60 custom Teensy_20 footprint numbering, USB end to opposite end.
# Only header perimeter GPIOs explicitly present on PJRC's C pinout card.
KI_PAD_TO_AVR={
    2:"B0",3:"B1",4:"B2",5:"B3",6:"B7",
    7:"D0",8:"D1",9:"D2",10:"D3",11:"C6",12:"C7",13:"D5",
    17:"D4",18:"D6",19:"D7",20:"B4",21:"B5",22:"B6",
    23:"F7",24:"F6",25:"F5",26:"F4",27:"F1",28:"F0",
}
OFFICIAL_PIN_CARD="https://www.pjrc.com/teensy/card2a_rev5_web.pdf"


def audit_teensy2_gpio(
    board:dict, source_audit:dict, matrix:dict,
    upstream_footprint:bytes, *, expected_footprint_sha256:str
)->dict:
    sha=board.get("source_sha256")
    if not sha or (source_audit.get("original_pcb_sha256")!=sha
                    or matrix.get("source_sha256")!=sha):
        raise ValueError("Teensy source identity differs from keyboard source")
    if source_audit.get("net_assignment_equivalence") is not True:
        raise ValueError("original schematic and PCB net assignment not verified")
    if matrix.get("ideal_directed_diode_matrix_model_passed") is not True:
        raise ValueError("original source matrix not consistent with all retained keys")
    digest=hashlib.sha256(upstream_footprint).hexdigest()
    if digest!=expected_footprint_sha256:
        raise ValueError("original Teensy footprint source SHA256 mismatch")
    footprints=[f for f in board.get("footprints",[])
                if f.get("ref")==matrix.get("original_controller_ref")]
    if len(footprints)!=1 or "Teensy" not in str(footprints[0].get("footprint","")):
        raise ValueError("expected exactly one original Teensy controller footprint")
    main=footprints[0]
    padmap={}
    for item in board.get("pads",[]):
        if item.get("ref")==main["ref"] and str(item.get("pad","")).isdigit():
            number=int(item["pad"])
            if number in padmap:
                raise ValueError("source controller has duplicated footprint pin")
            padmap[number]=item
    if set(padmap)!=set(range(1,32)):
        raise ValueError("source Teensy PCB footprint must retain its original 31 pads")

    pattern=r"\(pad\s+(\d+)\s+thru_hole\s+\w+\s+\(at\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)"
    raw=upstream_footprint.decode("utf-8")
    local={}
    for number,x,y in re.findall(pattern,raw):
        pin=int(number)
        if pin in local:
            raise ValueError("original source Teensy footprint duplicates pad")
        local[pin]=(float(x),float(y))
    if set(local)!=set(range(1,32)):
        raise ValueError("original custom Teensy footprint source missing physical pins")
    physical_checks=[]
    for pin in range(1,32):
        record=padmap[pin]
        # Original KiCad 4 footprint has no rotation in f.60. KiCad's local
        # footprint y-axis sign is opposite the global board y direction.
        dx,dy=local[pin]
        expected=(float(main["x"])+dx,float(main["y"])-dy)
        actual=(float(record["x"]),float(record["y"]))
        error=max(abs(expected[0]-actual[0]),abs(expected[1]-actual[1]))
        if error>0.02:
            raise ValueError(f"source U1 physical pad {pin} moved: error {error:.4f} mm")
        physical_checks.append(pin)

    firmware_rows=source_audit.get("firmware_gpio_rows")
    firmware_cols=source_audit.get("firmware_gpio_columns")
    if not isinstance(firmware_rows,list) or not isinstance(firmware_cols,list):
        raise ValueError("original upstream source firmware GPIO inventory missing")
    actual_gpio={gpio:pin for pin,gpio in KI_PAD_TO_AVR.items()}
    if len(actual_gpio)!=len(KI_PAD_TO_AVR):
        raise ValueError("duplicate physical Teensy GPIO map")
    if len(firmware_rows)!=matrix.get("source_row_count"):
        raise ValueError("source row GPIO mapping does not match original controller matrix")
    if len(firmware_cols)!=matrix.get("source_column_count"):
        raise ValueError("source column GPIO mapping does not match original controller matrix")
    results=[]
    for kind,gpios,prefix in (
        ("row",firmware_rows,"R"),("column",firmware_cols,"C")
    ):
        for index,gpio in enumerate(gpios):
            net=f"/{prefix}{index}"
            pin=actual_gpio.get(gpio)
            if pin is None:
                raise ValueError(f"firmware GPIO {gpio} not present on official Teensy2.0 pinout")
            entry=padmap[pin]
            if entry.get("net")!=net:
                raise ValueError(f"TMK {gpio} maps to KiCad U1 pad {pin} {entry.get('net')}, not {net}")
            proof_mapping=(
                matrix.get("controller_row_to_pin",{}).get(net)
                if kind=="row" else matrix.get("controller_column_to_pin",{}).get(net)
            )
            if proof_mapping!=str(pin):
                raise ValueError("original key scan inferred a different controller pad than Teensy C pinout")
            results.append({
                "matrix_kind":kind,
                "matrix_index":index,
                "source_net":net,
                "TMK_AVR_GPIO":gpio,
                "source_original_KiCad_pad":pin,
                "physical_library_footprint_geometry_match":True,
            })
    if len(results)!=19 or len(set(t["source_original_KiCad_pad"] for t in results))!=19:
        raise ValueError("not all original firmware pin assignments are unique and accounted")
    output={
        "schema":"hs.f60-teensy2-official-pinout-firmware-crosscheck.v1",
        "original_source_sha256":sha,
        "source_audit_sha256":source_audit["payload_sha256"],
        "full_matrix_proof_sha256":matrix["payload_sha256"],
        "upstream_source_footprint_sha256":digest,
        "external_PJRC_C_pinout_reference":OFFICIAL_PIN_CARD,
        "source_controller_ref":main["ref"],
        "source_original_controller_pads_positionally_verified":len(physical_checks),
        "firmware_row_pin_assignments_verified":len(firmware_rows),
        "firmware_column_pin_assignments_verified":len(firmware_cols),
        "firmware_total_gpio_assignments_verified":len(results),
        "all_source_TMK_AVR_GPIO_to_KiCad_pins_match_PJRC":True,
        "firmware_to_original_controller_physical_GPIO_mapping_proven_for_source_reference":True,
        "connection_map":results,
        "original_teensy_hardware_present":False,
        "powered_gpio_scan_tested":False,
        "firmware_compiled_flashed_or_USB_tested":False,
        "source_physical_assembly_quality_verified":False,
        "fabrication_authorized":False,
        "release":"PASS_SOURCE_PINOUT_RECONCILIATION_ONLY",
    }
    content=json.dumps(output,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    output["payload_sha256"]=hashlib.sha256(content.encode()).hexdigest()
    return output

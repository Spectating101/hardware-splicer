"""Source-bound Teensy 2.0 footprint pad and firmware GPIO mapping."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.keyboard_splice_teensy2 import audit_teensy2_gpio


ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_remount_round5"


def read(name):
    return json.loads((EVIDENCE/name).read_text(encoding="utf-8"))


def fixture():
    # A synthetic *unit fixture* derived from source PCB coordinates, not a
    # substitute for the pinned actual original footprint used by the run.
    board=read("F60_MATRIX_SOURCE_SLICE.json")
    source_audit=read("INDEPENDENT_SOURCE_AUDIT.json")
    matrix=read("FULL_MATRIX_SOURCE_PROOF.json")
    u=next(f for f in board["footprints"] if f["ref"]=="U1")
    lines=[]
    for pad in board["pads"]:
        if pad["ref"]=="U1":
            x=pad.get("x",None);y=pad.get("y",None)
            if x is None or y is None:
                # source slice deliberately excludes geometry; derive the
                # geometric data from the verified source reference layout
                # independently of the 19-pin firmware arrangement.
                break
    # The frozen source slice contains only pin/net identities. This 31-pad
    # layout is the public f.60 KiCad footprint's explicit 2.54mm perimeter.
    positions={}
    for index in range(1,13):
        positions[index]=(-13.97+(index-1)*2.54,7.62)
    for index in range(13,18):
        positions[index]=(13.97,7.62-(index-12)*2.54)
    for index in range(18,30):
        positions[index]=(13.97-(index-18)*2.54,-7.62)
    positions[30]=(-3.81,-5.08)
    positions[31]=(-3.81,5.08)
    # derive pad x/y from source footprint local positions, anchored by exact
    # source layout's U1 center. These synthetic positions test parser, port
    # map and fail-closed behavior; the real pinned footprint receipt is
    # separately asserted below.
    board["pads"]=[pad for pad in board["pads"] if pad["ref"]!="U1"]
    for pin,(dx,dy) in sorted(positions.items()):
        name="U1"
        net=next((p["net"] for p in read("F60_MATRIX_SOURCE_SLICE.json")["pads"]
                  if p["ref"]==name and p["pad"]==str(pin)),"")
        board["pads"].append({
            "ref":name,"pad":str(pin),"net":net,
            "x":round(u["x"]+dx,5),"y":round(u["y"]-dy,5)
        })
        lines.append(f"(pad {pin} thru_hole circle (at {dx} {dy}) (size 1.7 1.7))")
    original="(module Teensy_20\n"+"\n".join(lines)+"\n)"
    blob=original.encode()
    return board,source_audit,matrix,blob,hashlib.sha256(blob).hexdigest()


def test_teensy_2_perimeter_31_pads_all_19_gpio_signals_match():
    result=audit_teensy2_gpio(*fixture()[:4],
             expected_footprint_sha256=fixture()[4])
    assert result["firmware_row_pin_assignments_verified"]==5
    assert result["firmware_column_pin_assignments_verified"]==14
    assert result["firmware_total_gpio_assignments_verified"]==19
    assert result["source_original_controller_pads_positionally_verified"]==31
    assert result["all_source_TMK_AVR_GPIO_to_KiCad_pins_match_PJRC"] is True
    assert result["original_teensy_hardware_present"] is False
    assert result["powered_gpio_scan_tested"] is False
    assert result["fabrication_authorized"] is False
    pair={(r["source_net"],r["TMK_AVR_GPIO"]):r["source_original_KiCad_pad"]
          for r in result["connection_map"]}
    assert pair[("/R0","D0")]==7
    assert pair[("/R2","B0")]==2
    assert pair[("/C5","B1")]==3
    assert pair[("/C13","D7")]==19
    assert len(set(pair.values()))==19


@pytest.mark.parametrize("damage",[
    "wrong_footprint_sha","moved_U1_pad","missing_pad",
    "firmware_wrong_gpio","sourced_wrong_net","matrix_wrong_controller_pin"
])
def test_original_controller_pinout_fails_closed_on_mismatch(damage):
    data=list(fixture())
    b,a,m,footprint,sha=data
    if damage=="wrong_footprint_sha":
        sha="f"*64
    elif damage=="moved_U1_pad":
        next(p for p in b["pads"] if p["ref"]=="U1" and p["pad"]=="3")["x"]+=2.54
    elif damage=="missing_pad":
        b["pads"]=[p for p in b["pads"] if not (p["ref"]=="U1" and p["pad"]=="3")]
    elif damage=="firmware_wrong_gpio":
        a["firmware_gpio_columns"][5]="D0"
    elif damage=="sourced_wrong_net":
        next(p for p in b["pads"] if p["ref"]=="U1" and p["pad"]=="3")["net"]="/C77"
    else:
        m["controller_column_to_pin"]["/C5"]="12"
    with pytest.raises(ValueError):
        audit_teensy2_gpio(b,a,m,footprint,expected_footprint_sha256=sha)


def test_frozen_actual_pjrc_source_proof_is_cryptographically_bound():
    proof=read("PJRC_TEENSY2_PINOUT_PROOF.json")
    source_manifest=read("SOURCE_PIN_MANIFEST.json")
    pinned={r["name"]:r["sha256"] for r in source_manifest["files"]}
    assert proof["upstream_source_footprint_sha256"]==pinned["Teensy_20.kicad_mod"]
    assert proof["firmware_total_gpio_assignments_verified"]==19
    assert proof["source_original_controller_pads_positionally_verified"]==31
    assert proof["source_audit_sha256"]==read("INDEPENDENT_SOURCE_AUDIT.json")["payload_sha256"]
    assert proof["full_matrix_proof_sha256"]==read("FULL_MATRIX_SOURCE_PROOF.json")["payload_sha256"]
    assert proof["external_PJRC_C_pinout_reference"]=="https://www.pjrc.com/teensy/card2a_rev5_web.pdf"
    content={k:v for k,v in proof.items() if k!="payload_sha256"}
    checksum=hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False,
                    separators=(",",":")).encode()).hexdigest()
    assert checksum==proof["payload_sha256"]

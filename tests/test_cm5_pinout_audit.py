"""Deterministic Radxa CM5 300-contact import checks (no physical permission)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from hardware_splicer.cm5_pinout_audit import (
    XLSX_SHA, SYM_SHA, FP_SHA, PinoutError, audit, digest, footprint_pads,
    repair_symbol, require_hash, symbol_pins, vendor_pinout,
)

BASE=Path(__file__).resolve().parents[1]/"examples/cyberdeck/compute_carrier/cm5_reference"
PINS=json.loads((BASE/"vendor_pin_names.json").read_text(encoding="utf-8"))
REPORT=json.loads((BASE/"pinout_audit.json").read_text(encoding="utf-8"))
SYMBOL=(BASE/"HS_CM5_OFFICIAL.kicad_sym").read_text(encoding="utf-8")
FOOTPRINT=(BASE/"HS_CM5_OFFICIAL.pretty/Radxa_CM5.kicad_mod").read_text(encoding="utf-8")
EXPECTED={int(k):v for k,v in PINS["pin_names"].items()}

def test_official_revision_is_pinned_and_all_300_pins_resolve():
    assert PINS["source_sha256"]==XLSX_SHA
    assert PINS["community_symbol_source_sha256"]==SYM_SHA
    assert PINS["community_footprint_source_sha256"]==FP_SHA
    assert set(EXPECTED)==set(range(1,301))
    assert symbol_pins(SYMBOL)==EXPECTED
    assert REPORT["vendor_contact_count"]==300
    assert REPORT["pin_name_differences"]==192
    assert REPORT["manufacturer_NC_conflicts"]==22
    assert sum(v=="NC" for v in EXPECTED.values())==40

def test_real_kicad_footprint_numeric_contact_coverage():
    assert len(footprint_pads(FOOTPRINT))==300
    assert sorted(footprint_pads(FOOTPRINT))==list(range(1,301))
    assert digest(FOOTPRINT.encode())==FP_SHA

def test_corrected_symbol_is_byte_for_byte_verified_output():
    assert digest(SYMBOL.encode())==REPORT["kicad_symbol_sha256"]
    assert '(property "Footprint" "HS_CM5_OFFICIAL:Radxa_CM5"' in SYMBOL
    assert '(property "Footprint" "Radax:Radxa_CM5"' not in SYMBOL
    assert 'text "600mA Max"' not in SYMBOL
    assert SYMBOL.count('text "MAX CURRENT NOT VERIFIED"')==2

def test_third_connector_vendor_j1_is_global_201_to_300():
    assert PINS["third_connector_numbering"]=="sheet J1 1-100 -> KiCad global pin 201-300"
    assert EXPECTED[201]=="GND"
    assert EXPECTED[203].startswith("TYPEC0_")
    assert EXPECTED[300]

def test_manufacturer_says_22_previously_live_named_contacts_are_nc():
    conflicts=[x for x in REPORT["changed_contacts"] if x["manufacturer_no_connect"]]
    assert len(conflicts)==22
    assert {16,18,26}.issubset({x["pin"] for x in conflicts})
    assert {x["vendor"] for x in conflicts}=={"NC"}

def test_dangerous_old_symbol_must_not_be_used_as_vendor_netlist():
    assert REPORT["released_for_fabrication"] is False
    assert REPORT["pin_electrical_types_independently_validated"] is False
    assert REPORT["physical_pad_geometry_independently_validated"] is False
    assert len(REPORT["blockers"])>=4

def test_corrupt_input_xlsx_is_not_silently_read():
    with pytest.raises(PinoutError,match="source SHA256"):
        vendor_pinout(b"not an official workbook")

def test_mutated_symbol_fails_exact_full_contact_verification():
    tampered=SYMBOL.replace('(number "3"', '(number "301"',1)
    with pytest.raises(PinoutError,match="numbering"):
        symbol_pins(tampered)

def test_duplicate_footprint_pad_rejected():
    mutated=FOOTPRINT.replace('(pad "2" smd', '(pad "1" smd',1)
    with pytest.raises(PinoutError,match="300 distinct"):
        footprint_pads(mutated)

def test_symbol_patch_fail_closed_on_vendor_number_outside_source():
    fake={k:v for k,v in EXPECTED.items()}
    fake.pop(300)
    with pytest.raises(PinoutError,match="unrecognized"):
        repair_symbol(SYMBOL, fake)

def test_interface_candidate_is_only_documented_pin_names():
    m=json.loads((BASE/"candidate_interfaces.json").read_text())
    assert m["authority"]=="MANUFACTURER_PIN_LABEL_MATCH_ONLY"
    assert not m["fabrication_authorized"]
    assert not m["boot_power_tested"]
    assert not m["usb_keyboard_tested"]
    assert not m["hdmi_display_tested"]
    for pins in m["logical_subsystems"].values():
        assert all(EXPECTED[x["pin"]]==x["name"] for x in pins)
    assert m["no_connect_pins"]==sorted(k for k,v in EXPECTED.items() if v=="NC")

def test_pins_one_hundred_and_final_boundary_present():
    assert all(x in EXPECTED for x in (1,100,101,200,201,300))
    assert len({x["pin"] for values in json.loads((BASE/"candidate_interfaces.json").read_text())["logical_subsystems"].values() for x in values})>20


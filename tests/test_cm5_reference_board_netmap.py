"""Source-gated CM5 reference route extraction and safety assertions."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import pytest

from hardware_splicer.cm5_reference_board_netmap import (
    audit, vendor_names, parse_board_routed_pins, ReferenceBoardAuditError,
    BOARD_SHA256, BOARD_SOURCE_URL, EXPECTED_NAME_MISMATCHES
)

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/"examples/cyberdeck/compute_carrier/cm5_reference"
VENDOR=json.loads((DIR/"vendor_pin_names.json").read_text(encoding="utf-8"))
REPORT=json.loads((DIR/"reference_board_routed_net_map.json").read_text(encoding="utf-8"))

def test_pads_routed_to_known_manufacturer_reference_nets():
    assert REPORT["schema"]=="hs.cm5_reference_board_routed_nets.v1"
    assert REPORT["source_url"]==BOARD_SOURCE_URL
    assert REPORT["source_sha256"]==BOARD_SHA256
    assert REPORT["reference_contacts_with_routes"]==241
    assert REPORT["exact_matches_to_manufacturer_names"]==235
    assert REPORT["reference_unique_routed_net_names"]==159
    assert REPORT["reference_contact_net_conflicts"]==0
    assert len(REPORT["unrepresented_unrouted_or_single_terminal_contacts"])==59

def test_six_reference_pin_label_aliases_and_revision_conflicts_explicit():
    mismatches=REPORT["reference_net_name_differences"]
    assert {m["pin"] for m in mismatches}==EXPECTED_NAME_MISMATCHES
    assert REPORT["manufacturer_nc_with_reference_route"]==[
        {"pin":290,"manufacturer_label":"NC",
         "reference_board_nets":["RTC_32K_SOC"],"is_manufacturer_nc":True}
    ]
    assert REPORT["manufacturer_nc_count"]==40

def test_pads_with_matching_input_and_usb2():
    ports=REPORT["reference_contact_routed_net_map"]
    names=vendor_names(VENDOR)
    for pin in (77,79,81,83,85,87,103,105,245,247,263,265):
        assert ports[str(pin)]==[names[pin]]
    assert ports["203"]==["TYPEC0_SBU1"]
    assert ports["204"]==["GPIO3_C0"]
    assert ports["290"]==["RTC_32K_SOC"]

def test_40_no_connect_pins_are_not_all_ref_unrouted():
    assert sum(v=="NC" for v in vendor_names(VENDOR).values())==40
    assert any(x["manufacturer_label"]=="NC" for x in REPORT["reference_net_name_differences"])

def test_no_fab_or_assumed_electrical_release():
    assert not REPORT["safe_to_fabricate"]
    assert not REPORT["module_revision_compatibility_verified"]
    assert not REPORT["complete_schematic_erc_pass"]
    assert not REPORT["complete_pcb_drc_pass"]
    assert not REPORT["usb_signal_integration_tested"]
    assert not REPORT["physical_prototype_validated"]
    assert REPORT["power_input_mapping_review_required"]

def test_unknown_or_missing_vendor_manifest_rejected():
    bad=copy.deepcopy(VENDOR)
    bad["manufacturer_revision"]="V2.20"
    with pytest.raises(ReferenceBoardAuditError,match="revision"):
        vendor_names(bad)
    bad=copy.deepcopy(VENDOR)
    del bad["pin_names"]["290"]
    with pytest.raises(ReferenceBoardAuditError,match="300"):
        vendor_names(bad)

def test_altered_manufacturer_board_bytes_rejected():
    with pytest.raises(ReferenceBoardAuditError,match="SHA256"):
        parse_board_routed_pins(b"*ROUTE*\n*POUR*")

def test_source_parser_enforces_exact_two_connector_families():
    raw=(
        "U33             DF40C-200DS-D4-OK\n"
        "J24             DF40C_100DS\n"
        "*ROUTE*\n*SIGNAL* USB20_HOST0_DM 0 -2 ; \n"
        "U33.77    J24.3       \n"
        "*SIGNAL* GND 0 -2 ; \n"
        "U22.1    U33.203       \n"
        "*SIGNAL* GPIO3_C0 0 -2 ; \n"
        "J24.4    CON1.35     \n"
        "*POUR*\n"
    ).encode()
    pairs=parse_board_routed_pins(raw,verify_hash=False)
    assert pairs=={77:{"USB20_HOST0_DM"},203:{"USB20_HOST0_DM"},204:{"GPIO3_C0"}}

def test_conflicting_source_net_labels_for_one_contact_rejected():
    raw=(
        "U33             DF40C-200DS-D4-OK\n"
        "J24             DF40C_100DS\n"
        "*ROUTE*\n*SIGNAL* NET_A 0 -2 ; \nU33.77    U22.1       \n"
        "*SIGNAL* NET_B 0 -2 ; \nU33.77    U22.2       \n*POUR*\n"
    ).encode()
    with pytest.raises(ReferenceBoardAuditError,match="multiple"):
        parse_board_routed_pins(raw,verify_hash=False)

def test_j24_must_be_100_pin_connector():
    raw=(
        "U33             DF40C-200DS-D4-OK\n"
        "J24             DF40C_100DS\n"
        "*ROUTE*\n*SIGNAL* NET_A 0 -2 ; \nJ24.101    U22.1       \n*POUR*\n"
    ).encode()
    with pytest.raises(ReferenceBoardAuditError,match="J24 contact"):
        parse_board_routed_pins(raw,verify_hash=False)

def test_incomplete_or_corrupted_route_section_rejected():
    raw=b"U33             DF40C-200DS-D4-OK\nJ24             DF40C_100DS\n*ROUTE*\n"
    with pytest.raises(ReferenceBoardAuditError,match="sections"):
        parse_board_routed_pins(raw,verify_hash=False)

def test_fixture_does_not_claim_a_routed_board():
    pcb=(DIR/"REFERENCE_NET_LABELS_ONLY_NOT_ROUTED.kicad_pcb").read_text(encoding="utf-8")
    assert "(kicad_pcb" in pcb
    assert "MANUFACTURER ROUTED-NET LABELS ONLY" in pcb
    assert "RTC_32K_SOC" in pcb
    assert "USB20_HOST0_DP" in pcb
    assert "VCC_SYSIN" in pcb
    assert pcb.count("(segment ")==0
    assert pcb.count("(via ")==0

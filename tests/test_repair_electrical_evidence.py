"""Protect actual KiCad net identities before using exported pin measurement evidence."""
from __future__ import annotations
import csv
import json
from pathlib import Path

import pytest

from hardware_splicer.netlist.import_kicad import parse_kicad_netlist
from hardware_splicer.repair_electrical_evidence import capture_repair_evidence, write_repair_evidence

ROOT = Path(__file__).resolve().parents[1]
NET = ROOT / "examples/main_ctrl_esp32_servo.net"
HEADER = [
    "observation_id","observed_at","component_ref","pin",
    "measurement_kind","value","unit","instrument_id","operator_id","condition",
]


def measurements(tmp_path, rows):
    path=tmp_path/"observations.csv"
    with path.open("w",newline="",encoding="utf-8") as stream:
        writer=csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


def row(identifier="obs1",ref="J1",pin="1",kind="dc_voltage",
        value="5.1",unit="V",stamp="2026-10-01T09:00:00+08:00",
        condition="unloaded"):
    # SYNTHETIC TEST INPUT, NEVER AN ACTUAL MEASUREMENT.
    return [identifier,stamp,ref,pin,kind,value,unit,
            "SYNTHETIC_INSTRUMENT","SYNTHETIC_OPERATOR",condition]


def test_kicad_s_expression_fixture_is_parsed_into_real_net_pin_memberships():
    n=parse_kicad_netlist(NET.read_text(encoding="utf-8"))
    assert len(n.components)==9
    assert len(n.nets)==14
    assert sum(len(net.pins) for net in n.nets)==40
    nets={x.name:{p.key() for p in x.pins} for x in n.nets}
    assert {"J1.1","U2.7","U2.8","U3.3"} <= nets["VBUS"]
    assert {"J1.2","U1.15","U3.1"} <= nets["GND"]
    assert {"U1.25","R2.2"} == nets["GPIO0"]
    assert len(set(nets))==14
    assert all(not p.startswith("[") for members in nets.values() for p in members)


def test_real_netlist_synthetic_claims_produce_matched_pin_names_not_physical_truth(tmp_path):
    csv_file=measurements(tmp_path,[
        row(),
        row(identifier="obs2",value="4.8",stamp="2026-10-01T09:10:00+08:00",condition="under_load"),
        row(identifier="obs3",ref="U3",pin="1",kind="continuity",value="1",unit="boolean"),
    ])
    data=capture_repair_evidence(NET,csv_file)
    assert data["netlist"]["components"]==9
    assert data["netlist"]["nets"]==14
    assert data["netlist"]["pins_mapped"]==40
    assert len(data["observations"])==3
    assert data["observations"][0]["net"]=="VBUS"
    assert data["observations"][2]["net"]=="GND"
    assert data["condition_changes"][0]["delta"]==-0.3
    assert data["condition_changes"][0]["meaning"]=="operator_reported_condition_delta_not_component_causation"
    assert not data["physical_repair_verified"]
    assert not data["power_on_authorized"]
    assert not data["failed_component_identified"]
    assert not data["measurements"]["instrument_authenticated"]
    written=write_repair_evidence(NET,csv_file,tmp_path/"out")
    assert json.loads((tmp_path/"out/REPAIR_ELECTRICAL_EVIDENCE.json").read_text())==written
    assert "NOT instrument-authenticated" in (tmp_path/"out/REPAIR_ELECTRICAL_EVIDENCE.md").read_text()


@pytest.mark.parametrize("bad", [
    {"ref":"NOT_REAL"},
    {"pin":"45"},
    {"kind":"dc_voltage","unit":"ohm"},
    {"kind":"resistance","value":"-3","unit":"ohm"},
    {"kind":"continuity","value":"2","unit":"boolean"},
    {"value":"NaN"},
    {"value":"Infinity"},
    {"stamp":"2026-10-01T09:00:00"},
    {"identifier":""},
])
def test_unmapped_pin_invalid_unit_or_unattributed_reading_is_rejected(tmp_path,bad):
    path=measurements(tmp_path,[row(**bad)])
    with pytest.raises(ValueError):
        capture_repair_evidence(NET,path)


def test_duplicate_observation_not_counted_twice(tmp_path):
    path=measurements(tmp_path,[row(),row(value="4.2")])
    with pytest.raises(ValueError,match="duplicate"):
        capture_repair_evidence(NET,path)


def test_missing_instrument_id_not_accepted(tmp_path):
    r=row()
    r[7]=""
    path=measurements(tmp_path,[r])
    with pytest.raises(ValueError,match="instrument"):
        capture_repair_evidence(NET,path)


def test_hard_reject_if_source_netlist_has_no_components_or_nodes(tmp_path):
    p=tmp_path/"empty.net"
    p.write_text('(export (version "E") (components) (nets))',encoding="utf-8")
    obs=measurements(tmp_path,[row()])
    with pytest.raises(ValueError,match="components or nets"):
        capture_repair_evidence(p,obs)


def test_unknown_source_net_rejected_without_guessing_from_shared_ground(tmp_path):
    p=tmp_path/"bad.net"
    p.write_text('(export (components (comp (ref "U1") (value "IC"))) (nets (net (code "1") (name "PWR") (node (ref "U2") (pin "1")))))')
    with pytest.raises(ValueError,match="unknown component"):
        capture_repair_evidence(p,measurements(tmp_path,[row(ref="U1")]))

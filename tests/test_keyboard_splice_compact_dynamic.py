"""Source-bound 42-lead IDC connector preview; 8 spare contacts stay open."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_mechanical_round10"
GENERATOR=ROOT/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_compact_junction.py"
NATIVE="/usr/bin/python3"


def has_kicad():
    if not shutil.which("kicad-cli"):
        return False
    try:
        result=subprocess.run([NATIVE,"-c","import pcbnew"],capture_output=True,timeout=9)
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False


pytestmark=pytest.mark.skipif(not has_kicad(),reason="native KiCad missing")


def one_run(tmp_path,body):
    raw=tmp_path/"source.json"
    raw.write_text(json.dumps(body),encoding="utf-8")
    output=tmp_path/"IDC50"
    proc=subprocess.run([
        NATIVE,str(GENERATOR),"--full-junction-json",str(raw),
        "--out",str(output),
    ],capture_output=True,text=True,timeout=35)
    return proc,output


def test_generic_idc_connector_handles_42_actual_source_leads(tmp_path):
    original=json.loads((EVIDENCE/"full_junction/FULL_JUNCTION_WIRING.json").read_text())
    run,out=one_run(tmp_path,original)
    assert run.returncode==0,run.stderr
    manifest=json.loads((out/"COMPACT_JUNCTION_WIRING.json").read_text())
    frozen=json.loads((EVIDENCE/"compact_idc50/COMPACT_JUNCTION_WIRING.json").read_text())
    assert manifest==frozen
    assert manifest["source_original_wiring_assignments"]==42
    assert manifest["original_source_donor_contacts"]==34
    assert manifest["original_remounted_key_ports"]==8
    assert manifest["independent_source_bus_net_count"]==16
    assert manifest["IDC_used_pins"]==42
    assert manifest["IDC_unused_insulated_pins"]==list(range(43,51))
    assert manifest["source_original_junction_mutually_exclusive"] is True
    assert not manifest["fabrication_authorized"]
    pins=[row["IDC_header_pin"] for row in manifest["junction_pin_assignments"]]
    assert pins==list(range(1,43))
    assert len({(x["external_role"],x["source_ref"],x["source_pin"])
                for x in manifest["junction_pin_assignments"]})==42
    pcb=out/"compact_idc50_junction.kicad_pcb"
    drc=out/"NATIVE_DRC.json"
    checked=subprocess.run([
        "kicad-cli","pcb","drc","--severity-all","--format","json",
        "--output",str(drc),str(pcb)
    ],capture_output=True,text=True,timeout=60)
    assert checked.returncode==0,checked.stderr
    evidence=json.loads(drc.read_text())
    assert not evidence["violations"]
    assert not evidence["unconnected_items"]
    # Native KiCad generates fresh footprint UUIDs, so compare EDA geometry
    # and net assignments, not nonsemantic binary file identity.
    measured=subprocess.run([
        NATIVE,"-c",
        "import pcbnew as p,json,sys;"
        "b=p.LoadBoard(sys.argv[1]);"
        "print(json.dumps({'footprints':len(b.GetFootprints()),"
        "'tracks':len(b.GetTracks()),"
        "'pads':sum(len(list(f.Pads())) for f in b.GetFootprints()),"
        "'electrically_named_nets':len({t.GetNetname() for t in b.GetTracks() if t.GetNetname()})}))",
        str(pcb)
    ],capture_output=True,text=True,timeout=30)
    assert measured.returncode==0,measured.stderr
    assert json.loads(measured.stdout)=={
        "footprints":1,"tracks":26,"pads":50,"electrically_named_nets":16
    }


@pytest.mark.parametrize("bad",[
    "tamper_count","duplicate_source_contact","missing_bus","authorized"
])
def test_changing_the_shorter_source_wiring_refuses_idc_assembly(tmp_path,bad):
    original=copy.deepcopy(json.loads(
        (EVIDENCE/"full_junction/FULL_JUNCTION_WIRING.json").read_text()
    ))
    if bad=="tamper_count":
        original["total_junction_board_pins"]=43
    elif bad=="duplicate_source_contact":
        source=original["source_terminal_mapping"]
        source[1]["source_pin"]=source[0]["source_pin"]
        source[1]["source_ref"]=source[0]["source_ref"]
        source[1]["external_role"]=source[0]["external_role"]
    elif bad=="missing_bus":
        original["unique_source_nets_joined"]=17
    else:
        original["physical_assembly_authorized"]=True
    proc,_=one_run(tmp_path,original)
    assert proc.returncode!=0

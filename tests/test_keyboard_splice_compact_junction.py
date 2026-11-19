"""Actual KiCad 50-pin latching IDC groups 49 source-bound wire leads."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_remount_round5"
INPUT=EVIDENCE/"full_junction/FULL_JUNCTION_WIRING.json"
OUTPUT=EVIDENCE/"compact_idc50_round8"
GENERATOR=ROOT/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_compact_junction.py"
NATIVE="/usr/bin/python3"


def native_ready():
    if not shutil.which("kicad-cli"):
        return False
    try:
        command=subprocess.run([NATIVE,"-c","import pcbnew"],capture_output=True,timeout=9)
    except (OSError,subprocess.TimeoutExpired):
        return False
    return command.returncode==0


pytestmark=pytest.mark.skipif(not native_ready(),reason="actual KiCad native Python unavailable")


def run(input_data,tmp_path):
    inp=tmp_path/"full_wiring.json"
    inp.write_text(json.dumps(input_data,ensure_ascii=False),encoding="utf-8")
    output=tmp_path/"compact"
    command=subprocess.run(
        [NATIVE,str(GENERATOR),"--full-junction-json",str(inp),"--out",str(output)],
        capture_output=True,text=True,timeout=45
    )
    return command,output


def test_native_50pin_latch_reference_compact_board_has_no_short_or_open(tmp_path):
    original=json.loads(INPUT.read_text(encoding="utf-8"))
    run_data,output=run(original,tmp_path)
    assert run_data.returncode==0,run_data.stderr
    manifest=json.loads((output/"COMPACT_JUNCTION_WIRING.json").read_text(encoding="utf-8"))
    frozen=json.loads((OUTPUT/"COMPACT_JUNCTION_WIRING.json").read_text(encoding="utf-8"))
    assert manifest==frozen
    assert manifest["independent_source_bus_net_count"]==20
    assert manifest["source_original_wiring_assignments"]==49
    assert manifest["original_source_donor_contacts"]==39
    assert manifest["original_remounted_key_ports"]==10
    assert manifest["IDC_pin_count"]==50
    assert manifest["IDC_used_pins"]==49
    assert manifest["IDC_unused_insulated_pin"]==50
    assert manifest["board_area_reduction_percent"]==49.1
    assert manifest["compact_board_width_mm"]==42
    assert manifest["compact_board_height_mm"]==94
    assert manifest["source_original_junction_mutually_exclusive"] is True
    assert manifest["source_original_17_channel_interposer_mutually_exclusive"] is True
    assert not manifest["fabrication_authorized"]
    assert not manifest["actual_donor_wires_soldered"]
    assert manifest["physical_connector_mpn"] is None

    leadset={(row["external_role"],row["source_ref"],row["source_pin"])
             for row in original["source_terminal_mapping"]}
    assigned={(row["external_role"],row["source_ref"],row["source_pin"])
              for row in manifest["junction_pin_assignments"]}
    assert leadset==assigned
    assert len(assigned)==49
    assert sorted(row["IDC_header_pin"] for row in manifest["junction_pin_assignments"])==list(range(1,50))
    pairs={(row["IDC_header_pin"],row["original_source_net"])
           for row in manifest["junction_pin_assignments"]}
    assert len(pairs)==49
    assert len({row["original_source_net"] for row in manifest["junction_pin_assignments"]})==20
    assert not any(row["physical_connection_verified"] for row in manifest["junction_pin_assignments"])

    pcb=output/"compact_idc50_junction.kicad_pcb"
    checked=subprocess.run(["kicad-cli","pcb","drc","--format","json",
       "--severity-all","--output",str(output/"DRC.json"),str(pcb)],
       capture_output=True,text=True,timeout=60)
    assert checked.returncode==0,checked.stderr
    native=json.loads((output/"DRC.json").read_text(encoding="utf-8"))
    assert native["violations"]==[]
    assert native["unconnected_items"]==[]
    actual=subprocess.run([NATIVE,"-c",(
        "import pcbnew as p,json,sys;"
        "b=p.LoadBoard(sys.argv[1]);"
        "print(json.dumps({'footprints':len(b.GetFootprints()),"
        "'tracks':len(b.GetTracks()),'pads':sum(len(list(f.Pads())) for f in b.GetFootprints())}))"
    ),str(pcb)],capture_output=True,text=True,timeout=30)
    assert actual.returncode==0,actual.stderr
    assert json.loads(actual.stdout)=={"footprints":1,"tracks":29,"pads":50}


@pytest.mark.parametrize("bad",[
    "tamper_count","wrong_source_ref","invalid_role","installed_false_claim",
    "same_source_pin_twice","unauthorized","wrong_net_groups",
])
def test_compact_footprint_never_routes_unbound_or_authorized_wiring(tmp_path,bad):
    source=copy.deepcopy(json.loads(INPUT.read_text(encoding="utf-8")))
    wiring=source["source_terminal_mapping"]
    if bad=="tamper_count":
        source["total_junction_board_pins"]=48
    elif bad=="wrong_source_ref":
        wiring[0]["source_ref"]=None
    elif bad=="invalid_role":
        wiring[0]["external_role"]="external_power"
    elif bad=="installed_false_claim":
        wiring[0]["physical_wire_installed"]=True
    elif bad=="same_source_pin_twice":
        wiring[1]["external_role"]=wiring[0]["external_role"]
        wiring[1]["source_ref"]=wiring[0]["source_ref"]
        wiring[1]["source_pin"]=wiring[0]["source_pin"]
    elif bad=="unauthorized":
        source["physical_assembly_authorized"]=True
    elif bad=="wrong_net_groups":
        source["unique_source_nets_joined"]=18
    run_data,_=run(source,tmp_path)
    assert run_data.returncode!=0


def test_frozen_compact_artifacts_remain_source_bounded_and_unreleased():
    manifest=json.loads((OUTPUT/"COMPACT_JUNCTION_WIRING.json").read_text(encoding="utf-8"))
    receipt=json.loads((OUTPUT/"COMPACT_JUNCTION_VERIFICATION.json").read_text(encoding="utf-8"))
    original=json.loads(INPUT.read_text(encoding="utf-8"))
    native=json.loads((OUTPUT/"NATIVE_COMPACT_DRC.json").read_text(encoding="utf-8"))
    pcb=(OUTPUT/"compact_idc50_junction.kicad_pcb").read_bytes()
    assert manifest["source_sha256"]==receipt["source_sha256"]==original["source_sha256"]
    assert receipt["pcb_sha256"]==hashlib.sha256(pcb).hexdigest()
    assert receipt["native_drc_passed"] is True
    assert receipt["errors"]==receipt["warnings"]==receipt["unconnected_items"]==0
    assert native["violations"]==native["unconnected_items"]==[]
    assert receipt["fabrication_release"]=="BLOCKED_NATIVE_KICAD_COMPACT_IDC_PREVIEW"
    assert not manifest["fabrication_authorized"]
